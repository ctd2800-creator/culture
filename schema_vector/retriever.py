"""스키마 벡터 검색 (질문 → 관련 테이블/컬럼)."""

from __future__ import annotations

from typing import Any

from culture_db.table_config import LEGACY_EXCLUDED_TABLES
from schema_vector.bedrock_embed import embed_text
from schema_vector.config import schema_vector_enabled
from schema_vector.opensearch_store import knn_search


def _filter_excluded_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """폐기 테이블 문서는 검색 결과·데이터 사전 안내에서 제외."""
    return [
        hit
        for hit in hits
        if (hit.get("table") or "").strip() not in LEGACY_EXCLUDED_TABLES
    ]


def search_schema(query: str, *, k: int = 8) -> list[dict[str, Any]]:
    """질문과 유사한 테이블/컬럼 메타 문서 검색."""
    if not schema_vector_enabled():
        return []
    vector = embed_text(query)
    raw = knn_search(vector, k=max(k * 3, k + 6))
    return _filter_excluded_hits(raw)[:k]


def build_schema_pipeline_notice(query: str, hits: list[dict[str, Any]]) -> str:
    """채팅 UI용 데이터 사전 파이프라인 상태 문구."""
    from schema_vector.config import opensearch_index, schema_vector_enabled

    if not schema_vector_enabled():
        return ""
    index = opensearch_index()
    if not hits:
        return (
            "[데이터 사전] OpenSearch에 연결되었습니다. "
            f"이번 질문과 유사한 메타 문서는 인덱스({index})에서 찾지 못했습니다."
        )
    tables: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        table = (hit.get("table") or "").strip()
        if not table or table in seen:
            continue
        seen.add(table)
        korean = (hit.get("table_korean") or "").strip()
        label = f"{korean}({table})" if korean else table
        tables.append(label)
    top = hits[0]
    top_label = top.get("doc_id") or ""
    score = top.get("score")
    score_txt = f"{score:.2f}" if isinstance(score, (int, float)) else "?"
    table_summary = ", ".join(tables[:3])
    if len(tables) > 3:
        table_summary += f" 외 {len(tables) - 3}개"
    return (
        "[데이터 사전] 메타 추출 → Bedrock 임베딩 → OpenSearch k-NN 파이프라인이 정상 동작했습니다. "
        f"질문과 관련 스키마 {len(hits)}건을 검색했습니다 (인덱스: {index}, 최고 유사도 {score_txt}: {top_label}). "
        f"관련 테이블: {table_summary}."
    )


def hits_to_schema_context(hits: list[dict[str, Any]]) -> str:
    """검색 hit 목록을 Bedrock 질문 분석용 스키마 힌트 문자열로 변환."""
    if not hits:
        return ""
    lines = ["OpenSearch 스키마 검색 결과 (유사도 순):"]
    seen_tables: set[str] = set()
    for hit in hits:
        table = hit.get("table") or ""
        korean = hit.get("table_korean") or ""
        doc_type = hit.get("doc_type") or ""
        column = hit.get("column") or ""
        score = hit.get("score")
        score_txt = f"{score:.3f}" if isinstance(score, (int, float)) else "?"
        if doc_type == "table":
            lines.append(f"- 테이블 {table}({korean}) score={score_txt}")
            seen_tables.add(table)
        else:
            lines.append(
                f"- 컬럼 {table}.{column} ({korean}) score={score_txt}"
            )
            seen_tables.add(table)
    if seen_tables:
        lines.append("관련 테이블 후보: " + ", ".join(sorted(seen_tables)))
    return "\n".join(lines)


def get_schema_context_for_query(query: str, *, k: int = 6) -> str:
    """Bedrock 질문 분석용 스키마 힌트 문자열."""
    return hits_to_schema_context(search_schema(query, k=k))
