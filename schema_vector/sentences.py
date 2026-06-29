"""메타 JSON → 임베딩용 자연어 문장."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from schema_vector.metadata_extract import ColumnMeta, TableMeta


def _column_line(col: ColumnMeta) -> str:
    parts = [col.name]
    if col.is_pk:
        parts.append("PK")
    parts.append(col.data_type)
    if not col.nullable:
        parts.append("NOT NULL")
    if col.comment:
        parts.append(col.comment)
    return " · ".join(parts)


def table_to_sentence(table: TableMeta) -> str:
    """테이블 단위 문서."""
    label = table.table_korean or table.table
    lines = [
        f'테이블 {table.table}({label})은 {table.schema} 스키마에 있습니다.',
    ]
    if table.table_comment:
        lines.append(table.table_comment)
    if table.aliases:
        lines.append("별칭: " + ", ".join(table.aliases))
    if table.row_estimate is not None and table.row_estimate > 0:
        lines.append(f"대략 {table.row_estimate:,}건의 행이 있습니다.")

    pk_cols = [c.name for c in table.columns if c.is_pk]
    if pk_cols:
        lines.append("기본키: " + ", ".join(pk_cols))

    col_names = [c.name for c in table.columns[:20]]
    if col_names:
        lines.append("주요 컬럼: " + ", ".join(col_names))
        if len(table.columns) > 20:
            lines.append(f"외 {len(table.columns) - 20}개 컬럼")

    return "\n".join(lines)


def column_to_sentence(table: TableMeta, col: ColumnMeta) -> str:
    """컬럼 단위 문서."""
    label = table.table_korean or table.table
    lines = [
        f"{table.schema}.{table.table}({label}) 테이블의 컬럼 {col.name}.",
        _column_line(col),
    ]
    if col.aliases:
        lines.append("별칭/검색어: " + ", ".join(col.aliases))
    if table.table_comment:
        lines.append(f"테이블 설명: {table.table_comment}")
    return "\n".join(lines)


def build_schema_documents(tables: list[TableMeta]) -> list[dict[str, Any]]:
    """OpenSearch 적재용 문서 목록 (text + 메타)."""
    docs: list[dict[str, Any]] = []
    for table in tables:
        table_id = f"{table.schema}.{table.table}"
        table_text = table_to_sentence(table)
        docs.append(
            {
                "doc_id": f"{table_id}#table",
                "doc_type": "table",
                "schema": table.schema,
                "table": table.table,
                "column": "",
                "table_korean": table.table_korean,
                "text": table_text,
                "metadata": table.to_json(),
            }
        )
        for col in table.columns:
            col_text = column_to_sentence(table, col)
            docs.append(
                {
                    "doc_id": f"{table_id}#{col.name}",
                    "doc_type": "column",
                    "schema": table.schema,
                    "table": table.table,
                    "column": col.name,
                    "table_korean": table.table_korean,
                    "text": col_text,
                    "metadata": {
                        "schema": table.schema,
                        "table": table.table,
                        "table_korean": table.table_korean,
                        "column": asdict(col),
                    },
                }
            )
    return docs
