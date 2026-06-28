"""INST1 테이블 컬럼정의 → pg_description 동기화."""

from __future__ import annotations


def sync_inst1_column_comments(conn, table: str, *, schema: str = "INST1") -> int:
    from culture_db.table_config import INST1_COLUMN_DEFINITIONS

    defs = INST1_COLUMN_DEFINITIONS.get(table, {})
    with conn.cursor() as cur:
        for column, comment in defs.items():
            cur.execute(
                f'COMMENT ON COLUMN "{schema}"."{table}"."{column}" IS %s',
                (comment,),
            )
    return len(defs)
