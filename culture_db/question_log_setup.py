"""질문 내역 테이블 DDL 적용 및 저장·조회."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from culture_db.sql_util import ddl_without_grants
from culture_db.table_config import QUESTION_LOG_TABLE_NAME

_SQL_PATH = Path(__file__).resolve().parent / "question_log.sql"

_TABLE = f'public."{QUESTION_LOG_TABLE_NAME}"'


def ensure_question_log_table(conn) -> None:
    ddl = ddl_without_grants(_SQL_PATH.read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        cur.execute(ddl)


def insert_question(conn, *, member_id: str, question: str) -> None:
    """로그인 사용자의 질문 1건 저장."""
    member_id = (member_id or "").strip()
    question = (question or "").strip()
    if not member_id or not question:
        return
    with conn.cursor() as cur:
        cur.execute(
            f'INSERT INTO {_TABLE} ("아이디", "질문내용") VALUES (%s, %s)',
            (member_id, question),
        )


def fetch_recent_questions(
    conn, *, member_id: str, limit: int = 50
) -> list[dict[str, Any]]:
    """해당 사용자의 최근 질문 내역 (최신순)."""
    member_id = (member_id or "").strip()
    if not member_id:
        return []
    with conn.cursor() as cur:
        cur.execute(
            f'SELECT "일련번호", "질문내용", "등록일시" '
            f'FROM {_TABLE} WHERE "아이디" = %s '
            f'ORDER BY "등록일시" DESC, "일련번호" DESC LIMIT %s',
            (member_id, int(limit)),
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for seq, question, created_at in rows:
        out.append(
            {
                "id": int(seq),
                "question": question,
                "created_at": created_at.isoformat() if created_at else "",
            }
        )
    return out
