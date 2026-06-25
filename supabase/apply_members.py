"""Apply supabase/members.sql and seed 10 members."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in (ROOT / ".env.local", ROOT / ".env", Path(__file__).parent / ".env.local"):
        if path.is_file():
            load_dotenv(path, override=False)


def _read_windows_env(name: str) -> str:
    try:
        import winreg
    except ImportError:
        return ""
    for hive, subkey in (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ):
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        except OSError:
            continue
    return ""


def db_url() -> str:
    sys.path.insert(0, str(ROOT))
    from supabase.db_util import get_db_url
    return get_db_url()


def main() -> None:
    parser = argparse.ArgumentParser(description="회원 테이블 생성 및 10명 시드")
    parser.add_argument(
        "--force-seed",
        action="store_true",
        help="기존 데이터가 있어도 10명 upsert",
    )
    parser.add_argument("--ddl-only", action="store_true", help="테이블만 생성")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    import psycopg2

    from supabase.members_setup import setup_members
    from supabase.table_config import MEMBER_TABLE_NAME

    with psycopg2.connect(db_url()) as conn:
        result = setup_members(
            conn,
            seed=not args.ddl_only,
            force_seed=args.force_seed,
        )
        conn.commit()

    print(f"OK: table={MEMBER_TABLE_NAME}")
    print(f"  inserted/updated this run: {result['inserted']}")
    print(f"  total rows: {result['total']}")


if __name__ == "__main__":
    main()
