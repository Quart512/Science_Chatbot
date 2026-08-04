import re
import uuid

import requests
import streamlit as st

from common import BACKEND_URL

st.title("🧬 연구 워크플로우")

STAGES = [
    ("hypothesis", "가설"),
    ("design", "설계"),
    ("operation", "실험 운영"),
    ("report", "보고서"),
    ("writing", "논문 초안"),
]
# 각 단계가 "완료됐다"를 판정하는 대표 필드 — 그 단계의 마지막 산출물이 채워졌으면 완료로 본다.
STAGE_DONE_FIELD = {
    "hypothesis": "hypothesis",
    "design": "procedure",
    "operation": "outcome",
    "report": "experiment_report",
    "writing": "abstract",
}


def _stage_index(stage: str) -> int:
    return [s for s, _ in STAGES].index(stage)


def _has_stale_downstream(state: dict, target_stage: str) -> bool:
    # target_stage(포함) 이후 단계 중 이미 값이 채워진 게 있으면, 그 값들은 재생성 후에도
    # 자동으로 지워지지 않고 낡은 채 남는다(WorkflowState에 버전 관리가 없음 — RoadMap
    # "연구 워크플로우 화면" 설계 노트 §3). 사용자가 이 사실을 알고 진행하도록 경고만 한다.
    idx = _stage_index(target_stage)
    return any(state.get(STAGE_DONE_FIELD[s]) for s, _ in STAGES[idx:])


def _resolve_citations(text: str, references: list[dict]) -> str:
    mapping = {r["paper_id"]: r["title"] for r in references}

    def _replace(m):
        title = mapping.get(m.group(1))
        return f"({title})" if title else m.group(0)

    return re.sub(r"\[CITE:([^\]]+)\]", _replace, text or "")


def _advance(
    thread_id: str, stage: str, *, topic: str | None = None, experiment_results: str | None = None,
    from_checkpoint_id: str | None = None, keep_reference_paper_ids: list[str] | None = None,
) -> bool:
    payload = {"stage": stage}
    if topic is not None:
        payload["topic"] = topic
    if experiment_results is not None:
        payload["experiment_results"] = experiment_results
    if from_checkpoint_id is not None:
        payload["from_checkpoint_id"] = from_checkpoint_id
    if keep_reference_paper_ids is not None:
        payload["keep_reference_paper_ids"] = keep_reference_paper_ids
    try:
        resp = requests.post(f"{BACKEND_URL}/research/{thread_id}/advance", json=payload, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as e:
        st.error(f"요청 실패: {e}")
        return False
    return True


def _next_options(state: dict) -> list[dict]:
    stage = state["stage"]
    if not state.get(STAGE_DONE_FIELD[stage]):
        return []  # 이 단계가 아직 안 끝났으면(진행 중 실패 등) 다음 단계 선택지도 없음
    if stage == "hypothesis":
        options = [{"label": "설계 진행", "target": "design", "recommended": True, "needs_results": False}]
    elif stage == "design":
        options = [
            {"label": "실험 시작", "target": "operation", "recommended": True, "needs_results": True},
            {"label": "설계 재생성", "target": "design", "recommended": False, "needs_results": False},
        ]
    elif stage == "operation":
        outcome = state.get("outcome", "")
        options = [
            {"label": "보고서 작성", "target": "report", "recommended": outcome == "supported", "needs_results": False},
            {"label": "가설부터 재수립", "target": "hypothesis", "recommended": outcome == "hypothesis_wrong", "needs_results": False},
            {"label": "재설계", "target": "design", "recommended": outcome == "design_flawed", "needs_results": False},
            {"label": "같은 설계로 재실험", "target": "operation", "recommended": outcome == "execution_error", "needs_results": True},
            {"label": "결과 다시 입력해 재분석", "target": "operation", "recommended": outcome == "analysis_error", "needs_results": True},
        ]
    elif stage == "report":
        options = [{"label": "논문 작성", "target": "writing", "recommended": True, "needs_results": False}]
        for target, label in STAGES[:3]:
            options.append({"label": f"{label}로 돌아가 고치기", "target": target, "recommended": False, "needs_results": target == "operation"})
    elif stage == "writing":
        options = [{"label": "초안 재생성", "target": "writing", "recommended": False, "needs_results": False}]
    else:
        options = []
    # 추천 옵션을 맨 위로 — sorted()는 안정 정렬이라 recommended 안에서는 원래 순서 유지
    return sorted(options, key=lambda o: not o["recommended"])


def _render_stage_content(state: dict) -> None:
    stage = state["stage"]
    references = state.get("references", [])

    if stage == "hypothesis" and state.get("hypothesis"):
        st.subheader("가설")
        st.write(state["hypothesis"])
        st.caption(f"근거: {state.get('rationale', '')}")
        st.caption(f"검증 가능한 예측: {state.get('testable_prediction', '')}")

    elif stage == "design" and state.get("procedure"):
        st.subheader("실험 설계")
        st.markdown(f"**독립변수**: {state.get('independent_variable', '')}")
        st.markdown(f"**종속변수**: {state.get('dependent_variable', '')}")
        st.markdown(f"**통제변수**: {state.get('controlled_variables', '')}")
        st.markdown(f"**필요 장비**: {state.get('equipment_needed', '')}")
        st.markdown("**절차**")
        st.write(state["procedure"])

    elif stage == "operation" and state.get("outcome"):
        st.subheader("실험 결과 분석")
        st.markdown(f"**입력한 결과**: {state.get('experiment_results', '')}")
        st.markdown(f"**분석**: {state.get('analysis', '')}")
        st.markdown(f"**판정**: `{state['outcome']}`")

    elif stage == "report" and state.get("experiment_report"):
        st.subheader("실험 보고서")
        st.text(state["experiment_report"])

    elif stage == "writing" and state.get("abstract"):
        st.subheader(state.get("title") or "(제목 없음)")
        for field, label in [
            ("abstract", "초록"), ("introduction", "서론"), ("methods", "방법"),
            ("results", "결과"), ("discussion", "고찰"),
        ]:
            st.markdown(f"**{label}**")
            st.write(_resolve_citations(state.get(field, ""), references))
        if state.get("citations"):
            titles = {r["paper_id"]: r["title"] for r in references}
            with st.expander("인용 근거"):
                for c in state["citations"]:
                    title = titles.get(c["paper_id"], c["paper_id"])
                    st.caption(f"- {title}: {c.get('reasoning', '')}")

    if references:
        with st.expander(f"참고문헌 ({len(references)}편)"):
            for r in references:
                reasoning = f" — {r['reasoning']}" if r.get("reasoning") else ""
                st.caption(f"- [{r['source']}] {r['title']}{reasoning}")


def _render_next_options(
    thread_id: str, values: dict, tip_values: dict, from_checkpoint_id: str | None, view_key: str,
) -> None:
    # from_checkpoint_id가 있으면(=과거 탭에서 진행) 그 시점엔 없었지만 최신 tip에는
    # 있는 참고문헌을 골라서 보여준다 — 기본은 전부 미체크(=버림), 논문 제작 단계에서
    # 따로 참고문헌을 손볼 방법이 아직 없어서 이게 사실상 유일한 큐레이션 지점이다.
    new_refs = []
    if from_checkpoint_id is not None:
        past_ids = {r["paper_id"] for r in values.get("references", [])}
        new_refs = [r for r in tip_values.get("references", []) if r["paper_id"] not in past_ids]

    for opt in _next_options(values):
        label = opt["label"] + (" [추천]" if opt["recommended"] else "")
        # 일반 낡은-값 경고는 tip에서 그대로 진행할 때만 의미가 있다(과거 탭 진행은
        # 아래 참고문헌 diff로 이미 구체적으로 안내함) — RoadMap 설계 노트 §3.
        if from_checkpoint_id is None and _has_stale_downstream(values, opt["target"]):
            st.caption("⚠️ 재생성하면 이후 단계에 이미 만들어둔 값이 낡은 채로 남습니다(자동으로 지워지지 않음)")

        form_key = f"advance_form_{opt['target']}_{opt['label']}_{from_checkpoint_id or 'tip'}"
        with st.form(form_key):
            results_text = st.text_area("실험 결과", key=f"{form_key}_results") if opt["needs_results"] else None

            keep_ids = []
            if new_refs:
                st.caption(f"⚠️ 이 시점 이후 새로 찾은 참고문헌 {len(new_refs)}편이 있습니다 — 이 갈래에 남길 것만 선택하세요(기본은 버림).")
                for r in new_refs:
                    reasoning = f" — {r['reasoning']}" if r.get("reasoning") else ""
                    if st.checkbox(f"{r['title']}{reasoning}", value=False, key=f"{form_key}_keep_{r['paper_id']}"):
                        keep_ids.append(r["paper_id"])

            if st.form_submit_button(label):
                if opt["needs_results"] and not results_text:
                    st.warning("실험 결과를 입력해주세요.")
                elif _advance(
                    thread_id, opt["target"],
                    experiment_results=results_text,
                    from_checkpoint_id=from_checkpoint_id,
                    keep_reference_paper_ids=keep_ids if from_checkpoint_id else None,
                ):
                    st.session_state.pop(view_key, None)  # 새로 생긴 tip으로 보기를 리셋
                    st.rerun()


with st.sidebar:
    st.subheader("연구 세션")
    try:
        sessions_resp = requests.get(f"{BACKEND_URL}/research/sessions", timeout=10)
        sessions_resp.raise_for_status()
        sessions = sessions_resp.json()["sessions"]
    except requests.RequestException as e:
        st.error(f"세션 목록 조회 실패: {e}")
        sessions = []

    for s in sessions:
        tid = s["thread_id"]
        with st.container(border=True):
            if st.button(f"{s['title']} ({s['stage']})", key=f"select_{tid}", use_container_width=True):
                st.session_state.research_thread_id = tid
                st.rerun()
            with st.expander("이름 수정"):
                with st.form(f"rename_form_{tid}"):
                    new_title = st.text_input("제목", value=s["title"])
                    if st.form_submit_button("저장"):
                        try:
                            r = requests.post(f"{BACKEND_URL}/research/sessions/{tid}/title", json={"title": new_title}, timeout=10)
                            r.raise_for_status()
                            st.rerun()
                        except requests.RequestException as e:
                            st.error(f"수정 실패: {e}")
            if st.button("닫기", key=f"close_{tid}"):
                try:
                    r = requests.delete(f"{BACKEND_URL}/research/sessions/{tid}", timeout=10)
                    r.raise_for_status()
                    if st.session_state.get("research_thread_id") == tid:
                        st.session_state.research_thread_id = None
                    st.rerun()
                except requests.RequestException as e:
                    st.error(f"닫기 실패: {e}")

    st.divider()
    st.subheader("새 연구 시작")
    with st.form("new_research_form", clear_on_submit=True):
        topic = st.text_area("연구 주제·질문", height=80)
        if st.form_submit_button("시작"):
            if not topic:
                st.warning("주제를 입력해주세요.")
            else:
                new_thread_id = str(uuid.uuid4())
                if _advance(new_thread_id, "hypothesis", topic=topic):
                    st.session_state.research_thread_id = new_thread_id
                    st.rerun()

if not st.session_state.get("research_thread_id"):
    st.info("왼쪽에서 세션을 선택하거나 새 연구를 시작하세요.")
    st.stop()

thread_id = st.session_state.research_thread_id
try:
    history_resp = requests.get(f"{BACKEND_URL}/research/{thread_id}/history", timeout=10)
    history_resp.raise_for_status()
    history = history_resp.json()["history"]  # 오래된 것부터
except requests.RequestException as e:
    st.error(f"히스토리 조회 실패: {e}")
    st.stop()

if not history:
    st.error("이 세션의 기록이 없습니다.")
    st.stop()

tip = history[-1]

# 타임라인은 항상 최신(tip) 기준 — 값이 채워진 단계만 체크, 현재 단계 강조
cols = st.columns(len(STAGES))
for col, (stage_key, label) in zip(cols, STAGES):
    marker = "✅" if tip["values"].get(STAGE_DONE_FIELD[stage_key]) else "⬜"
    text = f"**{marker} {label}**"
    if tip["values"]["stage"] == stage_key:
        text += " ← 현재"
    col.markdown(text)

st.divider()

# 히스토리를 탭으로 — "탭처럼 왔다갔다" 설계 그대로. 각 탭은 그 시점의 값을 읽기 전용으로
# 보여주고, 그 탭에서 진행 버튼을 누르면 그 시점을 기준으로 새로 이어간다(과거 값은
# 체크포인트로 남아있으니 사라지지 않는다 — RoadMap 설계 노트 참고).
# st.tabs()는 재실행마다 첫 탭으로 초기화돼서(진행 직후에도 예전 탭에 머무름) 대신
# 세션 상태로 직접 선택을 관리한다 — 기본은 항상 최신(tip), 진행 액션이 성공하면
# _render_next_options()가 이 키를 지워서 다음 재실행에 자동으로 새 tip을 보여준다.
view_key = f"research_view_checkpoint_{thread_id}"
valid_ids = {e["checkpoint_id"] for e in history}
if st.session_state.get(view_key) not in valid_ids:
    st.session_state[view_key] = tip["checkpoint_id"]

STAGE_LABELS = dict(STAGES)
cols = st.columns(len(history))
for col, entry in zip(cols, history):
    ts = entry["created_at"][11:16] if entry.get("created_at") else ""
    suffix = " (현재)" if entry["checkpoint_id"] == tip["checkpoint_id"] else ""
    label = f"{STAGE_LABELS.get(entry['stage'], entry['stage'])} {ts}{suffix}"
    is_selected = entry["checkpoint_id"] == st.session_state[view_key]
    if col.button(label, key=f"tabbtn_{entry['checkpoint_id']}", type="primary" if is_selected else "secondary", use_container_width=True):
        st.session_state[view_key] = entry["checkpoint_id"]
        st.rerun()

selected = next(e for e in history if e["checkpoint_id"] == st.session_state[view_key])
values = selected["values"]
is_tip = selected["checkpoint_id"] == tip["checkpoint_id"]

st.divider()

if not is_tip:
    st.caption("과거 시점입니다 — 여기서 진행하면 이 시점을 기준으로 새로 이어집니다.")
if values.get("comment"):
    st.info(values["comment"])

_render_stage_content(values)

st.divider()
st.subheader("다음으로 갈 수 있는 곳")
_render_next_options(
    thread_id, values, tip_values=tip["values"],
    from_checkpoint_id=None if is_tip else selected["checkpoint_id"],
    view_key=view_key,
)
