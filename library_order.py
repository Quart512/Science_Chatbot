# 라이브러리 화면 4곳(관심사·논문·실험도구·지식노트) 공용 수동 정렬 — 위/아래 버튼으로
# sort_order 정수 컬럼을 인접 행과 swap하는 것만으로 구현(사용자가 드래그 대신 버튼을
# 골랐다 — 08-06, 새 프론트 의존성 없이 접근성도 기본으로 챙길 수 있어서). 테이블마다
# 이 로직을 따로 못박으면 4번 거의 같은 코드가 생기므로 여기 한 곳에 모은다.
#
# table/id_column은 항상 각 모듈이 코드로 넘기는 상수이지 사용자 입력이 아니다 — SQL에
# f-string으로 꽂아 넣어도 인젝션 경로가 없다(WHERE 절 값은 전부 파라미터 바인딩).

import sqlite3


def escape_like(term: str) -> str:
    """LIKE 패턴의 와일드카드(%, _)를 리터럴로 이스케이프하고 앞뒤에 %를 붙여 부분
    일치 패턴으로 만든다(08-06, 논문/노트 제목 검색 공용). 백슬래시부터 먼저
    이스케이프해야 한다 — 안 그러면 %,_를 이스케이프하며 새로 넣은 백슬래시 자체가
    다시 이스케이프 대상으로 잡혀 이중으로 escape된다. 호출부는 이 값을
    `LIKE ? ESCAPE '\\'`와 같이 써야 한다."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def next_sort_order(table: str, *, conn: sqlite3.Connection) -> int:
    """새 행을 목록 맨 끝에 넣기 위한 다음 sort_order 값. 빈 테이블이면 1."""
    row = conn.execute(f"SELECT MAX(sort_order) AS m FROM {table}").fetchone()
    return (row["m"] or 0) + 1


def move_item(
    table: str, id_column: str, item_id, direction: str, *,
    conn: sqlite3.Connection, scope_where: str = "", scope_params: tuple = (),
) -> bool:
    """item_id 행을 인접 행과 sort_order를 바꿔 한 칸 옮긴다.

    direction: "up"(정렬 순서상 더 앞으로) / "down"(더 뒤로). 이미 맨 앞/맨 뒤라 옮길
    인접 행이 없으면 아무것도 안 하고 False — 프론트가 경계에서 버튼을 disabled로
    두지만, 그거와 별개로 이 함수 자체도 안전해야 한다(레이스 등으로 눌렸을 때).

    scope_where/scope_params(papers 전용) — "인접 행"을 테이블 전체가 아니라 부분집합
    안에서만 찾는다. papers는 한 테이블에 recommended/owned/dismissed가 섞여 있는데
    화면에 순서 버튼이 있는 건 "보유 논문"(status='owned') 목록뿐이다 — 이 필터 없이
    전체에서 이웃을 찾으면, 화면에 안 보이는 다른 status 논문과 sort_order를 바꿔서
    "위로" 눌러도 목록이 그대로인 것처럼 보이는 버그가 난다.
    """
    if direction not in ("up", "down"):
        raise ValueError(f"direction은 'up'/'down'만 허용: {direction!r}")

    row = conn.execute(f"SELECT sort_order FROM {table} WHERE {id_column} = ?", (item_id,)).fetchone()
    if row is None:
        return False
    current = row["sort_order"]

    scope_sql = f" AND {scope_where}" if scope_where else ""
    if direction == "up":
        neighbor = conn.execute(
            f"SELECT {id_column} AS id, sort_order FROM {table} "
            f"WHERE sort_order < ?{scope_sql} ORDER BY sort_order DESC LIMIT 1",
            (current, *scope_params),
        ).fetchone()
    else:
        neighbor = conn.execute(
            f"SELECT {id_column} AS id, sort_order FROM {table} "
            f"WHERE sort_order > ?{scope_sql} ORDER BY sort_order ASC LIMIT 1",
            (current, *scope_params),
        ).fetchone()
    if neighbor is None:
        return False

    conn.execute(f"UPDATE {table} SET sort_order = ? WHERE {id_column} = ?", (neighbor["sort_order"], item_id))
    conn.execute(f"UPDATE {table} SET sort_order = ? WHERE {id_column} = ?", (current, neighbor["id"]))
    conn.commit()
    return True


def backfill_sort_order(table: str, id_column: str, *, conn: sqlite3.Connection) -> None:
    """sort_order 컬럼을 처음 추가한 직후 1회용 — 기존 행에 현재 표시 순서(rowid, 곧
    삽입 순서)를 그대로 채워 넣는다. 새로 추가되는 컬럼이라 전 행이 DEFAULT 0으로
    깔리는데(equipment.py 등과 같은 ALTER TABLE ADD COLUMN 패턴), 전부 0이면 sort_order
    기준 정렬이 (동률이라) 다시 삽입 순서로 안전하게 fallback되긴 하지만, 이후 move_item()이
    "인접 행"을 sort_order만으로 찾으므로 서로 구별되는 값이 있어야 스왑이 의미를 가진다."""
    conn.execute(f"UPDATE {table} SET sort_order = rowid")
    conn.commit()
