"""Amazon OpenSearch k-NN 인덱스·적재·검색."""

from __future__ import annotations

import json
from typing import Any

from schema_vector.config import (
    bedrock_embed_dimension,
    opensearch_basic_auth,
    opensearch_host,
    opensearch_index,
    opensearch_region,
    opensearch_use_iam,
)


def get_opensearch_client():
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from requests_aws4auth import AWS4Auth

    host_url = opensearch_host()
    host = host_url.replace("https://", "").replace("http://", "").rstrip("/")
    port = 443 if host_url.startswith("https") else 80
    use_ssl = host_url.startswith("https")

    http_auth: Any
    if opensearch_use_iam():
        import boto3

        session = boto3.Session()
        creds = session.get_credentials()
        if creds is None:
            raise RuntimeError("OpenSearch IAM 인증용 AWS 자격 증명이 없습니다.")
        frozen = creds.get_frozen_credentials()
        http_auth = AWS4Auth(
            frozen.access_key,
            frozen.secret_key,
            opensearch_region(),
            "es",
            session_token=frozen.token,
        )
    else:
        basic = opensearch_basic_auth()
        if not basic:
            raise RuntimeError(
                "OPENSEARCH_USE_IAM=0 이면 OPENSEARCH_USER/PASSWORD 가 필요합니다."
            )
        http_auth = basic

    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=http_auth,
        use_ssl=use_ssl,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
    )


def index_mapping(dimension: int | None = None) -> dict[str, Any]:
    dim = dimension or bedrock_embed_dimension()
    return {
        "settings": {
            "index": {
                "knn": True,
                "number_of_shards": 1,
                "number_of_replicas": 0,
            }
        },
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "doc_type": {"type": "keyword"},
                "schema": {"type": "keyword"},
                "table": {"type": "keyword"},
                "column": {"type": "keyword"},
                "table_korean": {"type": "text"},
                "text": {"type": "text"},
                "metadata_json": {"type": "text", "index": False},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dim,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                        "parameters": {"ef_construction": 128, "m": 16},
                    },
                },
            }
        },
    }


def ensure_index(client: Any | None = None, *, recreate: bool = False) -> str:
    client = client or get_opensearch_client()
    index = opensearch_index()
    exists = client.indices.exists(index=index)
    if exists and recreate:
        client.indices.delete(index=index)
        exists = False
    if not exists:
        client.indices.create(index=index, body=index_mapping())
    return index


def bulk_index_documents(
    documents: list[dict[str, Any]],
    *,
    client: Any | None = None,
    refresh: bool = True,
) -> tuple[int, list[str]]:
    """문서 + embedding 필드가 포함된 목록을 bulk upsert."""
    client = client or get_opensearch_client()
    index = opensearch_index()
    lines: list[str] = []
    for doc in documents:
        doc_id = doc["doc_id"]
        body = {
            "doc_id": doc_id,
            "doc_type": doc.get("doc_type", ""),
            "schema": doc.get("schema", ""),
            "table": doc.get("table", ""),
            "column": doc.get("column", ""),
            "table_korean": doc.get("table_korean", ""),
            "text": doc.get("text", ""),
            "metadata_json": json.dumps(doc.get("metadata", {}), ensure_ascii=False),
            "embedding": doc["embedding"],
        }
        lines.append(json.dumps({"index": {"_index": index, "_id": doc_id}}, ensure_ascii=False))
        lines.append(json.dumps(body, ensure_ascii=False))
    payload = "\n".join(lines) + "\n"
    result = client.bulk(body=payload, refresh=refresh)
    errors: list[str] = []
    if result.get("errors"):
        for item in result.get("items", []):
            action = item.get("index") or item.get("create") or {}
            if action.get("error"):
                errors.append(str(action["error"]))
    return len(documents), errors


def knn_search(
    query_vector: list[float],
    *,
    k: int = 8,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    client = client or get_opensearch_client()
    index = opensearch_index()
    body = {
        "size": k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_vector,
                    "k": k,
                }
            }
        },
        "_source": [
            "doc_id",
            "doc_type",
            "schema",
            "table",
            "column",
            "table_korean",
            "text",
            "metadata_json",
        ],
    }
    response = client.search(index=index, body=body)
    hits: list[dict[str, Any]] = []
    for hit in response.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        hits.append(
            {
                "score": hit.get("_score"),
                "doc_id": src.get("doc_id"),
                "doc_type": src.get("doc_type"),
                "schema": src.get("schema"),
                "table": src.get("table"),
                "column": src.get("column"),
                "table_korean": src.get("table_korean"),
                "text": src.get("text"),
                "metadata": _safe_json(src.get("metadata_json")),
            }
        )
    return hits


def _safe_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
