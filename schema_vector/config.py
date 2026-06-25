"""schema_vector 환경 변수."""

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


def _env(name: str, default: str = "") -> str:
    load_dotenv()
    return os.environ.get(name, default).strip()


def schema_vector_enabled() -> bool:
    return bool(_env("OPENSEARCH_HOST"))


def opensearch_host() -> str:
    host = _env("OPENSEARCH_HOST")
    if not host:
        raise RuntimeError("OPENSEARCH_HOST 환경 변수가 필요합니다.")
    if not host.startswith("http"):
        host = f"https://{host}"
    return host.rstrip("/")


def opensearch_index() -> str:
    return _env("OPENSEARCH_INDEX", "culture-schema-meta")


def opensearch_region() -> str:
    return _env("OPENSEARCH_REGION", _env("AWS_REGION", "ap-northeast-2"))


def opensearch_use_iam() -> bool:
    return _env("OPENSEARCH_USE_IAM", "1").lower() not in ("0", "false", "no")


def opensearch_basic_auth() -> tuple[str, str] | None:
    user = _env("OPENSEARCH_USER")
    password = _env("OPENSEARCH_PASSWORD")
    if user and password:
        return user, password
    return None


def bedrock_embed_model() -> str:
    return _env("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")


def bedrock_embed_dimension() -> int:
    return int(_env("BEDROCK_EMBED_DIMENSION", "1024"))


def bedrock_embed_region() -> str:
    return _env("AWS_BEDROCK_REGION", _env("AWS_REGION", "ap-northeast-2"))


def metadata_schemas() -> list[str]:
    raw = _env("SCHEMA_VECTOR_SCHEMAS", "INST1,public")
    return [s.strip() for s in raw.split(",") if s.strip()]
