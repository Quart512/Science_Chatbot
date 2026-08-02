# README_13 — 라이브러리 표면 1차 + 관심사 수정/재검색 + 모델 fallback 버그 수정

> RoadMap.md 완료 표는 짧게 요약만 남기고, 이 문서에 각 결정의 배경과 트레이드오프를 그대로 옮겨둔다.

## 0. 이번 주 한눈에

- **08-09 마무리**: `register_paper()`가 카탈로그 상태를 `owned`로 전환하도록 연동 — 08-09(추천 검색+스크리닝+카탈로그) 전체 완료.
- **08-11 라이브러리 표면 1차**: Streamlit을 멀티페이지로 전환하고 논문 탭·관심사 탭을 만들었다. 백엔드에 처음으로 `POST /papers`, `GET /interests`, `DELETE /interests/{id}`, `GET /papers`, `POST /interests/{id}/refresh`를 열었다.
- **관심사 탭 개선 3종**: 검색 페이지네이션(추가 검색), 관심사 수정 시 자동 재검색, 검색/추가 검색 버튼 통합.
- **버그 2건 발견·수정**: `models.py`의 `invoke_with_fallback()` 예외 화이트리스트가 최신 SDK 예외 타입을 못 잡아 fallback 없이 500까지 새던 문제.
- **모델 교체**: `gemini-2.5-flash` → `gemini-3.5-flash-lite` (무료 티어 일일 한도가 훨씬 높음), 컨텍스트 예산도 200만 자로 상향.
- **문서·주석 정리**: 코드 전체를 순회하며 장황한 이력 나열식 주석을 "왜"만 남기고 축약, 상세 이력은 이 문서로 이관.

---

## 1. `register_paper()` 카탈로그 연동 (08-09 마무리)

`paper/paper_ingest.py`의 `register_paper()`가 정상 등록(text_extractable) 시 `paper_catalog.mark_owned()`를 호출하도록 연결했다. 추천 검색(③)이 `upsert_recommended()`로 이미 심어둔 `recommended` 행이 있으면 `owned`로 전환하고, 없으면(추천 없이 바로 등록한 논문) 새로 만든다. `title`/`authors`/`year`는 등록 과정에서 이미 계산해둔 `bib_meta`(화이트리스트로 거른 서지정보)를 재사용 — 새로 뽑지 않는다.

**스캔본은 카탈로그도 안 건드린다** — VDB에 아무것도 저장하지 않는 것과 대칭. 카탈로그 쓰기 실패는 arxiv 자동조회(네트워크, best-effort)와 달리 삼키지 않고 그대로 전파한다 — "카탈로그에 반영됨"이 이제 이 함수 계약의 일부이기 때문이다.

**cross-id 매칭은 의도적으로 미뤘다**: 추천 시점엔 arxiv_id만 있어 `paper_id`가 `arxiv:XXXX`로 계산됐는데, 등록 시점에 사용자가 (arxiv가 안 준) DOI를 새로 넘기면 `normalize_paper_id()`가 DOI 우선이라 `paper_id`가 바뀌어 기존 `recommended` 행을 못 찾고 새 행이 생기는 경우가 있다. 라이브러리 UI가 아직 없어 이런 입력이 실제로 어떻게 들어올지 모르는 채로 매칭 로직을 미리 만들 근거가 없었다 — 실제로 걸리면 그때 doi/arxiv_id 컬럼으로 보완한다.

테스트 2개 추가(카탈로그 호출 인자 확인, 스캔본 스킵 확인) + 기존 테스트가 실제 `data/app.db`를 안 건드리게 `mark_owned`를 기본 no-op으로 스텁하는 autouse fixture 추가.

---

## 2. 08-11 라이브러리 표면 1차

### 2.1 순서 재검토

원래 로드맵 순서는 08-10(메인 챗 라우터) → 08-11(라이브러리 표면)이었다. 08-10을 먼저 설계하다가 막혔다 — 라우터가 라우팅할 대상 중 "문서 작성기"(⑦)는 아직 없고, "추천 조회"도 막상 보니 `paper_catalog`에 `interest_id` 연결이 없어 "이 관심사에 추천된 논문"처럼 특정해서 못 물어본다(전역 목록만 가능). 게다가 07-24 아키텍처 개편 이후 "추천 조회"는 원래 메인 챗이 아니라 **라이브러리 표면**(전용 UI 버튼)이 맡는 게 자연스럽다 — 사용자 지적으로 순서를 뒤집어 08-11을 먼저 하기로 했다.

### 2.2 프론트 스택 — Streamlit 유지

로드맵은 "표면 4개엔 Streamlit 한계, React 등 전환 검토"를 08-11과 겸행하기로 했었다. 이번엔 Streamlit을 유지하기로 결정했다 — 백엔드 엔드포인트는 스택과 무관하고, `st.navigation()`이 멀티페이지 전환에 저비용이라 지금 화면부터 만들고, React 전환이 필요해지면(화면이 더 늘거나 한계에 부딪히면) 백엔드는 그대로 두고 화면만 새로 짜면 된다.

### 2.3 멀티페이지 전환

`frontend/app.py`를 `st.navigation()`+`st.Page()`로 네비게이션만 담당하게 바꾸고, 기존 챗 화면은 `frontend/views/chat.py`로 그대로 옮겼다(기능 변경 없음). `pages/` 디렉터리 자동 인식 방식(구 Streamlit 관례) 대신 `st.navigation()`을 쓴 이유: 파일명 슬러그로 페이지 이름이 정해지는 관례보다 그룹(메인/라이브러리)·아이콘·기본 페이지를 명시적으로 통제할 수 있어서다.

### 2.4 논문 탭 (`frontend/views/papers.py`)

- **`POST /papers`(신규)**: `register_paper()`가 지금까지 `paper/paper_ingest.py`의 `__main__` 스모크 테스트로만 호출되던 걸 API로 처음 노출했다. `register_paper()`가 `pdf_path`(디스크 경로)를 받는 시그니처라, 업로드 바이트를 임시 파일에 한 번 써서 그 경로를 넘긴다(`register_paper()` 자체를 bytes 인자로 바꾸는 건 이 엔드포인트 하나만을 위한 리팩터링이라 범위 밖으로 뒀다). `fitz.FileDataError`(PyMuPDF가 유효한 PDF가 아니라고 판단할 때)는 사용자 입력 검증 경계에서 나는 에러라 500이 아니라 400으로 변환한다 — 지금까지 `register_paper()`의 유일한 호출자(CLI 스모크 테스트)는 항상 진짜 PDF를 줬으니 이 실패 모드를 신경 쓸 필요가 없었지만, API로 노출되는 순간 신뢰 못 할 입력이 된다.
- **`GET /papers`(신규)**: 카탈로그 전역 조회(`status` 쿼리 파라미터로 필터). 관심사별 필터는 `interest_paper` 조인 테이블이 없어 아직 불가.
- 등록 폼 제출 후 `title_check.status == "different_paper"`면 경고 표시, 카탈로그 목록은 고정 높이(300px) 테이블로 내부 스크롤(안 그러면 논문이 많아질수록 페이지가 계속 늘어남).

브라우저로 실제 14페이지 PDF를 등록해 확인 — 122개 청크, `status: "owned"`로 카탈로그 반영까지 실제 API 경로로 재확인됐다.

### 2.5 관심사 탭 (`frontend/views/interests.py`) — 1차

- **`GET /interests`(신규)**: 지금까지 생성(`POST`)만 API로 열려 있고 조회가 없었다.
- **`DELETE /interests/{id}`(신규)**: `interests.py`에 `delete_interest()` 추가. `interest_paper` 조인 테이블이 아직 없어 이 관심사가 추천한 카탈로그 행을 같이 지울지는 그 테이블이 생길 때 정하기로 하고, 지금은 `interests` 테이블 행 하나만 지운다.
- **수동 생성 폼**: 관심사를 만드는 원래 경로는 챗의 제안 흐름(`suggest_interest_node`가 초안을 만들면 "관심사 등록" 버튼으로 저장)이지만 그 버튼이 아직 프론트에 안 붙어 있어, 관리 UI답게 직접 만드는 경로도 같이 뒀다.
- 카드별 **수정** 폼은 기존 `POST /interests`의 `update_existing_id`를 그대로 재사용.

---

## 3. 관심사 탭 개선 3종 (같은 세션 내 추가 요청)

### 3.1 추천 검색 페이지네이션 — "추가 검색"

기존 "지금 검색" 버튼은 매번 `start=0`으로 같은 상위 결과만 돌려줬다. `arxiv_search()`가 `start`를 0으로 고정해뒀던 걸 열어 `paper_search.search_papers()` → `paper_recommend.recommend_for_interest()` → `POST /interests/{id}/search?start=`까지 관통시켰다. 프론트는 세션에 지금까지 받은 개수(offset)를 들고 있다가 다음 페이지 요청에 그대로 넘긴다.

### 3.2 관심사 수정 시 자동 재검색

사용자 지적: "관심사가 수정되면 수정된 내용에 따라 다시 검색해야 하는데, 기존에 검색했던 논문을 활용할 수 없을까?" — 수정이 큰 변화가 아닐 수도 있으니 기존 후보를 버리지 말자는 취지.

`paper_recommend.refresh_for_interest(interest_id, existing_candidates)`를 새로 만들었다:
1. 프론트가 세션에 쌓아둔 기존 후보(이미 한 번 스크리닝된 것)를 **수정된 관심사 기준으로 재스크리닝**해서 관련 있는 것만 남긴다(관련 없어진 건 버림).
2. 동시에 `recommend_for_interest()`로 **새 페이지 하나(`start=0`)를 정상 검색**한다(카탈로그 upsert도 그 경로가 기존과 똑같이 처리).
3. 겹치는 `paper_id`는 새 쪽에서 제거(중복 표시 방지), 합쳐서 관련도로 재정렬.

**구현상 트릭**: 프론트가 들고 있는 기존 후보 dict엔 `journal_ref` 원본이 없다(`peer_reviewed` bool로만 축약돼 전달됨). `screen_candidate()`는 `candidate.get("journal_ref")`로 `peer_reviewed`를 재계산하므로, 역산해서 `peer_reviewed=True`였으면 아무 비어있지 않은 문자열을 `journal_ref`에 채워 넣는다 — `bool(journal_ref)`가 다시 `True`로 복원되기만 하면 되고, 이건 재판정이 아니라 값을 보존하는 것뿐이다.

**재스크리닝으로 살아남은 기존 후보는 카탈로그에 재upsert하지 않는다** — 프론트가 들고 있던 후보엔 애초에 doi/arxiv_id가 없어(첫 검색 응답에도 안 실었음) 정확한 메타데이터로 넣을 수 없고, "카탈로그에 남기는 것"과 "화면에 보여주는 것"을 분리하는 `paper_recommend.py`의 기존 원칙과도 맞다.

**보류한 것**: 애초엔 "기존 것과 별개로 한 번 더 신선한 재검색"도 하자는 이야기가 있었지만, 실제로는 "재검색"이라는 별도 메커니즘을 만드는 대신 그냥 기존 검색/추가 검색 버튼을 다시 누르면 되는 걸로 정리됐다 — 관심사가 수정되면 그다음 검색 클릭이 자연히 새 기준을 반영하기 때문이다.

### 3.3 검색/추가 검색 버튼 통합

두 버튼(지금 검색 / 추가 검색)이 나란히 있는 대신, 하나의 버튼이 상태에 따라 라벨과 동작을 바꾼다 — 카드에 쌓인 결과가 없으면 "지금 검색"(`start=0`), 있으면 "추가 검색"(`start=offset`)으로. 버튼 클릭 직후 `st.rerun()`을 명시적으로 호출하는데, 이는 Streamlit이 클릭 시 이미 한 번 스크립트를 재실행한 상태라 세션 상태 갱신 후 라벨이 즉시 "추가 검색"으로 바뀌려면 한 번 더 재실행이 필요하기 때문이다(안 그러면 다음 상호작용 전까지 라벨이 낡은 채로 남는다).

### 3.4 표시 개선

- "관련 있음" O/X 컬럼을 없애고, 이미 관련도순으로 정렬돼 오는 순서를 그대로 신뢰해 순위 번호로 대체했다.
- 결과 테이블에 고정 높이(300px)를 줘서 내부 스크롤로 바꿨다(논문 탭의 카탈로그 테이블도 동일 처리).

---

## 4. `invoke_with_fallback` 예외 화이트리스트 갭 2건

라이브러리 UI 실사용(관심사 검색) 중 API 쿼터/크레딧 소진이 겹쳐 발견했다.

**(1) `google.genai.errors.ServerError`**: `langchain_google_genai`가 내부적으로 `google-genai` SDK로 갈아탄 뒤로, gemini 과부하(503)가 `ChatGoogleGenerativeAIError`로 안 감싸이고 그 SDK의 원본 예외 그대로 올라온다. 잡지 않으면 fallback을 못 타고 `RuntimeError`도 아니라서 호출부(`screen_candidate` 등)의 "실패한 후보만 건너뛴다" 처리도 못 받고 그대로 500까지 샜다(실제 재현). `ClientError`(4xx)/`ServerError`(5xx) 둘 다의 공통 부모(`google.genai.errors.APIError`)를 잡아 전부 fallback 대상으로 포함시켰다.

**(2) `anthropic.BadRequestError`**: anthropic 계정 크레딧 부족도 400(`BadRequestError`)으로 온다. 기존 화이트리스트의 `openai.BadRequestError`와 이름은 같지만 서로 다른 SDK의 별개 클래스라 하나를 잡는다고 다른 하나까지 잡히지 않는다 — 실제로 gemini 쿼터 소진 → claude로 fallback → claude도 크레딧 부족으로 실패하는 이중 장애를 겪으며 발견했다.

`models.py`의 예외 화이트리스트에 두 타입 다 추가하고, 회귀 테스트 2개(각각 실제 예외 인스턴스를 구성해 fallback이 정상적으로 다음 모델로 넘어가는지 확인) 추가.

---

## 5. Gemini 모델 교체

사용자 제보: `gemini-3.5-flash-lite`가 `gemini-2.5-flash`보다 무료 티어 일일 요청 한도가 훨씬 높다. 구글 공식 모델 문서(`ai.google.dev/gemini-api/docs/models`)와 AI Studio 요금 한도 페이지로 모델 ID(`gemini-3.5-flash-lite`, 실존 확인)와 컨텍스트 윈도우(1M 토큰급, 기존과 동급)를 확인한 뒤 `model_map["gemini"]`를 교체했다. 컨텍스트 윈도우가 동급이라 `CONTEXT_BUDGET_CHARS["gemini"]`는 안전 마진을 더 늘려 200만 자로 상향했다(기존 80만 자 — 논문 전문이 걸릴 여지를 더 줄이려는 목적, flash-lite도 1M 토큰급이라 여유 있음).

`evaluation/evaluate.py`가 별도로 `gemini-2.5-flash`를 하드코딩해 쓰는 곳(judge 등)은 재현성 목적의 독립적인 선택이라 이번 교체 범위에서 제외했다.

---

## 6. 코드·문서 정리

세션 막바지에 "주석·독스트링이 너무 장황하다"는 피드백을 받아 코드 전체(root .py, `paper/*.py`, `frontend/*.py`)를 순회하며 정리했다. 원칙:

- 이력을 날짜·세션 번호("07-31, 사용자 지적으로")로 나열하던 부분은 제거하고 "왜"만 남긴다.
- 여러 문단에 걸쳐 같은 설명을 반복하던 부분(예: References/Abstract 판정이 "헤더 계층 전체"를 봐야 하는 이유가 `paper_chunking.py`에서 4번 반복됨)은 모듈 docstring 한 곳에만 남기고 함수별 설명은 짧게 참조만.
- 실제 LLM 프롬프트 문자열(시스템 프롬프트, Pydantic `Field(description=...)`)은 건드리지 않음 — 이건 "주석"이 아니라 기능이다.
- 코드에서 걷어낸 이력·결정 배경은 이 문서(README_13)로 옮기고, RoadMap.md의 완료 표는 "무엇을 했는지" 한두 줄 요약 + 이 문서 링크로 축약했다.

이 작업은 여러 파일에 걸친 기계적 축약이라 매 파일마다 전체 회귀 테스트를 돌리진 않고, `paper/*.py`·`frontend/*.py` 단위로 묶어 pytest를 확인했다(전체 205개 통과 유지).
