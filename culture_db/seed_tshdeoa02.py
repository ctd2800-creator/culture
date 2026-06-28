"""INST1.TSHDEOA02 테이블 시드 적용."""
from __future__ import annotations

import os
import sys
import time
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
    from culture_db.db_util import get_db_url
    return get_db_url()


def main() -> None:
    sys.path.insert(0, str(ROOT))
    import psycopg2
    from psycopg2.extras import execute_batch

    from culture_db.table_config import TSHDEOA02_SCHEMA, TSHDEOA02_TABLE
    from culture_db.tshdeoa02_seed import (
        TSHDEOA02_202604_TARGET_COUNT,
        TSHDEOA02_INSERT_SQL,
        TSHDEOA02_SEED_MONTHS,
        iter_all_o02_seed_rows,
    )
    from culture_db.db_util import enable_db_writes
    from culture_db.tshdeoa02_setup import ensure_tshdeoa02_table

    batch_size = 5000
    months = TSHDEOA02_SEED_MONTHS
    per_month = TSHDEOA02_202604_TARGET_COUNT
    total_expected = per_month * len(months)

    started = time.time()
    inserted = 0
    batch: list[tuple] = []

    with psycopg2.connect(db_url()) as conn:
        with conn.cursor() as cur:
            enable_db_writes(cur)
        ensure_tshdeoa02_table(conn)
        with conn.cursor() as cur:
            for month in months:
                cur.execute(
                    f'DELETE FROM "{TSHDEOA02_SCHEMA}"."{TSHDEOA02_TABLE}" '
                    f'WHERE "기준년월" = %s AND "그룹회사코드" = %s',
                    (month, "KFG"),
                )
            conn.commit()

            for row in iter_all_o02_seed_rows():
                batch.append(row)
                if len(batch) >= batch_size:
                    execute_batch(cur, TSHDEOA02_INSERT_SQL, batch, page_size=batch_size)
                    inserted += len(batch)
                    batch.clear()
                    if inserted % 300_000 == 0:
                        elapsed = time.time() - started
                        print(
                            f"  ... {inserted:,} / {total_expected:,} rows ({elapsed:.0f}s)",
                            flush=True,
                        )
                        conn.commit()

            if batch:
                execute_batch(cur, TSHDEOA02_INSERT_SQL, batch, page_size=batch_size)
                inserted += len(batch)
                batch.clear()

            counts: dict[str, int] = {}
            for month in months:
                cur.execute(
                    f'SELECT COUNT(*) FROM "{TSHDEOA02_SCHEMA}"."{TSHDEOA02_TABLE}" '
                    f'WHERE "기준년월" = %s AND "그룹회사코드" = %s',
                    (month, "KFG"),
                )
                counts[month] = cur.fetchone()[0]
        conn.commit()

    elapsed = time.time() - started
    print(
        f"OK: seeded {inserted:,} rows into {TSHDEOA02_SCHEMA}.{TSHDEOA02_TABLE} "
        f"({per_month:,}건/월 × {len(months)}개월, {elapsed:.0f}s)",
        flush=True,
    )
    for month in months:
        print(f"  {month}/KFG rows in table: {counts[month]:,}", flush=True)


if __name__ == "__main__":
    main()
