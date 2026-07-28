# =========================================================
# 논문 마크다운(pdf_parse.py의 출력)을 헤더 기준으로 나누고, 짧은 섹션은 문서 순서를
# 유지한 채 인접 섹션과 합쳐 적당한 크기의 청크로 만든다.
#
# 이 병합이 필요한 이유(실제로 관찰됨): pymupdf4llm의 헤더 인식은 폰트 크기 휴리스틱
# 이라 저자명처럼 볼드체인 줄을 헤더로 오탐지하는 경우가 있다(실제 사례: 논문
# "거대 언어 모델의 멀티모달 입력..."에서 "## Jaebong Lee"가 헤더로 잡힘). 이런
# 오탐지 헤더를 별도 로직으로 걸러내는 대신, 헤더가 하나 나올 때마다 무조건 새
# 청크를 만들지 않고 max_chars를 넘기 전까지는 다음 섹션과 계속 합쳐버리면 — 오탐지
# 헤더는 어차피 내용이 짧으니 옆 섹션에 자연스럽게 흡수된다.
#
# 범위 밖(단순 경로부터 — 실제로 걸리는 걸 확인한 뒤에 추가):
#   - 헤더가 하나도 안 잡히는 논문(전체가 한 덩어리) — 정규식 섹션명 탐지나 문단
#     분할 폴백이 필요하지만, 아직 그런 논문을 실제로 만나지 않아 미구현
#   - 섹션 하나 자체가 max_chars를 넘는 경우도 그대로 큰 청크 하나로 반환한다 —
#     이걸 모델 컨텍스트 예산에 맞게 더 쪼갤지는 호출하는 쪽(LLM 호출 지점)의 몫
#
# 헤더 라벨의 신뢰도에 대해 (실제로 관찰됨, 07-28): 페이지가 넘어가는 지점에서
# 문장 중간이 볼드체로 잘못 인식돼 헤더로 오탐지되는 경우가 있다(예: "있음을 알
# 수 있다."가 헤더로 잡힘). 병합 로직이 "짧은 오탐지"는 옆 섹션에 흡수해 없애주지만,
# 오탐지된 헤더 뒤에 긴 진짜 본문이 이어지면 그 청크 전체가 엉뚱한 라벨을 달고
# 살아남는다. 이걸 정규식 등으로 걸러내는 대신(비용 대비 지금 아무도 안 쓰는
# 정확도), 이 헤더 라벨을 호출하는 쪽(추출 LLM 시스템 프롬프트)이 "정확한 주제
# 분류"가 아니라 "대략적인 위치 표시" 정도로만 취급하도록 명시할 것 — 예:
# "아래 각 청크 앞에 붙은 헤더 라벨은 자동 추출 과정에서 부정확할 수 있다.
# 라벨보다 본문 내용 자체를 근거로 판단해라." 같은 문구를 시스템 프롬프트에 넣는다.
# =========================================================

from langchain_text_splitters import MarkdownHeaderTextSplitter

HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


def split_into_sections(
    markdown: str, max_chars: int = 4000, overlap_chars: int = 300
) -> list[dict]:
    """마크다운을 헤더 기준으로 나눈 뒤, 문서 순서를 유지하면서 max_chars를 넘지
    않는 선까지 인접 섹션들을 하나의 청크로 합친다. 청크 경계마다 이전 청크
    꼬리의 overlap_chars만큼을 다음 청크 앞에 겹쳐 붙여, 경계에서 문장이 뚝
    끊긴 채로 LLM에 넘어가지 않게 한다(ingest.py의 chunk_overlap=50과 같은 이유
    — 다만 여기는 섹션 단위라 오버랩 크기가 훨씬 큼).

    반환: [{"headers": [...이 청크에 포함된 헤더 텍스트들...], "text": str}, ...]
    헤더 텍스트는 본문에서 지우지 않는다(strip_headers=False) — "## I. 서론" 같은
    표시가 그대로 남아 있는 편이, 나중에 이 텍스트를 읽는 LLM이 지금 어느 섹션을
    보고 있는지 알 수 있어 유리하다. 단, 헤더 라벨 자체의 신뢰도는 위 모듈
    docstring 참고 — 완벽하지 않다는 전제로 다뤄야 한다.
    """
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False
    )
    docs = splitter.split_text(markdown)

    merged: list[dict] = []
    current_texts: list[str] = []
    current_headers: list[str] = []
    current_len = 0

    for doc in docs:
        doc_len = len(doc.page_content)
        # metadata는 {"h1": "...", "h2": "...", ...} 형태 — 이 섹션이 속한 가장
        # 깊은(마지막) 헤더 하나만 대표로 기록한다. 상위 헤더까지 다 필요해지면
        # 그때 리스트로 바꾸면 됨 — 지금은 어느 섹션이 합쳐졌는지 추적용
        header_values = list(doc.metadata.values())
        header_label = header_values[-1] if header_values else ""

        # 지금까지 모아둔 게 있는데 이 섹션까지 더하면 넘친다 -> 먼저 flush
        if current_texts and current_len + doc_len > max_chars:
            flushed_text = "\n\n".join(current_texts)
            merged.append({"headers": current_headers, "text": flushed_text})

            # 방금 청크의 꼬리를 다음 청크 시작에 오버랩으로 이어붙임
            tail = flushed_text[-overlap_chars:] if overlap_chars else ""
            current_texts, current_headers, current_len = [], [], 0
            if tail:
                overlap_text = f"(...이전 내용에서 이어짐) {tail}"
                current_texts.append(overlap_text)
                current_len += len(overlap_text)

        current_texts.append(doc.page_content)
        current_headers.append(header_label)
        current_len += doc_len

    if current_texts:
        merged.append({"headers": current_headers, "text": "\n\n".join(current_texts)})

    return merged


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: uv run paper_sections.py <.parsed.md 경로> [max_chars] [overlap_chars]")
        sys.exit(1)

    max_chars = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    overlap_chars = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    text = open(sys.argv[1], encoding="utf-8").read()
    chunks = split_into_sections(text, max_chars=max_chars, overlap_chars=overlap_chars)

    print(f"청크 수: {len(chunks)} (max_chars={max_chars}, overlap_chars={overlap_chars})")
    for i, c in enumerate(chunks):
        print(f"[{i}] 헤더: {c['headers']} / 길이: {len(c['text'])}자")
        if i > 0:
            print(f"    (앞부분 미리보기: {c['text'][:80]!r})")
