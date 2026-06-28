"""Apply culture_db/question_log.sql (질문 내역 테이블 생성)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def db_url() -> str:
    sys.path.insert(0, str(ROOT))
    from culture_db.db_util import get_db_url

    return get_db_url()


def main() -> None:
    sys.path.insert(0, str(ROOT))
    import psycopg2

    from culture_db.question_log_setup import ensure_question_log_table
    from culture_db.table_config import QUESTION_LOG_TABLE_NAME

    with psycopg2.connect(db_url()) as conn:
        ensure_question_log_table(conn)
        conn.commit()

    print(f"OK: table={QUESTION_LOG_TABLE_NAME}")


if __name__ == "__main__":
    main()
