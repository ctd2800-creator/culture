"""Culture 앱 DB 연결 — Amazon Aurora PostgreSQL."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_db_url_cache: str | None = None


def load_dotenv() -> None:
    try:
        from dotenv import load_dotenv as _load
    except ImportError:
        return
    for path in (ROOT / ".env.local", ROOT / ".env"):
        if path.is_file():
            _load(path, override=False)


def _normalize_url(raw: str) -> str:
    raw = raw.strip()
    if "sslmode=" not in raw:
        raw += ("&" if "?" in raw else "?") + "sslmode=require"
    return raw


def aurora_db_url() -> str:
    load_dotenv()
    raw = os.environ.get("AURORA_DB_URL", "").strip()
    if not raw:
        raise RuntimeError(
            "`AURORA_DB_URL` 환경 변수를 설정해야 합니다. (.env.local 확인)"
        )
    return _normalize_url(raw)


def get_culture_db_url() -> str:
    global _db_url_cache
    if _db_url_cache is not None:
        return _db_url_cache
    _db_url_cache = aurora_db_url()
    return _db_url_cache


def culture_db_configured() -> bool:
    load_dotenv()
    return bool(os.environ.get("AURORA_DB_URL", "").strip())


def culture_db_backend() -> str:
    return "aurora" if culture_db_configured() else ""


def using_aurora() -> bool:
    return culture_db_configured()


def connect_culture_db(*, connect_timeout: int = 15):
    """Aurora PostgreSQL 연결.

    대용량(수천만 행) 집계 시 디스크 외부정렬을 피하도록 세션 work_mem를
    상향한다. AURORA_WORK_MEM(예: '256MB')로 조정 가능.
    """
    import psycopg2

    global _db_url_cache
    url = get_culture_db_url()
    work_mem = os.environ.get("AURORA_WORK_MEM", "256MB").strip()
    options = f"-c work_mem={work_mem}" if work_mem else None
    conn = psycopg2.connect(
        url,
        connect_timeout=connect_timeout,
        options=options,
    )
    _db_url_cache = url
    return conn
