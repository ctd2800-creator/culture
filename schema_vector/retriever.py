"""스키마 벡터 검색 (질문 → 관련 테이블/컬럼).

순수 k-NN 만으로는 도메인 용어(예: '스타클럽등급')와 기간 표현(예:
'최근 3개월')이 섞이면 의미상 겹치는 무관한 컬럼이 상위로 올라오는 오탐이
생긴다. 이를 보정하기 위해 k-NN 후보를 넉넉히 받은 뒤, 질문에 등장한
컬럼명/별칭/한글 테이블명에 가중치를 더해 재랭킹(하이브리드)한다.
"""

from __future__ import annotations

from typing import Any

from culture_db.summary_tables import is_summary_table
from culture_db.table_config import (
    INST1_DATA_TABLES,
    INST1_TABLE_KOREAN_NAMES,
    LEGACY_EXCLUDED_TABLES,
    inst1_column_alias_map,
)
from schema_vector.bedrock_embed import embed_text
from schema_vector.config import schema_vector_enabled
from schema_vector.opensearch_store import knn_search

# 재랭킹 가중치
_BOOST_COLUMN_EXACT = 0.20  # 질문에 컬럼명이 그대로 등장
_BOOST_ALIAS = 0.18  # 질문에 컬럼 별칭이 등장
_BOOST_TABLE_KOREAN = 0.10  # 질문에 한글 테이블명이 등장


def _filter_excluded_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """폐기 테이블·내부 요약 테이블 문서는 검색 결과·데이터 사전 안내에서 제외."""
    out: list[dict[str, Any]] = []
    for hit in hits:
        table = (hit.get("table") or "").strip()
        if table in LEGACY_EXCLUDED_TABLES or is_summary_table(table):
            continue
        out.append(hit)
    return out


def _keyword_boost(query: str, hit: dict[str, Any], alias_map: dict[str, list[str]]) -> float:
    """질문 텍스트와 hit의 컬럼/별칭/한글테이블명 일치 가중치."""
    boost = 0.0
    column = (hit.get("column") or "").strip()
    if column:
        if column in query:
            boost += _BOOST_COLUMN_EXACT
        else:
            for alias in alias_map.get(column, ()):  # 별칭 등장 시
                if alias and alias in query:
                    boost += _BOOST_ALIAS
                    break
    table_korean = (hit.get("table_korean") or "").strip()
    if table_korean and table_korean in query:
        boost += _BOOST_TABLE_KOREAN
    return boost


def search_schema(query: str, *, k: int = 8) -> list[dict[str, Any]]:
    """질문과 유사한 테이블/컬럼 메타 문서 검색 (k-NN + 키워드 재랭킹)."""
    if not schema_vector_enabled():
        return []
    vector = embed_text(query)
    raw = knn_search(vector, k=max(k * 4, k + 12))
    hits = _filter_excluded_hits(raw)
    alias_map = inst1_column_alias_map()
    for hit in hits:
        base = hit.get("score") if isinstance(hit.get("score"), (int, float)) else 0.0
        hit["rerank_score"] = base + _keyword_boost(query, hit, alias_map)
    hits.sort(key=lambda h: h.get("rerank_score", 0.0), reverse=True)
    return hits[:k]


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
    # 질문 키워드(컬럼명/별칭)에 직접 부합해 가중치를 받은 테이블이 있으면,
    # 의미상 우연히 겹친 잡음 테이블 대신 그 테이블만 후보로 좁힌다.
    boosted_tables = {
        (hit.get("table") or "").strip()
        for hit in hits
        if (hit.get("rerank_score", 0.0) or 0.0) - (hit.get("score", 0.0) or 0.0) > 1e-6
    }
    # 안내에는 실제 분석 대상인 INST1 데이터 테이블만 후보로 표시한다.
    tables: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        table = (hit.get("table") or "").strip()
        if not table or table in seen:
            continue
        if table not in INST1_DATA_TABLES:
            continue
        if boosted_tables and table not in boosted_tables:
            continue
        seen.add(table)
        korean = (hit.get("table_korean") or "").strip() or INST1_TABLE_KOREAN_NAMES.get(
            table, ""
        )
        label = f"{korean}({table})" if korean else table
        tables.append(label)

    top = hits[0]
    top_label = top.get("doc_id") or ""
    score = top.get("score")
    score_txt = f"{score:.2f}" if isinstance(score, (int, float)) else "?"
    table_summary = ", ".join(tables[:3]) if tables else "해당 없음"
    if len(tables) > 3:
        table_summary += f" 외 {len(tables) - 3}개"

    return (
        "[데이터 사전] 메타 추출 → Bedrock 임베딩 → OpenSearch k-NN 파이프라인이 정상 동작했습니다. "
        f"질문과 유사한 스키마 {len(hits)}건을 검색했습니다 (인덱스: {index}, 최고 유사도 {score_txt}: {top_label}). "
        f"스키마 검색 후보: {table_summary}."
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
