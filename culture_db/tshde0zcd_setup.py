"""INST1.TSHDE0ZCD 테이블 DDL 적용."""

from __future__ import annotations

from pathlib import Path

from culture_db.sql_util import ddl_without_grants

_SQL_PATH = Path(__file__).resolve().parent / "tshde0zcd.sql"


def ensure_tshde0zcd_table(conn) -> None:
    ddl = ddl_without_grants(_SQL_PATH.read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        cur.execute(ddl)
