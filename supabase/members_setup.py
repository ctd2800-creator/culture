"""회원 테이블 DDL 적용 및 시드."""

from __future__ import annotations

import os
from pathlib import Path

from werkzeug.security import generate_password_hash

from supabase.members_seed import MEMBER_ROWS, MEMBER_UPSERT_SQL
from supabase.table_config import MEMBER_TABLE_NAME

_SQL_PATH = Path(__file__).resolve().parent / "members.sql"


def ensure_members_table(conn) -> None:
    ddl = _SQL_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(ddl)


def seed_members(conn, *, force: bool = False) -> int:
    """회원 10명 upsert. force=False 이면 테이블이 비었을 때만 삽입."""
    with conn.cursor() as cur:
        if not force:
            cur.execute(f'SELECT COUNT(*) FROM public."{MEMBER_TABLE_NAME}"')
            if (cur.fetchone() or (0,))[0] > 0:
                return 0
        for row_id, plain_pw, name, email, dept in MEMBER_ROWS:
            cur.execute(
                MEMBER_UPSERT_SQL,
                (
                    row_id,
                    generate_password_hash(plain_pw),
                    name,
                    email,
                    dept,
                ),
            )
    return len(MEMBER_ROWS)


def setup_members(conn, *, seed: bool = True, force_seed: bool = False) -> dict[str, int]:
    ensure_members_table(conn)
    inserted = seed_members(conn, force=force_seed) if seed else 0
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM public."{MEMBER_TABLE_NAME}"')
        total = (cur.fetchone() or (0,))[0]
    return {"inserted": inserted, "total": int(total)}
