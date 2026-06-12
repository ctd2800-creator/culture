"""INST1.TSHDEOA01 테이블 시드 적용."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in (ROOT / ".env.local", ROOT / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)


def db_url() -> str:
    _load_dotenv()
    raw = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not raw:
        raise SystemExit("SUPABASE_DB_URL 환경 변수가 없습니다.")
    if "sslmode=" not in raw:
        raw += ("&" if "?" in raw else "?") + "sslmode=require"
    return raw


def main() -> None:
    sys.path.insert(0, str(ROOT))
    import psycopg2

    from supabase.table_config import TSHDEOA01_SCHEMA, TSHDEOA01_TABLE
    from supabase.tshdeoa01_seed import TSHDEOA01_ROWS, TSHDEOA01_UPSERT_SQL
    from supabase.tshdeoa01_setup import ensure_tshdeoa01_table

    with psycopg2.connect(db_url()) as conn:
        ensure_tshdeoa01_table(conn)
        with conn.cursor() as cur:
            for row in TSHDEOA01_ROWS:
                cur.execute(TSHDEOA01_UPSERT_SQL, row)
            cur.execute(
                f'SELECT COUNT(*) FROM "{TSHDEOA01_SCHEMA}"."{TSHDEOA01_TABLE}" '
                f'WHERE "기준년월" = %s AND "그룹회사코드" = %s',
                ("202604", "KFG"),
            )
            count = cur.fetchone()[0]
        conn.commit()

    print(f"OK: seeded {len(TSHDEOA01_ROWS)} rows into {TSHDEOA01_SCHEMA}.{TSHDEOA01_TABLE}")
    print(f"  202604/KFG rows in table: {count}")


if __name__ == "__main__":
    main()
