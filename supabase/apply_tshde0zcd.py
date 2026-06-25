"""Apply supabase/tshde0zcd.sql using AURORA_DB_URL."""
from __future__ import annotations

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
    sys.path.insert(0, str(ROOT))
    import psycopg2

    from supabase.table_config import TSHDE0ZCD_SCHEMA, TSHDE0ZCD_TABLE
    from supabase.tshde0zcd_setup import ensure_tshde0zcd_table

    with psycopg2.connect(db_url()) as conn:
        ensure_tshde0zcd_table(conn)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                """
                select column_name, data_type, character_maximum_length,
                       is_nullable
                from information_schema.columns
                where table_schema = %s and table_name = %s
                order by ordinal_position
                """,
                (TSHDE0ZCD_SCHEMA, TSHDE0ZCD_TABLE),
            )
            rows = cur.fetchall()

    fq = f"{TSHDE0ZCD_SCHEMA}.{TSHDE0ZCD_TABLE}"
    print(f"OK: applied tshde0zcd.sql (table={fq})")
    print(f"Columns ({len(rows)}):")
    for name, dtype, char_len, nullable in rows:
        type_label = f"{dtype}({char_len})" if char_len else dtype
        print(f"  - {name}: {type_label} ({nullable})")


if __name__ == "__main__":
    main()
