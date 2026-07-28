# =========================================================
# 논문 마크다운(pdf_parse.py의 출력)을 max_chars(호출하는 쪽이 모델 컨텍스트 예산에
# 맞춰 정함, 예: models.py의 CONTEXT_BUDGET_CHARS[model])를 넘지 않는 청크들로
# 나눈다. 2단계 폴백으로 동작한다:
#
#   1단계 — 헤더 기준 분할 + 병합: 헤더(#/##/###)로 먼저 나누고, 문서 순서를
#     유지하면서 max_chars를 넘기 전까지 인접 섹션들을 하나의 청크로 합친다.
#     이 병합이 필요한 이유(실제로 관찰됨): pymupdf4llm의 헤더 인식은 폰트 크기
#     휴리스틱이라 저자명처럼 볼드체인 줄을 헤더로 오탐지하는 경우가 있다(실제
#     사례: "## Jaebong Lee"가 헤더로 잡힘). 헤더 하나 나올 때마다 새 청크를
#     만들지 않고 계속 합쳐버리면, 오탐지 헤더는 내용이 짧으니 옆 섹션에
#     자연스럽게 흡수된다.
#
#   2단계 — 섹션 하나가 그 자체로 max_chars를 넘으면 더 작은 단위로 쪼갠 뒤
#     그 조각들을 1단계와 같은 방식으로 다시 채워나간다(07-28, 실제로 걸리는
#     사례를 확인한 뒤 추가 — 논문 "거대 언어 모델의 멀티모달 입력..."의
#     "2. 주요 문항별 풀이" 섹션이 11369자로 Qwen-tuned 예산 6000자를 넘김).
#     헤더 조각과 이 조각들은 병합 루프 입장에서 완전히 동일하게 취급된다.
#     **애초 계획은 "문단(빈 줄) 단위"였는데, 실제로 테스트해보니 틀렸다** —
#     MarkdownHeaderTextSplitter는 섹션 내부 텍스트를 재조립할 때 원본의 빈 줄
#     구분을 보존하지 않고 "  \n"(마크다운 하드 라인브레이크)로 모든 줄을
#     이어붙인다. 그래서 이 시점엔 "\n\n"이 doc.page_content 안에 이미 없고,
#     "\n\n" 기준으로 나누면 아예 안 나뉜 채 통째로 하나의(예산 초과) 청크가
#     되는 버그가 실제로 났다(테스트 실패로 발견). 그래서 줄(`\n`) 단위로 나눈다
#     — "문단"과 "줄"의 구분은 이 시점엔 이미 사라진 뒤라, 줄이 우리가 실제로
#     쪼갤 수 있는 가장 작은 단위다.
#
#   그래도 안 되면(줄 하나가 그 자체로 max_chars를 넘는 극단적인 경우) 그
#     줄을 그대로 하나의 청크로 반환한다 — 문장 단위 폴백은 아직 범위 밖
#     (실제로 이 경우를 만나면 그때 추가). 이 마지막 잔여 위험은 models.py의
#     check_context_budget()이 호출 직전 최종 안전망으로 잡는다 — "조용히
#     자르지 말고 정직하게 실패"는 이 최후의 경우를 위한 것이지, 평소 경로가
#     아니다.
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
#
# from_section 대신 from_chunk (07-28, 이어지는 논의): 구조화 추출(paper_extraction.py)
# 결과가 "어느 섹션에서 나왔는지"를 헤더 라벨로 정확히 못 박으려 하지 않는다 —
# 한 청크가 여러 헤더를 묶고 있을 수 있어 애초에 불가능하다. 대신 RAG의 출처
# 표기와 같은 방식으로 간다: 각 청크에 안정적인 id(paper_id + 이 함수가 매기는
# index로 호출하는 쪽이 조립 — 예: f"{paper_id}-section-{index}")를 붙여두고,
# 나중에 어떤 주장을 검증해야 할 때(⑦) 그 id로 원본 청크 전체를 그대로 다시
# 가져와 사람 또는 LLM이 읽게 한다. 정확한 섹션명을 추론해서 알려주는 대신
# "원문 통째로 찾아볼 수 있는 위치"만 보장하는 쪽이 더 정직하고 구현도 쉽다.
#
# 범위 밖(단순 경로부터 — 실제로 걸리는 걸 확인한 뒤에 추가):
#   - 헤더가 하나도 안 잡히는 논문(전체가 한 덩어리) — 정규식 섹션명 탐지 폴백이
#     필요하지만, 아직 그런 논문을 실제로 만나지 않아 미구현. 지금 이 함수는
#     그런 문서를 받으면 "헤더 1개(사실상 전체)"로 취급하고 2단계(문단 분할)로
#     넘어간다 — 완전히 망가지진 않지만 아직 검증은 안 됨
#   - 줄 하나가 그 자체로 max_chars를 넘는 경우(3단계, 문장 분할) — 위 참고
#
# split_for_embedding (07-28, paper_ingest.py 파이프라인 작업 중 추가): split_into_sections와
# 목적이 다른 별도 함수다 — 헷갈리지 말 것.
#   - split_into_sections: 구조화 추출(paper_extraction.py) LLM 호출 입력용. max_chars가
#     모델 컨텍스트 예산에 맞춰 크고(수천~수만자), 헤더를 넘나들며 병합한다.
#   - split_for_embedding: 임베딩·검색(fulltext_chunk)용. RoadMap "전문 처리" 설계 노트대로
#     ingest.py와 같은 결(500자/오버랩 50, RecursiveCharacterTextSplitter)로 잘게 쪼갠다 —
#     검색은 정밀도가 목적이라 섹션 경계에 맞춰 크게 자를 이유가 없다. 대신 각 조각이
#     어느 헤더 아래에 있었는지(header)와 References 여부(is_references)는 그대로 물려받는다.
#   헤더 하나의 본문 안에서만 잘게 쪼개므로(헤더를 넘나드는 병합 없음) 조각 하나에는
#   header가 항상 하나(또는 없음)다 — split_into_sections의 headers(list)와 달리 여기선
#   header(단수, str)로 이름 붙인 이유.
#
# References 청크 표시(07-28): 청크에 "is_references" 플래그를 붙인다 — 헤더가
# References/Bibliography/참고문헌 계열이면 True. **버리지 않는다** — 원문은
# 나중 서지 추출용으로 그대로 남겨두되(To Do "원문은 나중 서지 추출용으로 보관"),
# 호출하는 쪽(구조화 추출 LLM 입력 조립·임베딩 청크 생성)이 이 플래그로 걸러내게
# 한다. 인용 문자열 덩어리를 그대로 넘기면 (1) 임베딩 검색에 노이즈가 되고
# (2) 추출 LLM이 인용된 다른 논문의 제목을 이 논문의 주장으로 착각할 위험이
# 있다 — 그렇다고 여기서 개별 인용을 authors/title/year로 파싱하지는 않는다.
# 저널마다 인용 포맷이 달라 정규식 하나로 일반화하기 어려운 문제라(GROBID 같은
# 전용 도구가 따로 있는 이유 — RoadMap "PDF 파싱 라이브러리 선택" 참고), 지금
# 소비처(⑦ 논문 작성의 인용 목록)가 없는 상태에서 미리 만들어봤자 검증할 방법도
# 없다(품질 평가를 소비처 생길 때까지 미룬 것과 같은 논리).
#
# References 경계는 병합 max_chars와 별개로 강제 flush (07-28, 실사용 중 발견):
# is_references는 청크 단위로 any(headers)로 매겨지는데, 처음엔 병합 루프가 References
# 여부를 전혀 신경 안 쓰고 진행됐다 — 그러면 References 조각이 옆의 진짜 본문(예:
# Conclusion 끝부분)과 우연히 같은 청크로 묶이는 경우, 그 청크 전체가 is_references=True로
# 뭉뚱그려져서 진짜 본문까지 추출 LLM 입력에서 통째로 걸러지는 사고가 날 수 있었다(호출부는
# is_references 플래그만 보고 거르지, 청크 안에 뭐가 실제로 섞였는지 다시 안 들여다보므로).
# 그래서 References 안팎을 넘나드는 지점은 max_chars 여유가 남았어도 무조건 flush해 청크
# 경계로 강제한다 — 이러면 References 청크는 항상 순수하게 References만 담는다(본문 조각이
# 섞여 들어올 일이 없음). 이 강제 flush에는 overlap도 안 붙인다 — 본문↔참고문헌은 "문장이
# 뚝 끊긴 경계"가 아니라 "성격이 다른 섹션의 경계"라 이어붙일 이유가 없다.
# =========================================================

import re

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]

# References 헤더 판별 — 영문 논문(References/Bibliography/Works Cited)과
# 한국어 논문(참고문헌) 둘 다 커버. 대소문자 무시, 단어 중간이 아니라 헤더
# 텍스트 자체가 이 단어들로 시작/구성되는지만 본다(예: "References [1-34]" 같은
# 변형도 잡되, 본문 중 우연히 "참고문헌을 인용한 연구는..."처럼 문장 속에
# 섞인 경우까지 오탐하지 않도록 — 어차피 헤더 라벨에만 적용하므로 위험 낮음).
_REFERENCES_HEADER_RE = re.compile(
    r"^(references?|bibliography|works\s+cited|참고\s*문헌)\b", re.IGNORECASE
)


def _is_references_header(header_label: str) -> bool:
    # 헤더 라벨엔 "**REFERENCES**"처럼 마크다운 볼드 기호가 섞여 있을 수 있어
    # 앞뒤 '*'와 공백을 벗겨내고 판별한다.
    cleaned = header_label.strip().strip("*").strip()
    return bool(_REFERENCES_HEADER_RE.match(cleaned))


def _split_oversized_section(text: str, max_chars: int) -> list[str]:
    """섹션 하나가 max_chars를 넘을 때 줄(`\\n`) 단위로 쪼갠다.

    원래는 문단(빈 줄 `\\n\\n`) 단위로 나눌 계획이었지만, 실제로 테스트해보니
    틀렸다 — MarkdownHeaderTextSplitter가 섹션 내부 텍스트를 재조립할 때 원본의
    빈 줄 구분을 보존하지 않고 "  \\n"(마크다운 하드 라인브레이크)로 모든 줄을
    이어붙인다. 그래서 이 함수에 들어오는 시점엔 "\\n\\n"이 이미 없고, 그
    기준으로 나누면 아예 안 나뉜 채 통째로 반환돼버린다(테스트 실패로 실제
    발견, 07-28). 지금은 "\\n" 기준으로 나눈다 — "문단"과 "줄"의 구분은 이
    시점엔 이미 사라진 뒤라, 줄이 실제로 쪼갤 수 있는 가장 작은 단위다.

    줄이 하나도 안 잡히거나(개행이 아예 없는 텍스트) 줄 하나가 그 자체로도
    max_chars를 넘으면, 더 잘게 쪼개지 않고 그대로 돌려준다 — 문장 단위 폴백은
    아직 범위 밖(모듈 docstring "범위 밖" 참고).
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return lines if lines else [text]


def split_into_sections(
    markdown: str, max_chars: int = 4000, overlap_chars: int = 300
) -> list[dict]:
    """마크다운을 max_chars를 넘지 않는 청크들로 나눈다 (헤더 분할+병합 →
    섹션이 너무 크면 줄 단위 분할, 모듈 docstring의 2단계 폴백 참고). 청크
    경계마다 이전 청크 꼬리의 overlap_chars만큼을 다음 청크 앞에 겹쳐 붙여,
    경계에서 문장이 뚝 끊긴 채로 LLM에 넘어가지 않게 한다(ingest.py의
    chunk_overlap=50과 같은 이유 — 다만 여기는 섹션 단위라 오버랩 크기가 훨씬 큼).

    max_chars는 호출하는 쪽이 실제로 쓸 모델의 컨텍스트 예산에 맞춰 넘기는 게
    맞다(예: models.py의 CONTEXT_BUDGET_CHARS[model]) — 그래야 애초에 예산을
    넘는 청크가 나올 일이 거의 없다. 그래도 못 피하는 극단적 잔여 케이스(줄
    하나가 그 자체로도 예산을 넘는 경우)를 위해 models.py의
    check_context_budget()을 호출 직전 최종 안전망으로 같이 쓸 것.

    반환: [{"index": int, "headers": [...], "text": str, "is_references": bool}, ...]
    index는 이 리스트 안에서의 순서(0부터) — 호출하는 쪽이 paper_id와 합쳐
    안정적인 chunk id(f"{paper_id}-section-{index}")를 만드는 데 쓴다. 이 함수
    자체는 paper_id를 모르므로(등록 파이프라인에서만 알 수 있음) index만 낸다.
    is_references는 이 청크의 headers 중 하나라도 References/Bibliography/
    참고문헌 계열이면 True — 이 청크를 버리지는 않는다(원문 그대로 반환), 다만
    호출하는 쪽이 구조화 추출·임베딩 입력을 조립할 때 걸러내는 데 쓴다(모듈
    docstring "References 청크 표시" 참고).

    헤더 텍스트는 본문에서 지우지 않는다(strip_headers=False) — "## I. 서론" 같은
    표시가 그대로 남아 있는 편이, 나중에 이 텍스트를 읽는 LLM이 지금 어느 섹션을
    보고 있는지 알 수 있어 유리하다. 단, 헤더 라벨 자체의 신뢰도는 위 모듈
    docstring 참고 — 완벽하지 않다는 전제로 다뤄야 한다. 정밀한 출처 추적은
    헤더 라벨이 아니라 index 기반 chunk id로 한다(from_chunk, 위 참고).
    """
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False
    )
    docs = splitter.split_text(markdown)

    # 1단계 산출물(헤더 섹션)을 "합칠 수 있는 조각들"로 펼친다. 섹션이 max_chars
    # 보다 크면 2단계(줄 단위 분할)로 더 쪼개 여러 조각을 낸다 — 이러면 아래 병합
    # 루프가 "헤더에서 곧장 온 조각"과 "줄로 더 쪼개진 조각"을 구분할 필요
    # 없이 완전히 동일하게 취급할 수 있다.
    pieces: list[tuple[str, str]] = []  # (header_label, text)
    for doc in docs:
        # metadata는 {"h1": "...", "h2": "...", ...} 형태 — 이 섹션이 속한 가장
        # 깊은(마지막) 헤더 하나만 대표로 기록한다.
        header_values = list(doc.metadata.values())
        header_label = header_values[-1] if header_values else ""

        if len(doc.page_content) > max_chars:
            for line in _split_oversized_section(doc.page_content, max_chars):
                pieces.append((header_label, line))
        else:
            pieces.append((header_label, doc.page_content))

    # 2단계: 조각을 문서 순서대로 병합 — max_chars 넘기 전까지 계속 이어붙이고,
    # 넘치면 flush 후 오버랩을 남기고 새 청크를 시작한다.
    merged: list[dict] = []
    current_texts: list[str] = []
    current_headers: list[str] = []
    current_len = 0

    for header_label, text in pieces:
        piece_len = len(text)
        piece_is_ref = _is_references_header(header_label)
        current_is_ref = any(_is_references_header(h) for h in current_headers)
        # is_references는 청크 단위로 any(...)로 매겨지는데, 병합이 References 여부를
        # 신경 안 쓰고 진행되면 References 조각 하나가 옆의 진짜 본문(예: Conclusion
        # 끝부분)과 같은 청크로 묶여버려 그 청크 전체가 is_references=True로 잘못
        # 태깅된다 — 그러면 추출 LLM 입력에서 진짜 본문까지 통째로 걸러지는 사고가
        # 난다(호출부는 is_references만 보고 거르지, 청크 안에 뭐가 섞였는지 다시
        # 안 들여다봄). 그래서 References 안팎을 넘나드는 지점은 max_chars와 무관하게
        # 무조건 flush해 경계를 강제한다.
        crosses_reference_boundary = bool(current_headers) and piece_is_ref != current_is_ref

        # 지금까지 모아둔 게 있는데 이 조각까지 더하면 넘치거나, References 경계를
        # 막 넘으려는 참이면 -> 먼저 flush
        if current_texts and (current_len + piece_len > max_chars or crosses_reference_boundary):
            flushed_text = "\n\n".join(current_texts)
            merged.append({
                "index": len(merged),
                "headers": current_headers,
                "text": flushed_text,
                "is_references": current_is_ref,
            })

            # 방금 청크의 꼬리를 다음 청크 시작에 오버랩으로 이어붙임 — 단, References
            # 경계를 넘는 flush는 예외: 본문↔참고문헌은 "문장이 뚝 끊긴 경계"가 아니라
            # "성격이 다른 섹션의 경계"라 이어붙일 이유가 없고, 붙이면 References로
            # 태깅된 청크 안에 본문 조각이 다시 섞여 들어가 이 fix의 의미가 없어진다.
            tail = flushed_text[-overlap_chars:] if (overlap_chars and not crosses_reference_boundary) else ""
            current_texts, current_headers, current_len = [], [], 0
            if tail:
                overlap_text = f"(...이전 내용에서 이어짐) {tail}"
                current_texts.append(overlap_text)
                current_len += len(overlap_text)

        current_texts.append(text)
        # 줄 단위 분할로 조각이 여러 개 생기면 같은 header_label이 연달아 반복되므로,
        # 직전과 같으면 다시 안 넣는다(리스트가 "A","A","A",...로 도배되는 걸 방지)
        if not current_headers or current_headers[-1] != header_label:
            current_headers.append(header_label)
        current_len += piece_len

    if current_texts:
        merged.append({
            "index": len(merged),
            "headers": current_headers,
            "text": "\n\n".join(current_texts),
            "is_references": any(_is_references_header(h) for h in current_headers),
        })

    return merged


def split_for_embedding(
    markdown: str, chunk_size: int = 500, chunk_overlap: int = 50
) -> list[dict]:
    """임베딩·검색(fulltext_chunk)용 청킹 — split_into_sections()과는 목적이 다르다
    (모듈 docstring "split_for_embedding" 항목 참고). ingest.py와 같은 결로 헤더 섹션
    안에서 다시 잘게(chunk_size/chunk_overlap) 쪼갠다 — 섹션 경계에 청크 크기를
    맞추지 않고, 대신 각 조각에 헤더 라벨과 References 여부만 메타데이터로 물려준다.

    반환: [{"index": int, "text": str, "header": str, "is_references": bool}, ...]
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
        is_ref = _is_references_header(header_label)

        for text in fine_splitter.split_text(doc.page_content):
            pieces.append({
                "index": len(pieces),
                "text": text,
                "header": header_label,
                "is_references": is_ref,
            })

    return pieces


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
    for c in chunks:
        ref_tag = " [REFERENCES]" if c["is_references"] else ""
        print(f"[{c['index']}]{ref_tag} 헤더: {c['headers']} / 길이: {len(c['text'])}자")
        if c["index"] > 0:
            print(f"    (앞부분 미리보기: {c['text'][:80]!r})")
