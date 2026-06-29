"""TSHDEOA01~06 추출/집계 성능용 인덱스 일괄 생성.

추출 에이전트의 WHERE 조건은 다음 형태다(컬럼에 trim()을 쓰지 않음).
  - 그룹회사코드 보유 테이블: "그룹회사코드" = %s [AND "기준년월" 조건]
  - 미보유(TSHDEOA05):        "기준년월" 조건만

컬럼이 character(N) 고정길이지만 값에 패딩이 없어 trim() 없이 비교하며,
그 덕분에 아래 일반(컬럼) 인덱스를 그대로 사용한다.

- 그룹회사코드 보유: ("그룹회사코드", "기준년월")
- 미보유:           ("기준년월")

모두 IF NOT EXISTS 로 멱등(idempotent)하며, 생성 후 ANALYZE 한다.
과거 trim() 표현식 인덱스가 같은 이름으로 남아 있으면 자동으로 DROP 후
일반 인덱스로 재생성한다. 시드 스크립트 종료 시 자동 호출되고,
단독 실행도 가능하다.

usage:
  python culture_db/tshdeoa_indexes.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from culture_db.table_config import (  # noqa: E402
    INST1_DATA_TABLES,
    TSHDEOA01_SCHEMA,
    inst1_table_has_group_company,
)

_SCHEMA = TSHDEOA01_SCHEMA


def _index_plan() -> list[tuple[str, str, str]]:
    """(table, index_name, columns_sql) 목록 — 결정적 순서."""
    plan: list[tuple[str, str, str]] = []
    for table in sorted(INST1_DATA_TABLES):
        if inst1_table_has_group_company(table):
            idx = f"idx_{table.lower()}_grp_month"
            cols = '("그룹회사코드", "기준년월")'
        else:
            idx = f"idx_{table.lower()}_month"
            cols = '("기준년월")'
        plan.append((table, idx, cols))
    return plan


def _drop_if_legacy_expression_index(cur, table: str, idx: str) -> bool:
    """같은 이름의 인덱스가 trim() 표현식 인덱스면 DROP. DROP 했으면 True."""
    cur.execute(
        """
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = %s AND tablename = %s AND indexname = %s
        """,
        (_SCHEMA, table, idx),
    )
    row = cur.fetchone()
    if row and "trim(" in row[0].lower():
        cur.execute(f'DROP INDEX IF EXISTS "{_SCHEMA}"."{idx}"')
        print(f"  [drop-legacy] {idx} (trim 표현식 인덱스 제거)", flush=True)
        return True
    return False


def ensure_tshdeoa_indexes(conn, *, analyze: bool = True) -> list[str]:
    """6개 데이터 테이블에 성능 인덱스를 멱등 생성하고 ANALYZE.

    CREATE INDEX/ANALYZE 모두 트랜잭션 내에서 동작하므로 끝에 commit 한다.
    생성/확인한 인덱스명 목록을 반환한다.
    """
    created: list[str] = []
    with conn.cursor() as cur:
        for table, idx, cols in _index_plan():
            _drop_if_legacy_expression_index(cur, table, idx)
            started = time.time()
            cur.execute(
                f'CREATE INDEX IF NOT EXISTS {idx} '
                f'ON "{_SCHEMA}"."{table}" {cols}'
            )
            print(
                f"  [index] {idx} on {table} {cols} "
                f"({time.time() - started:.0f}s)",
                flush=True,
            )
            created.append(idx)
            if analyze:
                started = time.time()
                cur.execute(f'ANALYZE "{_SCHEMA}"."{table}"')
                print(
                    f"  [analyze] {table} ({time.time() - started:.0f}s)",
                    flush=True,
                )
    conn.commit()
    return created


def main() -> None:
    import psycopg2

    from culture_db.culture_db import aurora_db_url

    print("TSHDEOA01~06 index 생성 시작", flush=True)
    started = time.time()
    with psycopg2.connect(aurora_db_url()) as conn:
        ensure_tshdeoa_indexes(conn)
    print(f"OK: 인덱스 생성 완료 ({time.time() - started:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
