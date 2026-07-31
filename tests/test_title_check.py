"""
title_check.py — 제목 검증(07-29, 6-3b③)의 순수 함수. LLM·네트워크·PDF 파싱 없이 문자열
비교 로직만 검증하는 톨게이트 테스트. 등급 경계 테스트는 실제 SequenceMatcher 비율을
직접 계산해서 그 값이 임계값 사이에 오는지부터 자기검증한 뒤 classify_title_match()의
분기를 확인한다 — 임계값(MATCH_THRESHOLD/DIFFERENT_PAPER_THRESHOLD)이 나중에 실측으로
조정돼도 테스트가 조용히 의미를 잃지 않게(전제 자체를 assert함).
"""
from difflib import SequenceMatcher

import paper.title_check as title_check
from paper.title_check import classify_title_match, normalize_title


def test_normalize_title_lowercases_and_collapses_whitespace():
    assert normalize_title("  Quantum   Entanglement  ") == "quantum entanglement"


def test_normalize_title_strips_punctuation_and_latex_symbols():
    # 문자·숫자·공백만 남긴다 — LaTeX 기호($, \, {, } 등)와 구두점은 제거되지만,
    # \alpha처럼 기호 사이에 낀 영문자(alpha)는 문자이므로 그대로 남는다
    assert normalize_title("Review: $\\alpha$-Decay (2023)!") == "review alpha decay 2023"


def test_classify_returns_no_comparison_when_given_title_missing():
    assert classify_title_match(None, "Some PDF Title") == "no_comparison"


def test_classify_returns_no_comparison_when_pdf_title_missing():
    assert classify_title_match("Some Title", None) == "no_comparison"


def test_classify_returns_no_comparison_when_both_missing():
    assert classify_title_match(None, None) == "no_comparison"


def test_classify_identical_after_normalization_is_match():
    # 대소문자·콜론·공백 차이만 있는 표기 차이 — 정규화 후 사실상 같은 문자열
    given = "Quantum Entanglement in Many-Body Systems: A Review"
    pdf = "quantum entanglement in manybody systems a review"
    assert classify_title_match(given, pdf) == "match"


def test_classify_completely_unrelated_titles_is_different_paper():
    given = "Quantum Entanglement in Many-Body Systems"
    pdf = "A Survey of Kubernetes Deployment Strategies"
    assert classify_title_match(given, pdf) == "different_paper"


def test_classify_moderately_similar_titles_is_notation_diff():
    # arxiv 제목은 짧고 PDF 쪽엔 부제가 더 붙은 경우 흉내 — 앞부분은 그대로고 뒤에만 덧붙음
    given = "Deep Learning Approaches for Quantum Chemistry Simulations"
    pdf = "Deep Learning Approaches for Quantum Chemistry Simulations and Applications"

    # 전제 확인 — 이 예시가 실제로 두 임계값 사이에 오는지 자기검증(위 모듈 docstring 참고)
    ratio = SequenceMatcher(None, normalize_title(given), normalize_title(pdf)).ratio()
    assert title_check.DIFFERENT_PAPER_THRESHOLD < ratio < title_check.MATCH_THRESHOLD

    assert classify_title_match(given, pdf) == "notation_diff"
