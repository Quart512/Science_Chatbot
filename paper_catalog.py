# 논문 카탈로그 — RDB(SQLite). 논문 VDB(paper/paper_ingest.py)가 "내용 검색"을 맡고
# 여기는 "상태 관리"(등록 여부·추천/보유/기각·서지정보)만 맡는다. interests.py와 같은
# data/app.db를 다른 테이블로 공유(RoadMap "VDB vs RDB" 참고) — 경로 상수도 그쪽을 참조.
#
# 기본 키는 paper_id(normalize_paper_id: DOI>arXiv>해시, 한 번 정해지면 불변) — doi/
# arxiv_id는 nullable·unique 별도 컬럼으로 둬서, paper_id 하나로 못 잡는 매칭(추천
# 시점엔 arxiv_id만 알았는데 등록 시점엔 doi가 생기는 경우 등)을 보완할 여지를 남긴다.
# 실제 cross-id 매칭 로직은 아직 없음(단순 경로부터 — 필요해지면 이 컬럼으로 보완).
#
# 지표 필드(journal_ref, citation_count)는 계산 없이 컬럼만 미리 둔다 — 나중에 외부
# API 어댑터를 붙일 때 이 컬럼만 채우면 되게. status는 전용 함수(upsert_recommended/
# mark_owned/dismiss)로만 바꾼다 — 임의 필드 갱신 API는 안 둔다.
#
# interest_paper(08-03 추가) — 관심사↔논문 다대다 조인. papers 테이블(전역 상태)만
# 있으면 "이 관심사에 추천된 논문"을 못 구한다 — 한 논문이 여러 관심사와 관련될 수
# 있어 어느 한쪽에 태그를 붙이는 방식(예: papers에 interest_id 컬럼)은 안 맞는다.
# ③ 추천 검색(paper_recommend.py)이 스크리닝한 후보마다(관련 있음/없음 둘 다) 여기
# 기록한다 — 반환 목록이 이미 둘 다 포함하는 것과 같은 이유("추천에서 끝나고 결정은
# 사람이"). is_relevant/reasoning은 자동 계산된 신호일 뿐 사용자 결정이 아니므로
# upsert_recommended와 달리 재스크리닝 시 최신 값으로 덮어쓴다(record_screening 참고).

import os
import sqlite3
from datetime import datetime, timezone

import interests

APP_DB_PATH = interests.APP_DB_PATH

# library/ 루트(저장소·배포 루트에 나란히, docker-compose.yml이 여기로 바인드 마운트) —
# 08-05 설계 노트 "논문·노트 저장 방식 재설계" 참고. file_path 컬럼은 이 루트 기준
# 상대경로만 담으므로, 절대경로 조립·traversal 방어가 필요한 곳은 전부 이 상수를 기준점으로 쓴다.
LIBRARY_DIR = "library"

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    paper_id TEXT PRIMARY KEY,
    doi TEXT UNIQUE,
    arxiv_id TEXT UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    authors TEXT NOT NULL DEFAULT '',
    year TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'recommended' CHECK(status IN ('recommended', 'owned', 'dismissed')),
    journal_ref TEXT,
    citation_count INTEGER,
    filename TEXT NOT NULL DEFAULT '',
    file_path TEXT,
    content_sha256 TEXT,
    analysis_status TEXT NOT NULL DEFAULT 'untracked',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interest_paper (
    interest_id INTEGER NOT NULL,
    paper_id TEXT NOT NULL,
    is_relevant INTEGER NOT NULL,
    reasoning TEXT NOT NULL DEFAULT '',
    screened_at TEXT NOT NULL,
    PRIMARY KEY (interest_id, paper_id)
);
"""

# CREATE TABLE IF NOT EXISTS는 테이블이 이미 있으면 새로 추가한 컬럼(filename)을 기존
# DB에 안 만든다 — equipment.py가 precautions 컬럼에서 실제로 겪은 문제(§7.4 참고)와
# 같은 패턴이라 같은 방식으로 막는다. 배포 환경(EC2 바인드 마운트)의 기존 papers
# 테이블에 이 코드를 올리면 filename 없이 INSERT하다 "no such column"으로 터진다.
#
# file_path/content_sha256/analysis_status(08-05, "논문 파일 경로 추적 재설계" 착수
# ①) — RoadMap 설계 노트 참고. file_path는 library/ 루트 기준 **상대경로**로 둔다(절대
# 경로면 컨테이너 마운트 지점이 바뀌거나 portable 번들로 옮겨질 때 깨진다 — 설계 노트
# 항목 A). content_sha256은 DOI/arXiv 논문의 paper_id가 해시가 아니라(normalize_paper_id:
# DOI>arXiv>해시 우선순위) 그 경우도 파일↔레코드를 매칭할 별도 컬럼이 필요해서 둔다
# (설계 노트 항목 C — "경로는 변할 수 있는 속성, 해시가 신원"). analysis_status는 등록
# (트래킹)과 분석(파싱·색인)을 분리하는 다음 단계(설계 노트 항목 G)를 위해 미리 컬럼만
# 마련 — 지금은 아무 코드도 이 값을 안 채운다.
_EXPECTED_COLUMNS = {
    "filename": "TEXT NOT NULL DEFAULT ''",
    "file_path": "TEXT",
    "content_sha256": "TEXT",
    "analysis_status": "TEXT NOT NULL DEFAULT 'untracked'",
}


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(papers)")}
    for name, ddl in _EXPECTED_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE papers ADD COLUMN {name} {ddl}")
    conn.commit()


def _get_connection() -> sqlite3.Connection:
    # interests._get_connection()을 재사용하지 않는다 — 그건 interests 스키마까지
    # 같이 적용해 책임이 섞인다. 경로 상수만 참조하고 스키마 적용은 각자 한다.
    os.makedirs(os.path.dirname(APP_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_paper(paper_id: str, *, conn: sqlite3.Connection | None = None) -> dict | None:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
        return dict(row) if row else None
    finally:
        if owns_conn:
            conn.close()


def list_papers(*, status: str | None = None, conn: sqlite3.Connection | None = None) -> list[dict]:
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        if status is None:
            rows = conn.execute("SELECT * FROM papers ORDER BY paper_id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM papers WHERE status = ? ORDER BY paper_id", (status,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns_conn:
            conn.close()


def resolve_library_path(rel_path: str) -> str:
    """library/ 루트 기준 상대경로를 절대경로로 바꾸고 traversal을 막는다(②-B "트래킹에
    추가" 엔드포인트 전용 — RoadMap 설계 노트 §A가 ③ PDF 뷰어에 대해 짚어둔 것과 같은
    종류의 방어). scan_library_files()와 달리 여기 rel_path는 **사용자가 요청 본문으로
    직접 주는 값**이라 "../../etc/passwd" 같은 입력이 실제로 올 수 있다.

    검사를 os.path.realpath가 아니라 os.path.normpath로 한다(08-05, "라이브러리 외부
    경로 추적" — RoadMap 설계 노트 참고) — realpath는 심볼릭 링크까지 다 풀어버려서
    "../"로 벗어나려는 시도(막아야 함)와 사용자가 library/ 안에 일부러 걸어둔 심볼릭
    링크(허용해야 함 — portable 번들에서 library/ 밖 폴더를 원래 경로 그대로 추적하는
    수단)를 구분하지 못했다. normpath는 심볼릭 링크를 안 건드리고 "../"·"." 같은 문자열
    구조만 정규화하므로 — "../../etc/passwd"는 여전히 걸러지고, "external_link/foo.pdf"
    (링크 자체는 library/ 안에 있으므로 문자열상 안 벗어남)는 통과한다. 실제 파일을 열
    때는 OS가 알아서 링크를 따라간다(Docker에서는 컨테이너가 링크 target을 못 보므로
    자연히 깨진 링크로 실패 — scan_library_files()가 이미 걸러줌)."""
    library_root = os.path.realpath(LIBRARY_DIR)
    normalized = os.path.normpath(os.path.join(library_root, rel_path))
    if normalized != library_root and not normalized.startswith(library_root + os.sep):
        raise ValueError(f"library/ 루트를 벗어난 경로입니다: {rel_path}")
    return normalized


def scan_library_files(*, conn: sqlite3.Connection | None = None) -> list[dict]:
    """library/ 밑의 PDF를 재귀로 나열하고 papers.file_path와 대조해 tracked 여부를
    붙인다(②-A, 서버측 파일 브라우저의 스캔 단계 — RoadMap 설계 노트 참고). 반환:
    [{"path": "quantum/foo.pdf", "tracked": bool}, ...], path는 LIBRARY_DIR 기준
    상대경로(os.sep과 무관하게 항상 "/" 구분자로 통일 — 프론트·API 응답은 플랫폼 중립이어야 함).

    파일시스템 읽기 + DB 조회만 하는 순수 조회 함수(LLM·네트워크 없음).

    심볼릭 링크를 따라간다(followlinks=True, 08-05 "라이브러리 외부 경로 추적" —
    RoadMap 설계 노트 참고) — portable 파이썬 번들(컨테이너 경계 없음)에서 사용자가
    library/ 밖 폴더·파일을 원래 경로 그대로 추적하고 싶을 때, library/ 안에 심볼릭
    링크만 걸어두면 되게 하기 위해서다. Docker 배포에서는 컨테이너가 바인드 마운트
    밖의 호스트 경로를 애초에 못 보므로 그런 링크는 깨진 링크로 남고, os.path.isfile()이
    깨진 링크에 False를 돌려줘 자연히 스캔에서 빠진다 — 코드 분기 없이 두 배포 방식
    모두 안전하게 동작. 순환 심볼릭 링크(예: library/self -> library/)로 무한 루프에
    빠지지 않게 실제 경로(realpath) 기준으로 이미 방문한 디렉터리는 다시 안 내려간다.
    """
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        tracked_paths = {
            row[0]
            for row in conn.execute("SELECT file_path FROM papers WHERE file_path IS NOT NULL").fetchall()
        }
        library_root = os.path.realpath(LIBRARY_DIR)
        files = []
        seen_dirs = set()
        for dirpath, dirnames, filenames in os.walk(library_root, followlinks=True):
            real_dirpath = os.path.realpath(dirpath)
            if real_dirpath in seen_dirs:
                dirnames[:] = []  # 이미 방문한 실제 디렉터리 — 순환 방지, 더 안 내려감
                continue
            seen_dirs.add(real_dirpath)
            for name in filenames:
                if not name.lower().endswith(".pdf"):
                    continue
                full_path = os.path.join(dirpath, name)
                if not os.path.isfile(full_path):
                    continue  # 깨진 심볼릭 링크(Docker에서 컨테이너 밖 경로를 가리키는 경우 등) 무시
                rel_path = os.path.relpath(full_path, library_root).replace(os.sep, "/")
                files.append({"path": rel_path, "tracked": rel_path in tracked_paths})
        files.sort(key=lambda f: f["path"])
        return files
    finally:
        if owns_conn:
            conn.close()


def unique_library_filename(filename: str) -> str:
    """filename을 library/ 루트에 저장할 때 기존 파일과 안 겹치는 이름을 고른다(⑤ 업로드
    재정의, 08-05 — 기존 업로드 다이얼로그를 "고른 파일을 library/에 복사해 넣기"로
    재정의하면서 필요해짐, RoadMap 설계 노트 참고). 겹치면 파일명 스템에 `_2`, `_3`...를
    붙인다. `os.path.basename`으로 먼저 정리한다 — 브라우저가 주는 `UploadFile.filename`은
    보통 파일명뿐이지만, 방어적으로 경로 구분자가 섞여 들어와도 library/ 루트 밖에 안 쓰게."""
    library_root = os.path.realpath(LIBRARY_DIR)
    safe_name = os.path.basename(filename) or "업로드.pdf"
    stem, ext = os.path.splitext(safe_name)
    candidate = safe_name
    n = 2
    while os.path.exists(os.path.join(library_root, candidate)):
        candidate = f"{stem}_{n}{ext}"
        n += 1
    return candidate


def upsert_recommended(
    paper_id: str,
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    title: str = "",
    authors: str = "",
    year: str = "",
    conn: sqlite3.Connection | None = None,
) -> bool:
    """추천 검색(③)이 새 후보를 카탈로그에 기록한다. paper_id가 이미 있으면(추천이든
    보유든 기각이든) **손대지 않는다** — 특히 이미 owned/dismissed인 논문을 추천 검색이
    다시 찾아냈다고 recommended로 되돌리면 사용자가 이미 내린 결정(등록·기각)이 조용히
    뒤집힌다. 반환값은 "새로 추가됐는지" — 이미 있어서 스킵됐으면 False.

    filename이 없는 이유: 추천 후보는 검색 결과(arxiv 등)에서 오므로 업로드 파일 자체가
    없다 — 빈 문자열로 남고, 실제 파일명은 사용자가 나중에 등록(mark_owned)할 때 채워진다.
    """
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        if conn.execute("SELECT 1 FROM papers WHERE paper_id = ?", (paper_id,)).fetchone():
            return False
        now = _now()
        conn.execute(
            "INSERT INTO papers (paper_id, doi, arxiv_id, title, authors, year, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'recommended', ?, ?)",
            (paper_id, doi, arxiv_id, title, authors, year, now, now),
        )
        conn.commit()
        return True
    finally:
        if owns_conn:
            conn.close()


def mark_owned(
    paper_id: str,
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    title: str = "",
    authors: str = "",
    year: str = "",
    filename: str = "",
    file_path: str | None = None,
    content_sha256: str | None = None,
    analysis_status: str = "done",
    conn: sqlite3.Connection | None = None,
) -> None:
    """paper_id를 owned로 표시한다 — 있으면 status만 바꾸고, 없으면 새로 만든다.
    register_paper()가 등록 성공 시 호출한다. filename(업로드 원본 파일명)은 title이
    비어있는 논문(서지정보를 못 찾은 경우)을 화면에서 해시 대신 사람이 읽을 수 있는
    이름으로 보여주는 차선책 — 08-04 사용자 요청("해쉬값은 최후순위, 파일명이 그 앞").

    file_path·content_sha256(08-05, ②-B "트래킹에 추가" — RoadMap 설계 노트 참고)은
    library/ 경유로 등록됐을 때만 채워진다(기존 업로드 다이얼로그 경로는 여전히 None) —
    filename과 같은 방식으로 UPDATE·INSERT 양쪽에 반영해, 이미 recommended로 존재하던
    논문을 library/에서 트래킹에 추가해도 경로가 누락되지 않게 한다.

    title/authors/year는 UPDATE 분기에서 **빈 문자열이면 기존 값을 유지**한다(COALESCE+
    NULLIF) — recommended 승격 시나리오(추천 검색이 이미 넣어둔 title을 owned 전환이
    지우면 안 됨, test_mark_owned_transitions_existing_recommended_to_owned)를 지키기
    위해서다. **이 조건부 UPDATE가 실제로 필요해진 계기(08-05 버그 발견·수정)**: ④ 파싱
    분리 이후 track_in_background()가 파싱 시작 전에 title 없이 먼저 이 함수를 불러 행을
    만들고, 파싱이 끝난 뒤 register_paper()가 실제 title로 다시 부르는 2단계 호출이
    표준 경로가 됐다 — 이때 두 번째 호출은 항상 "행이 이미 존재하는" UPDATE 분기를 타는데,
    예전 UPDATE문은 title/authors/year 컬럼 자체를 SET 절에 안 넣고 있었다. 그래서
    register_paper()가 실제 제목(arXiv 조회분 포함)을 넘겨도 조용히 저장되지 않았다 —
    무조건 덮어쓰는 방식(filename처럼) 대신 조건부로 고친 이유는 recommended 승격
    시나리오를 그대로 보존하기 위함.

    analysis_status(08-05, ④ 파싱 분리)의 기본값이 "done"인 이유: 이 함수의 기존
    호출부(register_paper()가 파싱·청킹·임베딩을 전부 마친 뒤 호출)는 호출 시점에
    분석이 이미 끝나 있으므로 인자를 안 줘도 자동으로 done이 찍힌다. ④가 새로 추가한
    "빠른 등록" 단계(paper_ingest.track_in_background())만 명시적으로 "pending"을
    넘긴다 — 나머지(analyzing/failed)는 set_analysis_status()가 이 함수를 거치지
    않고 그 컬럼만 갱신한다(다른 필드를 덮어쓸 위험 없이)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        if conn.execute("SELECT 1 FROM papers WHERE paper_id = ?", (paper_id,)).fetchone():
            conn.execute(
                "UPDATE papers SET status = 'owned', "
                "title = COALESCE(NULLIF(?, ''), title), "
                "authors = COALESCE(NULLIF(?, ''), authors), "
                "year = COALESCE(NULLIF(?, ''), year), "
                "filename = ?, file_path = ?, content_sha256 = ?, "
                "analysis_status = ?, updated_at = ? WHERE paper_id = ?",
                (title, authors, year, filename, file_path, content_sha256, analysis_status, now, paper_id),
            )
        else:
            conn.execute(
                "INSERT INTO papers (paper_id, doi, arxiv_id, title, authors, year, status, filename, "
                "file_path, content_sha256, analysis_status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'owned', ?, ?, ?, ?, ?, ?)",
                (
                    paper_id, doi, arxiv_id, title, authors, year, filename, file_path, content_sha256,
                    analysis_status, now, now,
                ),
            )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def set_analysis_status(paper_id: str, status: str, *, conn: sqlite3.Connection | None = None) -> bool:
    """analysis_status 컬럼만 갱신한다(④, 08-05) — mark_owned()와 달리 다른 필드는
    안 건드린다. track_in_background()의 백그라운드 스레드가 analyzing 진입·실패
    시점에 호출한다(성공 시점은 register_paper()가 끝에서 부르는 mark_owned()의
    analysis_status="done" 기본값으로 이미 반영됨 — 이 함수를 또 부를 필요 없음).
    존재하지 않는 paper_id면 False."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute(
            "UPDATE papers SET analysis_status = ?, updated_at = ? WHERE paper_id = ?",
            (status, _now(), paper_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


def dismiss(paper_id: str, *, conn: sqlite3.Connection | None = None) -> bool:
    """추천을 기각한다 — 기각 이력은 그 자체로 스크리닝 기준의 정답 레이블이 된다
    (RoadMap "기각 이력이 평가 기준의 정답 레이블" 참고). 존재하지 않는 paper_id면 False."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        cur = conn.execute(
            "UPDATE papers SET status = 'dismissed', updated_at = ? WHERE paper_id = ?",
            (_now(), paper_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        if owns_conn:
            conn.close()


def record_screening(
    interest_id: int, paper_id: str, *, is_relevant: bool, reasoning: str = "",
    conn: sqlite3.Connection | None = None,
) -> None:
    """관심사 하나가 논문 하나를 스크리닝한 결과를 기록한다(③ 추천 검색이 후보마다
    호출, 관련 있음/없음 둘 다) — 파일 상단 주석 참고. 같은 (interest_id, paper_id)
    쌍이 다시 채점되면(refresh_for_interest의 재스크리닝) 최신 판정으로 덮어쓴다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        now = _now()
        if conn.execute(
            "SELECT 1 FROM interest_paper WHERE interest_id = ? AND paper_id = ?",
            (interest_id, paper_id),
        ).fetchone():
            conn.execute(
                "UPDATE interest_paper SET is_relevant = ?, reasoning = ?, screened_at = ? "
                "WHERE interest_id = ? AND paper_id = ?",
                (is_relevant, reasoning, now, interest_id, paper_id),
            )
        else:
            conn.execute(
                "INSERT INTO interest_paper (interest_id, paper_id, is_relevant, reasoning, screened_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (interest_id, paper_id, is_relevant, reasoning, now),
            )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def list_papers_for_interest(
    interest_id: int, *, only_relevant: bool = False, conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """이 관심사에 스크리닝된 논문을 papers와 조인해 반환 — 서지정보(title 등)와 전역
    status(recommended/owned/dismissed)까지 함께 나온다. only_relevant=True면 관련
    있다고 판정된 것만(라이브러리 카드가 기본으로 보여줄 목록), 기본은 둘 다.

    LEFT JOIN을 쓴다 — 카탈로그(papers)는 "관련 있는 것만" 기록하는 게 기존 원칙
    (recommend_for_interest 참고)이라, 관련 없다고 판정된 논문은 papers에 행이 없다.
    INNER JOIN이면 그런 행이 통째로 사라져 "관련 없음도 기록한다"는 이 테이블의
    목적 자체가 조회에서 무효화된다. papers 쪽 필드는 없으면 전부 None으로 나온다."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        query = (
            "SELECT interest_paper.paper_id, papers.doi, papers.arxiv_id, papers.title, papers.authors, "
            "papers.year, papers.status, papers.journal_ref, papers.citation_count, "
            "interest_paper.is_relevant, interest_paper.reasoning, interest_paper.screened_at "
            "FROM interest_paper LEFT JOIN papers ON papers.paper_id = interest_paper.paper_id "
            "WHERE interest_paper.interest_id = ?"
        )
        params = [interest_id]
        if only_relevant:
            query += " AND interest_paper.is_relevant = 1"
        query += " ORDER BY interest_paper.is_relevant DESC, interest_paper.screened_at DESC"
        rows = conn.execute(query, params).fetchall()
        # sqlite3는 is_relevant를 0/1 정수로 돌려준다 — record_screening()이 bool을
        # 받는 것과 대칭으로 여기서 다시 bool로 되돌려 호출자가 int/bool을 안 헷갈리게 한다.
        return [{**dict(r), "is_relevant": bool(r["is_relevant"])} for r in rows]
    finally:
        if owns_conn:
            conn.close()


def delete_screenings_for_interest(interest_id: int, *, conn: sqlite3.Connection | None = None) -> None:
    """관심사 하나가 남긴 interest_paper 행을 전부 지운다 — 관심사를 삭제할 때
    interests.delete_interest()와 같이 불러야 한다(08-04 실사용 중 발견한 버그: 이걸
    안 부르면 지운 관심사가 남긴 스크리닝 기록이 고아로 남아 "관심사와 무관한데
    recommended"로 혼란을 준다). interest_paper는 이 모듈이 스키마를 소유하므로
    interests.py가 직접 지우지 않고 여기 함수를 통해서만 지운다(순환 import 방지 +
    각 모듈이 자기 테이블만 아는 원칙)."""
    owns_conn = conn is None
    conn = conn or _get_connection()
    try:
        conn.execute("DELETE FROM interest_paper WHERE interest_id = ?", (interest_id,))
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    # 수동 스모크 테스트 — 실제 data/app.db에 씀
    added = upsert_recommended("arxiv:2401.12345", arxiv_id="2401.12345", title="테스트 논문")
    print(f"추천 등록: {added}, 현재: {get_paper('arxiv:2401.12345')}")
    mark_owned("arxiv:2401.12345")
    print(f"보유 전환 후: {get_paper('arxiv:2401.12345')}")
    record_screening(1, "arxiv:2401.12345", is_relevant=True, reasoning="테스트 근거")
    print(f"관심사 1의 논문 목록: {list_papers_for_interest(1)}")
