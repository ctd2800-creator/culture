"""Aurora TSHDEOA01 / TSHDEOA02 만 시드 (기준년월별 건수 적용).

TSHDEOA02 는 TSHDEOA01 과 동일한 그룹고객식별자를 재사용한다.
건수는 culture_db/tshdeoa01_seed.py 의 TSHDEOA01_MONTH_COUNTS 를 따른다.

usage:
  python culture_db/seed_aurora_o01_o02.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_PROGRESS_STEP = 500_000


def _seed_table_kfg(
    cur,
    *,
    schema: str,
    table: str,
    months: tuple[str, ...],
    insert_sql: str,
    row_iter,
    label: str,
    batch_size: int = 5000,
) -> int:
    from psycopg2.extras import execute_batch

    for month in months:
        cur.execute(
            f'DELETE FROM "{schema}"."{table}" '
            f'WHERE "기준년월" = %s AND "그룹회사코드" = %s',
            (month, "KFG"),
        )

    inserted = 0
    batch: list[tuple] = []
    started = time.time()

    for row in row_iter:
        batch.append(row)
        if len(batch) >= batch_size:
            execute_batch(cur, insert_sql, batch, page_size=batch_size)
            inserted += len(batch)
            batch.clear()
            if inserted % _PROGRESS_STEP == 0:
                print(
                    f"  [{label}] ... {inserted:,} rows ({time.time() - started:.0f}s)",
                    flush=True,
                )

    if batch:
        execute_batch(cur, insert_sql, batch, page_size=batch_size)
        inserted += len(batch)
        batch.clear()

    elapsed = time.time() - started
    print(f"  [{label}] done: {inserted:,} rows ({elapsed:.0f}s)", flush=True)
    return inserted


def main() -> None:
    sys.path.insert(0, str(ROOT))
    import psycopg2

    from culture_db.aurora_setup import ensure_tshdeoa_tables
    from culture_db.culture_db import aurora_db_url
    from culture_db.table_config import (
        TSHDEOA01_SCHEMA,
        TSHDEOA01_TABLE,
        TSHDEOA02_SCHEMA,
        TSHDEOA02_TABLE,
    )
    from culture_db.tshdeoa01_seed import (
        TSHDEOA01_INSERT_SQL,
        TSHDEOA01_MONTH_COUNTS,
        TSHDEOA01_SEED_MONTHS,
        iter_all_seed_rows,
    )
    from culture_db.tshdeoa02_seed import (
        TSHDEOA02_INSERT_SQL,
        iter_all_o02_seed_rows,
    )
    from culture_db.tshdeoa_indexes import ensure_tshdeoa_indexes
    from culture_db.summary_tables import build_summary_tables

    months = TSHDEOA01_SEED_MONTHS
    started = time.time()
    counts_label = ", ".join(f"{m}={TSHDEOA01_MONTH_COUNTS[m]:,}" for m in months)
    print(f"Aurora TSHDEOA01/02 seed - {counts_label}", flush=True)

    with psycopg2.connect(aurora_db_url()) as conn:
        print("ensuring tables ...", flush=True)
        ensure_tshdeoa_tables(conn)
        conn.commit()

        with conn.cursor() as cur:
            _seed_table_kfg(
                cur,
                schema=TSHDEOA01_SCHEMA,
                table=TSHDEOA01_TABLE,
                months=months,
                insert_sql=TSHDEOA01_INSERT_SQL,
                row_iter=iter_all_seed_rows(),
                label="TSHDEOA01",
            )
            conn.commit()

            _seed_table_kfg(
                cur,
                schema=TSHDEOA02_SCHEMA,
                table=TSHDEOA02_TABLE,
                months=months,
                insert_sql=TSHDEOA02_INSERT_SQL,
                row_iter=iter_all_o02_seed_rows(),
                label="TSHDEOA02",
            )
            conn.commit()

            print("\n=== row counts ===", flush=True)
            for table in (TSHDEOA01_TABLE, TSHDEOA02_TABLE):
                for month in months:
                    cur.execute(
                        f'SELECT COUNT(*) FROM "INST1"."{table}" '
                        f'WHERE "기준년월" = %s AND "그룹회사코드" = %s',
                        (month, "KFG"),
                    )
                    print(f"  {table} {month}: {cur.fetchone()[0]:,}", flush=True)

        print("\n=== ensure indexes ===", flush=True)
        ensure_tshdeoa_indexes(conn)

        print("\n=== build summary tables ===", flush=True)
        build_summary_tables(conn)

    elapsed = time.time() - started
    print(f"\nOK: Aurora TSHDEOA01/02 seed complete ({elapsed:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
