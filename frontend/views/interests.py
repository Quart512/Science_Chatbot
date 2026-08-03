import requests
import streamlit as st

from common import BACKEND_URL

st.title("🔬 관심사")

# 백엔드 recommend_for_interest()의 max_results 기본값(5)과 맞춘 페이지 크기 —
# "추가 검색"이 start를 이만큼씩 밀어야 다음 페이지를 이어받는다.
SEARCH_PAGE_SIZE = 5

# 지정 안 하면 st.dataframe이 행 수만큼 페이지를 계속 늘어뜨린다 — 고정 높이로 내부 스크롤.
RESULTS_TABLE_HEIGHT = 300


def _to_table_rows(results: list[dict]) -> list[dict]:
    """스크리닝 결과를 화면 표시용으로 다듬는다 — abstract/tokens_used는 빼고, 이미
    관련도순으로 정렬돼 오는 순서를 그대로 신뢰해 O/X 대신 순위 번호를 붙인다."""
    return [
        {
            "순위": i + 1,
            "제목": r["title"],
            "근거": r["reasoning"],
            "peer review": r["peer_reviewed"],
            "연도": r["year"],
            "인용수": r["citation_count"],
        }
        for i, r in enumerate(results)
    ]


# 수동 생성 폼 — 직접 만드는 경로. 챗 사이드바 "이 대화를 관심사로 등록" 버튼을 누르면
# GET /interests/draft로 만든 초안이 session_state.interest_draft에 실려 이 페이지로
# 넘어온다(chat.py 참고). value=로 프리필하면 매 rerun마다 초안 값으로 되돌아가
# 사용자가 고친 내용이 지워지므로(위젯에 매번 재적용됨), key=로 위젯 자체의 세션 상태에
# 최초 1회만 심어두고 그 다음부터는 사용자가 고친 값이 그대로 유지되게 한다.
_draft = st.session_state.pop("interest_draft", None)
if _draft:
    st.session_state["create_title"] = _draft.get("title", "")
    st.session_state["create_looking_for"] = _draft.get("looking_for", "")
    st.session_state["create_already_known"] = _draft.get("already_known", "")
    st.session_state["create_excluded_topics"] = _draft.get("excluded_topics", "")

with st.expander("새 관심사 만들기", expanded=bool(_draft)):
    with st.form("create_interest_form", clear_on_submit=True):
        title = st.text_input("제목", key="create_title")
        looking_for = st.text_area("찾는 것", key="create_looking_for", height=80)
        already_known = st.text_area("이미 아는 것", key="create_already_known", height=80)
        excluded_topics = st.text_input("제외할 주제", key="create_excluded_topics")
        create_submitted = st.form_submit_button("만들기")

    if create_submitted:
        if not title:
            st.warning("제목을 입력해주세요.")
        else:
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/interests",
                    json={
                        "title": title,
                        "looking_for": looking_for,
                        "already_known": already_known,
                        "excluded_topics": excluded_topics,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                st.success(f"생성됨 — interest_id={resp.json()['interest_id']}")
                st.rerun()
            except requests.RequestException as e:
                st.error(f"생성 실패: {e}")

st.divider()

try:
    resp = requests.get(f"{BACKEND_URL}/interests", timeout=10)
    resp.raise_for_status()
    interest_list = resp.json()["interests"]
except requests.RequestException as e:
    st.error(f"관심사 조회 실패: {e}")
    interest_list = []

if not interest_list:
    st.caption("등록된 관심사가 없습니다.")

# 카드별 수정/삭제/검색 + 보유·추천 논문(interest_paper 조인, 08-03). 검색 버튼을
# 누른 순간의 반환 목록(세션 임시)과 보유·추천 논문(영구 기록)은 서로 다른 것 —
# 전자는 이번 세션에서 새로 찾은 후보 전부(관련 없음 포함), 후자는 지금까지
# 스크리닝된 것 중 관련 있다고 판정된 것만의 누적 기록.
for interest in interest_list:
    interest_id = interest["id"]
    results_key = f"results_{interest_id}"
    offset_key = f"offset_{interest_id}"

    with st.container(border=True):
        st.subheader(interest["title"])
        if interest.get("looking_for"):
            st.caption(f"찾는 것: {interest['looking_for']}")

        # 보유·추천 논문 — interest_paper 조인 테이블에서 이 관심사에 스크리닝된 것 중
        # 관련 있다고 판정된 것만 가져온다(08-03에 조인 테이블이 생기기 전엔 전역
        # 목록만 가능했다). 캐시 안 하고 매 rerun마다 새로 조회 — 개인 단일 사용자
        # 규모라 부담 없고, 카탈로그 상태(recommended→owned 등) 변화를 놓치지 않는다.
        try:
            papers_resp = requests.get(
                f"{BACKEND_URL}/interests/{interest_id}/papers",
                params={"only_relevant": True},
                timeout=10,
            )
            papers_resp.raise_for_status()
            owned_papers = papers_resp.json()["papers"]
        except requests.RequestException as e:
            st.error(f"보유 논문 조회 실패: {e}")
            owned_papers = []

        if owned_papers:
            status_labels = {"recommended": "추천됨", "owned": "보유", "dismissed": "기각됨"}
            with st.expander(f"보유·추천 논문 ({len(owned_papers)})"):
                for p in owned_papers:
                    label = status_labels.get(p.get("status"), p.get("status") or "상태 없음")
                    st.markdown(f"**{p['title'] or p['paper_id']}** — {label}")
                    if p.get("reasoning"):
                        st.caption(p["reasoning"])

        # 수정 폼 — POST /interests에 update_existing_id를 실어 보내면 새로 안 만들고
        # 그 id를 갱신한다. 저장되면 이전에 쌓아둔 검색 결과를 버리지 않고
        # POST /interests/{id}/refresh로 새 기준 재스크리닝+재검색을 자동으로 돌린다.
        with st.expander("수정"):
            with st.form(f"edit_interest_form_{interest_id}"):
                edit_title = st.text_input("제목", value=interest["title"])
                edit_looking_for = st.text_area("찾는 것", value=interest.get("looking_for", ""), height=80)
                edit_already_known = st.text_area("이미 아는 것", value=interest.get("already_known", ""), height=80)
                edit_excluded_topics = st.text_input("제외할 주제", value=interest.get("excluded_topics", ""))
                edit_submitted = st.form_submit_button("저장")

            if edit_submitted:
                if not edit_title:
                    st.warning("제목을 입력해주세요.")
                else:
                    try:
                        edit_resp = requests.post(
                            f"{BACKEND_URL}/interests",
                            json={
                                "title": edit_title,
                                "looking_for": edit_looking_for,
                                "already_known": edit_already_known,
                                "excluded_topics": edit_excluded_topics,
                                "update_existing_id": interest_id,
                            },
                            timeout=10,
                        )
                        edit_resp.raise_for_status()
                    except requests.RequestException as e:
                        st.error(f"수정 실패: {e}")
                    else:
                        # 수정이 큰 변화가 아닐 수도 있으니 기존 후보를 버리지 않고
                        # 새 기준으로 재스크리닝해 관련 있는 것만 남긴 뒤 새 페이지
                        # 검색과 합친다(refresh_for_interest() 참고). 결과 없이 수정만
                        # 한 카드는 재활용할 기존 후보가 없을 뿐 그대로 동작.
                        with st.spinner("관심사가 바뀌어 다시 검색 중..."):
                            try:
                                refresh_resp = requests.post(
                                    f"{BACKEND_URL}/interests/{interest_id}/refresh",
                                    json={"existing_candidates": st.session_state.get(results_key, [])},
                                    timeout=180,
                                )
                                refresh_resp.raise_for_status()
                                st.session_state[results_key] = refresh_resp.json()["recommended"]
                                st.session_state[offset_key] = SEARCH_PAGE_SIZE
                            except requests.RequestException as e:
                                st.error(f"재검색 실패: {e}")
                                st.session_state.pop(results_key, None)
                                st.session_state.pop(offset_key, None)
                        st.rerun()

        col_search, col_delete = st.columns([1, 1])

        if col_delete.button("삭제", key=f"delete_{interest_id}"):
            try:
                delete_resp = requests.delete(f"{BACKEND_URL}/interests/{interest_id}", timeout=10)
                delete_resp.raise_for_status()
            except requests.RequestException as e:
                st.error(f"삭제 실패: {e}")
            else:
                st.session_state.pop(results_key, None)
                st.session_state.pop(offset_key, None)
                st.rerun()

        # 검색/추가 검색 통합 버튼 — 하나의 버튼이 상태에 따라 라벨과 동작을 바꾼다:
        # 쌓인 결과가 없으면 "지금 검색"(start=0), 있으면 "추가 검색"(start=offset부터
        # 이어서 검색해 병합). 정렬은 관련도만 기준(peer_review/인용수/연도는 안 씀).
        has_results = results_key in st.session_state
        button_label = "추가 검색" if has_results else "지금 검색"
        if col_search.button(button_label, key=f"search_{interest_id}"):
            start = st.session_state[offset_key] if has_results else 0
            with st.spinner("검색 중... (arXiv 검색 + 관련도 스크리닝이라 시간이 걸릴 수 있습니다)"):
                try:
                    search_resp = requests.post(
                        f"{BACKEND_URL}/interests/{interest_id}/search",
                        params={"start": start},
                        timeout=180,
                    )
                    search_resp.raise_for_status()
                    new_results = search_resp.json()["recommended"]
                except requests.RequestException as e:
                    st.error(f"검색 실패: {e}")
                else:
                    if has_results:
                        combined = st.session_state[results_key] + new_results
                        combined.sort(key=lambda r: not r["is_relevant"])
                        st.session_state[results_key] = combined
                        st.session_state[offset_key] += SEARCH_PAGE_SIZE
                    else:
                        st.session_state[results_key] = new_results
                        st.session_state[offset_key] = SEARCH_PAGE_SIZE
                    st.rerun()

        if results_key in st.session_state:
            results = st.session_state[results_key]
            if results:
                st.dataframe(_to_table_rows(results), width="stretch", height=RESULTS_TABLE_HEIGHT)
            else:
                st.caption("검색된 후보가 없습니다.")
