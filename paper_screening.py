# =========================================================
# 논문 스크리닝(②b) — abstract만 보고 관심사와의 관련도를 판정한다(유일한 LLM 판단).
# peer-review 여부·인용수·출판 연도는 계산/전달로만 얻고 관련도와 하나의 점수로 합치지
# 않는다(RoadMap "스크리닝 축을 합치지 않는다" 설계 노트) — 성격이 다른 축을 억지로
# 합치면 가중치가 임의적이고 정보가 사라진다. 관련도로 1차 필터만 하고 나머지는 나란히
# 반환해 호출하는 쪽(③ 추천 검색)이 정렬 기준을 고르게 한다.
#
# 전문을 읽지 않는다 — 유료 저널은 애초에 못 읽고, abstract만으로 충분히 빠르고 싸게
# 스크리닝해야 대량 후보를 다룰 수 있다(RoadMap "논문 처리 3분할" 참고).
#
# 후보 하나씩 스크리닝한다(배치 아님) — 여러 후보를 한 번에 프롬프트에 넣어 판정 리스트를
# 받는 방식도 고려했지만, 입력 개수와 출력 리스트 길이가 안 맞거나 순서가 섞이는 위험이
# 있고(LLM이 항목 하나를 빠뜨리면 어느 후보인지 되짚기 번거로움), 후보당 판정은 짧은 호출
# 하나라 단순한 쪽을 택했다(단순 경로부터). 대량 후보에서 호출 수가 문제가 되면 그때 배치로
# 전환.
#
# 모델 고정: BACKGROUND_SUMMARY_MODEL(paper_ingest.py)과 같은 논리 — 스크리닝은 사용자가
# 그 순간 고른 모델이 아니라 예산이 가장 넉넉한 고정 모델로 돌아야 대량 후보를 안정적으로
# 처리한다.
# =========================================================

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models import invoke_with_fallback

SCREENING_MODEL = "gemini"

RELEVANCE_SYSTEM_PROMPT = """논문 초록과 사용자의 관심사를 비교해서 이 논문이 관심사와
관련 있는지 판정해라. 관심사의 "찾는 것"에 초점을 맞추고, "이미 아는 것"이나 "제외할
주제"에만 해당한다면 관련 없음으로 판정해라. 애매하면 관련 있음 쪽으로 — 관련도는
1차 필터일 뿐이고 최종 판단은 사용자가 한다."""


class RelevanceScreen(BaseModel):
    is_relevant: bool = Field(description="초록이 관심사와 관련 있으면 True")
    reasoning: str = Field(default="", description="짧은 판단 근거(한 문장)")


def screen_candidate(candidate: dict, interest: dict, *, model: str = SCREENING_MODEL) -> dict:
    """후보 논문 하나를 관심사 기준으로 스크리닝한다.

    candidate: paper_search.search_papers()가 주는 형태(abstract/journal_ref/year/
    citation_count 포함, 혹은 같은 키를 가진 아무 dict).
    interest: interests.py의 관심사 레코드(title/looking_for/already_known/excluded_topics).

    반환: {"paper_id", "is_relevant", "reasoning", "peer_reviewed", "citation_count",
    "year", "tokens_used"} — 관련도(유일한 LLM 판단)와 나머지 축(계산·전달)을 하나의
    점수로 합치지 않고 나란히 담는다. peer_reviewed는 journal_ref 존재 여부로만 판단
    (arXiv API가 실제로 채워주는 필드, LLM 판단 아님).

    모델 소진 등으로 판정 자체가 실패하면 RuntimeError를 그대로 전파한다 — 이 함수는
    "판정 하나"의 정직한 계약만 지키고, 후보 여러 개를 도는 루프에서 하나가 실패했을 때
    나머지를 어떻게 할지는 호출하는 쪽(③ 추천 검색)의 몫이다.
    """
    interest_text = (
        f"제목: {interest.get('title', '')}\n"
        f"찾는 것: {interest.get('looking_for', '')}\n"
        f"이미 아는 것: {interest.get('already_known', '')}\n"
        f"제외할 주제: {interest.get('excluded_topics', '')}"
    )
    messages = [
        SystemMessage(content=RELEVANCE_SYSTEM_PROMPT),
        HumanMessage(content=f"관심사:\n{interest_text}\n\n논문 초록:\n{candidate.get('abstract', '')}"),
    ]
    result, _, _, tokens_used = invoke_with_fallback(model, messages, structured=RelevanceScreen)

    return {
        "paper_id": candidate.get("paper_id"),
        "is_relevant": result.is_relevant,
        "reasoning": result.reasoning,
        "peer_reviewed": bool(candidate.get("journal_ref")),
        "citation_count": candidate.get("citation_count"),
        "year": candidate.get("year"),
        "tokens_used": tokens_used,
    }
