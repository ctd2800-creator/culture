"""INST1.TSHDE0ZCD 데이터 확인."""
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


def main() -> int:
    _load_dotenv()
    raw = os.environ.get("AURORA_DB_URL", "").strip()
    if not raw:
        print("ERROR: AURORA_DB_URL 없음")
        return 1
    if "sslmode=" not in raw:
        raw += ("&" if "?" in raw else "?") + "sslmode=require"

    import psycopg2

    with psycopg2.connect(raw, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, inet_server_addr()::text")
            db, user, host = cur.fetchone()
            print(f"DB: {db}, user: {user}, host: {host or 'pooler'}")

            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_name = 'TSHDE0ZCD'
                ORDER BY table_schema
                """
            )
            print("TSHDE0ZCD tables:", cur.fetchall())

            cur.execute('SELECT COUNT(*) FROM "INST1"."TSHDE0ZCD"')
            print(f"INST1.TSHDE0ZCD count: {cur.fetchone()[0]}")

            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'TSHDE0ZCD'
                )
                """
            )
            if cur.fetchone()[0]:
                cur.execute('SELECT COUNT(*) FROM "public"."TSHDE0ZCD"')
                print(f"public.TSHDE0ZCD count: {cur.fetchone()[0]}")
            else:
                print("public.TSHDE0ZCD: 없음 (Table Editor 기본 스키마는 public)")

            cur.execute(
                """
                SELECT trim("그룹회사코드"), trim("인스턴스식별자"), trim("인스턴스코드"),
                       trim("인스턴스내용")
                FROM "INST1"."TSHDE0ZCD"
                WHERE trim("그룹회사코드") = 'KFG' AND trim("인스턴스식별자") = '0036'
                ORDER BY trim("인스턴스코드")
                """
            )
            rows = cur.fetchall()
            print(f"\nKFG/0036 FG그룹DB그룹회사코드: {len(rows)}건")
            for r in rows:
                print(" ", r)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
