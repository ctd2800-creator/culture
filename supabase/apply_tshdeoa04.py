"""Apply supabase/tshdeoa04.sql using SUPABASE_DB_URL."""
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
    _load_dotenv()
    raw = os.environ.get("SUPABASE_DB_URL", "").strip() or _read_windows_env("SUPABASE_DB_URL")
    if not raw:
        raise SystemExit("SUPABASE_DB_URL 환경 변수가 없습니다.")
    if "sslmode=" not in raw:
        raw += ("&" if "?" in raw else "?") + "sslmode=require"
    return raw


def main() -> None:
    sys.path.insert(0, str(ROOT))
    import psycopg2

    from supabase.table_config import TSHDEOA04_SCHEMA, TSHDEOA04_TABLE
    from supabase.tshdeoa04_setup import ensure_tshdeoa04_table

    with psycopg2.connect(db_url()) as conn:
        ensure_tshdeoa04_table(conn)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                """
                select column_name, data_type, character_maximum_length,
                       numeric_precision, numeric_scale, is_nullable
                from information_schema.columns
                where table_schema = %s and table_name = %s
                order by ordinal_position
                """,
                (TSHDEOA04_SCHEMA, TSHDEOA04_TABLE),
            )
            rows = cur.fetchall()

    fq = f"{TSHDEOA04_SCHEMA}.{TSHDEOA04_TABLE}"
    print(f"OK: applied tshdeoa04.sql (table={fq})")
    print(f"Columns ({len(rows)}):")
    for name, dtype, char_len, num_prec, num_scale, nullable in rows:
        if char_len:
            type_label = f"{dtype}({char_len})"
        elif num_prec is not None:
            type_label = f"{dtype}({num_prec},{num_scale or 0})"
        else:
            type_label = dtype
        print(f"  - {name}: {type_label} ({nullable})")


if __name__ == "__main__":
    main()
