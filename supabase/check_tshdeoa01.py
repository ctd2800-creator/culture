"""INST1.TSHDEOA01 존재 여부 및 연결 DB 확인."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    for p in (ROOT / ".env.local", ROOT / ".env"):
        if p.is_file():
            load_dotenv(p, override=False)
except ImportError:
    pass

import psycopg2

from supabase.table_config import TSHDEOA01_SCHEMA, TSHDEOA01_TABLE


def db_url() -> str:
    raw = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not raw:
        raise SystemExit("SUPABASE_DB_URL 없음")
    if "sslmode=" not in raw:
        raw += ("&" if "?" in raw else "?") + "sslmode=require"
    return raw


def main() -> None:
    url = db_url()
    parsed = urlparse(url.replace("postgresql://", "http://", 1))
    host = parsed.hostname or "?"
    port = parsed.port or 5432
    user = parsed.username or "?"
    dbname = (parsed.path or "/postgres").lstrip("/")
    print(f"연결: host={host} port={port} db={dbname} user={user[:20]}...")

    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("select current_database(), current_user, version()")
            db, user, ver = cur.fetchone()
            print(f"current_database={db} current_user={user}")

            cur.execute(
                """
                select schema_name
                from information_schema.schemata
                where schema_name not like 'pg_%' and schema_name <> 'information_schema'
                order by 1
                """
            )
            schemas = [r[0] for r in cur.fetchall()]
            print(f"스키마 목록 ({len(schemas)}): {', '.join(schemas)}")

            cur.execute(
                """
                select table_schema, table_name, table_type
                from information_schema.tables
                where table_schema = %s and table_name = %s
                """,
                (TSHDEOA01_SCHEMA, TSHDEOA01_TABLE),
            )
            row = cur.fetchone()
            if row:
                print(f"테이블 존재: {row[0]}.{row[1]} ({row[2]})")
            else:
                print(f"테이블 없음: {TSHDEOA01_SCHEMA}.{TSHDEOA01_TABLE}")
                cur.execute(
                    """
                    select table_schema, table_name
                    from information_schema.tables
                    where table_name ilike %s
                    order by 1, 2
                    """,
                    (f"%{TSHDEOA01_TABLE}%",),
                )
                similar = cur.fetchall()
                if similar:
                    print("유사 테이블:")
                    for s, t in similar:
                        print(f"  - {s}.{t}")
                raise SystemExit(1)

            cur.execute(
                """
                select column_name, ordinal_position, is_nullable, data_type,
                       character_maximum_length, numeric_precision, numeric_scale
                from information_schema.columns
                where table_schema = %s and table_name = %s
                order by ordinal_position
                """,
                (TSHDEOA01_SCHEMA, TSHDEOA01_TABLE),
            )
            print(f"\n컬럼 ({cur.rowcount}):")
            for col in cur.fetchall():
                name, pos, nullable, dtype, clen, nprec, nscale = col
                if clen:
                    t = f"{dtype}({clen})"
                elif nprec is not None:
                    t = f"{dtype}({nprec},{nscale or 0})"
                else:
                    t = dtype
                pk = "PK" if name in ("기준년월", "그룹회사코드", "그룹고객식별자") else ""
                print(f"  {pos:2}. {name}: {t} {nullable} {pk}")

            cur.execute(
                """
                select pg_get_userbyid(c.relowner), c.relname
                from pg_class c
                join pg_namespace n on n.oid = c.relnamespace
                where n.nspname = %s and c.relname = %s
                """,
                (TSHDEOA01_SCHEMA, TSHDEOA01_TABLE),
            )
            owner_row = cur.fetchone()
            if owner_row:
                print(f"\n소유자: {owner_row[0]}")


if __name__ == "__main__":
    main()
