"""INST1.TSHDEOA02 테이블 DDL 적용."""

from __future__ import annotations

from pathlib import Path

_SQL_PATH = Path(__file__).resolve().parent / "tshdeoa02.sql"


def ensure_tshdeoa02_table(conn) -> None:
    ddl = _SQL_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(ddl)
