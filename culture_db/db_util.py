"""Postgres(Aurora) 연결 유틸."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv() -> None:
    try:
        from dotenv import load_dotenv as _load
    except ImportError:
        return
    for path in (ROOT / ".env.local", ROOT / ".env"):
        if path.is_file():
            _load(path, override=False)


def read_windows_env(name: str) -> str:
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


def get_db_url() -> str:
    load_dotenv()
    raw = os.environ.get("AURORA_DB_URL", "").strip() or read_windows_env("AURORA_DB_URL")
    if not raw:
        raise SystemExit(
            "AURORA_DB_URL 환경 변수가 없습니다.\n"
            ".env.local 또는 Windows 사용자 환경 변수를 확인하세요."
        )
    from culture_db.culture_db import _normalize_url

    return _normalize_url(raw)


def enable_db_writes(cur) -> None:
    """읽기 전용 세션일 때 쓰기 허용."""
    cur.execute("SET default_transaction_read_only = off")
    cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE")
    cur.execute("SET transaction_read_only = off")
