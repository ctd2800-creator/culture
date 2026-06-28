"""INST1.TSHDEOA01 테이블 DDL 적용."""

from __future__ import annotations

from pathlib import Path

from culture_db.column_comments import sync_inst1_column_comments
from culture_db.sql_util import ddl_without_grants
from culture_db.table_config import TSHDEOA01_SCHEMA, TSHDEOA01_TABLE

_SQL_PATH = Path(__file__).resolve().parent / "tshdeoa01.sql"


def ensure_tshdeoa01_table(conn) -> None:
    ddl = ddl_without_grants(_SQL_PATH.read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        cur.execute(ddl)


def sync_tshdeoa01_column_comments(conn) -> int:
    return sync_inst1_column_comments(conn, TSHDEOA01_TABLE, schema=TSHDEOA01_SCHEMA)
