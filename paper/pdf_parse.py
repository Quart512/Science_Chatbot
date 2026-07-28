# =========================================================
# PDF 파싱 어댑터 — PyMuPDF(fitz) + pymupdf4llm을 이 모듈 뒤에 격리한다.
# arxiv_api.py와 같은 패턴: 다른 라이브러리로 바꿀 일이 생기면 이 파일의 함수 내부만
# 갈아끼우면 되고, 호출하는 쪽(논문 요약기 파이프라인)은 반환 dict 구조만 알면 된다.
#
# ⚠️ 라이선스 고지: PyMuPDF/pymupdf4llm은 AGPL-3.0 듀얼 라이선스다. 공개 레포·공개
# 배포 상태를 유지하는 지금 구조에서는 이 고지로 준수되지만, 프로젝트를 비공개화하거나
# 상용화하면 재검토가 필요하다. 대체 후보: pypdfium2(Apache-2.0/BSD-3, PDFium 기반) —
# 결정 근거는 docs/RoadMap.md "PDF 파싱 라이브러리 선택 (07-28)" 참고.
#
# 지금은 단순 경로만 구현한다 (To Do "단순 경로부터" 참고):
#   - 2단 조판 폴백(get_text sort=True → bbox 컬럼 분할 재조립)은 아직 없음 — 실제
#     2단 논문으로 pymupdf4llm.to_markdown() 결과를 먼저 눈으로 확인한 뒤에 붙인다
#     (To Do "2단 조판 먼저 눈으로 확인" 참고). 지금 이 함수는 그 확인 작업에도 그대로 쓴다.
#   - 조용히 자르거나 대충 짜맞추지 않는다 — 애매하면 text_extractable=False로
#     정직하게 보고한다 (뒷단이 "요약 불가"를 사용자에게 알릴 수 있게).
# =========================================================

import fitz  # PyMuPDF
import pymupdf4llm

# 페이지당 이 문자수 미만이면 텍스트 레이어가 없는 스캔본으로 판단.
# 완전 스캔본은 보통 0에 가깝고, 여백 등에 우연히 걸리는 텍스트 몇 글자 정도의 여유를 둔다.
# OCR은 붙이지 않는다 — 스캔본이면 그대로 정직하게 보고한다 (To Do "스캔본 감지" 참고).
SCANNED_CHAR_THRESHOLD_PER_PAGE = 20


def _looks_scanned(doc: fitz.Document) -> bool:
    """페이지당 평균 추출 문자수로 텍스트 레이어 존재 여부를 판단한다."""
    total_chars = sum(len(page.get_text("text")) for page in doc)
    avg_chars_per_page = total_chars / max(len(doc), 1)
    return avg_chars_per_page < SCANNED_CHAR_THRESHOLD_PER_PAGE


def parse_pdf(path: str) -> dict:
    """PDF 파일을 파싱해 마크다운 텍스트(헤딩 보존 시도)와 메타데이터를 반환한다.

    반환 키:
        text_extractable: bool — False면 스캔본(텍스트 레이어 없음), markdown은 빈 문자열
        markdown: str — pymupdf4llm이 뽑은 마크다운. 헤딩(`#`/`##`)은 폰트 크기
            휴리스틱으로 잡히므로 논문마다 인식률이 다를 수 있다 — 헤더 분할 단계의
            폴백(정규식 → 문단 분할)은 이 함수가 아니라 호출하는 쪽(섹션 분할 단계)의 몫.
        page_count: int

    그림 캡션은 pymupdf4llm이 기본으로 텍스트에 포함시켜 살아남고, 이미지 픽셀 자체나
    수식(폰트 인코딩에 따라 깨진 유니코드로 나올 수 있음)은 애초에 신뢰하지 않는다 —
    수식이 필요한 곳(예: 요약 메타데이터)에서는 "수식 신뢰 불가"로 별도 표기할 것.
    """
    # fitz.Document는 context manager를 지원한다 — with 블록을 빠져나갈 때(정상 종료든
    # 예외든 return이든) 파이썬이 알아서 doc.close()를 호출해준다. try/finally로 직접
    # close()를 챙기던 걸 이걸로 대체 — 동작은 동일하고 명시적으로 챙길 게 하나 준다.
    with fitz.open(path) as doc:
        page_count = len(doc)

        if _looks_scanned(doc):
            return {
                "text_extractable": False,
                "markdown": "",
                "page_count": page_count,
            }

        # doc(이미 열린 fitz.Document)을 그대로 넘겨 파일을 두 번 열지 않는다.
        markdown = pymupdf4llm.to_markdown(doc)

        return {
            "text_extractable": True,
            "markdown": markdown,
            "page_count": page_count,
        }


if __name__ == "__main__":
    import sys
    # from pathlib import Path  # 아래 .parsed.md 저장(주석 처리됨)에서만 쓰던 import

    if len(sys.argv) < 2:
        print("사용법: uv run paper/pdf_parse.py <PDF 경로>")
        sys.exit(1)

    result = parse_pdf(sys.argv[1])
    print(f"페이지 수: {result['page_count']}")
    print(f"텍스트 추출 가능: {result['text_extractable']}")
    if result["text_extractable"]:
        print(f"마크다운 총 길이: {len(result['markdown'])}자")

        # 전체 마크다운을 .md 파일로 떨궈서 에디터로 눈으로 확인하던 디버깅용 코드 —
        # 2단 조판 확인(To Do)이 이미 끝나서 지금은 안 씀. 다른 포맷의 논문을 새로
        # 눈으로 확인해야 할 일이 생기면 그때 다시 주석을 풀 것. 어떤 실제 코드도(예:
        # paper_ingest.py의 register_paper()) 이 .parsed.md 파일에 의존하지 않는다 —
        # 다들 parse_pdf()의 반환값(markdown 문자열)을 메모리에서 바로 쓴다.
        # out_path = Path(sys.argv[1]).with_suffix(".parsed.md")
        # out_path.write_text(result["markdown"], encoding="utf-8")
        # print(f"전체 마크다운을 파일로 저장함: {out_path}")
    else:
        print("스캔본으로 판단됨 (텍스트 레이어 없음) — OCR 미적용, text_extractable=False")
