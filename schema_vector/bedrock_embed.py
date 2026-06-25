"""Amazon Bedrock Titan 임베딩."""

from __future__ import annotations

import json
from typing import Any

import boto3

from schema_vector.config import (
    bedrock_embed_dimension,
    bedrock_embed_model,
    bedrock_embed_region,
    load_dotenv,
)


def _bedrock_credentials() -> dict[str, str] | None:
    load_dotenv()
    import os

    key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    if not key or not secret:
        return None
    creds: dict[str, str] = {
        "aws_access_key_id": key,
        "aws_secret_access_key": secret,
    }
    for name in ("AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"):
        token = os.environ.get(name, "").strip()
        if token:
            creds["aws_session_token"] = token
            break
    return creds


def get_bedrock_runtime_client():
    creds = _bedrock_credentials()
    region = bedrock_embed_region()
    if creds:
        return boto3.client("bedrock-runtime", region_name=region, **creds)
    profile = __import__("os").environ.get("AWS_PROFILE", "default")
    return boto3.Session(profile_name=profile, region_name=region).client(
        "bedrock-runtime"
    )


def embed_text(text: str, *, client: Any | None = None) -> list[float]:
    """단일 텍스트 임베딩."""
    client = client or get_bedrock_runtime_client()
    model = bedrock_embed_model()
    dim = bedrock_embed_dimension()
    body: dict[str, Any] = {"inputText": text}
    if "titan-embed-text-v2" in model:
        body["dimensions"] = dim
        body["normalize"] = True
    response = client.invoke_model(
        modelId=model,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body).encode("utf-8"),
    )
    payload = json.loads(response["body"].read())
    embedding = payload.get("embedding")
    if not embedding:
        raise RuntimeError(f"Bedrock 임베딩 응답에 embedding 없음: {payload}")
    return [float(x) for x in embedding]


def embed_texts(
    texts: list[str],
    *,
    client: Any | None = None,
    batch_log_every: int = 25,
) -> list[list[float]]:
    """여러 텍스트 순차 임베딩 (Titan은 1건씩 호출)."""
    client = client or get_bedrock_runtime_client()
    vectors: list[list[float]] = []
    for i, text in enumerate(texts, start=1):
        vectors.append(embed_text(text, client=client))
        if batch_log_every and i % batch_log_every == 0:
            print(f"  embedded {i}/{len(texts)}", flush=True)
    return vectors
