import streamlit as st

# 08-11 라이브러리 표면 1차 — 단일 파일 챗 화면을 멀티페이지로 전환하는 첫 단위.
# 여긴 이제 네비게이션 구조만 갖고 있고, 실제 화면은 views/ 아래 각 파일이 담당한다.
# st.set_page_config()는 앱 전체에서 딱 한 번, 가장 먼저 호출돼야 하므로 각 페이지가
# 아니라 여기서만 호출한다(페이지 쪽에서 다시 부르면 에러).
#
# pages/ 디렉터리 자동 인식 방식(구 Streamlit 관례) 대신 st.navigation()+st.Page()를
# 쓰는 이유: 파일명 슬러그로 페이지 이름이 정해지는 관례보다 그룹(메인/라이브러리)·
# 아이콘·기본 페이지를 명시적으로 통제할 수 있다.
st.set_page_config(page_title="Science Chatbot", page_icon="🔬")

pages = {
    "메인": [st.Page("views/chat.py", title="챗", icon="💬", default=True)],
    "라이브러리": [
        st.Page("views/papers.py", title="논문", icon="📄"),
        st.Page("views/interests.py", title="관심사", icon="🔬"),
    ],
}

st.navigation(pages).run()
