"""Aurora: 회원 테이블 + TSHDE0ZCD 시드."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    sys.path.insert(0, str(ROOT))
    import psycopg2

    from culture_db.aurora_setup import ensure_tshde0zcd_table
    from culture_db.culture_db import get_culture_db_url
    from culture_db.members_setup import setup_members
    from culture_db.table_config import MEMBER_TABLE_NAME, TSHDE0ZCD_SCHEMA, TSHDE0ZCD_TABLE
    from culture_db.tshde0zcd_seed import TSHDE0ZCD_ROWS, TSHDE0ZCD_UPSERT_SQL


    with psycopg2.connect(get_culture_db_url()) as conn:
        member_stats = setup_members(conn, seed=True, force_seed=False)
        ensure_tshde0zcd_table(conn)
        with conn.cursor() as cur:
            for row in TSHDE0ZCD_ROWS:
                cur.execute(TSHDE0ZCD_UPSERT_SQL, row)
            cur.execute(f'SELECT COUNT(*) FROM "{TSHDE0ZCD_SCHEMA}"."{TSHDE0ZCD_TABLE}"')
            zcd_total = cur.fetchone()[0]
        conn.commit()

    print(f"OK: members inserted={member_stats['inserted']}, total={member_stats['total']}")
    print(f"OK: {TSHDE0ZCD_SCHEMA}.{TSHDE0ZCD_TABLE} rows={zcd_total}")


if __name__ == "__main__":
    main()
