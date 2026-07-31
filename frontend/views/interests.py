import requests
import streamlit as st

from common import BACKEND_URL

st.title("🔬 관심사")

# 수동 생성 폼 — 관심사를 만드는 원래 경로는 챗의 제안 흐름(orchestrator.py의
# suggest_interest_node가 초안을 만들면 "관심사 등록" 버튼으로 저장)이지만, 그 버튼은
# 아직 프론트에 안 붙어 있다(08-10/향후 과제). 그때까지 이 화면만으로는 테스트할
# 관심사가 하나도 안 생기므로, 관리 UI답게 직접 만드는 경로도 같이 둔다 —
# POST /interests(08-07 호출 경로)를 그대로 호출.
with st.expander("새 관심사 만들기"):
    with st.form("create_interest_form", clear_on_submit=True):
        title = st.text_input("제목")
        looking_for = st.text_area("찾는 것", height=80)
        already_known = st.text_area("이미 아는 것", height=80)
        excluded_topics = st.text_input("제외할 주제")
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

# 카드별 "지금 검색" 트리거(08-09③ 호출 경로) — 관심사에서 트리거할 때만 실행한다는
# 원칙 그대로, cron 없이 이 버튼이 유일한 진입점이다. 보유/권위 논문 목록은 아직 못
# 붙인다 — interest_paper 조인 테이블이 없어 "이 관심사의" 논문을 못 특정한다
# (RoadMap "관심사↔논문이 다대다다" 열린 질문). 지금은 검색 버튼을 누른 그 순간의
# 반환 목록만 그 자리에서 보여준다.
for interest in interest_list:
    with st.container(border=True):
        st.subheader(interest["title"])
        if interest.get("looking_for"):
            st.caption(f"찾는 것: {interest['looking_for']}")

        col_search, col_delete = st.columns([1, 1])

        if col_delete.button("삭제", key=f"delete_{interest['id']}"):
            try:
                delete_resp = requests.delete(f"{BACKEND_URL}/interests/{interest['id']}", timeout=10)
                delete_resp.raise_for_status()
            except requests.RequestException as e:
                st.error(f"삭제 실패: {e}")
            else:
                st.rerun()

        if col_search.button("지금 검색", key=f"search_{interest['id']}"):
            with st.spinner("검색 중... (arXiv 검색 + 관련도 스크리닝이라 시간이 걸릴 수 있습니다)"):
                try:
                    search_resp = requests.post(
                        f"{BACKEND_URL}/interests/{interest['id']}/search", timeout=180
                    )
                    search_resp.raise_for_status()
                    results = search_resp.json()["recommended"]
                except requests.RequestException as e:
                    st.error(f"검색 실패: {e}")
                    results = None

            if results is not None:
                if results:
                    # abstract/tokens_used는 화면에 필요 없는(길거나 내부용) 필드라 뺀다 —
                    # "스크리닝 축을 합치지 않는다" 원칙 그대로 관련도·peer_review·인용수·
                    # 연도를 나란히 보여주고 재정렬은 안 한다(paper_recommend.py가 이미
                    # 관련도만으로 정렬해 넘겨준 순서 그대로).
                    table = [
                        {
                            "제목": r["title"],
                            "관련 있음": r["is_relevant"],
                            "근거": r["reasoning"],
                            "peer review": r["peer_reviewed"],
                            "연도": r["year"],
                            "인용수": r["citation_count"],
                        }
                        for r in results
                    ]
                    st.dataframe(table, width="stretch")
                else:
                    st.caption("검색된 후보가 없습니다.")
