"""TSHDE0ZCD 인스턴스 코드 → 인스턴스내용 디코딩."""

from __future__ import annotations

import os
from typing import Any

import psycopg2

from supabase.table_config import (
    COLUMN_INSTANCE_IDS,
    TSHDE0ZCD_SCHEMA,
    TSHDE0ZCD_TABLE,
)

from supabase.culture_db import connect_culture_db

_FALLBACK_GROUP_CODES = ("K00", "KFG", "KB0", "KC0")

_lookup_cache: dict[str, dict[tuple[str, str], str]] = {}
_group_company_lookup_cache: dict[str, str] | None = None

GROUP_COMPANY_INSTANCE_ID = "0036"

_db_url_cache: str | None = None


def _normalize_instance_code(column: str, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if not text:
        return ""
    if column == "연령코드" and text.isdigit():
        return text.zfill(3)
    if column == "거래기간구분" and text.isdigit():
        return text.zfill(2)
    return text


def _get_conn():
    return connect_culture_db(connect_timeout=15)


def clear_lookup_cache() -> None:
    global _group_company_lookup_cache
    _lookup_cache.clear()
    _group_company_lookup_cache = None


def load_group_company_lookup() -> dict[str, str]:
    """인스턴스식별자 0036 — 인스턴스코드 → 인스턴스내용 (전체 그룹회사)."""
    global _group_company_lookup_cache
    if _group_company_lookup_cache is not None:
        return _group_company_lookup_cache

    lookup: dict[str, str] = {}
    sql = (
        f'SELECT trim("그룹회사코드"), trim("인스턴스코드"), trim("인스턴스내용") '
        f'FROM "{TSHDE0ZCD_SCHEMA}"."{TSHDE0ZCD_TABLE}" '
        f'WHERE trim("인스턴스식별자") = %s '
        f'ORDER BY trim("그룹회사코드"), trim("인스턴스코드")'
    )
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (GROUP_COMPANY_INSTANCE_ID,))
            for grp, code, content in cur.fetchall():
                # KFG 마스터 우선, 동일 코드는 먼저 로드된 값 유지
                if code and code not in lookup:
                    lookup[code] = content or code
                elif grp == "KFG" and code:
                    lookup[code] = content or code

    _group_company_lookup_cache = lookup
    return lookup


def load_instance_lookup(group_company: str) -> dict[tuple[str, str], str]:
    """(인스턴스식별자, 인스턴스코드) → 인스턴스내용."""
    group = (group_company or "KFG").strip()
    if group in _lookup_cache:
        return _lookup_cache[group]

    groups = [group]
    for g in _FALLBACK_GROUP_CODES:
        if g not in groups:
            groups.append(g)

    lookup: dict[tuple[str, str], str] = {}
    inst_ids = list({v for v in COLUMN_INSTANCE_IDS.values() if v != GROUP_COMPANY_INSTANCE_ID})
    sql = (
        f'SELECT trim("그룹회사코드"), trim("인스턴스식별자"), '
        f'trim("인스턴스코드"), trim("인스턴스내용") '
        f'FROM "{TSHDE0ZCD_SCHEMA}"."{TSHDE0ZCD_TABLE}" '
        f'WHERE trim("그룹회사코드") = ANY(%s) '
        f'OR trim("인스턴스식별자") = ANY(%s)'
    )
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (groups, inst_ids))
            for grp, inst_id, code, content in cur.fetchall():
                key = (inst_id, code)
                if grp == group or key not in lookup:
                    lookup[key] = content or code

    for code, content in load_group_company_lookup().items():
        lookup.setdefault((GROUP_COMPANY_INSTANCE_ID, code), content)

    _lookup_cache[group] = lookup
    return lookup


def decode_instance_value(
    column: str,
    value: Any,
    lookup: dict[tuple[str, str], str],
) -> Any:
    if value is None:
        return value
    code = _normalize_instance_code(column, value)
    if not code:
        return value

    if column == "그룹회사코드":
        label = load_group_company_lookup().get(code) or lookup.get(
            (GROUP_COMPANY_INSTANCE_ID, code)
        )
        return label if label else value

    inst_id = COLUMN_INSTANCE_IDS.get(column)
    if not inst_id:
        return value
    label = lookup.get((inst_id, code))
    return label if label else value


def decode_rows(
    rows: list[dict[str, Any]],
    *,
    group_company: str,
    lookup: dict[tuple[str, str], str] | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return rows
    zcd = lookup if lookup is not None else load_instance_lookup(group_company)
    decoded: list[dict[str, Any]] = []
    for row in rows:
        new_row: dict[str, Any] = {}
        for col, val in row.items():
            if col in COLUMN_INSTANCE_IDS:
                new_row[col] = decode_instance_value(col, val, zcd)
            else:
                new_row[col] = val
        decoded.append(new_row)
    return decoded


def decode_inst1_data(
    data: dict[str, list[dict[str, Any]]],
    group_company: str,
) -> dict[str, list[dict[str, Any]]]:
    if not data:
        return data
    lookup = load_instance_lookup(group_company)
    return {key: decode_rows(rows, group_company=group_company, lookup=lookup) for key, rows in data.items()}
