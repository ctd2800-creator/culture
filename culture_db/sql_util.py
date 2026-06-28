"""Aurora PostgreSQL DDL 유틸."""

from __future__ import annotations


def ddl_without_grants(sql: str) -> str:
    """GRANT 문 제외 (Aurora PostgreSQL)."""
    return "\n".join(
        line for line in sql.splitlines() if not line.strip().lower().startswith("grant ")
    )
