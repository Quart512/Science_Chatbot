import json
import uuid

import requests
import streamlit as st

from common import BACKEND_URL

st.title("🔬 Science Chatbot — 물리 연구 어시스턴트")

# thread_id: 세션당 하나만 발급하고 rerun에도 유지해야 함 — 매번 새로 만들면
# 백엔드 입장에서 매 요청이 새 대화(단기기억 끊김)로 보임
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# 화면 표시용 대화 이력 (백엔드가 checkpointer로 들고 있는 messages와는 별개 — 여긴 그냥 렌더링용)
if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    model = st.selectbox("모델", ["gemini", "claude", "Qwen-tuned"])
    effort = st.selectbox("검색/재시도 강도 (effort)", ["low", "medium", "high"], index=1)
    st.caption(f"thread_id: `{st.session_state.thread_id}`")

    st.divider()
    # 라우터 대신 명시적 버튼(RoadMap "메인 챗 라우터 착수 보류" 08-02 결정) — 클릭
    # 자체가 의도 신호라 GET /interests/draft가 should_suggest 판정 없이 곧장 초안을
    # 만든다. 저장은 안 하고 관심사 탭으로 넘겨 폼에서 확인·수정 후 저장하게 한다.
    if st.button("💡 이 대화를 관심사로 등록"):
        try:
            draft_resp = requests.get(
                f"{BACKEND_URL}/interests/draft",
                params={"thread_id": st.session_state.thread_id},
                timeout=60,
            )
            draft_resp.raise_for_status()
        except requests.RequestException as e:
            st.error(f"초안 생성 실패: {e}")
        else:
            st.session_state.interest_draft = draft_resp.json()
            st.switch_page("views/interests.py")

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("comment"):
            st.caption(f"💬 {msg['comment']}")

if question := st.chat_input("물리에 대해 궁금한 걸 물어보세요"):
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        # /query가 이제 SSE로 진행 로그를 실시간으로 흘려보낸다(final=False인 동안은 판단 기록,
        # final=True가 뜨는 순간이 진짜 최종 answer). progress_box는 그 로그를 실시간으로 덮어쓰는 자리 —
        # 다 끝나면 지우고 답변만 깔끔히 남긴 뒤, 판단 기록은 접힌 expander로 아래에 남긴다.
        progress_box = st.empty()
        answer, comment, last_progress = "", "", ""
        try:
            with requests.post(
                f"{BACKEND_URL}/query",
                json={
                    "prompt": question,
                    "effort": effort,
                    "model": model,
                    "thread_id": st.session_state.thread_id,
                },
                timeout=120,
                stream=True,
            ) as res:
                res.raise_for_status()
                for line in res.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data: "):
                        continue
                    payload = json.loads(line[len("data: "):])
                    # trace: 내부 디버그 로그(진행 중 로그·판단 과정 expander용) / comment: 진짜 사용자용 코멘트(최종에만 있음)
                    last_progress = payload.get("trace", "") or last_progress
                    if payload.get("final"):
                        answer, comment = payload["answer"], payload.get("comment", "")
                    else:
                        progress_box.caption("⏳ " + last_progress.strip().splitlines()[-1] if last_progress.strip() else "⏳ 진행 중...")
        except requests.RequestException as e:
            answer = f"백엔드 호출 실패: {e}"

        progress_box.empty()
        st.write(answer)
        if comment:
            st.caption(f"💬 {comment}")
        if last_progress:
            with st.expander("판단 과정 보기"):
                st.text(last_progress)

    st.session_state.history.append({"role": "assistant", "content": answer, "comment": comment})
