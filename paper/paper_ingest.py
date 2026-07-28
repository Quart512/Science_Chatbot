# =========================================================
# 논문 요약기(②a) 오케스트레이션 — pdf_parse.py → paper_chunking.py → paper_id.py →
# paper_extraction.py(LLM 구조화 추출) → 논문 VDB(retrieval.py의 papers_vectorstore)를
# 잇는다. To Do "과학챗봇 6-3" / RoadMap "논문 처리 3분할"·"전문 처리" 설계 노트 참고.
#
# 이 파일이 하는 일은 정확히 두 가지, 시점이 다르다:
#
#   register_paper() — 등록 시점. PDF를 파싱해 임베딩용으로 잘게 쪼갠 뒤(fulltext_chunk)
#     그대로 VDB에 저장한다. 요약은 여기서 만들지 않는다("등록 시 인코딩과 요약 생성 분리",
#     RoadMap "논문 처리 3분할"). 비용이 드는 LLM 호출이 전혀 없다 — PDF 파싱과 로컬 임베딩만.
#
#   get_paper_summary() — 조회 시점(lazy). 라이브러리에서 요약을 요청했거나, QA·⑦이 요약을
#     찾는데 없을 때만 호출된다. 이미 만든 적 있으면(doc_type=summary로 캐시돼 있으면) 그걸
#     그대로 반환 — 추가 LLM 호출 0. 없으면 등록된 fulltext_chunk를 모아 구조화 추출 LLM을
#     "한 번" 호출한다. **재귀 분할(map-reduce)은 만들지 않았다** — RoadMap "전문 처리" 노트의
#     명시적 순서: "단순 경로(한 번에 넣기 + 예산 초과 가드) 먼저, 재귀 분할은 실제로 걸리는 걸
#     확인한 뒤". models.py의 check_context_budget()/ContextBudgetExceeded가 정확히 이
#     시점을 위해 미리 만들어둔 안전망이다 — 예산을 넘으면 여기서 잡지 않고 그대로 호출자에게
#     전파한다. 호출자(라이브러리 UI·QA 노드)가 "논문이 길어 요약 생성 불가(분할 미구현)"로
#     정직하게 고지할 것.
#
#   ensure_summary_in_background() — QA(graph.py의 retrieve())가 부른다. "QA 중 요약 부재
#     시 전문 청크로 답하고 요약 생성은 백그라운드로"(To Do 6-3)의 후반부를 담당한다. 전반부
#     ("전문 청크로 답한다")는 사실 별도 코드가 필요 없다 — summary 문서가 없으면 유사도
#     검색이 애초에 fulltext_chunk만 돌려주므로 retrieve()는 항상 하던 대로 동작한다. 이
#     함수는 그 뒤에서 "이 논문 요약이 아직 없으니 만들어두자"만 비동기로 처리한다: 이번
#     턴의 응답 생성을 막지 않도록 daemon thread로 get_paper_summary()를 실행하고 즉시
#     반환한다(스레드가 끝날 때까지 기다리지 않음). 완료 여부를 이번 요청 스트림으로 실시간
#     통지하지는 않는다 — 다음에 같은 논문이 조회될 때 캐시로 잡히는 것 자체가 결과다(단순
#     경로부터: 완료 알림 채널을 새로 만들 만큼 지금 당장 아쉬운 지점이 아니다).
#     같은 논문이 짧은 시간에 여러 번 걸리면(멀티턴 대화에서 흔함) 모듈 전역 in-flight
#     집합(_IN_FLIGHT)으로 중복 생성을 막는다 — 안 그러면 답변마다 LLM을 또 부르게 된다.
#     실제 스레드 기동은 _spawn_background() 한 함수로 분리해뒀다 — 테스트에서 이 함수만
#     동기 호출로 갈아끼우면 진짜 스레드·진짜 LLM 없이 판단 로직(캐시 확인/중복 방지)만
#     검증할 수 있다.
#
# doc_type 구분: 한 컬렉션(papers_vectorstore)에 fulltext_chunk/summary를 metadata로 구분해
# 같이 둔다(RoadMap "열린 질문" — 지금은 한 컬렉션+필터로 시작). 둘 다 임베딩되므로 QA가
# "참고"로 both 검색해 인용할 수 있다 — 요약이 생기고 나면 추가 호출 없이 그냥 검색 결과에
# 섞여 들어온다(To Do "완성 직후 QA에 참고 부착... 추가 호출 0").
#
# is_references 필터링: paper_chunking.py가 태깅해둔 is_references는 (1) 임베딩 시에는 그대로
# 저장하되(버리지 않음 — 나중 서지 추출용 원문 보관), (2) 구조화 추출 LLM 입력을 조립할 때는
# 제외한다 — 인용 문자열 덩어리가 추출 LLM을 오염시키는 걸 막는다(paper_chunking.py 모듈
# docstring "References 청크 표시" 참고).
#
# 재등록 처리: register_paper()는 삽입 "전에" 같은 paper_id의 기존 문서를 전부 지운다
# (fulltext_chunk뿐 아니라 summary도 — 전문이 바뀌었는데 옛 요약이 캐시로 남아있으면 새
# 내용과 안 맞는 요약을 정직한 것처럼 계속 돌려주게 된다. 재등록 = 요약 캐시 무효화는 의도된
# 동작이지 버그가 아니다). 삭제 없이 재삽입만 하면 청크 수가 줄었을 때 이전 잔여 청크가
# paper_id 아래 계속 남는다(RoadMap "논문 id 정규화 + 재등록 처리" 참고).
#
# 수식 신뢰 불가 고지 (To Do "그림 캡션은 살리고... 수식 신뢰 불가 표기"): 논문마다 다른 값이
# 아니라 모든 논문에 붙는 고정 문구라 LLM 판단이 아니라 이 파일의 상수(FORMULA_DISCLAIMER)로
# 박아 넣는다 — "이 논문은 수식이 있다/없다"를 LLM에게 판단시키지 않는다.
#
# 테스트 방식: 이 파일의 함수들은 vectorstore를 인자로 받는다(기본값 None이면 그때 가서
# retrieval.py에서 실제 객체를 가져온다 — 모듈 최상단에서 import하지 않는 이유는 retrieval.py가
# import되는 순간 BAAI/bge-m3 임베딩 모델(~2GB)이 로딩되기 때문, conftest.py의 설명과 동일한
# 이유). 테스트는 이 자리에 가짜 vectorstore(인메모리 dict 흉내)를 주입하고, parse_pdf/
# invoke_with_fallback은 monkeypatch로 갈아끼워 실제 PDF·임베딩·LLM 호출 없이 순수 로직만 검증한다.
#
# 패키지 구조 (07-28): 이 5개 파일(pdf_parse/paper_chunking(구 paper_sections)/paper_id/paper_extraction/
# paper_ingest)은 paper/ 패키지로 묶여 있다 — 전부 "논문 하나를 파싱→분할→식별→추출→
# 저장"하는 한 파이프라인의 단계들이라 경계가 뚜렷하다. retrieval.py(feynman QA와 papers_
# vectorstore를 둘 다 담당하는 공용 인프라)와 arxiv_api.py(tool.py의 일반 검색 tool도 쓰는
# 범용 외부 API 어댑터)는 이 파이프라인 전용이 아니라서 루트에 그대로 남겨뒀다.
#
# 실사용 리뷰로 발견된 수정 (07-28): (1) bibliographic을 화이트리스트 없이 통째로 받으면
# arxiv abstract 같은 긴 필드가 청크 수만큼 그대로 복제돼 VDB에 쌓인다 — _BIBLIOGRAPHIC_
# WHITELIST로 막음. (2) 백그라운드 요약 생성이 state.model을 따라가면 예산이 작은 모델이
# 선택된 턴에 캐시가 영영 안 생긴다 — BACKGROUND_SUMMARY_MODEL로 고정하고, 그래도 나는
# ContextBudgetExceeded(결정론적 실패)는 _PERMANENTLY_FAILED로 기록해 매 조회마다 재시도
# 안 함(그 외 일시적 실패는 계속 재시도됨 — 아래 ensure_summary_in_background 참고).
# (3) _fetch_summary가 metadatas[0]["extraction_json"]을 대괄호로 바로 읽으면 스키마가
# 바뀌었을 때 KeyError로 조회 자체가 터진다 — .get()으로 받고 없으면 캐시 미스로 취급.
# (4) register_paper()가 파일을 두 번(해시용 + parse_pdf 내부의 fitz.open(path)) 읽던
# 것을 한 번만 읽어 재사용하도록 parse_pdf()를 경로가 아니라 바이트를 받게 바꿈.
# =========================================================

import threading

from langchain_core.messages import HumanMessage, SystemMessage

from models import ContextBudgetExceeded, check_context_budget, invoke_with_fallback
from paper.paper_extraction import PaperExtraction
from paper.paper_id import normalize_paper_id
from paper.paper_chunking import split_for_embedding  # 구 paper_sections.py
from paper.pdf_parse import parse_pdf

FORMULA_DISCLAIMER = "(주의: 수식·이미지는 파싱 과정에서 신뢰할 수 없어 이 요약에 반영하지 않았습니다.)"

# 백그라운드 요약 생성에 쓸 고정 모델(07-28, 리뷰 지적): ensure_summary_in_background()가
# 그 턴에 사용자가 고른 모델(graph.py의 state.model)을 그대로 따라가면 안 된다 — 요약은
# 한 번 생성되면 모든 사용자·모든 턴이 공유하는 캐시 산출물인데, 성공 여부와 품질이
# "우연히 그 턴에 선택된 모델"에 좌우되면 안 된다. 특히 Qwen-tuned(CONTEXT_BUDGET_CHARS
# 6,000자)로 걸리면 논문 대부분이 매 턴 ContextBudgetExceeded로 실패하고 캐시가 영영 안
# 생긴다. 그래서 예산이 가장 넉넉한 모델(gemini, 800,000자, models.py 참고)로 고정한다.
BACKGROUND_SUMMARY_MODEL = "gemini"

EXTRACTION_SYSTEM_PROMPT = """너는 논문에서 구조화된 정보를 추출하는 어시스턴트다. 판단이나 품질
평가를 하지 마라 — 오직 본문에 있는 내용만 추출해라. 본문에 없는 내용은 추론해서 채우지 말고
빈 값으로 남겨라. 수식은 PDF 파싱 과정에서 깨진 유니코드로 나올 수 있어 신뢰할 수 없다 — 수식
자체의 정확한 형태에 근거해 판단하지 말고, 서술된 주장·설명 텍스트만 근거로 삼아라."""


def _get_papers_vectorstore():
    # 함수 안에서 import하는 이유는 위 모듈 docstring "테스트 방식" 참고 — 무거운 임베딩
    # 모델 로딩을 이 함수가 실제로 호출될 때까지(=vectorstore를 주입받지 않았을 때만) 미룬다.
    from retrieval import papers_vectorstore
    return papers_vectorstore


# register_paper()가 청크마다(!) 메타데이터로 복제해도 되는 서지 필드 화이트리스트
# (07-28, 리뷰 지적): arxiv_search()가 주는 abstract는 1~2천자짜리 긴 텍스트라, 화이트
# 리스트 없이 bibliographic dict를 통째로 받으면 논문 한 편이 N개 청크로 쪼개질 때 그
# abstract가 N번 그대로 Chroma에 들어간다(60청크 논문이면 abstract 60부). 지금은
# abstract를 아예 받지 않는다 — 소비하는 곳이 없어서(PaperExtraction 스키마에도 abstract
# 필드가 없다) 미리 어딘가에 심어봤자 검증할 방법이 없다(품질 평가를 소비처 생길 때까지
# 미룬 것과 같은 논리, paper_chunking.py 모듈 docstring 참고). 나중에 필요해지면 청크마다
# 복제하지 말고 summary 문서(_store_summary가 만드는 doc_type="summary" 문서) 메타데이터에
# 한 번만 넣는 방식으로 추가할 것.
_BIBLIOGRAPHIC_WHITELIST = ("title", "authors", "year", "arxiv_id", "pdf_url")


def _flatten_bibliographic(bibliographic: dict | None) -> dict:
    """arxiv_search() 등이 주는 서지정보 dict에서 화이트리스트(_BIBLIOGRAPHIC_WHITELIST)에
    있는 키만 골라 Chroma 메타데이터로 쓸 수 있게 편다.

    Chroma 메타데이터 값은 str/int/float/bool만 허용(리스트·None 불가) — authors 같은
    list[str] 필드는 문자열로 합치고, None 값은 키 자체를 생략한다(빈 문자열로 채우면
    "값이 없음"과 "빈 문자열이 실제 값"을 구분 못 하게 된다).
    """
    if not bibliographic:
        return {}
    flat = {}
    for k in _BIBLIOGRAPHIC_WHITELIST:
        v = bibliographic.get(k)
        if v is None:
            continue
        if isinstance(v, list):
            flat[k] = ", ".join(str(x) for x in v)
        else:
            flat[k] = v
    return flat


def register_paper(
    pdf_path: str,
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    bibliographic: dict | None = None,
    vectorstore=None,
) -> dict:
    """PDF를 파싱해 임베딩용 청크(doc_type=fulltext_chunk)로 등록한다. 요약은 만들지
    않는다(lazy — get_paper_summary()가 필요할 때 따로 생성).

    doi/arxiv_id 중 있는 것만 넘기면 된다(paper_id.py 우선순위: DOI > arXiv > 파일 해시).
    bibliographic은 arxiv_search() 반환 dict(title/authors/year/pdf_url 등)를 그대로
    넘기면 되고, 없어도 동작한다(해시 기반 paper_id로 등록만 되고 서지정보는 비어 있음).

    반환: {"paper_id": str, "text_extractable": bool, "chunk_count": int, "page_count": int}
    스캔본(text_extractable=False)이면 chunk_count=0으로 정직하게 보고하고 아무것도 저장하지
    않는다 — OCR을 붙이지 않는다는 pdf_parse.py의 원칙을 그대로 물려받는다.
    """
    # 파일을 한 번만 읽는다(07-28, 리뷰 지적) — 이 file_bytes를 paper_id 계산(해시)과
    # parse_pdf() 양쪽에 그대로 재사용한다. 예전엔 여기서 읽은 뒤 parse_pdf(pdf_path)가
    # 내부에서 fitz.open(path)로 같은 파일을 디스크에서 또 읽었다 — 큰 PDF에서 불필요한
    # 중복 I/O였다.
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    parsed = parse_pdf(file_bytes)
    paper_id = normalize_paper_id(doi=doi, arxiv_id=arxiv_id, file_bytes=file_bytes)

    if not parsed["text_extractable"]:
        # 스캔본은 저장할 청크가 없으므로 vectorstore를 아예 건드리지 않는다 —
        # vectorstore가 None으로 들어왔다면(운영 경로) 여기서 무거운 임베딩 모델 로딩도 피함.
        return {
            "paper_id": paper_id,
            "text_extractable": False,
            "chunk_count": 0,
            "page_count": parsed["page_count"],
        }

    vectorstore = vectorstore or _get_papers_vectorstore()
    pieces = split_for_embedding(parsed["markdown"])
    bib_meta = _flatten_bibliographic(bibliographic)

    ids = [f"{paper_id}-{p['index']}" for p in pieces]
    texts = [p["text"] for p in pieces]
    metadatas = [
        {
            "paper_id": paper_id,
            "doc_type": "fulltext_chunk",
            "index": p["index"],
            "is_references": p["is_references"],
            "header": p["header"],
            **bib_meta,
        }
        for p in pieces
    ]

    # 재등록 처리 — 삽입 전에 같은 paper_id의 기존 문서를 전부 삭제(fulltext_chunk+summary
    # 둘 다, 위 모듈 docstring "재등록 처리" 참고). 청크가 하나도 없던 첫 등록이면 삭제할
    # 게 없으므로 no-op.
    vectorstore.delete(where={"paper_id": paper_id})
    if texts:
        vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    # 재등록 = 요약 캐시 무효화와 같은 논리로, "영구 실패" 기록도 같이 지운다 — 전문
    # 내용이 바뀌었으면(예: 불필요한 섹션 제거, 더 짧은 판본으로 교체) 전에는 예산을
    # 넘었던 논문이 이번엔 안 넘을 수 있다. 옛 판정을 그대로 들고 있으면 재등록해도
    # 영원히 재시도가 안 된다(아래 ensure_summary_in_background 모듈 docstring 참고).
    _PERMANENTLY_FAILED.discard(paper_id)

    return {
        "paper_id": paper_id,
        "text_extractable": True,
        "chunk_count": len(pieces),
        "page_count": parsed["page_count"],
    }


def _fetch_fulltext_chunks(vectorstore, paper_id: str) -> list[dict]:
    """등록된 fulltext_chunk를 index 순서로 모아 반환한다. is_references인 조각은
    여기서 걸러낸다(저장은 돼 있지만 추출 LLM 입력에서는 제외 — 모듈 docstring 참고)."""
    result = vectorstore.get(where={"$and": [{"paper_id": paper_id}, {"doc_type": "fulltext_chunk"}]})
    items = [
        {"text": doc, "index": meta.get("index", 0), "is_references": meta.get("is_references", False)}
        for doc, meta in zip(result["documents"], result["metadatas"])
    ]
    items.sort(key=lambda c: c["index"])
    return [c for c in items if not c["is_references"]]


def _fetch_summary(vectorstore, paper_id: str) -> PaperExtraction | None:
    result = vectorstore.get(where={"$and": [{"paper_id": paper_id}, {"doc_type": "summary"}]})
    metadatas = result.get("metadatas", [])
    if not metadatas:
        return None
    # .get()으로 받는다(07-28, 리뷰 지적) — extraction_json은 이 코드가 직접 넣은 필드라
    # 정상 경로에선 항상 있지만, 스키마가 바뀌거나 다른 경로로 doc_type="summary" 문서가
    # 생기면 metadatas[0]["extraction_json"]이 KeyError로 조회 자체를 터뜨린다. 없으면
    # "캐시 없음"(None)으로 취급 — 어차피 이 경우 재생성이 정답이므로 캐시 미스와 같은
    # 처리로 충분하다.
    extraction_json = metadatas[0].get("extraction_json")
    if extraction_json is None:
        return None
    return PaperExtraction.model_validate_json(extraction_json)


def _render_summary_text(extraction: PaperExtraction) -> str:
    """PaperExtraction을 임베딩·검색 가능한 사람이 읽는 텍스트로 렌더링한다. 구조화된
    필드값(extraction_json)은 메타데이터에 그대로 보존하고, 이 텍스트는 검색 매칭용이다."""
    lines = ["핵심 주장:"]
    lines += [f"- {c}" for c in extraction.core_claims]

    if extraction.evidence:
        lines.append("근거:")
        lines += [f"- ({e.kind}) {e.detail}" for e in extraction.evidence]

    if extraction.author_stated_limitations:
        lines.append("저자가 밝힌 한계:")
        lines += [f"- {l}" for l in extraction.author_stated_limitations]

    if extraction.unresolved_questions:
        lines.append("미해결 지점:")
        lines += [f"- {q}" for q in extraction.unresolved_questions]

    if extraction.code_data_availability:
        lines.append(f"코드·데이터 공개: {extraction.code_data_availability}")

    lines.append(FORMULA_DISCLAIMER)
    return "\n".join(lines)


def _store_summary(vectorstore, paper_id: str, extraction: PaperExtraction) -> None:
    # cache-miss로 여기까지 왔다는 건 보통 기존 summary 문서가 없다는 뜻이지만, 혹시 남아있는
    # 경우(예: 동시 호출 등)를 대비한 안전망으로 삽입 전에 한 번 더 지운다 — 주 무효화 경로는
    # register_paper()의 재등록 삭제다.
    vectorstore.delete(where={"$and": [{"paper_id": paper_id}, {"doc_type": "summary"}]})
    vectorstore.add_texts(
        texts=[_render_summary_text(extraction)],
        metadatas=[{
            "paper_id": paper_id,
            "doc_type": "summary",
            "extraction_json": extraction.model_dump_json(),
        }],
        ids=[f"{paper_id}-summary"],
    )


def get_paper_summary(paper_id: str, *, model: str = BACKGROUND_SUMMARY_MODEL, vectorstore=None) -> dict:
    """paper_id의 구조화 요약을 lazy 생성 후 캐시해 반환한다.

    model 기본값은 리터럴 "gemini"가 아니라 BACKGROUND_SUMMARY_MODEL을 그대로 참조한다
    (07-28, 리뷰 지적) — 나중에 그 상수를 바꿀 때 이 함수의 기본값(예: 라이브러리 UI가
    model 없이 그냥 호출하는 경로)만 옛 모델에 남아 어긋나는 일이 없게 한다.

    이미 만든 적 있으면(doc_type=summary 캐시) 그대로 반환 — 추가 LLM 호출 0. 없으면
    register_paper()가 저장해둔 fulltext_chunk를 모아(is_references 제외) 한 번에
    구조화 추출을 시도한다. 컨텍스트 예산을 넘으면 ContextBudgetExceeded를 여기서 잡지
    않고 그대로 전파한다 — 호출한 쪽(라이브러리 UI·QA)이 "논문이 길어 요약 생성 불가
    (분할 미구현)"로 정직하게 고지할 것(모듈 docstring 참고).

    paper_id가 아예 등록된 적 없으면(fulltext_chunk가 하나도 없으면) ValueError.

    반환: {"paper_id", "extraction": PaperExtraction, "from_cache": bool,
           "generated_by": str | None, "tokens_used": dict | None}
    """
    vectorstore = vectorstore or _get_papers_vectorstore()

    cached = _fetch_summary(vectorstore, paper_id)
    if cached is not None:
        return {
            "paper_id": paper_id,
            "extraction": cached,
            "from_cache": True,
            "generated_by": None,
            "tokens_used": None,
        }

    chunks = _fetch_fulltext_chunks(vectorstore, paper_id)
    if not chunks:
        raise ValueError(f"paper_id={paper_id!r}: 등록된 전문 청크가 없음 — register_paper()를 먼저 호출해야 함")

    full_text = "\n\n".join(c["text"] for c in chunks)
    # 예산 초과 시 ContextBudgetExceeded — 여기서 안 잡고 그대로 전파(모듈 docstring 참고)
    check_context_budget(model, full_text)

    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=full_text),
    ]
    extraction, generated_by, _disabled_models, tokens_used = invoke_with_fallback(
        model, messages, structured=PaperExtraction
    )

    _store_summary(vectorstore, paper_id, extraction)

    return {
        "paper_id": paper_id,
        "extraction": extraction,
        "from_cache": False,
        "generated_by": generated_by,
        "tokens_used": tokens_used,
    }


# 같은 프로세스 안에서 "지금 백그라운드로 생성 중인 paper_id" 집합 — 짧은 시간에 같은
# 논문이 여러 번 조회될 때(멀티턴 대화에서 흔함) 중복으로 LLM을 부르지 않기 위한 가드.
# Lock으로 감싸는 이유: 백그라운드 스레드(생성 완료 시 discard)와 다음 요청을 처리하는
# 메인 스레드(조회 시 add)가 동시에 건드릴 수 있음.
_IN_FLIGHT: set[str] = set()
_IN_FLIGHT_LOCK = threading.Lock()

# "재시도해도 결과가 똑같이 실패할 게 확실한" paper_id 집합(07-28, 리뷰 지적) —
# ContextBudgetExceeded는 같은 모델(BACKGROUND_SUMMARY_MODEL로 고정돼 있으므로 항상
# 같은 예산)로 같은 전문 텍스트를 보내면 항상 다시 예산을 넘는다. 이 실패를 기록 안
# 하면 논문을 볼 때마다(멀티턴 대화라면 매 턴) retrieve()가 매번 새 스레드를 띄운다 —
# 예산 초과 자체는 API 호출 전이라 비용은 0이지만, 무의미한 스레드 기동이 계속 반복된다.
# 반대로 다른 예외(네트워크 순단, rate limit 등 일시적 실패)는 여기 안 넣는다 — 그런
# 실패는 다음 시도에서 성공할 수 있으므로 계속 재시도돼야 한다(기존 동작 그대로 유지).
# register_paper()가 재등록 시 이 집합에서 해당 paper_id를 지운다(위 register_paper
# 참고) — 전문이 바뀌면 예산 초과 여부도 다시 확인해볼 가치가 있다.
_PERMANENTLY_FAILED: set[str] = set()


def _spawn_background(fn) -> None:
    """실제로 daemon thread를 띄우는 부분만 분리해둔 한 줄짜리 함수 — 테스트에서
    monkeypatch로 동기 실행(즉시 fn() 호출)이나 no-op으로 갈아끼우기 위한 지점이다."""
    threading.Thread(target=fn, daemon=True).start()


def ensure_summary_in_background(paper_id: str, *, model: str = BACKGROUND_SUMMARY_MODEL, vectorstore=None) -> bool:
    """paper_id에 캐시된 요약이 없으면 백그라운드에서 생성을 시작한다(모듈 docstring
    "ensure_summary_in_background" 항목 참고). 이번 턴의 응답은 막지 않는다 — QA는 그동안
    (이미 그렇게 동작하던 대로) 전문 청크로 답한다.

    model은 호출하는 쪽(graph.py의 retrieve())이 그 턴의 state.model을 넘기면 안 된다
    (07-28, 리뷰 지적) — 요약은 모든 사용자·모든 턴이 공유하는 캐시 산출물이라 기본값
    BACKGROUND_SUMMARY_MODEL(예산이 가장 넉넉한 모델)로 고정해서 쓴다.

    이미 요약이 있거나, 이미 같은 paper_id에 대해 생성이 진행 중이거나, 전에 시도했다가
    영구 실패로 기록됐으면(_PERMANENTLY_FAILED — ContextBudgetExceeded, 아래 참고)
    아무것도 안 하고 False를 반환한다. 새로 생성을 시작했으면 True — 호출자(retrieve())가
    이 값으로 trace에 "백그라운드로 시작함"을 기록하는 데 쓴다(실제 완료 여부와는 무관 —
    완료는 다음 조회 때 캐시로 확인된다).
    """
    vectorstore = vectorstore or _get_papers_vectorstore()

    # 영구 실패 집합 확인이 먼저다(07-28, 리뷰 지적) — 이건 프로세스 메모리 안 set
    # 조회라 사실상 공짜지만, _fetch_summary()는 vectorstore.get() 호출(DB 조회)이라
    # 비용이 있다. 영구 실패로 이미 아는 논문이면 굳이 DB까지 갈 필요가 없다.
    if paper_id in _PERMANENTLY_FAILED:
        return False

    if _fetch_summary(vectorstore, paper_id) is not None:
        return False

    with _IN_FLIGHT_LOCK:
        if paper_id in _IN_FLIGHT:
            return False
        _IN_FLIGHT.add(paper_id)

    def _run():
        try:
            get_paper_summary(paper_id, model=model, vectorstore=vectorstore)
        except ContextBudgetExceeded as e:
            # 같은 모델(고정됨)·같은 전문 텍스트로는 다시 불러도 항상 똑같이 예산을
            # 넘는다 — 재시도해도 결과가 바뀌지 않는 결정론적 실패이므로 영구 실패로
            # 기록해 매 조회마다 스레드를 새로 띄우는 낭비를 막는다(위 _PERMANENTLY_FAILED
            # 참고). register_paper()가 재등록 시 이 기록을 지운다.
            _PERMANENTLY_FAILED.add(paper_id)
            print(f"백그라운드 요약 생성 영구 실패(재등록 전까지 재시도 안 함, paper_id={paper_id}): {e}")
        except Exception as e:
            # 그 외 실패(파싱 에러, 일시적 네트워크·rate limit 등)는 다음 시도에서
            # 성공할 수 있으므로 영구 실패로 기록하지 않는다 — 백그라운드라 이 예외를
            # 돌려줄 곳(사용자·호출 스택)이 없어 최소한 콘솔에는 남긴다. 다음 조회 때
            # 캐시가 여전히 없으므로 자연히 재시도된다(별도 재시도 로직 불필요).
            print(f"백그라운드 요약 생성 실패 (paper_id={paper_id}): {type(e).__name__}: {e}")
        finally:
            with _IN_FLIGHT_LOCK:
                _IN_FLIGHT.discard(paper_id)

    _spawn_background(_run)
    return True


if __name__ == "__main__":
    # 수동 스모크 테스트용 — pytest는 vectorstore/parse_pdf를 전부 가짜로 갈아끼운
    # 순수 로직 검증이라, 진짜 PyMuPDF+Chroma+LLM이 실제로 맞물려 도는지는 이 경로로
    # 직접 한 번 확인해야 한다(지금 이 세션에서 실행 환경이 막혀 있어 내가 직접 못 돌려봄).
    # 사용법: uv run -m paper.paper_ingest <PDF 경로> [arxiv_id]
    import sys

    if len(sys.argv) < 2:
        print("사용법: uv run -m paper.paper_ingest <PDF 경로> [arxiv_id]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    arxiv_id = sys.argv[2] if len(sys.argv) > 2 else None

    reg = register_paper(pdf_path, arxiv_id=arxiv_id)
    print(f"등록 결과: {reg}")

    if reg["text_extractable"]:
        summary = get_paper_summary(reg["paper_id"])
        print(f"요약 (from_cache={summary['from_cache']}):")
        print(summary["extraction"].model_dump_json(indent=2))
