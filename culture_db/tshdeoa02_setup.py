"""INST1.TSHDEOA02 테이블 DDL 적용."""

from __future__ import annotations

from pathlib import Path

from culture_db.column_comments import sync_inst1_column_comments
from culture_db.sql_util import ddl_without_grants
from culture_db.table_config import TSHDEOA02_SCHEMA, TSHDEOA02_TABLE

_SQL_PATH = Path(__file__).resolve().parent / "tshdeoa02.sql"


def ensure_tshdeoa02_table(conn) -> None:
    ddl = ddl_without_grants(_SQL_PATH.read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        cur.execute(ddl)


def sync_tshdeoa02_column_comments(conn) -> int:
    return sync_inst1_column_comments(conn, TSHDEOA02_TABLE, schema=TSHDEOA02_SCHEMA)
