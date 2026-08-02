# 논문 마크다운(pdf_parse.py 출력)을 max_chars(호출자가 모델 컨텍스트 예산에 맞춰 정함)
# 이하 청크로 나눈다. 2단계: (1) 헤더(#/##/###) 분할 + 인접 섹션 병합 — pymupdf4llm의
# 헤더 오탐지(저자명 등)를 짧은 조각이 옆 섹션에 자연히 흡수되게 해서 완화. (2) 섹션이
# 그 자체로 max_chars를 넘으면 줄(`\n`) 단위로 더 쪼갠 뒤 같은 병합 루프로 채운다 —
# 원래 "문단(빈 줄)" 단위 계획은 MarkdownHeaderTextSplitter가 재조립 시 빈 줄을
# 안 보존해서 틀렸음이 실측으로 드러남(_split_oversized_section 참고). 그래도 줄 하나가
# max_chars를 넘는 극단적 경우는 그대로 반환 — 최종 안전망은 models.check_context_budget().
#
# 헤더 라벨은 표시용일 뿐 신뢰도가 낮다(페이지 경계에서 본문이 헤더로 오탐지되는 사례
# 있음) — 그래서 구조화 추출은 섹션명이 아니라 index 기반 chunk id로 출처를 추적한다
# (from_section이 아니라 from_chunk: 원문을 통째로 다시 찾아볼 수 있는 위치만 보장).
#
# is_references/is_abstract 판정은 **헤더 계층 전체**로 하고, 표시용 라벨(header_label,
# 가장 깊은 헤더 하나)과는 다른 값에서 파생시킨다 — 라벨 하나만 보고 판정하면 "# References"
# 아래 "## 부록 A" 같은 하위 절을 놓친다(같은 버그를 References·Abstract 두 번 겪음).
# References 조각은 버리지 않되(서지 추출용으로 보관) 구조화 추출·임베딩 입력에서는
# is_references로 걸러낸다. References 경계는 max_chars 여유와 무관하게 강제 flush —
# 안 그러면 References 조각이 옆 본문과 같은 청크로 묶여 본문까지 통째로 걸러질 수 있다
# (강제 flush에는 overlap도 안 붙임 — 성격이 다른 섹션 경계라 이어붙일 이유 없음).
#
# split_into_chunks(구조화 추출 LLM 입력용, 헤더 넘나들며 큰 단위로 병합)와
# split_for_embedding(검색용, ingest.py와 같은 결로 500자/오버랩 50 잘게 쪼갬)은 목적이
# 다른 별도 함수 — 후자는 헤더를 안 넘나들어 header가 단수(str), 전자는 headers(list).

import re

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]

# References 헤더 판별 — 영문(References/Bibliography/Works Cited)·한국어(참고문헌/
# 인용문헌/참고자료) 둘 다 커버. 헤더 텍스트가 이 단어로 시작하는지만 봐서(본문 문장
# 속 우연한 등장은 애초에 대상이 아님) 오탐 위험이 낮다. \s*로 붙여쓰기/띄어쓰기 둘 다 잡음.
_REFERENCES_HEADER_RE = re.compile(
    r"^(references?|bibliography|works\s*cited|참고\s*문헌|인용\s*문헌|참고\s*자료)\b",
    re.IGNORECASE,
)


def _is_references_header(header_label: str) -> bool:
    cleaned = header_label.strip().strip("*").strip()  # 마크다운 볼드(**REFERENCES**) 제거
    return bool(_REFERENCES_HEADER_RE.match(cleaned))


# Abstract 헤더 판별 — register_paper()가 arxiv abstract가 없을 때 PDF에서 뽑을
# 대체 출처로 쓴다. 한국어 "초록"도 잡는다.
_ABSTRACT_HEADER_RE = re.compile(r"^(abstract|초록)\b", re.IGNORECASE)


def _is_abstract_header(header_label: str) -> bool:
    cleaned = header_label.strip().strip("*").strip()
    return bool(_ABSTRACT_HEADER_RE.match(cleaned))


def _split_oversized_section(text: str, max_chars: int) -> list[str]:
    """섹션이 max_chars를 넘을 때 줄(`\\n`) 단위로 쪼갠다 — 이 시점엔 이미 빈 줄
    구분이 없어(모듈 docstring 참고) 줄이 가장 작은 분할 단위다. 문장 단위 폴백은
    범위 밖(안 잘리면 그대로 반환)."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return lines if lines else [text]


def split_into_chunks(
    markdown: str, max_chars: int = 4000, overlap_chars: int = 300
) -> list[dict]:
    """마크다운을 max_chars 이하 청크로 나눈다(헤더 분할+병합 → 초과 섹션은 줄 단위
    분할, 모듈 docstring 참고). 청크 경계마다 overlap_chars만큼 겹쳐 붙여 문장이
    뚝 끊긴 채로 안 넘어가게 한다. max_chars는 호출자가 실제 모델 예산에 맞춰
    넘기고, 잔여 극단 케이스는 models.check_context_budget()이 최종 안전망.

    반환: [{"index", "headers", "text", "is_references"}, ...]. index는 호출자가
    paper_id와 합쳐 chunk id를 만드는 데 씀. 헤더 텍스트는 안 지운다(strip_headers=
    False) — LLM이 섹션 맥락을 보게, 다만 라벨 신뢰도는 낮다(모듈 docstring 참고).
    """
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False
    )
    docs = splitter.split_text(markdown)

    # 1단계 산출물을 "합칠 수 있는 조각"으로 펼친다 — 초과 섹션은 2단계로 더 쪼개서,
    # 아래 병합 루프가 출처(헤더/줄)를 구분할 필요 없이 동일하게 취급하게 한다.
    pieces: list[tuple[str, str, bool]] = []  # (header_label, text, is_references)
    for doc in docs:
        header_values = list(doc.metadata.values())
        header_label = header_values[-1] if header_values else ""
        is_ref = any(_is_references_header(v) for v in header_values)  # 계층 전체로 판정(모듈 docstring)

        if len(doc.page_content) > max_chars:
            for line in _split_oversized_section(doc.page_content, max_chars):
                pieces.append((header_label, line, is_ref))
        else:
            pieces.append((header_label, doc.page_content, is_ref))

    # 2단계: 문서 순서대로 병합 — max_chars 넘기 전까지 이어붙이고, 넘치면 flush.
    merged: list[dict] = []
    current_texts: list[str] = []
    current_headers: list[str] = []
    current_is_ref = False
    current_len = 0

    for header_label, text, piece_is_ref in pieces:
        piece_len = len(text)
        # References 경계는 max_chars 여유와 무관하게 강제 flush(모듈 docstring 참고) —
        # current_is_ref는 라벨을 재판정하지 않고 piece_is_ref를 OR로 누적한다.
        crosses_reference_boundary = bool(current_headers) and piece_is_ref != current_is_ref

        if current_texts and (current_len + piece_len > max_chars or crosses_reference_boundary):
            flushed_text = "\n\n".join(current_texts)
            merged.append({
                "index": len(merged),
                "headers": current_headers,
                "text": flushed_text,
                "is_references": current_is_ref,
            })

            # References 경계를 넘는 flush는 overlap을 안 붙인다(성격이 다른 섹션 경계).
            tail = flushed_text[-overlap_chars:] if (overlap_chars and not crosses_reference_boundary) else ""
            current_texts, current_headers, current_len = [], [], 0
            current_is_ref = False
            if tail:
                overlap_text = f"(...이전 내용에서 이어짐) {tail}"
                current_texts.append(overlap_text)
                current_len += len(overlap_text)

        current_texts.append(text)
        if not current_headers or current_headers[-1] != header_label:  # 줄 분할로 반복되는 라벨 중복 방지
            current_headers.append(header_label)
        current_is_ref = current_is_ref or piece_is_ref
        current_len += piece_len

    if current_texts:
        merged.append({
            "index": len(merged),
            "headers": current_headers,
            "text": "\n\n".join(current_texts),
            "is_references": current_is_ref,
        })

    return merged


def split_for_embedding(
    markdown: str, chunk_size: int = 500, chunk_overlap: int = 50
) -> list[dict]:
    """임베딩·검색(fulltext_chunk)용 청킹 — split_into_chunks()과는 목적이 다르다
    (모듈 docstring "split_for_embedding" 항목 참고). ingest.py와 같은 결로 헤더 섹션
    안에서 다시 잘게(chunk_size/chunk_overlap) 쪼갠다 — 섹션 경계에 청크 크기를
    맞추지 않고, 대신 각 조각에 헤더 라벨과 References/Abstract 소속 여부만 메타데이터로
    물려준다.

    반환: [{"index": int, "text": str, "header": str, "is_references": bool,
            "is_abstract": bool}, ...]
    index는 이 리스트 안에서의 순서 — register_paper()가 paper_id와 합쳐 chunk id
    (f"{paper_id}-{index}")를 만드는 데 쓴다.

    주의(문서화만, 코드로 막지 않음): chunk_overlap 때문에 인접 조각끼리 경계의 일부
    텍스트가 중복된다. 검색(유사도 매칭)에는 무해하지만, 이 조각들을 나중에 다시
    이어붙여 "전문"을 재구성할 때(예: paper_ingest.py의 lazy 요약 생성이 저장된
    fulltext_chunk를 모아 LLM에 넣을 때) 그 중복이 그대로 섞여 들어간다 — 원본
    그대로의 정확한 재구성이 아니라 "약간의 반복이 섞인 근사 재구성"이다. LLM
    구조화 추출 입력으로는 사소한 노이즈라 지금은 그대로 둔다(단순 경로부터).
    """
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False
    )
    docs = splitter.split_text(markdown)

    fine_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    pieces: list[dict] = []
    for doc in docs:
        header_values = list(doc.metadata.values())
        header_label = header_values[-1] if header_values else ""
        # is_references/is_abstract 둘 다 라벨이 아니라 계층 전체로 판정(모듈 docstring 참고)
        is_ref = any(_is_references_header(v) for v in header_values)
        is_abs = any(_is_abstract_header(v) for v in header_values)

        for text in fine_splitter.split_text(doc.page_content):
            pieces.append({
                "index": len(pieces),
                "text": text,
                "header": header_label,
                "is_references": is_ref,
                "is_abstract": is_abs,
            })

    return pieces


def extract_abstract(pieces: list[dict]) -> str | None:
    """split_for_embedding()이 만든 조각들 중 Abstract 섹션 소속(is_abstract)만 index
    순으로 이어붙여 반환한다 — register_paper()가 arxiv abstract가 없을 때 대체로 쓴다.
    소속 판정은 이 함수가 아니라 split_for_embedding()에서 헤더 계층 전체로 이미
    끝냈다(모듈 docstring 참고). 조각이 하나도 없으면 None."""
    abstract_pieces = sorted(
        (p for p in pieces if p["is_abstract"]),
        key=lambda p: p["index"],
    )
    if not abstract_pieces:
        return None
    return "\n\n".join(p["text"] for p in abstract_pieces)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: uv run paper/paper_chunking.py <.parsed.md 경로> [max_chars] [overlap_chars]")
        sys.exit(1)

    max_chars = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    overlap_chars = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    text = open(sys.argv[1], encoding="utf-8").read()
    chunks = split_into_chunks(text, max_chars=max_chars, overlap_chars=overlap_chars)

    print(f"청크 수: {len(chunks)} (max_chars={max_chars}, overlap_chars={overlap_chars})")
    for c in chunks:
        ref_tag = " [REFERENCES]" if c["is_references"] else ""
        print(f"[{c['index']}]{ref_tag} 헤더: {c['headers']} / 길이: {len(c['text'])}자")
        if c["index"] > 0:
            print(f"    (앞부분 미리보기: {c['text'][:80]!r})")
