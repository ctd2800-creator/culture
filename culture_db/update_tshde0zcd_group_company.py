"""INST1.TSHDE0ZCD 그룹회사코드 일괄 업데이트."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
TARGET_GROUP = "KFG"


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
    with psycopg2.connect(db_url(), connect_timeout=15) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT trim("그룹회사코드"), COUNT(*)
                FROM "INST1"."TSHDE0ZCD"
                GROUP BY 1
                ORDER BY 1
                """
            )
            before = cur.fetchall()
            print("업데이트 전 그룹회사코드 분포:", before)

            cur.execute(
                """
                UPDATE "INST1"."TSHDE0ZCD"
                SET "그룹회사코드" = %s
                WHERE trim("그룹회사코드") IS DISTINCT FROM %s
                """,
                (TARGET_GROUP, TARGET_GROUP),
            )
            updated = cur.rowcount
            conn.commit()

            cur.execute(
                """
                SELECT trim("그룹회사코드"), COUNT(*)
                FROM "INST1"."TSHDE0ZCD"
                GROUP BY 1
                ORDER BY 1
                """
            )
            after = cur.fetchall()
            print(f"업데이트 건수: {updated}")
            print("업데이트 후 그룹회사코드 분포:", after)
    print(f"OK: INST1.TSHDE0ZCD 그룹회사코드 → {TARGET_GROUP}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1) from e
