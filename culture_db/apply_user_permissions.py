"""Apply culture_db/user_permissions.sql (유저 권한 테이블 생성 + 권한 시드).

usage:
  python culture_db/apply_user_permissions.py          # 비었을 때만 시드
  python culture_db/apply_user_permissions.py --force   # 정의된 권한 재설정
"""
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

    from culture_db.permissions_setup import setup_user_permissions
    from culture_db.table_config import USER_PERMISSION_TABLE_NAME

    force = "--force" in sys.argv[1:]

    with psycopg2.connect(db_url()) as conn:
        result = setup_user_permissions(conn, seed=True, force_seed=force)
        conn.commit()

    print(
        f"OK: table={USER_PERMISSION_TABLE_NAME} "
        f"inserted={result['inserted']} total={result['total']}"
    )


if __name__ == "__main__":
    main()
