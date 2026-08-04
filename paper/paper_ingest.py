# 논문 요약기(②a) 오케스트레이션 — pdf_parse → paper_chunking → paper_id →
# paper_extraction(LLM 구조화 추출) → 논문 VDB(retrieval.papers_vectorstore)를 잇는다.
#
# 세 진입점, 시점이 다르다:
#   register_paper() — 등록 시점. PDF를 파싱해 fulltext_chunk로 저장(LLM 호출 없음,
#     PDF 파싱+로컬 임베딩만). 요약은 여기서 안 만든다(등록과 요약 생성을 분리).
#   get_paper_summary() — 조회 시점(lazy). 캐시(doc_type=summary)가 있으면 그대로 반환
#     (추가 호출 0), 없으면 fulltext_chunk를 모아 구조화 추출을 한 번 호출한다. 재귀
#     분할(map-reduce)은 미구현 — 예산 초과 시 ContextBudgetExceeded를 그대로 전파해
#     호출자가 정직하게 고지한다(단순 경로부터, RoadMap "전문 처리" 참고).
#   ensure_summary_in_background() — QA(graph.retrieve())가 부른다. 요약 없는 논문은
#     전문 청크로 답하고(이미 되는 동작), 생성만 daemon thread로 백그라운드 트리거한다.
#     완료 알림 채널은 없음 — 다음 조회 때 캐시로 확인되는 것 자체가 결과.
#
# doc_type(fulltext_chunk/summary/abstract)은 한 컬렉션에 metadata로 구분해 같이 둔다.
# is_references 청크는 임베딩엔 남기되(서지 추출용 보관) 구조화 추출 입력에서는 제외.
# 재등록 시 같은 paper_id의 기존 문서(청크+summary+abstract)를 전부 지우고 다시 넣는다
# — 전문이 바뀌었는데 옛 요약이 캐시로 남으면 안 맞는 요약을 정직한 것처럼 계속 준다.
#
# 테스트 방식: 함수들이 vectorstore를 인자로 받는다(기본 None이면 그제서야 retrieval.py에서
# 가져옴 — 모듈 최상단 import 시 BAAI/bge-m3가 로딩되는 걸 피하려고). 테스트는 가짜
# vectorstore를 주입하고 parse_pdf/invoke_with_fallback은 monkeypatch로 갈아끼운다.

import threading

from langchain_core.messages import HumanMessage, SystemMessage

import paper_catalog
from arxiv_api import fetch_by_id
from models import ContextBudgetExceeded, check_context_budget, invoke_with_fallback
from paper.paper_extraction import PaperExtraction
from paper.paper_id import normalize_paper_id
from paper.paper_chunking import extract_abstract, split_for_embedding  # 구 paper_sections.py
from paper.title_check import classify_title_match
from paper.pdf_parse import parse_pdf

FORMULA_DISCLAIMER = "(주의: 수식·이미지는 파싱 과정에서 신뢰할 수 없어 이 요약에 반영하지 않았습니다.)"

# 요약은 모든 사용자·모든 턴이 공유하는 캐시 산출물이라 그 턴에 우연히 고른 모델(예:
# 예산 작은 Qwen-tuned)을 따라가면 안 된다 — 예산이 가장 넉넉한 모델로 고정.
BACKGROUND_SUMMARY_MODEL = "gemini"

EXTRACTION_SYSTEM_PROMPT = """너는 논문에서 구조화된 정보를 추출하는 어시스턴트다. 판단이나 품질
평가를 하지 마라 — 오직 본문에 있는 내용만 추출해라. 본문에 없는 내용은 추론해서 채우지 말고
빈 값으로 남겨라. 수식은 PDF 파싱 과정에서 깨진 유니코드로 나올 수 있어 신뢰할 수 없다 — 수식
자체의 정확한 형태에 근거해 판단하지 말고, 서술된 주장·설명 텍스트만 근거로 삼아라."""

# abstract가 있을 때만 시스템 프롬프트에 추가하는 앵커 지침(없으면 EXTRACTION_SYSTEM_
# PROMPT 그대로라 회귀 없음) — 초록은 core_claims 식별 기준으로 삼되, 한계·미해결·공개
# 여부는 초록에 거의 안 나오므로 반드시 본문에서 찾으라고 명시한다.
ABSTRACT_ANCHOR_INSTRUCTION = """
사용자 메시지 맨 앞에 이 논문의 초록이 [논문 초록]으로 붙어 있다. 초록은 핵심 주장(core_claims)을
식별하는 기준으로 삼아라 — 초록에 있는 주장이라고 core_claims에서 빼면 안 된다. 다만 저자가
밝힌 한계(author_stated_limitations)·미해결 지점(unresolved_questions)·코드·데이터 공개
(code_data_availability)는 초록에 보통 없으니 반드시 [본문]에서 찾아라."""


def _get_papers_vectorstore():
    # 함수 안에서 import — 무거운 임베딩 모델 로딩을 실제 호출 시점까지 미룬다(모듈 docstring 참고).
    from retrieval import papers_vectorstore
    return papers_vectorstore


# register_paper()가 청크마다 메타데이터로 복제해도 되는 서지 필드 화이트리스트 — abstract는
# 1~2천자라 화이트리스트 없이 통째로 받으면 청크 수만큼(예: 60개) 복제된다. abstract는 대신
# doc_type="abstract" 문서 하나로 별도 저장(아래 register_paper() 참고).
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
    filename: str = "",
    vectorstore=None,
) -> dict:
    """PDF를 파싱해 임베딩용 청크(doc_type=fulltext_chunk)로 등록한다. 요약은 lazy
    (get_paper_summary()가 필요할 때 따로 생성).

    doi/arxiv_id 중 있는 것만 넘기면 된다(우선순위: DOI > arXiv > 파일 해시). bibliographic
    없이도 동작(해시 기반 paper_id, 서지정보는 비움). arxiv_id는 있는데 abstract가 없으면
    fetch_by_id()로 자동 조회(title 등도 같이 채워짐, 호출자 값이 우선) — 조회 실패는
    등록을 막지 않는다. filename(업로드 원본 파일명)은 카탈로그에만 저장되고 파싱에는
    안 쓰인다 — title이 비어있는 논문을 화면에서 해시 대신 보여줄 차선책(08-04 참고).

    반환: {"paper_id", "text_extractable", "chunk_count", "page_count", "title_check":
    {"status", "given_title", "pdf_title"}}. 스캔본은 chunk_count=0으로 정직하게 보고하고
    아무것도 저장 안 함(title_check 없음). title_check는 서지 title과 PDF 자체 제목을
    대조한 결과(classify_title_match 참고) — "different_paper"여도 등록은 그대로 진행,
    판정만 반환값에 실어 보낸다(경고 표시는 호출하는 쪽 몫).
    """
    # file_bytes를 paper_id 해시 계산과 parse_pdf() 양쪽에 재사용 — 같은 파일 중복 I/O 방지.
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

    # arxiv_id는 있는데 서지정보(특히 abstract)가 없으면 arxiv API로 자동 조회한다
    # (07-29, 답변 근거 표시 작업 중 논의) — arxiv_search()는 키워드 검색이라 제목 등으로
    # 찾으면 다른 논문이 걸릴 위험이 있는데, 여기선 이미 정확한 arxiv_id를 알고 있으니
    # fetch_by_id()(id_list 조회, arxiv_api.py)로 그 논문 자체를 정확히 가져온다. abstract만
    # 채우는 게 아니라 title/authors/year/pdf_url까지 한 번에 채운다 — arxiv_search()가
    # 애초에 이 전부를 한 dict로 주기 때문에 abstract만 골라 쓰는 게 오히려 부자연스럽다.
    # 호출자가 이미 bibliographic을 넘겼다면(abstract 포함) 그 값이 최선이라 조회를
    # 건너뛴다 — 조회 실패(네트워크 오류·잘못된 id 등)는 등록을 막을 이유가 없으므로
    # 콘솔에 로그만 남기고 서지정보 없이 계속 진행한다(abstract 미확보와 같은 "없음" 취급).
    if arxiv_id and not (bibliographic or {}).get("abstract"):
        try:
            fetched = fetch_by_id(arxiv_id)
            if fetched:
                # 호출자가 명시한 값이 우선이지만, "명시"를 키 존재만으로 판단하면 안 된다 —
                # 호출자가 {"title": None}처럼 값을 모른다는 뜻으로 None을 넘겨도 **로 그냥
                # 병합하면 그 None이 arxiv에서 방금 가져온 title을 덮어써버린다. None인
                # 키는 "명시 안 함"으로 취급해 걸러내고 남은 값만 우선순위를 준다.
                explicit = {k: v for k, v in bibliographic.items() if v is not None} if bibliographic else {}
                bibliographic = {**fetched, **explicit}
        except Exception as e:
            print(f"arxiv 서지정보 자동 조회 실패(등록은 계속 진행, arxiv_id={arxiv_id}): {type(e).__name__}: {e}")

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

    # 재등록 처리 — 삽입 전에 같은 paper_id의 기존 문서를 전부 삭제(fulltext_chunk+summary+
    # abstract 전부, 위 모듈 docstring "재등록 처리" 참고). 청크가 하나도 없던 첫 등록이면
    # 삭제할 게 없으므로 no-op.
    vectorstore.delete(where={"paper_id": paper_id})
    if texts:
        vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    # abstract 확보 (07-29, 6-3 후속) — 우선순위: arxiv_search()가 준 abstract > PDF에서
    # 뽑은 Abstract 섹션(위에서 이미 계산한 pieces 재사용, 새로 파싱하지 않음) > 없음.
    # summary와 달리 여기서 바로 저장한다 — summary는 lazy라 등록 직후엔 없는데, abstract는
    # 그 공백(등록 직후~요약 생성 전)을 메우는 게 목적이라 등록 시점에 있어야 의미가 있다
    # (RoadMap "abstract와 ②a의 관계" 설계 노트 참고). 청크마다 복제하지 않고 summary와
    # 같은 패턴으로 doc_type="abstract" 문서 하나만 저장. bib_meta(title 등)를 같이 넣는
    # 이유(07-29, QA 답변 근거 표시 작업 중 발견): register_paper()에는 bib_meta가 이미
    # 있으니 여기 넣는 건 공짜지만, 안 넣으면 abstract만 검색되고 fulltext_chunk가 context에
    # 안 낀 경우 어느 논문인지 paper_id(예: arxiv:2401.12345)로만 표시된다 — summary 문서도
    # 같은 문제가 있었는데, get_paper_summary()는 bibliographic을 안 받는 별도 호출이라
    # _fetch_fulltext()가 청크를 읽을 때 그 메타데이터에서 같이 뽑아 넘기는 방식으로 해결했다
    # (아래 _store_summary 호출부 참고).
    abstract_text = (bibliographic or {}).get("abstract") or extract_abstract(pieces)
    if abstract_text:
        vectorstore.add_texts(
            texts=[abstract_text],
            metadatas=[{"paper_id": paper_id, "doc_type": "abstract", **bib_meta}],
            ids=[f"{paper_id}-abstract"],
        )

    # 재등록 = 요약 캐시 무효화와 같은 논리로 "영구 실패" 기록도 지운다 — 전문이
    # 바뀌면 전에 예산 초과였던 논문이 이번엔 안 넘을 수 있다.
    _PERMANENTLY_FAILED.discard(paper_id)

    # 제목 검증 — 등록을 막지 않는다. 판정만 반환값에 실어 보내고, 경고 표시 여부는
    # 소비하는 쪽(라이브러리 UI) 몫(title_check.py 참고).
    given_title = (bibliographic or {}).get("title")
    title_check = classify_title_match(given_title, parsed.get("pdf_title"))

    # 카탈로그 연동 — 추천 검색이 이미 심어둔 recommended 행이 있으면 owned로 전환,
    # 없으면 새로 만든다(paper_catalog.mark_owned() 참고). cross-id 매칭(추천 시점
    # arxiv_id만 있었는데 등록 시점에 다른 DOI가 들어와 paper_id가 바뀌는 경우)은
    # 아직 안 함 — 실제로 걸리면 doi/arxiv_id 컬럼으로 기존 행을 찾는 로직을 추가한다.
    paper_catalog.mark_owned(
        paper_id,
        doi=doi,
        arxiv_id=arxiv_id,
        title=bib_meta.get("title", ""),
        authors=bib_meta.get("authors", ""),
        year=bib_meta.get("year", ""),
        filename=filename,
    )

    return {
        "paper_id": paper_id,
        "text_extractable": True,
        "chunk_count": len(pieces),
        "page_count": parsed["page_count"],
        "title_check": {"status": title_check, "given_title": given_title, "pdf_title": parsed.get("pdf_title")},
    }


def _fetch_abstract(vectorstore, paper_id: str) -> str | None:
    """저장된 doc_type="abstract" 문서의 텍스트를 반환한다(없으면 None) —
    get_paper_summary()가 추출 프롬프트의 앵커로 쓴다."""
    result = vectorstore.get(where={"$and": [{"paper_id": paper_id}, {"doc_type": "abstract"}]})
    documents = result.get("documents", [])
    return documents[0] if documents else None


def _pick_bib_meta(metadata: dict) -> dict:
    """청크 메타데이터 하나에서 서지 필드만 골라내는 순수 함수 — 모든 청크에 같은
    값이 복제돼 있어 어느 청크를 넣어도 결과가 같다."""
    return {k: metadata[k] for k in _BIBLIOGRAPHIC_WHITELIST if k in metadata}


def _fetch_fulltext(vectorstore, paper_id: str) -> tuple[list[dict], dict]:
    """등록된 fulltext_chunk를 index 순서로 모으고(is_references 조각은 추출 입력에서
    제외) 청크에 복제된 서지 필드도 같이 반환한다(한 조회로 같이 받아 중복 조회 방지).

    반환: (chunks, bib_meta) — chunks는 [{"text", "index", "is_references"}, ...]"""
    result = vectorstore.get(where={"$and": [{"paper_id": paper_id}, {"doc_type": "fulltext_chunk"}]})
    metadatas = result["metadatas"]
    bib_meta = _pick_bib_meta(metadatas[0]) if metadatas else {}

    items = [
        {"text": doc, "index": meta.get("index", 0), "is_references": meta.get("is_references", False)}
        for doc, meta in zip(result["documents"], metadatas)
    ]
    items.sort(key=lambda c: c["index"])
    return [c for c in items if not c["is_references"]], bib_meta


def _fetch_summary(vectorstore, paper_id: str) -> PaperExtraction | None:
    result = vectorstore.get(where={"$and": [{"paper_id": paper_id}, {"doc_type": "summary"}]})
    metadatas = result.get("metadatas", [])
    if not metadatas:
        return None
    # .get()으로 받는다 — 스키마가 바뀌면 대괄호 접근은 KeyError로 조회 자체를 터뜨린다.
    # 없으면 캐시 미스로 취급(재생성이 정답이므로 충분).
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


def _store_summary(vectorstore, paper_id: str, extraction: PaperExtraction, bib_meta: dict | None = None) -> None:
    # 삽입 전 한 번 더 삭제 — 동시 호출 등 안전망(주 무효화 경로는 register_paper()의 재등록 삭제).
    vectorstore.delete(where={"$and": [{"paper_id": paper_id}, {"doc_type": "summary"}]})
    vectorstore.add_texts(
        texts=[_render_summary_text(extraction)],
        metadatas=[{
            "paper_id": paper_id,
            "doc_type": "summary",
            "extraction_json": extraction.model_dump_json(),
            **(bib_meta or {}),  # _fetch_fulltext()가 청크에서 뽑아 넘겨준 title 등
        }],
        ids=[f"{paper_id}-summary"],
    )


def get_paper_summary(paper_id: str, *, model: str = BACKGROUND_SUMMARY_MODEL, vectorstore=None) -> dict:
    """paper_id의 구조화 요약을 lazy 생성 후 캐시해 반환한다.

    캐시(doc_type=summary)가 있으면 그대로 반환(추가 LLM 호출 0). 없으면 등록된
    fulltext_chunk를 모아(is_references 제외) 구조화 추출을 한 번 시도한다. abstract가
    있으면 프롬프트 앵커로 같이 보낸다(ABSTRACT_ANCHOR_INSTRUCTION). 컨텍스트 예산
    초과 시 ContextBudgetExceeded를 여기서 안 잡고 그대로 전파 — 호출한 쪽(라이브러리
    UI·QA)이 "요약 생성 불가"로 정직하게 고지한다.

    paper_id가 등록된 적 없으면(fulltext_chunk 없음) ValueError.

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

    chunks, bib_meta = _fetch_fulltext(vectorstore, paper_id)
    if not chunks:
        raise ValueError(f"paper_id={paper_id!r}: 등록된 전문 청크가 없음 — register_paper()를 먼저 호출해야 함")

    full_text = "\n\n".join(c["text"] for c in chunks)

    # abstract를 앵커로 추가 제공(없으면 human_content는 full_text 그대로, 회귀 없음) —
    # abstract는 full_text 안에도 이미 있으므로 이건 강조 중복이지 정보 보충이 아니다.
    abstract = _fetch_abstract(vectorstore, paper_id)
    if abstract:
        system_prompt = EXTRACTION_SYSTEM_PROMPT + ABSTRACT_ANCHOR_INSTRUCTION
        human_content = f"[논문 초록]\n{abstract}\n\n[본문]\n{full_text}"
    else:
        system_prompt = EXTRACTION_SYSTEM_PROMPT
        human_content = full_text

    # 실제로 LLM에 보낼 최종 텍스트(abstract 포함) 기준으로 검사 — full_text만 검사하면
    # abstract를 더해 예산을 살짝 넘긴 경계 케이스를 놓친다.
    check_context_budget(model, human_content)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]
    extraction, generated_by, _disabled_models, tokens_used = invoke_with_fallback(
        model, messages, structured=PaperExtraction
    )

    _store_summary(vectorstore, paper_id, extraction, bib_meta)

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

# 재시도해도 똑같이 실패할 게 확실한 paper_id 집합 — ContextBudgetExceeded는 같은
# 모델·같은 텍스트면 항상 다시 넘친다. 기록 안 하면 매 조회마다 무의미한 스레드가
# 뜬다. 일시적 실패(네트워크 등)는 여기 안 넣어 계속 재시도되게 둔다. register_paper()가
# 재등록 시 지운다(전문이 바뀌면 다시 확인해볼 가치가 있음).
_PERMANENTLY_FAILED: set[str] = set()


def _spawn_background(fn) -> None:
    """실제로 daemon thread를 띄우는 부분만 분리해둔 한 줄짜리 함수 — 테스트에서
    monkeypatch로 동기 실행(즉시 fn() 호출)이나 no-op으로 갈아끼우기 위한 지점이다."""
    threading.Thread(target=fn, daemon=True).start()


def ensure_summary_in_background(paper_id: str, *, model: str = BACKGROUND_SUMMARY_MODEL, vectorstore=None) -> bool:
    """paper_id에 캐시된 요약이 없으면 백그라운드에서 생성을 시작한다. 이번 턴의
    응답은 막지 않는다 — model은 호출자의 state.model이 아니라 항상
    BACKGROUND_SUMMARY_MODEL(공유 캐시라 예산 가장 넉넉한 모델로 고정).

    이미 요약이 있거나 생성 중이거나 영구 실패로 기록됐으면 아무것도 안 하고 False.
    새로 시작했으면 True(완료 여부와는 무관 — 완료는 다음 조회 때 캐시로 확인됨).
    """
    vectorstore = vectorstore or _get_papers_vectorstore()

    # 영구 실패 집합 확인이 먼저 — 메모리 조회라 공짜지만 _fetch_summary()는 DB 조회.
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
            # 같은 모델·같은 텍스트로는 다시 불러도 항상 똑같이 예산을 넘는 결정론적
            # 실패 — 영구 실패로 기록(register_paper() 재등록 시 지워짐).
            _PERMANENTLY_FAILED.add(paper_id)
            print(f"백그라운드 요약 생성 영구 실패(재등록 전까지 재시도 안 함, paper_id={paper_id}): {e}")
        except Exception as e:
            # 일시적 실패는 기록하지 않음 — 다음 조회 때 캐시가 여전히 없어 자연히 재시도됨.
            print(f"백그라운드 요약 생성 실패 (paper_id={paper_id}): {type(e).__name__}: {e}")
        finally:
            with _IN_FLIGHT_LOCK:
                _IN_FLIGHT.discard(paper_id)

    _spawn_background(_run)
    return True


if __name__ == "__main__":
    # 수동 스모크 테스트용 — pytest는 vectorstore/parse_pdf를 전부 가짜로 갈아끼운
    # 순수 로직 검증이라, 진짜 PyMuPDF+Chroma+LLM이 실제로 맞물려 도는지는 이 경로로 확인.
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
