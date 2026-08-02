import streamlit as st

# 네비게이션 구조만 담당 — 실제 화면은 views/ 아래 각 파일. st.set_page_config()는
# 앱 전체에서 한 번, 가장 먼저 호출돼야 해서 각 페이지가 아니라 여기서만 호출한다.
# pages/ 디렉터리 자동 인식 대신 st.navigation()+st.Page()를 쓰는 이유: 그룹·아이콘·
# 기본 페이지를 파일명 슬러그가 아니라 명시적으로 통제할 수 있어서.
st.set_page_config(page_title="Science Chatbot", page_icon="🔬")

pages = {
    "메인": [st.Page("views/chat.py", title="챗", icon="💬", default=True)],
    "라이브러리": [
        st.Page("views/papers.py", title="논문", icon="📄"),
        st.Page("views/interests.py", title="관심사", icon="🔬"),
    ],
}

st.navigation(pages).run()
