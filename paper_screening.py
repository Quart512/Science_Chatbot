# 논문 스크리닝(②b) — abstract만 보고 관심사와의 관련도를 LLM으로 판정한다(유일한 LLM
# 판단). peer-review·인용수·연도는 계산/전달만 하고 관련도와 하나의 점수로 합치지 않는다
# (RoadMap "스크리닝 축을 합치지 않는다") — 성격이 다른 축을 합치면 정보가 사라진다.
# 후보는 배치가 아니라 하나씩 스크리닝(입출력 개수 불일치 위험 회피, 단순 경로부터).
# 모델은 사용자 선택과 무관하게 고정(paper_ingest.py의 BACKGROUND_SUMMARY_MODEL과 같은 이유).

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models import invoke_with_fallback

SCREENING_MODEL = "gemini"

RELEVANCE_SYSTEM_PROMPT = """논문 초록과 주어진 주제를 비교해서 이 논문이 주제와 관련
있는지 판정해라. 주제에 "찾는 것"이 적혀 있다면 거기에 초점을 맞추고, "이미 아는 것"이나
"제외할 주제"가 적혀 있고 초록이 그것에만 해당한다면 관련 없음으로 판정해라(주제에 그런
구분이 없으면 이 기준은 그냥 무시해라). 애매하면 관련 있음 쪽으로 — 관련도는 1차
필터일 뿐이고 최종 판단은 사용자가 한다."""


class RelevanceScreen(BaseModel):
    is_relevant: bool = Field(description="초록이 주제와 관련 있으면 True")
    reasoning: str = Field(default="", description="짧은 판단 근거(한 문장)")


def screen_candidate(
    candidate: dict, topic: str, *, model: str = SCREENING_MODEL,
    disabled_models: list[str] | None = None,
) -> dict:
    """후보 논문 하나를 주어진 주제 기준으로 스크리닝한다.

    candidate: paper_search.search_papers() 형태(abstract/journal_ref/year/
    citation_count 포함). topic: 자유 텍스트 — 관심사 레코드(title/looking_for/
    already_known/excluded_topics를 호출자가 조립한 텍스트, ③ 추천 검색이 이렇게
    씀)일 수도, 문장 하나(참고문헌 추천기가 텍스트에서 뽑은 주장)일 수도 있다.
    이 함수는 그 출처를 몰라도 된다 — 그냥 주어진 텍스트와 초록을 비교할 뿐이다
    (08-02, 관심사 dict를 통째로 요구하던 걸 문자열로 축소해 여러 호출자가 재사용
    가능하게 함).

    disabled_models: 여러 후보를 연달아 도는 호출자가 서킷 브레이커를 이어받기 위한
    선택 인자다. 안 넘기면 종전대로 매 호출이 백지에서 시작한다(③ 추천 검색·배치 경로).
    넘기면 갱신된 목록을 반환 dict의 같은 키로 돌려주므로, 앞 후보에서 죽은 모델을
    다음 후보가 다시 때려보는 낭비가 사라진다.

    반환: {"paper_id", "is_relevant", "reasoning", "peer_reviewed", "citation_count",
    "year", "tokens_used", "disabled_models"}. peer_reviewed는 journal_ref 존재
    여부로만 판단(LLM 아님).

    판정 실패(모델 소진 등)는 RuntimeError를 그대로 전파 — 여러 후보를 도는 루프에서
    하나가 실패했을 때 어떻게 할지는 호출하는 쪽(③ 추천 검색)의 몫이다.
    """
    messages = [
        SystemMessage(content=RELEVANCE_SYSTEM_PROMPT),
        HumanMessage(content=f"주제:\n{topic}\n\n논문 초록:\n{candidate.get('abstract', '')}"),
    ]
    result, _, disabled_models, tokens_used = invoke_with_fallback(
        model, messages, structured=RelevanceScreen, disabled_models=disabled_models
    )

    return {
        "paper_id": candidate.get("paper_id"),
        "is_relevant": result.is_relevant,
        "reasoning": result.reasoning,
        "peer_reviewed": bool(candidate.get("journal_ref")),
        "citation_count": candidate.get("citation_count"),
        "year": candidate.get("year"),
        "tokens_used": tokens_used,
        "disabled_models": disabled_models,
    }
