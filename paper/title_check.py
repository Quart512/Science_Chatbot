# =========================================================
# 제목 검증(07-29, 6-3b③) — register_paper()에 넘어온 서지정보의 제목(주로 arxiv API가
# 준 값)과 PDF 자체에서 뽑은 제목(pdf_parse.py의 pdf_title)을 대조해 등급을 매긴다.
# RoadMap "제목 검증 — 막지 말고 경고, 단 등급을 나눈다" 설계 노트 참고.
#
# 막지 않는다 — 이 모듈은 등록을 거부할지 말지 판단하지 않는다. register_paper()는
# 이 판정과 무관하게 항상 등록을 진행하고, 판정 결과만 반환값에 실어 보낸다. 실제로
# "빨간 경고를 띄울지"는 이 판정을 소비하는 쪽(프론트)의 몫이다.
#
# 등급을 둘로 나누는 이유(제목 검증 설계 노트 참고): 불일치는 성격이 다른 두 사고를
# 가리킨다 — "표기 차이"(줄바꿈·부제·LaTeX 기호 등, 무해)와 "아예 다른 논문"(arxiv id
# 오입력 등, paper_id 자체가 잘못됐을 위험). 하나의 "불일치" 신호로 뭉뚱그리면 프론트가
# 둘을 구분해서 다른 안내("제목 하나 골라주세요" vs "arxiv id가 맞나요?")를 할 수 없다.
#
# "PDF 제목 추출 실패"는 불일치가 아니다: 헤딩 인식이 폰트 크기 휴리스틱이라(파일
# 메타데이터도 비어 있을 수 있음) 제목을 아예 못 뽑을 수 있다. 이때 "불일치"로 처리하면
# 거짓 경보가 쌓여 사용자가 경고 자체를 무시하게 된다 — no_comparison으로 조용히 넘어간다.
# =========================================================

import re
from difflib import SequenceMatcher
from typing import Literal

# 유사도 임계값 — CONTEXT_BUDGET_CHARS(models.py)와 같은 처지: 실측 전 대략치다.
# 실제 논문 제목 쌍으로 오탐·누락을 관찰하면 조정할 것(값을 여기 한 곳에 모아둔 이유도 같음).
MATCH_THRESHOLD = 0.9        # 이 이상이면 사실상 같은 제목(표기 차이도 거의 없음)
DIFFERENT_PAPER_THRESHOLD = 0.5  # 이 미만이면 아예 다른 논문일 가능성


def normalize_title(title: str) -> str:
    """대소문자·공백·구두점 차이를 흡수해 비교하기 좋은 형태로 만든다. 소문자화하고
    영문자·숫자·공백만 남긴 뒤(LaTeX 기호 `$\\alpha$`, 콜론·하이픈 등은 제거) 연속
    공백을 하나로 줄인다 — 의미를 해석하지 않는 순수 문자열 정규화다."""
    lowered = title.lower()
    kept = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", kept).strip()


def classify_title_match(
    given_title: str | None, pdf_title: str | None
) -> Literal["match", "notation_diff", "different_paper", "no_comparison"]:
    """given_title(주로 arxiv 서지정보의 title)과 pdf_title(pdf_parse.py가 뽑은 후보)을
    비교해 등급을 반환한다. 둘 중 하나라도 없으면(대조 자체가 불가능하면) "no_comparison"
    — 이건 "불일치"가 아니라 "판단 근거 부족"이라 프론트가 경고를 띄우면 안 된다.

    "match"/"notation_diff" 경계와 "notation_diff"/"different_paper" 경계는
    MATCH_THRESHOLD/DIFFERENT_PAPER_THRESHOLD(둘 다 실측 전 대략치)로 나눈다.
    """
    if not given_title or not pdf_title:
        return "no_comparison"

    ratio = SequenceMatcher(None, normalize_title(given_title), normalize_title(pdf_title)).ratio()
    if ratio >= MATCH_THRESHOLD:
        return "match"
    if ratio >= DIFFERENT_PAPER_THRESHOLD:
        return "notation_diff"
    return "different_paper"
