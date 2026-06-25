"""Aurora용 TSHDEOA DDL 적용."""
from __future__ import annotations

from pathlib import Path

_SQL_FILES = (
    "tshdeoa01.sql",
    "tshdeoa02.sql",
    "tshdeoa04.sql",
    "tshde0zcd.sql",
)


def aurora_sql_text(path: Path) -> str:
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().lower().startswith("grant "):
            continue
        lines.append(line)
    return "\n".join(lines)


def apply_sql_file(conn, filename: str) -> None:
    path = Path(__file__).resolve().parent / filename
    with conn.cursor() as cur:
        cur.execute(aurora_sql_text(path))


def ensure_tshdeoa_tables(conn) -> None:
    base = Path(__file__).resolve().parent
    with conn.cursor() as cur:
        for name in _SQL_FILES[:3]:
            cur.execute(aurora_sql_text(base / name))


def ensure_tshde0zcd_table(conn) -> None:
    apply_sql_file(conn, "tshde0zcd.sql")
