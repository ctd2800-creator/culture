"""Aurora TSHDEOA01~06 전체 시드 (기준년월별 건수 적용)."""
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
            if inserted % _PROGRESS_STEP == 0:
                print(f"  [{label}] ... {inserted:,} rows ({time.time() - started:.0f}s)", flush=True)

    if batch:
        from psycopg2.extras import execute_batch

        execute_batch(cur, insert_sql, batch, page_size=batch_size)
        inserted += len(batch)
        batch.clear()

    elapsed = time.time() - started
    print(f"  [{label}] done: {inserted:,} rows ({elapsed:.0f}s)", flush=True)
    return inserted


def _seed_table_o05(
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
            f'DELETE FROM "{schema}"."{table}" WHERE "기준년월" = %s',
            (month,),
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
            if inserted % _PROGRESS_STEP == 0:
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

    from culture_db.aurora_setup import ensure_tshdeoa_tables
    from culture_db.culture_db import aurora_db_url
    from culture_db.table_config import (
        TSHDEOA01_SCHEMA,
        TSHDEOA01_TABLE,
        TSHDEOA02_SCHEMA,
        TSHDEOA02_TABLE,
        TSHDEOA03_SCHEMA,
        TSHDEOA03_TABLE,
        TSHDEOA04_SCHEMA,
        TSHDEOA04_TABLE,
        TSHDEOA05_SCHEMA,
        TSHDEOA05_TABLE,
        TSHDEOA06_SCHEMA,
        TSHDEOA06_TABLE,
    )
    from culture_db.tshdeoa01_seed import (
        TSHDEOA01_INSERT_SQL,
        TSHDEOA01_MONTH_COUNTS,
        TSHDEOA01_SEED_MONTHS,
        iter_all_seed_rows,
    )
    from culture_db.tshdeoa02_seed import TSHDEOA02_INSERT_SQL, iter_all_o02_seed_rows
    from culture_db.tshdeoa03_seed import TSHDEOA03_INSERT_SQL, iter_all_o03_seed_rows
    from culture_db.tshdeoa04_seed import TSHDEOA04_INSERT_SQL, iter_all_o04_seed_rows
    from culture_db.tshdeoa05_seed import TSHDEOA05_INSERT_SQL, iter_all_o05_seed_rows
    from culture_db.tshdeoa06_seed import TSHDEOA06_INSERT_SQL, iter_all_o06_seed_rows
    from culture_db.tshdeoa_indexes import ensure_tshdeoa_indexes

    months = TSHDEOA01_SEED_MONTHS
    started = time.time()
    counts_label = ", ".join(f"{m}={TSHDEOA01_MONTH_COUNTS[m]:,}" for m in months)
    print(f"Aurora TSHDEOA01~06 seed - {counts_label}", flush=True)

    seed_jobs = (
        (TSHDEOA01_SCHEMA, TSHDEOA01_TABLE, TSHDEOA01_INSERT_SQL, iter_all_seed_rows(), "kfg"),
        (TSHDEOA02_SCHEMA, TSHDEOA02_TABLE, TSHDEOA02_INSERT_SQL, iter_all_o02_seed_rows(), "kfg"),
        (TSHDEOA03_SCHEMA, TSHDEOA03_TABLE, TSHDEOA03_INSERT_SQL, iter_all_o03_seed_rows(), "kfg"),
        (TSHDEOA04_SCHEMA, TSHDEOA04_TABLE, TSHDEOA04_INSERT_SQL, iter_all_o04_seed_rows(), "kfg"),
        (TSHDEOA05_SCHEMA, TSHDEOA05_TABLE, TSHDEOA05_INSERT_SQL, iter_all_o05_seed_rows(), "o05"),
        (TSHDEOA06_SCHEMA, TSHDEOA06_TABLE, TSHDEOA06_INSERT_SQL, iter_all_o06_seed_rows(), "kfg"),
    )

    with psycopg2.connect(aurora_db_url()) as conn:
        print("ensuring tables ...", flush=True)
        ensure_tshdeoa_tables(conn)
        conn.commit()

        with conn.cursor() as cur:
            for schema, table, insert_sql, row_iter, mode in seed_jobs:
                if mode == "o05":
                    _seed_table_o05(
                        cur,
                        schema=schema,
                        table=table,
                        months=months,
                        insert_sql=insert_sql,
                        row_iter=row_iter,
                        label=table,
                    )
                else:
                    _seed_table_kfg(
                        cur,
                        schema=schema,
                        table=table,
                        months=months,
                        insert_sql=insert_sql,
                        row_iter=row_iter,
                        label=table,
                    )
                conn.commit()

            print("\n=== row counts ===", flush=True)
            kfg_tables = (
                TSHDEOA01_TABLE,
                TSHDEOA02_TABLE,
                TSHDEOA03_TABLE,
                TSHDEOA04_TABLE,
                TSHDEOA06_TABLE,
            )
            for table in kfg_tables:
                for month in months:
                    cur.execute(
                        f'SELECT COUNT(*) FROM "INST1"."{table}" '
                        f'WHERE "기준년월" = %s AND "그룹회사코드" = %s',
                        (month, "KFG"),
                    )
                    print(f"  {table} {month}: {cur.fetchone()[0]:,}", flush=True)
            for month in months:
                cur.execute(
                    f'SELECT COUNT(*) FROM "INST1"."{TSHDEOA05_TABLE}" '
                    f'WHERE "기준년월" = %s',
                    (month,),
                )
                print(f"  {TSHDEOA05_TABLE} {month}: {cur.fetchone()[0]:,}", flush=True)

        print("\n=== ensure indexes ===", flush=True)
        ensure_tshdeoa_indexes(conn)

    elapsed = time.time() - started
    print(f"\nOK: Aurora TSHDEOA01~06 seed complete ({elapsed:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
