"""INST1.TSHDEOA05 테이블 DDL 적용."""

from __future__ import annotations

from pathlib import Path

from culture_db.column_comments import sync_inst1_column_comments
from culture_db.sql_util import ddl_without_grants
from culture_db.table_config import TSHDEOA05_SCHEMA, TSHDEOA05_TABLE

_SQL_PATH = Path(__file__).resolve().parent / "tshdeoa05.sql"


def ensure_tshdeoa05_table(conn) -> None:
    ddl = ddl_without_grants(_SQL_PATH.read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        cur.execute(ddl)


def sync_tshdeoa05_column_comments(conn) -> int:
    return sync_inst1_column_comments(conn, TSHDEOA05_TABLE, schema=TSHDEOA05_SCHEMA)
