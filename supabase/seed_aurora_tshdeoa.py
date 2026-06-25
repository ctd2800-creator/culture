"""Aurora에 TSHDEOA01/02/04 테이블 생성 및 시드 적용."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _seed_table(
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
            from psycopg2.extras import execute_batch

            execute_batch(cur, insert_sql, batch, page_size=batch_size)
            inserted += len(batch)
            batch.clear()
            if inserted % 300_000 == 0:
                print(f"  [{label}] ... {inserted:,} rows ({time.time() - started:.0f}s)", flush=True)

    if batch:
        from psycopg2.extras import execute_batch

        execute_batch(cur, insert_sql, batch, page_size=batch_size)
        inserted += len(batch)
        batch.clear()

    elapsed = time.time() - started
    print(f"  [{label}] done: {inserted:,} rows ({elapsed:.0f}s)", flush=True)
    return inserted


def main() -> None:
    sys.path.insert(0, str(ROOT))
    import psycopg2

    from supabase.aurora_db import aurora_db_url
    from supabase.aurora_setup import ensure_tshdeoa_tables
    from supabase.table_config import (
        TSHDEOA01_SCHEMA,
        TSHDEOA01_TABLE,
        TSHDEOA02_SCHEMA,
        TSHDEOA02_TABLE,
        TSHDEOA04_SCHEMA,
        TSHDEOA04_TABLE,
    )
    from supabase.tshdeoa01_seed import (
        TSHDEOA01_202604_TARGET_COUNT,
        TSHDEOA01_INSERT_SQL,
        TSHDEOA01_SEED_MONTHS,
        iter_all_seed_rows,
    )
    from supabase.tshdeoa02_seed import (
        TSHDEOA02_INSERT_SQL,
        TSHDEOA02_SEED_MONTHS,
        iter_all_o02_seed_rows,
    )
    from supabase.tshdeoa04_seed import (
        TSHDEOA04_INSERT_SQL,
        TSHDEOA04_SEED_MONTHS,
        iter_all_o04_seed_rows,
    )

    per_month = TSHDEOA01_202604_TARGET_COUNT
    months = TSHDEOA01_SEED_MONTHS
    started = time.time()

    print(f"Aurora TSHDEOA seed - {per_month:,}/month x {len(months)} months", flush=True)

    with psycopg2.connect(aurora_db_url()) as conn:
        print("creating tables ...", flush=True)
        ensure_tshdeoa_tables(conn)
        conn.commit()

        with conn.cursor() as cur:
            _seed_table(
                cur,
                schema=TSHDEOA01_SCHEMA,
                table=TSHDEOA01_TABLE,
                months=months,
                insert_sql=TSHDEOA01_INSERT_SQL,
                row_iter=iter_all_seed_rows(),
                label="TSHDEOA01",
            )
            conn.commit()

            _seed_table(
                cur,
                schema=TSHDEOA02_SCHEMA,
                table=TSHDEOA02_TABLE,
                months=TSHDEOA02_SEED_MONTHS,
                insert_sql=TSHDEOA02_INSERT_SQL,
                row_iter=iter_all_o02_seed_rows(),
                label="TSHDEOA02",
            )
            conn.commit()

            _seed_table(
                cur,
                schema=TSHDEOA04_SCHEMA,
                table=TSHDEOA04_TABLE,
                months=TSHDEOA04_SEED_MONTHS,
                insert_sql=TSHDEOA04_INSERT_SQL,
                row_iter=iter_all_o04_seed_rows(),
                label="TSHDEOA04",
            )
            conn.commit()

            print("\n=== row counts ===", flush=True)
            for table in (TSHDEOA01_TABLE, TSHDEOA02_TABLE, TSHDEOA04_TABLE):
                for month in months:
                    cur.execute(
                        f'SELECT COUNT(*) FROM "INST1"."{table}" '
                        f'WHERE "기준년월" = %s AND "그룹회사코드" = %s',
                        (month, "KFG"),
                    )
                    print(f"  {table} {month}: {cur.fetchone()[0]:,}", flush=True)

    elapsed = time.time() - started
    print(f"\nOK: Aurora TSHDEOA seed complete ({elapsed:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
