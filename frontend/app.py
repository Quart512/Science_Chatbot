import os
import uuid

import requests
import streamlit as st

# 로컬(uv run)에선 기본값(localhost)을 쓰고, Docker Compose로 뜰 땐 서비스 이름으로
# 오버라이드된다 — models.py의 LOCAL_MODEL_URL과 완전히 같은 패턴.
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Science Chatbot", page_icon="🔬")
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
    top_k = st.slider("검색 문서 수 (top_k)", min_value=1, max_value=10, value=3)
    st.caption(f"thread_id: `{st.session_state.thread_id}`")

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
        with st.spinner("생각 중..."):
            try:
                res = requests.post(
                    f"{BACKEND_URL}/query",
                    json={
                        "prompt": question,
                        "top_k": top_k,
                        "model": model,
                        "thread_id": st.session_state.thread_id,
                    },
                    timeout=120,
                )
                res.raise_for_status()
                data = res.json()
                answer, comment = data["answer"], data.get("comment", "")
            except requests.RequestException as e:
                answer, comment = f"백엔드 호출 실패: {e}", ""

        st.write(answer)
        if comment:
            st.caption(f"💬 {comment}")

    st.session_state.history.append({"role": "assistant", "content": answer, "comment": comment})
