import requests
import streamlit as st

from common import BACKEND_URL

st.title("📄 논문")

# 등록 폼 — doi/arxiv_id는 있는 것만 넘기면 register_paper()가 우선순위(DOI>arXiv>해시)로
# paper_id를 계산한다 — 둘 다 비워도 파일 해시로 등록은 된다.
with st.form("register_paper_form", clear_on_submit=True):
    uploaded = st.file_uploader("PDF 파일", type=["pdf"])
    col1, col2 = st.columns(2)
    doi = col1.text_input("DOI (선택)")
    arxiv_id = col2.text_input("arXiv id (선택)")
    submitted = st.form_submit_button("등록")

if submitted:
    if uploaded is None:
        st.warning("PDF 파일을 선택해주세요.")
    else:
        data = {}
        if doi:
            data["doi"] = doi
        if arxiv_id:
            data["arxiv_id"] = arxiv_id

        with st.spinner("등록 중... (PDF 파싱 + 임베딩이라 시간이 걸릴 수 있습니다)"):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/papers",
                    files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                    data=data,
                    timeout=300,
                )
                resp.raise_for_status()
                result = resp.json()
            except requests.RequestException as e:
                st.error(f"등록 실패: {e}")
                result = None

        if result is not None:
            if not result["text_extractable"]:
                # pdf_parse.py 원칙 그대로 — 스캔본은 OCR 없이 정직하게 저장을 건너뛴다.
                st.warning(f"스캔본으로 판단되어 저장하지 않았습니다 (페이지 {result['page_count']}쪽, 텍스트 레이어 없음).")
            else:
                st.success(f"등록 완료 — paper_id=`{result['paper_id']}`, 청크 {result['chunk_count']}개, {result['page_count']}쪽")
                title_check = result.get("title_check") or {}
                if title_check.get("status") == "different_paper":
                    st.warning(
                        f"제목이 크게 달라 다른 논문일 수 있습니다 — 입력한 제목 '{title_check.get('given_title')}' "
                        f"vs PDF 제목 '{title_check.get('pdf_title')}'"
                    )

st.divider()
st.subheader("카탈로그 상태")

# 전역 목록만 가능 — 관심사별 필터는 interest_paper 조인 테이블이 없어 아직 없음(RoadMap 참고).
try:
    resp = requests.get(f"{BACKEND_URL}/papers", timeout=10)
    resp.raise_for_status()
    papers = resp.json()["papers"]
except requests.RequestException as e:
    st.error(f"카탈로그 조회 실패: {e}")
else:
    if papers:
        st.dataframe(papers, width="stretch", height=300)  # 고정 높이 — 안 그러면 논문이 많아질수록 페이지가 계속 늘어남
    else:
        st.caption("등록된 논문이 없습니다.")
