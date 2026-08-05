# PDF 파싱 어댑터 — PyMuPDF(fitz)+pymupdf4llm을 이 모듈 뒤에 격리(교체 대비, arxiv_api.py와
# 같은 패턴). ⚠️ AGPL-3.0 듀얼 라이선스 — 공개 배포 상태에서만 유효한 전제(비공개화·상용화
# 시 재검토, 대체 후보 pypdfium2). 2단 조판 폴백은 아직 없음(실제로 걸리면 착수). 애매하면
# text_extractable=False로 정직하게 보고 — 조용히 자르거나 짜맞추지 않는다.

import fitz  # PyMuPDF
import pymupdf4llm

# 페이지당 이 문자수 미만이면 텍스트 레이어가 없는 스캔본으로 판단.
# 완전 스캔본은 보통 0에 가깝고, 여백 등에 우연히 걸리는 텍스트 몇 글자 정도의 여유를 둔다.
# OCR은 붙이지 않는다 — 스캔본이면 그대로 정직하게 보고한다 (To Do "스캔본 감지" 참고).
SCANNED_CHAR_THRESHOLD_PER_PAGE = 20

# 스캔본 판별용 표본 페이지 수 — 전체를 다 훑을 필요 없다(스캔본이면 앞쪽 몇 페이지로
# 이미 명백, 아니면 첫 페이지부터 텍스트가 있음). 전체 순회는 뒤의 to_markdown()과 중복.
SCANNED_DETECTION_SAMPLE_PAGES = 5


def _looks_scanned(doc: fitz.Document) -> bool:
    """앞쪽 최대 SCANNED_DETECTION_SAMPLE_PAGES 페이지만 표본으로 추출 문자수 평균을
    내 텍스트 레이어 존재 여부를 판단한다(전체 페이지 순회 안 함 — 위 모듈 상수 참고)."""
    sample_page_count = min(SCANNED_DETECTION_SAMPLE_PAGES, len(doc))
    total_chars = sum(len(doc[i].get_text("text")) for i in range(sample_page_count))
    avg_chars_per_page = total_chars / max(sample_page_count, 1)
    return avg_chars_per_page < SCANNED_CHAR_THRESHOLD_PER_PAGE


def parse_pdf(file_bytes: bytes) -> dict:
    """PDF 파일을 파싱해 마크다운 텍스트와 메타데이터를 반환한다.

    file_bytes: 경로가 아니라 바이트를 받는다 — 호출자(register_paper())가 paper_id
    계산(파일 해시)에도 같은 바이트가 필요해 이미 읽어둔 걸 그대로 재사용, 중복 I/O 방지.

    반환 키: text_extractable(False면 스캔본, markdown 빈 문자열) / markdown(헤딩은 폰트
    크기 휴리스틱이라 인식률 편차 있음, 폴백은 호출하는 쪽 몫) / page_count.

    수식은 폰트 인코딩에 따라 깨진 유니코드로 나올 수 있어 신뢰하지 않는다 — 필요한 곳에서
    "수식 신뢰 불가"로 별도 표기할 것.
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

    if len(sys.argv) < 2:
        print("사용법: uv run paper/pdf_parse.py <PDF 경로>")
        sys.exit(1)

    with open(sys.argv[1], "rb") as f:
        result = parse_pdf(f.read())
    print(f"페이지 수: {result['page_count']}")
    print(f"텍스트 추출 가능: {result['text_extractable']}")
    if result["text_extractable"]:
        print(f"마크다운 총 길이: {len(result['markdown'])}자")
    else:
        print("스캔본으로 판단됨 (텍스트 레이어 없음) — OCR 미적용, text_extractable=False")
