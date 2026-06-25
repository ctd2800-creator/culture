"""INST1.TSHDE0ZCD 테이블 시드 적용."""
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
    sys.path.insert(0, str(ROOT))
    from supabase.db_util import get_db_url
    return get_db_url()


def main() -> None:
    sys.path.insert(0, str(ROOT))
    import psycopg2

    from supabase.table_config import TSHDE0ZCD_SCHEMA, TSHDE0ZCD_TABLE
    from supabase.tshde0zcd_seed import TSHDE0ZCD_ROWS, TSHDE0ZCD_UPSERT_SQL
    from supabase.tshde0zcd_setup import ensure_tshde0zcd_table

    with psycopg2.connect(db_url()) as conn:
        ensure_tshde0zcd_table(conn)
        with conn.cursor() as cur:
            for row in TSHDE0ZCD_ROWS:
                cur.execute(TSHDE0ZCD_UPSERT_SQL, row)
            cur.execute(f'SELECT COUNT(*) FROM "{TSHDE0ZCD_SCHEMA}"."{TSHDE0ZCD_TABLE}"')
            total = cur.fetchone()[0]
            summary = [
                ("116252000", "연령코드"),
                ("106308000", "거래기간구분코드"),
                ("0036", "FG그룹DB그룹회사코드"),
                ("100243000", "고객구분코드"),
                ("101644000", "성별구분코드"),
                ("102132000", "여부"),
                ("132648000", "FG그룹직업분류코드"),
            ]
            counts: list[tuple[str, int]] = []
            for inst_id, inst_name in summary:
                cur.execute(
                    f'SELECT COUNT(*) FROM "{TSHDE0ZCD_SCHEMA}"."{TSHDE0ZCD_TABLE}" '
                    f'WHERE trim("인스턴스식별자") = %s AND "인스턴스명" = %s',
                    (inst_id, inst_name),
                )
                counts.append((inst_name, cur.fetchone()[0]))
        conn.commit()

    print(f"OK: seeded {len(TSHDE0ZCD_ROWS)} rows into {TSHDE0ZCD_SCHEMA}.{TSHDE0ZCD_TABLE}")
    print(f"  테이블 전체: {total}건")
    for name, n in counts:
        print(f"  {name}: {n}건")


if __name__ == "__main__":
    main()
