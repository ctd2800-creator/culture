"""Aurora/PostgreSQL information_schema + pg_description 메타 추출."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from culture_db.summary_tables import is_summary_table
from culture_db.table_config import (
    COLUMN_INSTANCE_IDS,
    INST1_COLUMN_DEFINITIONS,
    INST1_TABLE_ALIASES,
    INST1_TABLE_KOREAN_NAMES,
    LEGACY_EXCLUDED_TABLES,
    inst1_column_aliases_for_table,
)


@dataclass
class ColumnMeta:
    name: str
    data_type: str
    nullable: bool
    comment: str = ""
    is_pk: bool = False
    ordinal: int = 0
    aliases: list[str] = field(default_factory=list)


@dataclass
class TableMeta:
    schema: str
    table: str
    table_korean: str = ""
    table_comment: str = ""
    columns: list[ColumnMeta] = field(default_factory=list)
    row_estimate: int | None = None
    aliases: list[str] = field(default_factory=list)

    @property
    def fqn(self) -> str:
        return f'{self.schema}."{self.table}"'

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


_COLUMNS_SQL = """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    obj_description(c.oid, 'pg_class') AS table_comment,
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
    NOT a.attnotnull AS nullable,
    col_description(c.oid, a.attnum) AS column_comment,
    a.attnum AS ordinal
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
WHERE c.relkind = 'r'
  AND n.nspname = ANY(%s)
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY n.nspname, c.relname, a.attnum
"""

_PK_SQL = """
SELECT
    tc.table_schema,
    tc.table_name,
    kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
 AND tc.table_name = kcu.table_name
WHERE tc.constraint_type = 'PRIMARY KEY'
  AND tc.table_schema = ANY(%s)
"""

_ROW_EST_SQL = """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    GREATEST(c.reltuples::bigint, 0) AS row_estimate
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND n.nspname = ANY(%s)
"""


def _fetch_pk_columns(cur, schemas: list[str]) -> set[tuple[str, str, str]]:
    cur.execute(_PK_SQL, (schemas,))
    return {
        (row[0], row[1], row[2])
        for row in cur.fetchall()
    }


def _fetch_row_estimates(cur, schemas: list[str]) -> dict[tuple[str, str], int]:
    cur.execute(_ROW_EST_SQL, (schemas,))
    return {(row[0], row[1]): int(row[2] or 0) for row in cur.fetchall()}


def extract_table_metadata(conn, schemas: list[str] | None = None) -> list[TableMeta]:
    """스키마 목록의 테이블·컬럼 메타데이터 추출."""
    from schema_vector.config import metadata_schemas

    schemas = schemas or metadata_schemas()
    with conn.cursor() as cur:
        pk_cols = _fetch_pk_columns(cur, schemas)
        row_est = _fetch_row_estimates(cur, schemas)
        cur.execute(_COLUMNS_SQL, (schemas,))
        rows = cur.fetchall()

    tables: dict[tuple[str, str], TableMeta] = {}
    for (
        schema_name,
        table_name,
        table_comment,
        column_name,
        data_type,
        nullable,
        column_comment,
        ordinal,
    ) in rows:
        if table_name in LEGACY_EXCLUDED_TABLES or is_summary_table(table_name):
            continue
        key = (schema_name, table_name)
        if key not in tables:
            korean = INST1_TABLE_KOREAN_NAMES.get(table_name, "")
            aliases = list(INST1_TABLE_ALIASES.get(table_name, ()))
            tables[key] = TableMeta(
                schema=schema_name,
                table=table_name,
                table_korean=korean,
                table_comment=(table_comment or "").strip(),
                row_estimate=row_est.get(key),
                aliases=aliases,
            )
        tables[key].columns.append(
            ColumnMeta(
                name=column_name,
                data_type=data_type,
                nullable=bool(nullable),
                comment=(column_comment or "").strip(),
                is_pk=(schema_name, table_name, column_name) in pk_cols,
                ordinal=int(ordinal),
            )
        )

    return sorted(tables.values(), key=lambda t: (t.schema, t.table))


def enrich_with_column_definitions(table: TableMeta) -> TableMeta:
    """table_config 컬럼정의내용을 comment에 반영."""
    defs = INST1_COLUMN_DEFINITIONS.get(table.table, {})
    for col in table.columns:
        defn = defs.get(col.name)
        if defn:
            col.comment = defn
    return table


def enrich_with_column_aliases(table: TableMeta) -> TableMeta:
    """table_config의 컬럼 별칭(검색어)을 ColumnMeta.aliases에 반영."""
    amap = inst1_column_aliases_for_table(table.table)
    for col in table.columns:
        al = amap.get(col.name)
        if al:
            col.aliases = list(al)
    return table


def enrich_with_instance_ids(table: TableMeta) -> TableMeta:
    """컬럼별 TSHDE0ZCD 인스턴스 식별자 힌트 (table_config)."""
    for col in table.columns:
        inst_id = COLUMN_INSTANCE_IDS.get(col.name)
        if inst_id and inst_id not in col.comment:
            suffix = f" / 인스턴스식별자: {inst_id}"
            col.comment = (col.comment + suffix).strip(" /")
    return table


def tables_to_json(tables: list[TableMeta]) -> str:
    payload = [t.to_json() for t in tables]
    return json.dumps(payload, ensure_ascii=False, indent=2)
