"""
split_into_chunks — paper_chunking.py의 순수 함수. LLM·PDF 파싱 없이 마크다운
문자열만 가지고 도는 톨게이트 테스트. 검증 대상: index 순서, 짧은 섹션 병합,
오버랩 삽입, 섹션 하나가 max_chars를 넘을 때의 줄 단위 분할 폴백(원래 문단
단위로 계획했다가 MarkdownHeaderTextSplitter가 빈 줄 구분을 안 지켜서 줄
단위로 바꾼 이유는 paper_chunking.py 모듈 docstring 참고), 줄마저 너무 큰
극단적 경우의 최종 처리.
"""
from paper.paper_chunking import (
    _is_abstract_header,
    _is_references_header,
    extract_abstract,
    split_for_embedding,
    split_into_chunks,
)

SAMPLE_MD = """# Title

Intro paragraph before any subsection.

## Author Name

## A. First Section

""" + ("첫 번째 섹션 내용. " * 20) + """

## B. Second Section

""" + ("두 번째 섹션 내용. " * 20) + """

## C. Third Section

""" + ("세 번째 섹션 내용. " * 20)

# B 섹션 하나가 그 자체로 max_chars(아래 테스트에서 300 사용)를 넘도록, 짧은
# 문단 여러 개로 구성된 큰 섹션 — 문단 분할 폴백이 이 안에서 자연스럽게
# 재조립되는지 확인하는 데 씀
OVERSIZED_SECTION_MD = "# Title\n\n## Huge Section\n\n" + "\n\n".join(
    f"문단 {i}번 내용입니다." * 3 for i in range(30)
)

# 문단 구분(빈 줄)이 아예 없는, 그 자체로 거대한 단일 덩어리 — 3단계(문장 분할)는
# 아직 없으므로 그대로 하나의 큰 청크로 남아야 하는 극단적 케이스
NO_PARAGRAPH_BREAK_MD = "# Title\n\n## One Giant Blob\n\n" + ("x" * 5000)


def test_index_is_sequential_from_zero():
    chunks = split_into_chunks(SAMPLE_MD, max_chars=4000, overlap_chars=100)
    assert [c["index"] for c in chunks] == list(range(len(chunks)))


def test_short_header_gets_merged_not_isolated():
    # "Author Name"처럼 내용이 거의 없는 헤더는 옆 섹션과 합쳐져야 한다 —
    # 독립된 청크로 살아남으면(즉 헤더 수만큼 청크가 나오면) 병합이 안 된 것
    chunks = split_into_chunks(SAMPLE_MD, max_chars=4000, overlap_chars=0)
    all_headers = [h for c in chunks for h in c["headers"]]
    assert "Author Name" in all_headers
    # 헤더는 5개(Title/Author Name/A/B/C)인데 병합 덕에 청크 수는 그보다 적어야 함
    assert len(chunks) < 5


def test_no_content_lost_across_chunks():
    chunks = split_into_chunks(SAMPLE_MD, max_chars=4000, overlap_chars=0)
    combined = "".join(c["text"] for c in chunks)
    assert "첫 번째 섹션 내용." in combined
    assert "두 번째 섹션 내용." in combined
    assert "세 번째 섹션 내용." in combined


def test_overlap_prefix_present_on_non_first_chunks():
    # max_chars를 작게 줘서 강제로 여러 청크가 나오게 함
    chunks = split_into_chunks(SAMPLE_MD, max_chars=200, overlap_chars=50)
    assert len(chunks) > 1
    for c in chunks[1:]:
        assert c["text"].startswith("(...이전 내용에서 이어짐)")
    assert not chunks[0]["text"].startswith("(...이전 내용에서 이어짐)")


def test_oversized_section_falls_back_to_line_split():
    # "Huge Section" 하나가 max_chars(300)보다 훨씬 큼 -> 줄 단위로 쪼개져
    # 여러 청크로 재조립돼야 한다. 줄 자체는 훨씬 작으므로(각 줄 30자 안팎)
    # 결과 청크들이 max_chars를 훌쩍 넘는 채로 남아있으면 안 됨(오버랩 몫만 허용)
    chunks = split_into_chunks(OVERSIZED_SECTION_MD, max_chars=300, overlap_chars=0)
    assert len(chunks) > 1
    assert all(len(c["text"]) <= 300 for c in chunks)
    # 내용도 안 없어졌는지 확인
    combined = "".join(c["text"] for c in chunks)
    assert "문단 0번 내용입니다." in combined
    assert "문단 29번 내용입니다." in combined


def test_line_itself_too_big_is_returned_as_is():
    # 빈 줄로 나눌 지점이 아예 없는 5000자짜리 덩어리 -> 문장 분할(3단계)은
    # 아직 없으므로, 이 함수는 그걸 그대로 하나의(예산 초과) 청크로 반환해야
    # 한다 — 여기서 죽거나 내용을 잘라버리면 안 됨. 이 잔여 케이스를 실제로
    # 막는 건 models.py의 check_context_budget()(호출 직전 안전망)의 몫.
    chunks = split_into_chunks(NO_PARAGRAPH_BREAK_MD, max_chars=300, overlap_chars=0)
    assert any(len(c["text"]) > 300 for c in chunks)
    combined = "".join(c["text"] for c in chunks)
    assert "x" * 5000 in combined


# --- References 헤더 판별 (07-28) ---------------------------------------


def test_is_references_header_matches_common_variants():
    # 영문(References/Bibliography/Works Cited, 붙여쓴 WorksCited 포함) + 마크다운
    # 볼드("**REFERENCES**", 실제 PDF 출력에서 관찰됨) + 한국어(참고문헌/인용문헌/
    # 참고자료, 07-29 추가 — 띄어쓰기 여부 둘 다) 전부 잡아야 한다
    assert _is_references_header("REFERENCES")
    assert _is_references_header("References")
    assert _is_references_header("**REFERENCES**")
    assert _is_references_header("Bibliography")
    assert _is_references_header("Works Cited")
    assert _is_references_header("WorksCited")
    assert _is_references_header("참고문헌")
    assert _is_references_header("참고 문헌")
    assert _is_references_header("인용문헌")
    assert _is_references_header("인용 문헌")
    assert _is_references_header("참고자료")
    assert _is_references_header("참고 자료")


def test_is_references_header_rejects_non_references():
    # 정상 섹션 오탐은 내용이 통째로 걸러지는 사고로 이어진다. 또한 헤더 텍스트가
    # "references"로 시작하지 않으면 오탐하지 않는다 — 문장 중간에 그 단어가
    # 섞인 경우까지 잡으면 오탐 위험이 커진다.
    assert not _is_references_header("I. 서론")
    assert not _is_references_header("A. First Section")
    assert not _is_references_header("See references section")
    assert not _is_references_header("참고문헌을 인용한 연구는")


# --- Abstract 헤더 판별 + 추출 (07-29, 6-3 후속 "abstract 확보") ---------


def test_is_abstract_header_matches_common_variants():
    assert _is_abstract_header("Abstract")
    assert _is_abstract_header("ABSTRACT")
    assert _is_abstract_header("**Abstract**")
    assert _is_abstract_header("초록")


def test_is_abstract_header_rejects_non_abstract():
    assert not _is_abstract_header("Introduction")
    # "초록" 뒤에 다른 글자가 바로 이어지면(예: "초록색") 별개 단어이므로 오탐하면 안 됨
    assert not _is_abstract_header("초록색 물질")


def test_extract_abstract_joins_pieces_in_index_order():
    # 헤더가 Abstract인 조각이 여러 개(500자 단위로 쪼개져) 있으면 index 순으로
    # 이어붙여야 한다 — 입력 순서가 뒤섞여 있어도 index 기준으로 정렬해야 함
    pieces = [
        {"index": 2, "text": "이어짐", "header": "Abstract"},
        {"index": 0, "text": "초록 시작", "header": "Abstract"},
        {"index": 1, "text": "본론", "header": "Introduction"},
    ]
    assert extract_abstract(pieces) == "초록 시작\n\n이어짐"


def test_extract_abstract_returns_none_when_no_abstract_header():
    pieces = [{"index": 0, "text": "x", "header": "Introduction"}]
    assert extract_abstract(pieces) is None


# --- split_into_chunks()의 is_references 필드 --------------------------

REFERENCES_MD = (
    SAMPLE_MD
    + "\n\n## References\n\n"
    + "[1] Some Author, Some Title, Some Journal, 2020.\n" * 20
)


def test_normal_chunks_are_not_flagged_as_references():
    chunks = split_into_chunks(SAMPLE_MD, max_chars=4000, overlap_chars=0)
    assert all(c["is_references"] is False for c in chunks)


def test_references_chunk_is_flagged_but_not_dropped():
    chunks = split_into_chunks(REFERENCES_MD, max_chars=4000, overlap_chars=0)
    ref_chunks = [c for c in chunks if c["is_references"]]
    assert ref_chunks, "References 헤더를 포함한 청크가 최소 하나는 있어야 함"
    # 버리지 않고 원문 그대로 남겨둬야 한다(모듈 docstring 참고)
    combined = "".join(c["text"] for c in ref_chunks)
    assert "Some Author, Some Title" in combined


# Conclusion과 References를 합쳐도 max_chars(4000)를 넉넉히 넘지 않을 만큼 짧게 만듦 —
# 병합 로직이 References 경계를 무시하면 이 둘이 같은 청크로 합쳐져버린다(07-28 버그 참고)
CONCLUSION_THEN_REFERENCES_MD = (
    "# Title\n\n## Conclusion\n\n짧은 결론 내용입니다.\n\n"
    "## References\n\n[1] Some Author, Some Title, Some Journal, 2020.\n"
)


def test_reference_boundary_forces_separate_chunk_without_overlap():
    # 병합이 max_chars만 보고 References 여부를 무시하면, Conclusion 내용이 References
    # 조각과 한 청크로 묶여 통째로 is_references=True가 돼버려서 진짜 본문(Conclusion)까지
    # 추출 LLM 입력에서 걸러지는 사고가 난다(07-28 버그) — 청크가 분리되는지, 그리고
    # 그 경계엔 오버랩도 안 붙는지(본문↔참고문헌은 "문장이 끊긴 경계"가 아니므로,
    # 붙이면 References 청크 안에 본문 조각이 다시 섞여 들어가 fix가 무의미해짐) 확인.
    chunks = split_into_chunks(CONCLUSION_THEN_REFERENCES_MD, max_chars=4000, overlap_chars=50)

    non_ref_chunks = [c for c in chunks if not c["is_references"]]
    ref_chunks = [c for c in chunks if c["is_references"]]

    assert any("짧은 결론 내용입니다" in c["text"] for c in non_ref_chunks)
    assert all("Some Author" not in c["text"] for c in non_ref_chunks)
    assert ref_chunks
    assert all("짧은 결론 내용입니다" not in c["text"] for c in ref_chunks)
    assert not ref_chunks[0]["text"].startswith("(...이전 내용에서 이어짐)")


# References(h1) 아래에 그 자체로는 References로 안 읽히는 하위섹션(h2)이 있는 경우 —
# 라벨(가장 깊은 헤더 하나, "Appendix A")만 보면 References 정규식에 안 걸리지만,
# 실제로는 References 섹션 소속이므로 is_references=True로 잡혀야 한다(07-28 버그)
REFERENCES_WITH_SUBSECTION_MD = (
    "# Title\n\n## Intro\n\n" + "본문 내용입니다. " * 30
    + "\n\n# References\n\n## Appendix A\n\n[1] Some Author, Some Title, Some Journal, 2020.\n"
)


def test_references_detected_even_under_non_matching_subsection_label():
    # header_label(표시용, 가장 깊은 헤더 하나)만 보고 판정했다면 "Appendix A"라 놓쳤을
    # 케이스 — is_references는 헤더 계층 전체(h1=References 포함)를 봐야 한다.
    chunks = split_into_chunks(REFERENCES_WITH_SUBSECTION_MD, max_chars=4000, overlap_chars=0)
    ref_chunks = [c for c in chunks if c["is_references"]]
    assert ref_chunks, "References(h1) 아래 하위섹션 청크도 is_references=True여야 함"
    combined = "".join(c["text"] for c in ref_chunks)
    assert "Some Author, Some Title" in combined


# --- split_for_embedding() — 임베딩·검색용 청킹 (split_into_chunks과 별개 함수) ------

def test_split_for_embedding_index_is_sequential_from_zero():
    pieces = split_for_embedding(SAMPLE_MD, chunk_size=500, chunk_overlap=50)
    assert [p["index"] for p in pieces] == list(range(len(pieces)))


def test_split_for_embedding_chunks_are_small():
    # split_into_chunks과 달리 여기는 조각이 작아야 한다(기본 500자 근방) —
    # 헤더 섹션 하나 전체가 통째로 나오면 잘게 쪼개는 목적 자체가 실패한 것
    pieces = split_for_embedding(SAMPLE_MD, chunk_size=500, chunk_overlap=50)
    assert len(pieces) > 3  # 최소한 섹션 수(5개 헤더)보다는 많이 쪼개져야 함(각 섹션이 500자보다 김)
    assert all(len(p["text"]) <= 600 for p in pieces)  # 약간의 여유(오버랩 등)만 허용


def test_split_for_embedding_no_content_lost():
    pieces = split_for_embedding(SAMPLE_MD, chunk_size=500, chunk_overlap=50)
    combined = "".join(p["text"] for p in pieces)
    assert "첫 번째 섹션 내용." in combined
    assert "두 번째 섹션 내용." in combined
    assert "세 번째 섹션 내용." in combined


def test_split_for_embedding_flags_references_pieces():
    pieces = split_for_embedding(REFERENCES_MD, chunk_size=500, chunk_overlap=50)
    ref_pieces = [p for p in pieces if p["is_references"]]
    non_ref_pieces = [p for p in pieces if not p["is_references"]]
    assert ref_pieces, "References 헤더 아래 조각이 최소 하나는 있어야 함"
    assert non_ref_pieces, "일반 섹션 조각도 그대로 있어야 함(버리지 않음)"
    combined_refs = "".join(p["text"] for p in ref_pieces)
    assert "Some Author, Some Title" in combined_refs


def test_split_for_embedding_detects_references_under_non_matching_subsection_label():
    # split_into_chunks()의 같은 버그(07-28)를 split_for_embedding()도 공유했다 —
    # 라벨(가장 깊은 헤더, "Appendix A")만 보면 놓치는 케이스를 헤더 계층 전체로 잡는지 확인.
    pieces = split_for_embedding(REFERENCES_WITH_SUBSECTION_MD, chunk_size=500, chunk_overlap=50)
    ref_pieces = [p for p in pieces if p["is_references"]]
    assert ref_pieces, "References(h1) 아래 하위섹션 조각도 is_references=True여야 함"
    combined = "".join(p["text"] for p in ref_pieces)
    assert "Some Author, Some Title" in combined
