# 참고문헌 추천기 — 텍스트(초안 문단·답변)에서 검색어를 뽑아 참고할 논문 목록을 만든다.
# 연구 워크플로우 각 단계·논문 작성(⑦)·메인 챗(④) 온디맨드가 공용으로 쓸 함수
# (README "참고문헌 추천기" 참고) — 그래프 노드가 아니라 평범한 함수다.
#
# paper_search.search_papers()·paper_screening.screen_candidate()를 그대로 재사용한다
# (paper_recommend.recommend_for_interest()를 부르는 게 아니라 그 안의 부품만 공유 —
# 관심사는 "등록된 넓은 주제" 하나인데 이 함수는 "문장 하나"마다 불려야 해서 애초에
# 입력 성격이 다르다. RoadMap "참고문헌 추천기 착수" 08-02 참고).
#
# 보유 논문(VDB)을 먼저 보고 스크리닝 없이 채택한다 — 이미 라이브러리에 등록됐다는
# 것 자체가 신뢰 신호(파인만 QA의 retrieve()가 논문 VDB를 무조건 신뢰하는 것과 같은
# 결). 부족할 때만 신규 검색+스크리닝(②b)으로 보충한다. 서로 다른 신뢰 축이라 하나의
# 점수로 합쳐 재정렬하지 않고 보유 결과를 앞에 그대로 둔다("스크리닝 축을 합치지
# 않는다" 원칙과 같은 결).

import requests
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models import EMPTY_TOKENS, add_tokens, invoke_with_fallback
from retrieval import papers_vectorstore
import paper_screening
import paper_search


class ReferenceSearchError(Exception):
    """arxiv 검색 자체가 실패했을 때(네트워크 장애·API 오류 등) — 모델 소진
    (RuntimeError)과 원인이 다르므로 별도 타입으로 구분한다. _make_reference_node가
    이 타입을 보고 사용자에게 "arXiv 검색 오류"와 "AI 모델 소진"을 다른 문구로
    안내한다(RoadMap "참고문헌만 재검색 + 실패 사유 표시" 참고)."""

EXTRACTION_MODEL = "gemini"

# 보유 논문 VDB에서 "논문 N편"을 얻으려면 청크는 N개보다 훨씬 많이 뒤져야 한다 — 논문
# 한 편이 100청크를 넘고(14페이지 논문이 122청크였다) 유사도 상위권은 거의 항상 같은
# 논문의 인접 청크라, k=N이면 dedupe 후 1~2편만 남아 보유 논문이 있어도 항상 외부 검색으로
# 넘어간다. graph.py의 retrieve()가 MAX_CHUNKS_PER_PAPER로 푼 것과 같은 성격의 문제.
# 임계값(거리 컷)으로 걸러내진 않는다 — 보유 논문은 사용자가 직접 등록한 것 자체가
# 신뢰 신호라는 기존 원칙(retrieve()가 논문 VDB를 무조건 신뢰하는 것과 같은 결)을
# 유지한다. 08-05 라이브 검증에서 실측치(관련 질의 L2 거리 0.44~0.57, 무관한 질의
# 1.04~1.34)로 "근거 없는 숫자" 쪽 반론은 풀렸지만, "등록 자체가 신뢰 신호"라는 원칙은
# 데이터로 풀리는 게 아니라 판단이라 유지하기로 함(사용자 결정) — 대신 판정으로
# 걸러내지 않고 거리값을 reasoning에 실어 사람이 직접 볼 수 있게 한다("판정 대신
# 추출/신호" 원칙과 같은 결, OWNED_MATCH_REASONING 참고).
OWNED_CHUNK_DEPTH_FACTOR = 20

# L2 거리는 그 자체로 의미가 안 와닿는 숫자라 "낮을수록 관련도 높음" 해석을 같이 적는다.
# "자동으로 걸러내지 않음"까지 명시하는 이유 — 값이 커도(무관해 보여도) 이 항목이 그냥
# 빠지지 않고 그대로 남아있다는 걸 읽는 사람이 오해하지 않게. 문장에 "이 정도면 괜찮다"
# 식의 경계값을 안 박아두는 것도 의도적 — 그 판단까지 대신하면 "판정 대신 신호" 원칙이
# 무색해진다.
OWNED_MATCH_REASONING = "보유 논문 벡터 검색 결과 — 질의와의 거리 {score:.2f}(참고용, 0에 가까울수록 관련도 높음, 자동으로 걸러내지 않음)"

EXTRACTION_PROMPT = """주어진 텍스트를 읽고 참고문헌을 찾기 위한 검색어를 하나 뽑아라.
텍스트의 핵심 주장이나 개념을 논문 검색에 쓸 수 있는 간결한 구·문장으로 요약해라 —
텍스트에 실제로 있는 내용만 반영하고 없는 내용을 지어내지 마라.

검색어는 반드시 영어로 뽑아라(08-03) — arXiv 메타데이터가 거의 전부 영어라, 텍스트가
한국어여도 검색어는 영어로 번역해서 내라. 그러지 않으면 한국어 문장에 우연히 걸리는
영어 단어(예: "표면 부호"의 "표면"→surface) 하나로 무관한 논문이 검색 단계에서부터
잘못 걸린다(실사용 중 재현된 문제, RoadMap 참고)."""


class SearchQuery(BaseModel):
    query: str = Field(description="논문 검색에 쓸 핵심 검색어")


def extract_search_query(
    text: str, *, model: str = EXTRACTION_MODEL, disabled_models: list[str] | None = None,
) -> tuple[str, list[str], dict]:
    """text에서 검색어 하나를 뽑는다. 실패(모델 소진 등)는 RuntimeError를 그대로
    전파 — 검색어 자체가 없으면 이 함수를 호출한 recommend_references()가 통째로
    실패하는 게 맞다(빈 검색어로 검색해봤자 의미 없는 결과만 나옴).

    반환: (검색어, 갱신된 disabled_models, tokens_used) — invoke_with_fallback과 같은
    모양으로 서킷 브레이커·토큰을 호출자에게 그대로 넘긴다."""
    messages = [SystemMessage(content=EXTRACTION_PROMPT), HumanMessage(content=text)]
    result, _, disabled_models, tokens_used = invoke_with_fallback(
        model, messages, structured=SearchQuery, disabled_models=disabled_models
    )
    return result.query, disabled_models, tokens_used


def recommend_references(
    text: str, *, max_results: int = 5, min_owned_results: int = 3,
    disabled_models: list[str] | None = None,
) -> tuple[list[dict], str | None, list[str], dict]:
    """text에서 검색어를 뽑아 참고문헌 후보 목록을 만든다.

    1. 보유 논문 VDB 우선 검색(papers_vectorstore) — 스크리닝 없이 그대로 채택.
       청크를 max_results보다 훨씬 깊게(OWNED_CHUNK_DEPTH_FACTOR배) 가져와 paper_id로
       접은 뒤 상위 max_results편만 남긴다 — 깊이와 개수 상한은 별개 축이라 k 하나로
       둘 다 조절하면(원래 그랬다) 깊이를 못 키운다.
    2. 보유 결과가 min_owned_results 미만이면 paper_search.search_papers()로 신규
       검색 → screen_candidate()로 관련도만 걸러 통과분만 추가(실패한 후보는 건너뜀,
       paper_recommend.py와 같은 정책).

    반환: (참고문헌 목록, 실패 사유, 갱신된 disabled_models, 누적 tokens_used). 목록은
    보유 결과가 먼저, 신규(관련 있는 것만) 결과가 뒤. 각 항목:
    {"paper_id", "title", "source": "owned" 또는 "external", "reasoning"}.

    실패 사유(목록이 비었을 때만 의미 있음, 아니면 None) — 호출부(research_workflow의
    _make_reference_node)가 사용자에게 왜 못 찾았는지 구분해서 보여줄 수 있게
    한다(RoadMap "참고문헌만 재검색 + 실패 사유 표시" 참고):
    - "no_candidates": 신규 검색 자체가 0건(또는 애초에 신규 검색을 안 함)
    - "all_irrelevant": 후보는 찾았지만 스크리닝에서 전부 무관 판정
    - "models_exhausted": 스크리닝 도중 최소 한 후보에서 전 모델 소진(RuntimeError)이 나서
      끝까지 평가하지 못함(서킷 브레이커가 이어지므로 남은 후보도 사실상 다 같이 실패)
    검색어 추출 단계의 전 모델 소진이나 arxiv 네트워크 장애는 반환값이 아니라 예외
    (RuntimeError / ReferenceSearchError)로 그대로 전파된다 — 그 시점엔 검색 자체를
    시작도 못 했으므로 "빈 목록"이 아니라 "호출 실패"가 맞다.

    보유 논문은 스크리닝을 안 거치므로 사람이 검토할 근거 문장이 따로 없다 — 대신
    `reasoning`에 벡터 검색 거리(OWNED_MATCH_REASONING, 08-05 라이브 검증 후속)를
    사람이 읽을 수 있는 짧은 문장으로 채운다. 거리로 걸러내진 않는다(위
    OWNED_CHUNK_DEPTH_FACTOR 주석 참고) — 그래서 값이 커도(관련 없어 보여도) 항목
    자체는 그대로 남고, 판단은 사람 몫으로 넘긴다. `reasoning` 키 자체를 항상 채우는 건
    소비자(⑦ 논문 작성 등)가 source에 따라 키가 있다 없다 하는 걸 기억해야 하면 그
    규칙은 소비자가 늘수록 언젠가 깨지기 때문 — 생산자가 한 번 채우는 쪽이 싸다.

    이 함수는 검색어 추출 1회 + 스크리닝 N회로 워크플로우에서 LLM을 가장 많이 부르는
    지점이라, 서킷 브레이커(disabled_models)와 토큰을 호출 안에서 이어받고 밖으로도
    돌려준다. 이어받지 않으면 한 번의 호출 안에서조차 앞 후보에서 죽은 모델을 뒤 후보가
    매번 다시 때려보고 실패한다(호출당 최대 N번 낭비).
    """
    query, disabled_models, query_tokens = extract_search_query(
        text, disabled_models=disabled_models
    )
    tokens_used = add_tokens(EMPTY_TOKENS, query_tokens)

    owned_hits = papers_vectorstore.similarity_search_with_score(
        query, k=max_results * OWNED_CHUNK_DEPTH_FACTOR
    )
    seen_paper_ids: set[str] = set()
    owned_results = []
    for doc, score in owned_hits:
        if len(owned_results) >= max_results:
            break  # 유사도순이라 앞에서 끊으면 곧 "가장 가까운 논문 max_results편"
        paper_id = doc.metadata.get("paper_id")
        if not paper_id or paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id)
        owned_results.append({
            "paper_id": paper_id,
            "title": doc.metadata.get("title", ""),
            "source": "owned",
            "reasoning": OWNED_MATCH_REASONING.format(score=score),
        })

    external_results = []
    candidates: list[dict] | None = None
    screening_exhausted = False
    if len(owned_results) < min_owned_results:
        try:
            candidates = paper_search.search_papers(query, max_results=max_results)
        except requests.exceptions.RequestException as e:
            raise ReferenceSearchError(f"arxiv 검색 실패: {type(e).__name__}: {e}") from e
        for candidate in candidates:
            if candidate["paper_id"] in seen_paper_ids:
                continue
            try:
                screened = paper_screening.screen_candidate(
                    candidate, query, disabled_models=disabled_models
                )
            except RuntimeError as e:
                # 이 경로에서는 disabled_models 갱신을 못 건진다 — invoke_with_fallback이
                # 재귀하면서 쌓은 목록이 예외와 함께 스택에 묻히기 때문. 다만 이 RuntimeError는
                # 애초에 "전 모델 소진"일 때만 나므로 남은 후보도 어차피 다 실패한다(잃는 게 없음).
                print(f"참고문헌 스크리닝 실패, 이 후보는 건너뜀(paper_id={candidate['paper_id']}): {type(e).__name__}: {e}")
                screening_exhausted = True
                continue
            disabled_models = screened["disabled_models"]
            tokens_used = add_tokens(tokens_used, screened["tokens_used"])
            if screened["is_relevant"]:
                seen_paper_ids.add(candidate["paper_id"])
                external_results.append({
                    "paper_id": candidate["paper_id"],
                    "title": candidate["title"],
                    "source": "external",
                    "reasoning": screened["reasoning"],
                })

    results = owned_results + external_results
    reason = None
    if not results:
        if screening_exhausted:
            reason = "models_exhausted"
        elif not candidates:
            reason = "no_candidates"
        else:
            reason = "all_irrelevant"

    return results, reason, disabled_models, tokens_used
