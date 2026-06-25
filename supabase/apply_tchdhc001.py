"""Apply supabase/tchdhc001.sql using AURORA_DB_URL."""
from __future__ import annotations

import os
import sys
from pathlib import Path

SQL_PATH = Path(__file__).resolve().parent / "tchdhc001.sql"
ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in (
        ROOT / ".env.local",
        ROOT / ".env",
        Path(__file__).resolve().parent / ".env.local",
    ):
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
    from supabase.table_config import TABLE_NAME

    sql = SQL_PATH.read_text(encoding="utf-8")
    import psycopg

    with psycopg.connect(db_url(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                """
                select column_name, data_type, is_nullable
                from information_schema.columns
                where table_schema = 'public' and table_name = %s
                order by ordinal_position;
                """,
                (TABLE_NAME,),
            )
            rows = cur.fetchall()

    print(f"OK: applied {SQL_PATH.name} (table={TABLE_NAME})")
    print(f"Columns ({len(rows)}):")
    for name, dtype, nullable in rows:
        print(f"  - {name}: {dtype} ({nullable})")


if __name__ == "__main__":
    main()
