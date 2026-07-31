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

# 스캔본 판별에 쓸 표본 페이지 수(07-28, 리뷰 지적): 전체 페이지를 다 훑을 필요가
# 없다 — 스캔본이면 앞쪽 몇 페이지만 봐도 텍스트 레이어 부재가 이미 명백하고, 텍스트가
# 있는 논문이면 첫 페이지부터 이미 있다. 전체를 다 훑으면 어차피 뒤에서 pymupdf4llm.
# to_markdown()이 전체를 다시 추출할 큰 논문에서 같은 페이지를 두 번 순회하는 중복
# 작업이 된다.
SCANNED_DETECTION_SAMPLE_PAGES = 5


def _looks_scanned(doc: fitz.Document) -> bool:
    """앞쪽 최대 SCANNED_DETECTION_SAMPLE_PAGES 페이지만 표본으로 추출 문자수 평균을
    내 텍스트 레이어 존재 여부를 판단한다(전체 페이지 순회 안 함 — 위 모듈 상수 참고)."""
    sample_page_count = min(SCANNED_DETECTION_SAMPLE_PAGES, len(doc))
    total_chars = sum(len(doc[i].get_text("text")) for i in range(sample_page_count))
    avg_chars_per_page = total_chars / max(sample_page_count, 1)
    return avg_chars_per_page < SCANNED_CHAR_THRESHOLD_PER_PAGE


def _extract_pdf_title(doc: fitz.Document, markdown: str) -> str | None:
    """제목 후보를 뽑는다(07-29, 6-3b③ 제목 검증용) — PDF 내장 메타데이터
    (`doc.metadata["title"]`)를 우선 쓴다. arxiv가 생성한 PDF는 대개 여기에 제목이
    박혀 있어, `paper_chunking.py`에 이미 기록된 헤더 오탐지(저자명이 헤더로 잡히는
    사례)보다 안정적이다. 메타데이터가 비어 있으면 마크다운 첫 줄로 폴백(완벽하지
    않음 — 그래서 title_check.py가 "추출 실패"를 불일치와 다르게 취급한다).

    문서 메타데이터는 텍스트 레이어와 무관하게 항상 읽을 수 있으므로 스캔본에도
    시도할 가치가 있다 — 그래서 이 함수는 scanned 여부를 모르는 채로 호출돼도 된다
    (마크다운이 빈 문자열이면 그냥 첫 줄 폴백만 안 됨).
    """
    meta_title = (doc.metadata.get("title") or "").strip()
    if meta_title:
        return meta_title
    for line in markdown.splitlines():
        line = line.strip().lstrip("#").strip("* ").strip()
        if line:
            return line
    return None


def parse_pdf(file_bytes: bytes) -> dict:
    """PDF 파일을 파싱해 마크다운 텍스트(헤딩 보존 시도)와 메타데이터를 반환한다.

    file_bytes: PDF 원본 바이트. 경로 문자열이 아니라 바이트를 받는 이유(07-28, 리뷰
    지적): 호출하는 쪽(register_paper())이 paper_id 계산(파일 해시)에도 같은 바이트가
    필요해서 이미 파일을 한 번 읽어둔다 — 여기서 다시 경로로 fitz.open(path)를 하면
    디스크에서 같은 파일을 또 읽는 중복 I/O가 생긴다. 이미 메모리에 있는 바이트를
    stream=으로 그대로 넘겨 재사용한다.

    반환 키:
        text_extractable: bool — False면 스캔본(텍스트 레이어 없음), markdown은 빈 문자열
        markdown: str — pymupdf4llm이 뽑은 마크다운. 헤딩(`#`/`##`)은 폰트 크기
            휴리스틱으로 잡히므로 논문마다 인식률이 다를 수 있다 — 헤더 분할 단계의
            폴백(정규식 → 문단 분할)은 이 함수가 아니라 호출하는 쪽(섹션 분할 단계)의 몫.
        page_count: int
        pdf_title: str | None — 제목 후보(07-29, _extract_pdf_title 참고). 못 찾으면 None.

    그림 캡션은 pymupdf4llm이 기본으로 텍스트에 포함시켜 살아남고, 이미지 픽셀 자체나
    수식(폰트 인코딩에 따라 깨진 유니코드로 나올 수 있음)은 애초에 신뢰하지 않는다 —
    수식이 필요한 곳(예: 요약 메타데이터)에서는 "수식 신뢰 불가"로 별도 표기할 것.
    """
    # fitz.Document는 context manager를 지원한다 — with 블록을 빠져나갈 때(정상 종료든
    # 예외든 return이든) 파이썬이 알아서 doc.close()를 호출해준다. try/finally로 직접
    # close()를 챙기던 걸 이걸로 대체 — 동작은 동일하고 명시적으로 챙길 게 하나 준다.
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        page_count = len(doc)

        if _looks_scanned(doc):
            return {
                "text_extractable": False,
                "markdown": "",
                "page_count": page_count,
                "pdf_title": _extract_pdf_title(doc, ""),  # 메타데이터만 시도(마크다운 없음)
            }

        # doc(이미 열린 fitz.Document)을 그대로 넘겨 파일을 두 번 열지 않는다.
        markdown = pymupdf4llm.to_markdown(doc)

        return {
            "text_extractable": True,
            "markdown": markdown,
            "page_count": page_count,
            "pdf_title": _extract_pdf_title(doc, markdown),
        }


if __name__ == "__main__":
    import sys
    # from pathlib import Path  # 아래 .parsed.md 저장(주석 처리됨)에서만 쓰던 import

    if len(sys.argv) < 2:
        print("사용법: uv run paper/pdf_parse.py <PDF 경로>")
        sys.exit(1)

    with open(sys.argv[1], "rb") as f:
        result = parse_pdf(f.read())
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
