"""Drop legacy public tables: calendar, info, 그룹멤버십계열사기초데이터검증."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from culture_db.table_config import LEGACY_EXCLUDED_TABLES

TABLES = tuple(LEGACY_EXCLUDED_TABLES)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in (ROOT / ".env.local", ROOT / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)


def db_url() -> str:
    sys.path.insert(0, str(ROOT))
    from culture_db.db_util import get_db_url
    return get_db_url()


def main() -> int:
    url = db_url()
    with psycopg2.connect(url, connect_timeout=15) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                select table_schema, table_name
                from information_schema.tables
                where table_type = 'BASE TABLE'
                  and table_name = any(%s)
                order by table_schema, table_name
                """,
                (list(TABLES),),
            )
            found = cur.fetchall()
            print("발견된 테이블:")
            for schema, name in found:
                print(f"  - {schema}.{name}")

            if not found:
                print("삭제할 테이블이 없습니다.")
                return 0

            for schema, name in found:
                sql = f'DROP TABLE IF EXISTS "{schema}"."{name}" CASCADE;'
                print(f"실행: {sql}")
                cur.execute(sql)
                print(f"삭제 완료: {schema}.{name}")

    print("완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
