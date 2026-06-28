"""Aurora용 TSHDEOA DDL 적용."""
from __future__ import annotations

from pathlib import Path

from culture_db.sql_util import ddl_without_grants

_TSHDEOA_SQL_FILES = (
    "tshdeoa01.sql",
    "tshdeoa02.sql",
    "tshdeoa03.sql",
    "tshdeoa04.sql",
    "tshdeoa05.sql",
    "tshdeoa06.sql",
)

_SQL_FILES = (*_TSHDEOA_SQL_FILES, "tshde0zcd.sql")


def aurora_sql_text(path: Path) -> str:
    return ddl_without_grants(path.read_text(encoding="utf-8"))


def apply_sql_file(conn, filename: str) -> None:
    path = Path(__file__).resolve().parent / filename
    with conn.cursor() as cur:
        cur.execute(aurora_sql_text(path))


def ensure_tshdeoa_tables(conn) -> None:
    base = Path(__file__).resolve().parent
    with conn.cursor() as cur:
        for name in _TSHDEOA_SQL_FILES:
            cur.execute(aurora_sql_text(base / name))


def ensure_tshde0zcd_table(conn) -> None:
    apply_sql_file(conn, "tshde0zcd.sql")
