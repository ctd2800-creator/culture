"""Aurora에 TSHDEOA03/05/06 테이블 생성 및 시드 적용."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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

    from culture_db.aurora_setup import ensure_tshdeoa_tables
    from culture_db.culture_db import aurora_db_url
    from culture_db.table_config import (
        TSHDEOA03_SCHEMA,
        TSHDEOA03_TABLE,
        TSHDEOA05_SCHEMA,
        TSHDEOA05_TABLE,
        TSHDEOA06_SCHEMA,
        TSHDEOA06_TABLE,
    )
    from culture_db.tshdeoa01_seed import TSHDEOA01_202604_TARGET_COUNT, TSHDEOA01_SEED_MONTHS
    from culture_db.tshdeoa03_seed import (
        TSHDEOA03_INSERT_SQL,
        TSHDEOA03_SEED_MONTHS,
        iter_all_o03_seed_rows,
    )
    from culture_db.tshdeoa05_seed import (
        TSHDEOA05_INSERT_SQL,
        TSHDEOA05_SEED_MONTHS,
        iter_all_o05_seed_rows,
    )
    from culture_db.tshdeoa06_seed import (
        TSHDEOA06_INSERT_SQL,
        TSHDEOA06_SEED_MONTHS,
        iter_all_o06_seed_rows,
    )
    from culture_db.tshdeoa03_setup import ensure_tshdeoa03_table, sync_tshdeoa03_column_comments
    from culture_db.tshdeoa05_setup import ensure_tshdeoa05_table, sync_tshdeoa05_column_comments
    from culture_db.tshdeoa06_setup import ensure_tshdeoa06_table, sync_tshdeoa06_column_comments
    from culture_db.tshdeoa_indexes import ensure_tshdeoa_indexes

    per_month = TSHDEOA01_202604_TARGET_COUNT
    months = TSHDEOA01_SEED_MONTHS
    started = time.time()

    print(f"Aurora TSHDEOA03/05/06 seed - {per_month:,}/month x {len(months)} months", flush=True)

    with psycopg2.connect(aurora_db_url()) as conn:
        print("creating tables ...", flush=True)
        ensure_tshdeoa_tables(conn)
        ensure_tshdeoa03_table(conn)
        ensure_tshdeoa05_table(conn)
        ensure_tshdeoa06_table(conn)
        sync_tshdeoa03_column_comments(conn)
        sync_tshdeoa05_column_comments(conn)
        sync_tshdeoa06_column_comments(conn)
        conn.commit()

        with conn.cursor() as cur:
            _seed_table_kfg(
                cur,
                schema=TSHDEOA03_SCHEMA,
                table=TSHDEOA03_TABLE,
                months=TSHDEOA03_SEED_MONTHS,
                insert_sql=TSHDEOA03_INSERT_SQL,
                row_iter=iter_all_o03_seed_rows(),
                label="TSHDEOA03",
            )
            conn.commit()

            _seed_table_o05(
                cur,
                schema=TSHDEOA05_SCHEMA,
                table=TSHDEOA05_TABLE,
                months=TSHDEOA05_SEED_MONTHS,
                insert_sql=TSHDEOA05_INSERT_SQL,
                row_iter=iter_all_o05_seed_rows(),
                label="TSHDEOA05",
            )
            conn.commit()

            _seed_table_kfg(
                cur,
                schema=TSHDEOA06_SCHEMA,
                table=TSHDEOA06_TABLE,
                months=TSHDEOA06_SEED_MONTHS,
                insert_sql=TSHDEOA06_INSERT_SQL,
                row_iter=iter_all_o06_seed_rows(),
                label="TSHDEOA06",
            )
            conn.commit()

            print("\n=== row counts ===", flush=True)
            for table, has_grp in (
                (TSHDEOA03_TABLE, True),
                (TSHDEOA05_TABLE, False),
                (TSHDEOA06_TABLE, True),
            ):
                for month in months:
                    if has_grp:
                        cur.execute(
                            f'SELECT COUNT(*) FROM "INST1"."{table}" '
                            f'WHERE "기준년월" = %s AND "그룹회사코드" = %s',
                            (month, "KFG"),
                        )
                    else:
                        cur.execute(
                            f'SELECT COUNT(*) FROM "INST1"."{table}" '
                            f'WHERE "기준년월" = %s',
                            (month,),
                        )
                    print(f"  {table} {month}: {cur.fetchone()[0]:,}", flush=True)

        print("\n=== ensure indexes ===", flush=True)
        ensure_tshdeoa_indexes(conn)

    elapsed = time.time() - started
    print(f"\nOK: Aurora TSHDEOA03/05/06 seed complete ({elapsed:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
