# 논문 스크리닝(②b) — abstract만 보고 관심사와의 관련도를 LLM으로 판정한다(유일한 LLM
# 판단). peer-review·인용수·연도는 계산/전달만 하고 관련도와 하나의 점수로 합치지 않는다
# (RoadMap "스크리닝 축을 합치지 않는다") — 성격이 다른 축을 합치면 정보가 사라진다.
# 후보는 배치가 아니라 하나씩 스크리닝(입출력 개수 불일치 위험 회피, 단순 경로부터).
# 모델은 사용자 선택과 무관하게 고정(paper_ingest.py의 BACKGROUND_SUMMARY_MODEL과 같은 이유).

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

    candidate: paper_search.search_papers() 형태(abstract/journal_ref/year/
    citation_count 포함). interest: interests.py 관심사 레코드.

    반환: {"paper_id", "is_relevant", "reasoning", "peer_reviewed", "citation_count",
    "year", "tokens_used"}. peer_reviewed는 journal_ref 존재 여부로만 판단(LLM 아님).

    판정 실패(모델 소진 등)는 RuntimeError를 그대로 전파 — 여러 후보를 도는 루프에서
    하나가 실패했을 때 어떻게 할지는 호출하는 쪽(③ 추천 검색)의 몫이다.
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
