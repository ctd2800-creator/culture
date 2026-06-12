"""
INST1 TSHDEOA01 / TSHDEOA02 질문 분석·데이터 추출 에이전트.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

import os

import psycopg2

from culture_zcd_lookup import decode_inst1_data
from supabase.table_config import (
    INST1_AGGREGATE_COLUMNS,
    INST1_GROUP_ALIASES,
    INST1_JOIN_KEYS,
    INST1_NUMERIC_COLUMNS,
    INST1_TABLE_ALIASES,
    INST1_TABLE_COLUMNS,
    INST1_TABLE_KOREAN_NAMES,
    INST1_TABLE_ORDER,
    INST1_TABLE_SQL_ALIAS,
    TSHDEOA01_KOREAN_NAME,
    TSHDEOA01_SCHEMA,
    TSHDEOA01_TABLE,
    TSHDEOA02_KOREAN_NAME,
    TSHDEOA02_SCHEMA,
    TSHDEOA02_TABLE,
    TSHDE0ZCD_KOREAN_NAME,
    TSHDE0ZCD_SCHEMA,
    TSHDE0ZCD_TABLE,
)

ANALYZE_SYSTEM_PROMPT = """당신은 Culture 앱의 질문 분석 에이전트입니다.
사용자 질문을 읽고 JSON만 출력하세요(다른 텍스트 금지).

가능한 intent:
- inst1_table_prompt: 테이블 한글명만 언급(예: "그룹고객기본정보") — 데이터 조회 전 추천 질문 제안
- inst1_aggregate_prompt: 집계 데이터 조회 전 집계 컬럼 선택 요청 (예: "집계 데이터를 보여드릴까요?")
- inst1_column_desc: 테이블 컬럼 설명 요청 (예: "그룹고객기본정보 컬럼 설명")
- inst1_data_summary: 테이블 데이터 요약 요청 (예: "그룹고객기본정보 데이터 요약")
- inst1_extract: TSHDEOA01·TSHDEOA02·TSHDE0ZCD 테이블에서 데이터 조회·추출 요청
- inst1_chart: 직전 집계 조회 결과로 막대 차트 생성
- general_chat: 일반 대화

JSON 스키마:
{
  "intent": "inst1_table_prompt|inst1_aggregate_prompt|inst1_column_desc|inst1_data_summary|inst1_extract|inst1_chart|general_chat",
  "query_type": "select|aggregate|join_aggregate",
  "tables": ["TSHDEOA01", "TSHDEOA02"],
  "month": "YYYYMM 또는 빈 문자열",
  "group_company": "KFG 등 또는 빈 문자열",
  "customer_id": "10자리 그룹고객식별자 또는 null",
  "group_by": ["집계 기준 컬럼명"] 또는 null,
  "reason": "판단 근거 한 줄"
}

테이블 한글명: 그룹고객기본정보=TSHDEOA01, 그룹고객거래기본=TSHDEOA02, 그룹고객분석인스턴스목록=TSHDE0ZCD
라우팅 규칙:
- 테이블명만 → inst1_table_prompt
- "집계 데이터"·"집계 데이터를 보여" (집계 컬럼 미지정) → inst1_aggregate_prompt
- "컬럼"·"필드" 언급(데이터 조회·요약 아님) → inst1_column_desc
- "요약"·"정리" 언급 → inst1_data_summary
- "조회"·"보여"·"데이터" 등 데이터 조회 → inst1_extract
inst1_extract 예: "그룹고객기본정보 202604 조회", "그룹고객거래기본 거래잔액 조회"
inst1_column_desc 예: "그룹고객거래기본의 컬럼", "그룹고객기본정보 컬럼 설명"
inst1_data_summary 예: "그룹고객기본정보 데이터 요약"
집계 예: "26.04월 그룹고객기본정보 KB스타클럽그룹최고등급별, 성별구분별 고객수 집계"
  → tables=["TSHDEOA01"], query_type=aggregate, group_by=["KB스타클럽그룹최고등급","성별구분"]
TSHDEOA01(그룹고객기본정보)·TSHDEOA02(그룹고객거래기본) 모두 컬럼별 고객수 집계 가능.
집계 예2: "그룹고객거래기본 급여이체여부별, 당월상품신규계약수별 집계" → tables=["TSHDEOA02"]
조인 집계 예: "그룹고객기본정보·그룹고객거래기본 참조 2026.04 KB스타클럽그룹본인등급별, 보유수신상품계약수별 고객수 집계"
  → query_type=join_aggregate, join_tables=["TSHDEOA01","TSHDEOA02"]
tables는 inst1_extract일 때만 채우고, 언급 없으면 둘 다 포함할 수 있습니다."""

TABLE_HINTS: dict[str, tuple[str, ...]] = {
    "TSHDEOA01": (
        "TSHDEOA01",
        "TSHDE0A01",
        TSHDEOA01_KOREAN_NAME,
        "그룹 고객 기본정보",
        "그룹고객 기본정보",
        "고객속성",
        "고객 속성",
        "연령코드",
        "스타클럽",
        "당월고객계열사",
        "활동고객계열사",
        "핵심고객계열사",
    ),
    "TSHDEOA02": (
        "TSHDEOA02",
        "TSHDE0A02",
        TSHDEOA02_KOREAN_NAME,
        "그룹 고객 거래기본",
        "그룹고객 거래기본",
        "거래잔액",
        "수신잔액",
        "여신잔액",
        "거래기간",
        "창구거래",
        "비대면거래",
        "상품계약",
    ),
    "TSHDE0ZCD": (
        "TSHDE0ZCD",
        TSHDE0ZCD_KOREAN_NAME,
        "그룹 고객 분석 인스턴스 목록",
        "인스턴스목록",
        "인스턴스코드",
    ),
}

EXTRACT_HINTS = (
    "조회",
    "추출",
    "보여",
    "데이터",
    "목록",
    "가져",
    "출력",
    "보기",
    "알려",
    "리스트",
    "테이블",
    "select",
    "fetch",
    "extract",
    "집계",
    "고객수",
    "건수",
    "참조",
    "조인",
)

AGGREGATE_HINTS = ("집계", "고객수", "건수", "count", "별")
JOIN_HINTS = ("참조", "조인", "join", "JOIN")

TABLE_SQL_FQN: dict[str, str] = {
    "TSHDEOA01": f'"{TSHDEOA01_SCHEMA}"."{TSHDEOA01_TABLE}"',
    "TSHDEOA02": f'"{TSHDEOA02_SCHEMA}"."{TSHDEOA02_TABLE}"',
    "TSHDE0ZCD": f'"{TSHDE0ZCD_SCHEMA}"."{TSHDE0ZCD_TABLE}"',
}

INST1_TABLE_SCHEMA: dict[str, str] = {
    TSHDEOA01_TABLE: TSHDEOA01_SCHEMA,
    TSHDEOA02_TABLE: TSHDEOA02_SCHEMA,
    TSHDE0ZCD_TABLE: TSHDE0ZCD_SCHEMA,
}

COLUMN_DESC_HINTS = ("컬럼", "필드", "항목")
COLUMN_DESC_ACTION_HINTS = ("설명", "알려", "의미", "정의", "소개", "드릴까요")
DATA_SUMMARY_HINTS = ("요약", "정리")
DATA_SHOW_HINTS = (
    "조회",
    "추출",
    "보여",
    "가져",
    "출력",
    "보기",
    "리스트",
    "select",
    "fetch",
    "extract",
    "집계",
    "고객수",
    "건수",
    "참조",
    "조인",
)

CHART_HINTS = ("차트", "그래프", "막대", "시각화", "그려", "chart")
AGGREGATE_CHART_FOLLOW_UP = "조회한 집계 데이터로 차트를 그려드릴까요?"

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "inst1_table_prompt": "테이블 추천 질문 에이전트",
    "inst1_aggregate_prompt": "집계 컬럼 선택 에이전트",
    "inst1_column_desc": "컬럼 설명 에이전트",
    "inst1_data_summary": "데이터 요약 에이전트",
    "inst1_extract": "데이터 추출 에이전트",
    "inst1_chart": "차트 에이전트",
    "inst1_excel": "엑셀 저장 에이전트",
    "inst1_report": "보고서 PDF 에이전트",
    "general_chat": "일반 대화 에이전트",
}

_AGGREGATE_PROMPT_SKIP_COLUMNS = frozenset({"그룹회사코드", "그룹고객식별자"})

INST1_SUMMARY_SYSTEM_PROMPT = """당신은 금융·그룹고객 INST1 데이터 분석가입니다.
주어진 테이블 조회 결과만 근거로 한국어로 요약하세요.
- 조회 건수, 주요 수치·분포, 눈에 띄는 패턴을 3~6문장으로 정리하세요.
- 통계 요약이 있으면 활용하세요.
- 데이터에 없는 내용은 추측하지 마세요."""

DEFAULT_MONTH = "202604"
DEFAULT_GROUP = "KFG"
MAX_ROWS = 100

ALL_ROWS_HINTS: tuple[str, ...] = (
    "전체 데이터",
    "전체데이터",
    "전체를 보여",
    "전체 보여",
    "전부 보여",
    "모두 보여",
    "모든 데이터",
    "전체 조회",
    "전체조회",
    "전체 목록",
    "limit 없",
    "리밋 없",
    "무제한",
    "다 보여줘",
    "다 보여",
    "no limit",
    "all rows",
)

_db_url_cache: str | None = None


def get_conn():
    global _db_url_cache
    if _db_url_cache is None:
        raw = os.environ.get("SUPABASE_DB_URL", "").strip()
        if not raw:
            raise RuntimeError("`SUPABASE_DB_URL` 환경 변수를 설정해야 합니다.")
        if "sslmode=" not in raw:
            raw += ("&" if "?" in raw else "?") + "sslmode=require"
        _db_url_cache = raw
    return psycopg2.connect(_db_url_cache, connect_timeout=15)


def _wants_all_rows(message: str) -> bool:
    msg = message.strip()
    lower = msg.lower()
    if any(h in msg or h in lower for h in ALL_ROWS_HINTS):
        return True
    if "전체" in msg and any(w in msg for w in ("보여", "조회", "출력", "데이터", "목록", "가져")):
        return True
    return False


def _resolve_row_limit(message: str, *, explicit: Any = None) -> int | None:
    """None이면 LIMIT 없음(전체 조회)."""
    if _wants_all_rows(message):
        return None
    if explicit is not None and str(explicit).strip().isdigit():
        return int(explicit)
    return MAX_ROWS


def _sql_limit_suffix(limit: int | None) -> str:
    return "" if limit is None else f"\nLIMIT {limit}"


def parse_month(text: str) -> str | None:
    m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월", text)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}"
    m = re.search(r"(20\d{2})[.\-/](\d{1,2})\b", text)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}"
    m = re.search(r"(?<!\d)(\d{2})[.\-/](\d{1,2})\s*월?", text)
    if m:
        return f"20{m.group(1)}{int(m.group(2)):02d}"
    m = re.search(r"\b(20\d{4})\b", text)
    if m:
        return m.group(1)
    return None


def format_yyyymm(yyyymm: str) -> str:
    if len(yyyymm) == 6 and yyyymm.isdigit():
        return f"{yyyymm[:4]}년 {int(yyyymm[4:6])}월"
    return yyyymm


def _parse_customer_id(text: str) -> str | None:
    m = re.search(r"\b(\d{10})\b", text)
    return m.group(1) if m else None


def _parse_group_company(text: str) -> str:
    m = re.search(r"\b(KFG|K00|KB0|KC0)\b", text, re.I)
    return m.group(1).upper() if m else DEFAULT_GROUP


def _is_aggregate_request(message: str) -> bool:
    msg = message.strip()
    return any(h in msg for h in AGGREGATE_HINTS)


def _is_false_byeol_match(message: str, start: int, token: str) -> bool:
    """'성별구분' 등 컬럼명 내부 '성+별'을 집계 패턴으로 오인하지 않도록."""
    for table in INST1_TABLE_ORDER:
        for col in INST1_TABLE_COLUMNS.get(table, ()):
            if message.startswith(col, start) and len(col) > len(token) + 1:
                return True
    return False


def _resolve_group_column(name: str, table: str) -> str | None:
    token = name.strip()
    if not token:
        return None
    columns = INST1_AGGREGATE_COLUMNS.get(table, ())
    aliases = INST1_GROUP_ALIASES.get(table, {})
    if token in columns:
        return token
    if token in aliases:
        return aliases[token]
    for col in sorted(columns, key=len, reverse=True):
        if token in col or col in token:
            return col
    return None


def _sql_group_col(table: str, col: str) -> str:
    if col in INST1_NUMERIC_COLUMNS.get(table, frozenset()):
        return f'"{col}"'
    return f'trim("{col}")'


def _sql_qual_group_col(alias: str, logical_table: str, col: str) -> str:
    if col in INST1_NUMERIC_COLUMNS.get(logical_table, frozenset()):
        return f'{alias}."{col}"'
    return f'trim({alias}."{col}")'


def _normalize_group_by(value: Any) -> list[str]:
    if not value:
        return []
    items = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    columns: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            continue
        col = item.strip()
        if col and col not in seen:
            columns.append(col)
            seen.add(col)
    return columns


def _parse_group_by_columns(message: str, table: str) -> list[str]:
    msg = message.strip()
    columns_def = INST1_AGGREGATE_COLUMNS.get(table)
    if not columns_def:
        return []

    columns: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"([\w가-힣]+)별", msg):
        token = match.group(1)
        if _is_false_byeol_match(msg, match.start(), token):
            continue
        resolved = _resolve_group_column(token, table)
        if resolved and resolved not in seen:
            columns.append(resolved)
            seen.add(resolved)
    if columns:
        return columns

    best_col: str | None = None
    best_len = 0
    for col in sorted(columns_def, key=len, reverse=True):
        if col in msg and len(col) > best_len:
            best_col = col
            best_len = len(col)
    if best_col:
        return [best_col]

    aliases = INST1_GROUP_ALIASES.get(table, {})
    for alias, col in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in msg and len(alias) > best_len:
            best_col = col
            best_len = len(alias)
    return [best_col] if best_col else []


def _parse_group_by_details(message: str) -> list[dict[str, str]]:
    msg = message.strip()
    details: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r"([\w가-힣]+)별", msg):
        token = match.group(1)
        if _is_false_byeol_match(msg, match.start(), token):
            continue
        for table in INST1_TABLE_ORDER:
            col = _resolve_group_column(token, table)
            if col and col not in seen:
                details.append({"table": table, "column": col})
                seen.add(col)
                break
    return details


def _infer_join_tables(
    tables: list[str],
    message: str,
    group_by_details: list[dict[str, str]],
) -> list[str]:
    involved = {d["table"] for d in group_by_details}
    if len(involved) >= 2:
        return [t for t in INST1_TABLE_ORDER if t in involved]
    korean = _mentioned_korean_tables(message)
    if len(korean) >= 2:
        return [t for t in INST1_TABLE_ORDER if t in korean]
    if any(h in message for h in JOIN_HINTS) and len(tables) >= 2:
        return [t for t in INST1_TABLE_ORDER if t in tables]
    return []


def _detect_aggregate_table(tables: list[str], message: str) -> tuple[str | None, list[str]]:
    msg = message.strip()
    details = _parse_group_by_details(msg)
    if details:
        involved = {d["table"] for d in details}
        if len(involved) == 1:
            table = next(iter(involved))
            return table, [d["column"] for d in details]
    for table in tables:
        cols = _parse_group_by_columns(msg, table)
        if cols:
            return table, cols
    if len(tables) == 1:
        cols = _parse_group_by_columns(msg, tables[0])
        return (tables[0], cols) if cols else (None, [])
    return None, []


def _hint_in_message(hint: str, msg: str, lower: str) -> bool:
    if hint.isascii():
        return hint.lower() in lower
    return hint in msg


def _tables_from_hints(message: str) -> list[str]:
    msg = message.strip()
    lower = msg.lower()
    tables: list[str] = []
    for table, hints in TABLE_HINTS.items():
        if any(_hint_in_message(h, msg, lower) for h in hints):
            tables.append(table)
    return tables


def _resolve_query_tables(message: str, hinted: list[str] | None = None) -> list[str]:
    """질문에 명시된 테이블만 반환 (ZCD 단독 조회 시 A01/A02 제외)."""
    msg = message.strip()
    tables = list(hinted or _tables_from_hints(msg))
    zcd_named = (
        TSHDE0ZCD_KOREAN_NAME in msg
        or "TSHDE0ZCD" in msg.upper()
        or TSHDE0ZCD_TABLE in tables
    )
    a01_named = TSHDEOA01_KOREAN_NAME in msg or "TSHDEOA01" in msg.upper()
    a02_named = TSHDEOA02_KOREAN_NAME in msg or "TSHDEOA02" in msg.upper()
    if zcd_named and not a01_named and not a02_named:
        return [TSHDE0ZCD_TABLE]
    return tables


def _mentioned_korean_tables(message: str) -> list[str]:
    msg = message.strip()
    matched: list[str] = []
    for table, aliases in INST1_TABLE_ALIASES.items():
        if any(alias in msg for alias in aliases):
            matched.append(table)
    return matched


def _strip_table_names_from_message(msg: str, table: str) -> str:
    korean = INST1_TABLE_KOREAN_NAMES.get(table, "")
    remainder = msg
    names = {table, korean, *INST1_TABLE_ALIASES.get(table, ())}
    for name in sorted((n for n in names if n), key=len, reverse=True):
        remainder = remainder.replace(name, "")
    return remainder.strip(" \t\n.,?!:;'")


def _detect_table_name_only(message: str) -> tuple[str | None, str | None]:
    """테이블명만 입력된 경우 (logical_table, korean_name)."""
    msg = message.strip()
    if not msg:
        return None, None

    tables = _resolve_query_tables(msg, _tables_from_hints(msg))
    if len(tables) != 1:
        return None, None

    table = tables[0]
    remainder = _strip_table_names_from_message(msg, table)
    if remainder:
        if any(h in remainder for h in EXTRACT_HINTS):
            return None, None
        if _is_aggregate_request(remainder):
            return None, None
        if parse_month(remainder) or _parse_customer_id(remainder):
            return None, None
        if parse_mentioned_columns(remainder):
            return None, None
        if re.search(r"[\w가-힣]+별", remainder):
            return None, None
        return None, None

    if _is_aggregate_request(msg):
        return None, None
    if parse_month(msg) or _parse_customer_id(msg):
        return None, None
    if parse_mentioned_columns(msg):
        return None, None
    if re.search(r"[\w가-힣]+별", msg):
        return None, None
    return table, INST1_TABLE_KOREAN_NAMES.get(table, table)


def _build_table_prompt_payload(
    table: str,
    korean: str,
    *,
    reason: str,
) -> dict[str, Any]:
    return {
        "intent": "inst1_table_prompt",
        "query_type": "prompt",
        "tables": [table],
        "table_korean": korean,
        "month": "",
        "group_company": "",
        "customer_id": None,
        "group_by": [],
        "group_by_details": [],
        "join_tables": [],
        "aggregate_table": None,
        "mentioned_columns": [],
        "limit": MAX_ROWS,
        "unlimited_rows": False,
        "reason": reason,
    }


def format_agent_banner(analysis: dict[str, Any]) -> str:
    intent = (analysis.get("intent") or "").strip()
    label = AGENT_DISPLAY_NAMES.get(intent, intent or "알 수 없음")
    return f"[호출 에이전트: {label}]"


def with_agent_banner(text: str, analysis: dict[str, Any]) -> str:
    body = (text or "").strip()
    banner = format_agent_banner(analysis)
    return f"{banner}\n\n{body}" if body else banner


def _wants_column_description(msg: str) -> bool:
    if _is_aggregate_request(msg):
        return False
    if not any(h in msg for h in COLUMN_DESC_HINTS):
        return False
    if _wants_data_summary(msg):
        return False
    if any(h in msg for h in DATA_SHOW_HINTS):
        return False
    if "데이터" in msg:
        return False
    return True


def _wants_data_summary(msg: str) -> bool:
    if not any(h in msg for h in DATA_SUMMARY_HINTS):
        return False
    if any(h in msg for h in COLUMN_DESC_HINTS):
        return False
    return (
        "데이터" in msg
        or bool(_mentioned_korean_tables(msg))
        or bool(_tables_from_hints(msg))
    )


def _wants_aggregate_data_prompt(msg: str) -> bool:
    if "집계" not in msg:
        return False
    if _wants_column_description(msg) or _wants_data_summary(msg):
        return False
    if not ("데이터" in msg or "보여" in msg or "조회" in msg):
        return False
    if _parse_group_by_details(msg):
        return False
    return True


def _wants_chart(msg: str) -> bool:
    return any(h in msg for h in CHART_HINTS)


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in row.items():
        if isinstance(val, Decimal):
            out[key] = float(val)
        else:
            out[key] = val
    return out


def _aggregate_chart_label(row: dict[str, Any], group_by: list[str]) -> str:
    parts = [str(row.get(col, "") or "-").strip() for col in group_by]
    return " / ".join(parts) if parts else "-"


def build_aggregate_chart_specs(pending_chart: dict[str, Any]) -> list[dict[str, Any]]:
    """집계 결과 pending_chart → Chart.js 막대그래프 스펙."""
    rows = list(pending_chart.get("rows") or [])
    group_by = _normalize_group_by(pending_chart.get("group_by"))
    if not rows or not group_by:
        return []
    if "고객수" not in rows[0]:
        return []

    display = pending_chart.get("display_label") or "집계"
    month = (pending_chart.get("month") or "").strip()
    month_suffix = f" · {format_yyyymm(month)}" if month else ""
    group_cols_label = ", ".join(group_by)

    sorted_rows = sorted(
        rows,
        key=lambda r: _aggregate_chart_label(r, group_by),
    )
    labels = [_aggregate_chart_label(r, group_by) for r in sorted_rows]
    counts = []
    for row in sorted_rows:
        val = row.get("고객수")
        try:
            counts.append(float(val) if val is not None else 0.0)
        except (TypeError, ValueError):
            counts.append(0.0)

    return [
        {
            "type": "bar",
            "title": f"{display} · {group_cols_label}별 고객수{month_suffix}",
            "labels": labels,
            "datasets": [
                {
                    "label": "고객수",
                    "data": counts,
                    "backgroundColor": "rgba(124, 58, 237, 0.78)",
                    "borderColor": "rgba(109, 40, 217, 1)",
                    "borderWidth": 1,
                }
            ],
        }
    ]


def build_pending_chart_payload(
    analysis: dict[str, Any],
    extract_result: dict[str, Any],
) -> dict[str, Any]:
    """집계 조회 성공 시 차트 follow-up용 세션 데이터."""
    query_type = analysis.get("query_type") or ""
    if query_type not in ("aggregate", "join_aggregate"):
        return {}
    group_by = _normalize_group_by(analysis.get("group_by"))
    if not group_by:
        return {}
    data: dict[str, list] = extract_result.get("inst1_data") or {}
    labels: dict[str, str] = extract_result.get("inst1_result_labels") or {}
    for key, rows in data.items():
        if not rows or "고객수" not in rows[0]:
            continue
        return {
            "result_key": key,
            "rows": [_json_safe_row(r) for r in rows],
            "group_by": group_by,
            "display_label": labels.get(key, inst1_result_label(key)),
            "month": (extract_result.get("month") or "").strip(),
            "group_company": (extract_result.get("group_company") or "").strip(),
        }
    return {}


def format_chart_agent_reply(
    analysis: dict[str, Any],
    pending_chart: dict[str, Any],
    chart_specs: list[dict[str, Any]],
) -> str:
    display = pending_chart.get("display_label") or "집계 데이터"
    group_by = ", ".join(_normalize_group_by(pending_chart.get("group_by")))
    row_count = len(pending_chart.get("rows") or [])
    title = (chart_specs[0].get("title") if chart_specs else "") or display
    body = "\n".join(
        [
            "[집계 데이터 차트]",
            f"- 대상: {display}",
            f"- 집계 기준: {group_by}",
            f"- 표시 건수: {row_count}건",
            f"- 차트: {title}",
            "",
            "아래 막대그래프에서 고객수를 확인하세요.",
            "보고서 버튼으로 PDF 보고서를 생성·저장할 수 있습니다.",
        ]
    )
    return with_agent_banner(body, analysis)


def build_report_export(
    *,
    agent: str,
    content: str,
    table_label: str,
    month: str = "",
    chart_specs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """차트·요약 에이전트 응답 → PDF 보고서 저장용 payload."""
    from culture_pdf_s3 import ascii_report_filename

    text = (content or "").strip()
    if not text:
        return {}
    return {
        "agent": agent,
        "content": text,
        "table_label": table_label,
        "month": (month or "").strip(),
        "chart_specs": list(chart_specs or []),
        "filename": ascii_report_filename("culture_report"),
    }


def build_inst1_excel_export(
    extract_result: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """데이터 추출 에이전트 조회 결과 → 엑셀 저장 payload."""
    from culture_excel import ascii_export_filename

    month = (extract_result.get("month") or "").strip()
    if not month and analysis:
        month = (analysis.get("month") or "").strip()
    month_label = f" ({format_yyyymm(month)})" if month else ""
    filename = ascii_export_filename("culture_export")

    inst1_data: dict[str, list] = extract_result.get("inst1_data") or {}
    column_orders: dict[str, list[str]] = extract_result.get("inst1_column_orders") or {}
    labels: dict[str, str] = extract_result.get("inst1_result_labels") or {}

    sheets: list[dict[str, Any]] = []
    for key, rows in inst1_data.items():
        if not rows:
            continue
        cols = list(column_orders.get(key) or list(rows[0].keys()))
        display = labels.get(key, inst1_result_label(key))
        sheets.append(
            {
                "sheet_name": display[:31],
                "title": f"{display} 조회 결과{month_label}",
                "columns": cols,
                "rows": [_json_safe_row(r) for r in rows],
            }
        )

    if not sheets:
        return {}

    if len(sheets) == 1:
        s = sheets[0]
        return {
            "agent": "inst1_extract",
            "title": s["title"],
            "sheet_name": s["sheet_name"],
            "filename": filename,
            "columns": s["columns"],
            "rows": s["rows"],
        }

    return {
        "agent": "inst1_extract",
        "title": f"데이터 추출 조회 결과{month_label}",
        "filename": filename,
        "sheets": sheets,
    }


def _detect_chart_followup(
    message: str,
    pending_chart: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not pending_chart or not pending_chart.get("rows"):
        return None
    if not _wants_chart(message.strip()):
        return None
    return {
        "intent": "inst1_chart",
        "query_type": "chart",
        "tables": [],
        "month": pending_chart.get("month") or "",
        "group_company": pending_chart.get("group_company") or "",
        "customer_id": None,
        "group_by": list(pending_chart.get("group_by") or []),
        "reason": "집계 데이터 차트 생성 요청",
    }


def _wants_data_extract(msg: str) -> bool:
    if _wants_chart(msg):
        return False
    if _wants_aggregate_data_prompt(msg):
        return False
    if _wants_column_description(msg):
        return False
    if _wants_data_summary(msg):
        return False
    if _is_aggregate_request(msg):
        return True
    if any(h in msg for h in DATA_SHOW_HINTS):
        return True
    if "데이터" in msg:
        return True
    if "목록" in msg and not any(
        name in msg for name in (TSHDE0ZCD_KOREAN_NAME, "인스턴스목록")
    ):
        return True
    return False


def format_inst1_table_prompt_reply(analysis: dict[str, Any]) -> str:
    """테이블명만 언급된 경우 추천 질문 응답."""
    table = (analysis.get("tables") or [None])[0]
    korean = analysis.get("table_korean") or INST1_TABLE_KOREAN_NAMES.get(
        table or "", table or ""
    )
    parts = [
        f"[{korean}] 테이블을 선택하셨습니다.",
        "아래 중 원하시는 질문을 이어서 입력해 주세요.",
        "",
        "추천 질문",
        f"- {korean}의 데이터를 보여드릴까요?",
        f"- {korean}의 집계 데이터를 보여드릴까요?",
        f"- {korean}의 컬럼을 설명해 드릴까요?",
        f"- {korean}의 데이터를 요약해 드릴까요?",
    ]
    return with_agent_banner("\n".join(parts), analysis)


def _build_aggregate_prompt_payload(
    table: str,
    korean: str,
    *,
    reason: str,
) -> dict[str, Any]:
    return {
        "intent": "inst1_aggregate_prompt",
        "query_type": "aggregate_prompt",
        "tables": [table],
        "table_korean": korean,
        "month": "",
        "group_company": "",
        "customer_id": None,
        "group_by": [],
        "group_by_details": [],
        "join_tables": [],
        "aggregate_table": None,
        "mentioned_columns": [],
        "limit": MAX_ROWS,
        "unlimited_rows": False,
        "reason": reason,
    }


def format_inst1_aggregate_prompt_reply(analysis: dict[str, Any]) -> str:
    """집계 컬럼 선택 안내 응답."""
    table = (analysis.get("tables") or [None])[0]
    korean = analysis.get("table_korean") or INST1_TABLE_KOREAN_NAMES.get(
        table or "", table or ""
    )
    suggest_cols = [
        col
        for col in INST1_AGGREGATE_COLUMNS.get(table or "", ())
        if col not in _AGGREGATE_PROMPT_SKIP_COLUMNS
    ]
    parts = [
        f"[{korean}] 집계 데이터 조회",
        "집계를 원하시는 컬럼을 말씀해 주세요.",
        "",
        "입력 예: 성별구분, 연령코드  또는  성별구분별, 연령코드별",
    ]
    if suggest_cols:
        parts.extend(["", "집계 가능 컬럼 예:"])
        parts.extend(f"- {col}" for col in suggest_cols)
    return with_agent_banner("\n".join(parts), analysis)


def _parse_aggregate_column_list(message: str, table: str) -> list[str]:
    """집계 follow-up 메시지에서 컬럼 목록 추출."""
    msg = message.strip()
    details = [d for d in _parse_group_by_details(msg) if d["table"] == table]
    if details:
        return [d["column"] for d in details]

    allowed = set(INST1_AGGREGATE_COLUMNS.get(table, ()))
    mentioned = [c for c in parse_mentioned_columns(msg) if c in allowed]
    if mentioned:
        return mentioned

    columns: list[str] = []
    seen: set[str] = set()
    for chunk in re.split(r"[,，、\n]+", msg):
        token = chunk.strip().rstrip("별").strip()
        if not token:
            continue
        col = _resolve_group_column(token, table)
        if col and col not in seen:
            columns.append(col)
            seen.add(col)
    return columns


def _detect_aggregate_prompt_intent(message: str) -> dict[str, Any] | None:
    msg = message.strip()
    if not _wants_aggregate_data_prompt(msg):
        return None
    tables = _resolve_query_tables(msg, _tables_from_hints(msg))
    if len(tables) != 1:
        return None
    table = tables[0]
    if table == TSHDE0ZCD_TABLE:
        return None
    korean = INST1_TABLE_KOREAN_NAMES.get(table, table)
    return _build_aggregate_prompt_payload(
        table,
        korean,
        reason="집계 데이터 조회 — 컬럼 선택 대기",
    )


def _detect_aggregate_followup(
    message: str,
    pending: dict[str, Any],
) -> dict[str, Any] | None:
    table = (pending.get("table") or "").strip()
    if not table:
        return None
    cols = _parse_aggregate_column_list(message, table)
    if not cols:
        return None
    korean = pending.get("korean") or INST1_TABLE_KOREAN_NAMES.get(table, table)
    msg = message.strip()
    group_by_details = [{"table": table, "column": col} for col in cols]
    return {
        "intent": "inst1_extract",
        "query_type": "aggregate",
        "tables": [table],
        "table_korean": korean,
        "month": parse_month(msg) or "",
        "group_company": _parse_group_company(msg),
        "customer_id": _parse_customer_id(msg),
        "group_by": cols,
        "group_by_details": group_by_details,
        "join_tables": [],
        "aggregate_table": table,
        "mentioned_columns": cols,
        "limit": _resolve_row_limit(msg),
        "unlimited_rows": _wants_all_rows(msg),
        "reason": f"집계 컬럼 지정 ({', '.join(cols)})",
    }


def _build_meta_intent_payload(
    table: str,
    korean: str,
    intent: str,
    message: str,
    *,
    reason: str,
) -> dict[str, Any]:
    msg = message.strip()
    return {
        "intent": intent,
        "query_type": "meta",
        "tables": [table],
        "table_korean": korean,
        "month": parse_month(msg) or "",
        "group_company": _parse_group_company(msg),
        "customer_id": _parse_customer_id(msg),
        "group_by": [],
        "group_by_details": [],
        "join_tables": [],
        "aggregate_table": None,
        "mentioned_columns": [],
        "limit": MAX_ROWS,
        "unlimited_rows": False,
        "reason": reason,
    }


def _detect_meta_intent(message: str) -> dict[str, Any] | None:
    msg = message.strip()
    if not (_wants_column_description(msg) or _wants_data_summary(msg)):
        return None
    tables = _resolve_query_tables(msg, _tables_from_hints(msg))
    if len(tables) != 1:
        return None
    table = tables[0]
    korean = INST1_TABLE_KOREAN_NAMES.get(table, table)
    if _wants_column_description(msg):
        return _build_meta_intent_payload(
            table,
            korean,
            "inst1_column_desc",
            msg,
            reason="테이블 컬럼 설명 요청",
        )
    return _build_meta_intent_payload(
        table,
        korean,
        "inst1_data_summary",
        msg,
        reason="테이블 데이터 요약 요청",
    )


def _parse_column_comment(comment: str | None, column: str) -> str:
    if not comment:
        return column
    parts = [p.strip() for p in comment.split("/")]
    detail: list[str] = []
    for part in parts:
        if part.startswith("속성:"):
            detail.append(part.replace("속성:", "", 1).strip())
        elif part.startswith("인스턴스:"):
            detail.append(f"코드유형 {part.replace('인스턴스:', '', 1).strip()}")
        elif part.startswith("식별자:"):
            detail.append(f"인스턴스ID {part.replace('식별자:', '', 1).strip()}")
        elif any(
            token in part
            for token in ("CHAR", "NUMBER", "VARCHAR", "TIMESTAMP", "NUMERIC")
        ):
            detail.append(part)
    if "PK" in parts:
        detail.append("PK")
    return " · ".join(detail) if detail else comment.strip()


def fetch_inst1_column_descriptions(table: str) -> list[tuple[str, str]]:
    """테이블 컬럼명·설명 목록 (DDL comment 기반)."""
    schema = INST1_TABLE_SCHEMA.get(table)
    if not schema:
        raise ValueError(f"지원하지 않는 테이블입니다: {table}")
    sql = """
        SELECT a.attname AS column_name,
               col_description(a.attrelid, a.attnum) AS description
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = %s
          AND c.relname = %s
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY a.attnum
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (schema, table))
            rows = cur.fetchall()
    if rows:
        return [
            (name, _parse_column_comment(desc, name))
            for name, desc in rows
        ]
    fallback = INST1_TABLE_COLUMNS.get(table, ())
    return [(col, col) for col in fallback]


def explain_inst1_columns(analysis: dict[str, Any]) -> str:
    """컬럼 설명 에이전트 — 테이블 컬럼 메타데이터 응답."""
    table = (analysis.get("tables") or [None])[0]
    if not table:
        raise ValueError("설명할 테이블을 찾을 수 없습니다.")
    korean = analysis.get("table_korean") or INST1_TABLE_KOREAN_NAMES.get(table, table)
    label = inst1_result_label(table)
    columns = fetch_inst1_column_descriptions(table)
    lines = [
        f"[{korean}] 테이블 컬럼 설명",
        f"- 테이블: {label}",
        f"- 컬럼 수: {len(columns)}개",
        "",
    ]
    for idx, (name, desc) in enumerate(columns, start=1):
        lines.append(f"{idx}. {name} — {desc}")
    return with_agent_banner("\n".join(lines), analysis)


def _numeric_summary_stats(rows: list[dict[str, Any]], column: str) -> str | None:
    values: list[float] = []
    for row in rows:
        val = row.get(column)
        if val is None:
            continue
        try:
            values.append(float(val))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return (
        f"{column}: min={min(values):,.0f}, max={max(values):,.0f}, "
        f"avg={sum(values) / len(values):,.1f} (n={len(values)})"
    )


def _build_summary_sample_stats(
    table: str,
    rows: list[dict[str, Any]],
) -> list[str]:
    numeric_cols = INST1_NUMERIC_COLUMNS.get(table, frozenset())
    stats: list[str] = []
    for col in numeric_cols:
        line = _numeric_summary_stats(rows, col)
        if line:
            stats.append(f"- {line}")
    return stats


def summarize_inst1_table_data(
    analysis: dict[str, Any],
    *,
    bedrock_ask=None,
) -> str:
    """데이터 요약 에이전트 — 샘플 조회 후 Bedrock 요약."""
    table = (analysis.get("tables") or [None])[0]
    if not table:
        raise ValueError("요약할 테이블을 찾을 수 없습니다.")
    korean = analysis.get("table_korean") or INST1_TABLE_KOREAN_NAMES.get(table, table)
    extract_analysis = {
        **analysis,
        "intent": "inst1_extract",
        "query_type": "select",
        "tables": [table],
        "group_by": [],
        "group_by_details": [],
        "join_tables": [],
        "aggregate_table": None,
        "limit": MAX_ROWS,
        "unlimited_rows": False,
    }
    result = extract_inst1_data(extract_analysis)
    errors = list(result.get("errors") or [])
    data = result.get("inst1_data") or {}
    rows = data.get(table) or next(iter(data.values()), [])
    if not rows:
        detail = "; ".join(errors) if errors else "조회된 데이터가 없습니다."
        raise ValueError(detail)

    month = result.get("month") or analysis.get("month") or ""
    group = result.get("group_company") or analysis.get("group_company") or ""
    stats = _build_summary_sample_stats(table, rows)
    sample = rows[:20]
    header = [
        f"[{korean}] 데이터 요약",
        f"- 테이블: {inst1_result_label(table)}",
    ]
    if month:
        header.append(f"- 기준년월: {month} ({format_yyyymm(month)})")
    if group:
        header.append(f"- 그룹회사코드: {group}")
    header.append(f"- 조회 건수: {len(rows)}건 (요약 샘플 최대 {len(sample)}건)")
    if stats:
        header.extend(["", "[수치 요약]", *stats])

    if bedrock_ask is None:
        header.extend(["", "[데이터 미리보기]", _format_rows_preview(sample)])
        return with_agent_banner("\n".join(header), analysis)

    data_json = json.dumps(sample, ensure_ascii=False, indent=2, default=str)
    stats_text = "\n".join(stats) if stats else "(수치 통계 없음)"
    prompt = (
        f"테이블: {inst1_result_label(table)}\n"
        f"기준년월: {month} ({format_yyyymm(month) if month else '-'})\n"
        f"그룹회사코드: {group or '-'}\n"
        f"전체 조회 건수: {len(rows)}건\n\n"
        f"수치 통계:\n{stats_text}\n\n"
        f"샘플 데이터(JSON, 최대 {len(sample)}건):\n{data_json}\n\n"
        "위 데이터를 한국어로 요약하세요."
    )
    summary = bedrock_ask(
        INST1_SUMMARY_SYSTEM_PROMPT,
        [{"role": "user", "content": prompt}],
        2048,
    )
    body = "\n".join(
        [
            *header,
            "",
            summary.strip(),
            "",
            "보고서 버튼으로 PDF 보고서를 생성·저장할 수 있습니다.",
        ]
    )
    return with_agent_banner(body, analysis)


def _format_rows_preview(rows: list[dict[str, Any]], limit: int = 5) -> str:
    if not rows:
        return "(데이터 없음)"
    cols = list(rows[0].keys())
    lines = [" | ".join(cols)]
    for row in rows[:limit]:
        lines.append(" | ".join(str(row.get(c, "")) for c in cols))
    if len(rows) > limit:
        lines.append(f"… 외 {len(rows) - limit}건")
    return "\n".join(lines)


def _build_analysis_payload(
    message: str,
    *,
    tables: list[str],
    reason: str,
) -> dict[str, Any]:
    msg = message.strip()
    group_by_details = _parse_group_by_details(msg)
    group_by = [d["column"] for d in group_by_details]
    join_tables = _infer_join_tables(tables, msg, group_by_details)
    aggregate_table: str | None = None
    query_type = "select"

    if _is_aggregate_request(msg) and group_by_details and len(join_tables) >= 2:
        query_type = "join_aggregate"
        tables = join_tables
    elif _is_aggregate_request(msg) and group_by_details:
        aggregate_table, group_by = _detect_aggregate_table(tables, msg)
        query_type = "aggregate" if group_by else "select"
    elif _is_aggregate_request(msg):
        aggregate_table, group_by = _detect_aggregate_table(tables, msg)
        query_type = "aggregate" if group_by else "select"
    korean_tables = _mentioned_korean_tables(msg)
    if korean_tables:
        labels = dict(INST1_TABLE_KOREAN_NAMES)
        alias_note = ", ".join(
            f"{labels.get(table, table)}→{table}" for table in korean_tables
        )
        reason = f"{reason} ({alias_note})"
    return {
        "intent": "inst1_extract",
        "query_type": query_type,
        "tables": tables,
        "month": parse_month(msg) or "",
        "group_company": _parse_group_company(msg),
        "customer_id": _parse_customer_id(msg),
        "group_by": group_by,
        "group_by_details": group_by_details,
        "join_tables": join_tables if query_type == "join_aggregate" else [],
        "aggregate_table": aggregate_table if query_type == "aggregate" else None,
        "mentioned_columns": parse_mentioned_columns(msg),
        "limit": _resolve_row_limit(msg),
        "unlimited_rows": _wants_all_rows(msg),
        "reason": reason,
    }


def _rule_based_analysis(
    message: str,
    *,
    pending_aggregate: dict[str, Any] | None = None,
    pending_chart: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    msg = message.strip()
    chart_followup = _detect_chart_followup(msg, pending_chart)
    if chart_followup:
        return chart_followup
    if pending_aggregate:
        followup = _detect_aggregate_followup(msg, pending_aggregate)
        if followup:
            return followup
    table, korean = _detect_table_name_only(msg)
    if table and korean:
        return _build_table_prompt_payload(
            table,
            korean,
            reason="테이블명만 언급 — 추천 질문 제안",
        )
    aggregate_prompt = _detect_aggregate_prompt_intent(msg)
    if aggregate_prompt:
        return aggregate_prompt
    meta = _detect_meta_intent(msg)
    if meta:
        return meta
    tables = _resolve_query_tables(msg, _tables_from_hints(msg))
    wants_extract = _wants_data_extract(msg)
    if not tables and wants_extract:
        if TSHDE0ZCD_KOREAN_NAME in msg or "TSHDE0ZCD" in msg.upper():
            tables = [TSHDE0ZCD_TABLE]
        elif any(
            k in msg
            for k in (
                "거래",
                "잔액",
                "INST1",
                "inst1",
                TSHDEOA01_KOREAN_NAME,
                TSHDEOA02_KOREAN_NAME,
            )
        ):
            tables = ["TSHDEOA01", "TSHDEOA02"]
    if not tables or not wants_extract:
        return None
    return _build_analysis_payload(
        msg,
        tables=tables if tables else ["TSHDEOA01", "TSHDEOA02"],
        reason="키워드 기반 INST1 데이터 추출 요청",
    )


def analyze_question(
    message: str,
    *,
    bedrock_ask=None,
    pending_aggregate: dict[str, Any] | None = None,
    pending_chart: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """질문 분석 에이전트 — intent·테이블·필터 추출."""
    ruled = _rule_based_analysis(
        message,
        pending_aggregate=pending_aggregate,
        pending_chart=pending_chart,
    )
    if ruled:
        return ruled
    if bedrock_ask is None:
        return {
            "intent": "general_chat",
            "tables": [],
            "month": "",
            "group_company": "",
            "customer_id": None,
            "reason": "일반 대화로 분류",
        }
    try:
        raw = bedrock_ask(
            ANALYZE_SYSTEM_PROMPT,
            [{"role": "user", "content": message}],
            512,
        )
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(raw[start : end + 1])
            if parsed.get("intent") == "inst1_extract":
                tables = parsed.get("tables") or ["TSHDEOA01", "TSHDEOA02"]
                merged = _build_analysis_payload(
                    message,
                    tables=tables,
                    reason=parsed.get("reason") or "Bedrock 질문 분석",
                )
                rule_cols = _normalize_group_by(merged.get("group_by"))
                bedrock_cols = _normalize_group_by(parsed.get("group_by"))
                if _is_aggregate_request(message):
                    merged["group_by"] = rule_cols or bedrock_cols
                    if parsed.get("query_type") in (
                        "aggregate",
                        "join_aggregate",
                    ):
                        merged["query_type"] = parsed["query_type"]
                    elif merged.get("group_by"):
                        merged["query_type"] = "aggregate"
                else:
                    merged["group_by"] = rule_cols
                    merged["query_type"] = merged.get("query_type") or "select"
                resolved_tables = _resolve_query_tables(
                    message, merged.get("tables") or []
                )
                if resolved_tables:
                    merged["tables"] = resolved_tables
                prompt_table, prompt_korean = _detect_table_name_only(message)
                if prompt_table and prompt_korean:
                    return _build_table_prompt_payload(
                        prompt_table,
                        prompt_korean,
                        reason=merged.get("reason") or "Bedrock 질문 분석 — 테이블명만 언급",
                    )
                return merged
            if parsed.get("intent") == "inst1_table_prompt":
                prompt_table, prompt_korean = _detect_table_name_only(message)
                if prompt_table and prompt_korean:
                    return _build_table_prompt_payload(
                        prompt_table,
                        prompt_korean,
                        reason=parsed.get("reason") or "Bedrock 질문 분석 — 테이블명만 언급",
                    )
            if parsed.get("intent") == "inst1_aggregate_prompt":
                ruled_agg = _detect_aggregate_prompt_intent(message)
                if ruled_agg:
                    ruled_agg["reason"] = parsed.get("reason") or ruled_agg.get(
                        "reason", ""
                    )
                    return ruled_agg
            if parsed.get("intent") in ("inst1_column_desc", "inst1_data_summary"):
                ruled_meta = _detect_meta_intent(message)
                if ruled_meta:
                    ruled_meta["reason"] = parsed.get("reason") or ruled_meta.get(
                        "reason", ""
                    )
                    return ruled_meta
            if parsed.get("intent") == "inst1_chart":
                ruled_chart = _detect_chart_followup(message, pending_chart)
                if ruled_chart:
                    ruled_chart["reason"] = parsed.get("reason") or ruled_chart.get(
                        "reason", ""
                    )
                    return ruled_chart
            if parsed.get("intent") not in (
                "inst1_table_prompt",
                "inst1_aggregate_prompt",
                "inst1_column_desc",
                "inst1_data_summary",
                "inst1_chart",
                "general_chat",
            ):
                return {
                    "intent": "general_chat",
                    "tables": [],
                    "month": "",
                    "group_company": "",
                    "customer_id": None,
                    "reason": "일반 대화로 분류",
                }
            return parsed
    except Exception:
        pass
    return {
        "intent": "general_chat",
        "tables": [],
        "month": "",
        "group_company": "",
        "customer_id": None,
        "reason": "일반 대화로 분류",
    }


def _table_name_spans(message: str) -> list[tuple[int, int]]:
    names = {TSHDEOA01_KOREAN_NAME, TSHDEOA02_KOREAN_NAME}
    for aliases in INST1_TABLE_ALIASES.values():
        names.update(aliases)
    spans: list[tuple[int, int]] = []
    for name in sorted(names, key=len, reverse=True):
        start = 0
        while True:
            pos = message.find(name, start)
            if pos < 0:
                break
            spans.append((pos, pos + len(name)))
            start = pos + len(name)
    return spans


def _match_inside_table_name(message: str, pos: int, hint: str) -> bool:
    end = pos + len(hint)
    return any(start <= pos and end <= stop for start, stop in _table_name_spans(message))


def _column_match_candidates() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for table in INST1_TABLE_ORDER:
        for col in INST1_TABLE_COLUMNS.get(table, ()):
            candidates.append((col, col))
        for alias, col in INST1_GROUP_ALIASES.get(table, {}).items():
            candidates.append((alias, col))
    return sorted(candidates, key=lambda item: len(item[0]), reverse=True)


def parse_mentioned_columns(message: str) -> list[str]:
    """질문에 등장한 컬럼명·별칭·'XXX별' 패턴을 등장 순서대로 반환."""
    msg = message.strip()
    ordered: list[str] = []
    seen: set[str] = set()

    for match in re.finditer(r"([\w가-힣]+)별", msg):
        token = match.group(1)
        if _is_false_byeol_match(msg, match.start(), token):
            continue
        for table in INST1_TABLE_ORDER:
            col = _resolve_group_column(token, table)
            if col and col not in seen:
                ordered.append(col)
                seen.add(col)
                break

    positions: dict[str, int] = {}
    for hint, col in _column_match_candidates():
        if col in seen:
            continue
        pos = msg.find(hint)
        if pos >= 0 and col not in positions and not _match_inside_table_name(msg, pos, hint):
            positions[col] = pos

    for col, _ in sorted(positions.items(), key=lambda item: item[1]):
        ordered.append(col)
        seen.add(col)

    return ordered


def build_display_column_order(
    row_keys: list[str],
    *,
    mentioned: list[str],
    table_order: tuple[str, ...],
) -> list[str]:
    keys_set = set(row_keys)
    ordered: list[str] = []
    seen: set[str] = set()

    if mentioned:
        for col in mentioned:
            if col in keys_set and col not in seen:
                ordered.append(col)
                seen.add(col)
        for col in table_order:
            if col in keys_set and col not in seen:
                ordered.append(col)
                seen.add(col)
    else:
        for col in table_order:
            if col in keys_set and col not in seen:
                ordered.append(col)
                seen.add(col)

    for col in row_keys:
        if col not in seen:
            ordered.append(col)
            seen.add(col)

    return _order_result_columns(ordered)


def _default_table_order(analysis: dict[str, Any], result_key: str) -> tuple[str, ...]:
    query_type = analysis.get("query_type") or "select"
    group_by = tuple(_normalize_group_by(analysis.get("group_by")))

    if query_type == "join_aggregate" or result_key.startswith("JOIN_"):
        return group_by
    if query_type == "aggregate" and group_by:
        if result_key.startswith("TSHDEOA01") and analysis.get("aggregate_table") == "TSHDEOA01":
            return group_by
        if (
            result_key.startswith("TSHDEOA02") or result_key == "TSHDEOA02"
        ) and analysis.get("aggregate_table") == "TSHDEOA02":
            return group_by
        if "별고객수" in result_key:
            return group_by

    if TSHDE0ZCD_TABLE in result_key:
        return INST1_TABLE_COLUMNS.get(TSHDE0ZCD_TABLE, ())
    if "TSHDEOA02" in result_key:
        return INST1_TABLE_COLUMNS.get(TSHDEOA02_TABLE, ())
    return INST1_TABLE_COLUMNS.get(TSHDEOA01_TABLE, ())


def _reorder_rows(rows: list[dict[str, Any]], column_order: list[str]) -> list[dict[str, Any]]:
    return [{col: row[col] for col in column_order if col in row} for row in rows]


def apply_column_order_to_results(
    result: dict[str, list[dict[str, Any]]],
    analysis: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[str]]]:
    query_type = analysis.get("query_type") or "select"
    mentioned = list(analysis.get("mentioned_columns") or [])
    group_by = _normalize_group_by(analysis.get("group_by"))
    if query_type in ("aggregate", "join_aggregate") and group_by:
        mentioned = group_by
    elif query_type == "select":
        mentioned = list(analysis.get("mentioned_columns") or [])

    ordered: dict[str, list[dict[str, Any]]] = {}
    column_orders: dict[str, list[str]] = {}
    for key, rows in result.items():
        if not rows:
            ordered[key] = rows
            column_orders[key] = []
            continue
        col_order = build_display_column_order(
            list(rows[0].keys()),
            mentioned=mentioned,
            table_order=_default_table_order(analysis, key),
        )
        ordered[key] = _reorder_rows(rows, col_order)
        column_orders[key] = col_order
    return ordered, column_orders


def _order_result_columns(cols: list[str]) -> list[str]:
    if "고객수" not in cols:
        return cols
    return [c for c in cols if c != "고객수"] + ["고객수"]


def _row_to_dict(cols: list[str], row: tuple) -> dict[str, Any]:
    ordered_cols = _order_result_columns(cols)
    raw: dict[str, Any] = {}
    for c, v in zip(cols, row):
        if isinstance(v, Decimal):
            raw[c] = float(v)
        elif isinstance(v, str):
            raw[c] = v.strip()
        else:
            raw[c] = v
    return {c: raw[c] for c in ordered_cols if c in raw}


def _should_filter_month_in_where(
    month: str,
    group_by: list[str] | None = None,
) -> bool:
    """질문에 기준년월이 있고 GROUP BY에 없을 때만 WHERE에 포함."""
    if not (month or "").strip():
        return False
    if "기준년월" in set(_normalize_group_by(group_by or [])):
        return False
    return True


def _filter_condition_text(
    *,
    month: str,
    group: str,
    customer_id: str | None,
) -> str:
    parts = [f"그룹회사={group}"]
    if (month or "").strip():
        parts.insert(0, f"기준년월={month}")
    if customer_id:
        parts.append(f"고객={customer_id}")
    return ", ".join(parts)


def _base_where_parts(
    *,
    month: str,
    group_company: str,
    customer_id: str | None,
    for_display: bool,
    group_by: list[str] | None = None,
) -> tuple[list[str], list[Any]]:
    filter_month = _should_filter_month_in_where(month, group_by)
    if for_display:
        where_parts: list[str] = []
        if filter_month:
            where_parts.append(f'"기준년월" = \'{month}\'')
        where_parts.append(f'trim("그룹회사코드") = \'{group_company}\'')
        if customer_id:
            where_parts.append(f'trim("그룹고객식별자") = \'{customer_id}\'')
        return where_parts, []

    where_parts: list[str] = []
    params: list[Any] = []
    if filter_month:
        where_parts.append('"기준년월" = %s')
        params.append(month)
    where_parts.append('trim("그룹회사코드") = %s')
    params.append(group_company)
    if customer_id:
        where_parts.append('trim("그룹고객식별자") = %s')
        params.append(customer_id)
    return where_parts, params


def build_aggregate_query(
    schema: str,
    table: str,
    *,
    month: str,
    group_company: str,
    customer_id: str | None,
    group_by: list[str],
    logical_table: str,
) -> str:
    """집계용 GROUP BY 쿼리 문자열 생성 (표시용)."""
    cols = _normalize_group_by(group_by)
    if not cols:
        raise ValueError("집계 기준 컬럼이 없습니다.")
    where_parts, _ = _base_where_parts(
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=True,
        group_by=cols,
    )
    select_cols = ",\n       ".join(
        f'{_sql_group_col(logical_table, col)} AS "{col}"' for col in cols
    )
    group_expr = ", ".join(_sql_group_col(logical_table, col) for col in cols)
    order_expr = ", ".join(f'"{col}"' for col in cols)
    where_clause = f'WHERE {" AND ".join(where_parts)}\n' if where_parts else ""
    return (
        f"SELECT {select_cols},\n"
        f'       COUNT(DISTINCT "그룹고객식별자") AS "고객수"\n'
        f'FROM "{schema}"."{table}"\n'
        f"{where_clause}"
        f"GROUP BY {group_expr}\n"
        f"ORDER BY {order_expr};"
    )


def build_select_query(
    schema: str,
    table: str,
    *,
    month: str,
    group_company: str,
    customer_id: str | None,
    limit: int | None,
) -> str:
    """추출 조건에 맞는 SELECT 쿼리 문자열 생성 (표시용)."""
    where_parts, _ = _base_where_parts(
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=True,
    )
    return (
        f'SELECT *\n'
        f'FROM "{schema}"."{table}"\n'
        f'WHERE {" AND ".join(where_parts)}\n'
        f'ORDER BY "그룹고객식별자"'
        f'{_sql_limit_suffix(limit)};'
    )


def _fetch_table(
    schema: str,
    table: str,
    *,
    month: str,
    group_company: str,
    customer_id: str | None,
    limit: int | None,
) -> tuple[list[dict[str, Any]], str]:
    display_sql = build_select_query(
        schema,
        table,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        limit=limit,
    )
    where, params = _base_where_parts(
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=False,
    )
    exec_sql = (
        f'SELECT * FROM "{schema}"."{table}" '
        f"WHERE {' AND '.join(where)} "
        f'ORDER BY "그룹고객식별자"'
    )
    if limit is not None:
        exec_sql += " LIMIT %s"
        params.append(limit)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(exec_sql, params)
            cols = [d[0] for d in cur.description]
            table_order = INST1_TABLE_COLUMNS.get(table, ())
            rows = [
                _reorder_rows(
                    [_row_to_dict(cols, row)],
                    build_display_column_order(
                        cols,
                        mentioned=[],
                        table_order=table_order,
                    ),
                )[0]
                for row in cur.fetchall()
            ]
    return rows, display_sql


def _zcd_where_parts(
    group_company: str,
    *,
    for_display: bool,
) -> tuple[list[str], list[Any]]:
    if for_display:
        return [f'trim("그룹회사코드") = \'{group_company}\''], []
    return ['trim("그룹회사코드") = %s'], [group_company]


def build_zcd_select_query(
    schema: str,
    table: str,
    *,
    group_company: str,
    limit: int | None,
) -> str:
    where_parts, _ = _zcd_where_parts(group_company, for_display=True)
    return (
        f'SELECT *\n'
        f'FROM "{schema}"."{table}"\n'
        f'WHERE {" AND ".join(where_parts)}\n'
        f'ORDER BY "인스턴스식별자", "인스턴스코드"'
        f'{_sql_limit_suffix(limit)};'
    )


def _fetch_zcd_table(
    schema: str,
    table: str,
    *,
    group_company: str,
    limit: int | None,
) -> tuple[list[dict[str, Any]], str]:
    display_sql = build_zcd_select_query(
        schema,
        table,
        group_company=group_company,
        limit=limit,
    )
    where, params = _zcd_where_parts(group_company, for_display=False)
    exec_sql = (
        f'SELECT * FROM "{schema}"."{table}" '
        f"WHERE {' AND '.join(where)} "
        f'ORDER BY "인스턴스식별자", "인스턴스코드"'
    )
    if limit is not None:
        exec_sql += " LIMIT %s"
        params.append(limit)
    table_order = INST1_TABLE_COLUMNS.get(table, ())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(exec_sql, params)
            cols = [d[0] for d in cur.description]
            rows = [
                _reorder_rows(
                    [_row_to_dict(cols, row)],
                    build_display_column_order(
                        cols,
                        mentioned=[],
                        table_order=table_order,
                    ),
                )[0]
                for row in cur.fetchall()
            ]
    return rows, display_sql


def _fetch_aggregate(
    schema: str,
    table: str,
    *,
    month: str,
    group_company: str,
    customer_id: str | None,
    group_by: list[str],
    logical_table: str,
) -> tuple[list[dict[str, Any]], str]:
    cols = _normalize_group_by(group_by)
    display_sql = build_aggregate_query(
        schema,
        table,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        group_by=cols,
        logical_table=logical_table,
    )
    where, params = _base_where_parts(
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=False,
        group_by=cols,
    )
    select_cols = ", ".join(
        f'{_sql_group_col(logical_table, col)} AS "{col}"' for col in cols
    )
    group_expr = ", ".join(_sql_group_col(logical_table, col) for col in cols)
    order_expr = ", ".join(f'"{col}"' for col in cols)
    where_sql = f"WHERE {' AND '.join(where)} " if where else ""
    exec_sql = (
        f"SELECT {select_cols}, "
        f'COUNT(DISTINCT "그룹고객식별자") AS "고객수" '
        f'FROM "{schema}"."{table}" '
        f"{where_sql}"
        f"GROUP BY {group_expr} "
        f"ORDER BY {order_expr}"
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(exec_sql, params)
            cols = [d[0] for d in cur.description]
            rows = [_row_to_dict(cols, row) for row in cur.fetchall()]
    return rows, display_sql


def _join_on_sql(base_alias: str, join_alias: str) -> str:
    parts: list[str] = []
    for key in INST1_JOIN_KEYS:
        if key in ("그룹회사코드", "그룹고객식별자"):
            parts.append(f'trim({base_alias}."{key}") = trim({join_alias}."{key}")')
        else:
            parts.append(f'{base_alias}."{key}" = {join_alias}."{key}"')
    return " AND ".join(parts)


def _join_where_sql(
    primary_alias: str,
    *,
    month: str,
    group_company: str,
    customer_id: str | None,
    for_display: bool,
    group_by_columns: list[str] | None = None,
) -> tuple[list[str], list[Any]]:
    filter_month = _should_filter_month_in_where(month, group_by_columns)
    if for_display:
        where_parts: list[str] = []
        if filter_month:
            where_parts.append(f'{primary_alias}."기준년월" = \'{month}\'')
        where_parts.append(f'trim({primary_alias}."그룹회사코드") = \'{group_company}\'')
        if customer_id:
            where_parts.append(
                f'trim({primary_alias}."그룹고객식별자") = \'{customer_id}\''
            )
        return where_parts, []

    where_parts: list[str] = []
    params: list[Any] = []
    if filter_month:
        where_parts.append(f'{primary_alias}."기준년월" = %s')
        params.append(month)
    where_parts.append(f'trim({primary_alias}."그룹회사코드") = %s')
    params.append(group_company)
    if customer_id:
        where_parts.append(f'trim({primary_alias}."그룹고객식별자") = %s')
        params.append(customer_id)
    return where_parts, params


def build_join_aggregate_query(
    join_tables: list[str],
    group_by_details: list[dict[str, str]],
    *,
    month: str,
    group_company: str,
    customer_id: str | None,
) -> str:
    if len(join_tables) < 2:
        raise ValueError("조인 집계에는 2개 이상 테이블이 필요합니다.")
    if not group_by_details:
        raise ValueError("집계 기준 컬럼이 없습니다.")

    ordered = [t for t in INST1_TABLE_ORDER if t in join_tables]
    primary = ordered[0]
    primary_alias = INST1_TABLE_SQL_ALIAS[primary]

    select_cols = ",\n       ".join(
        f'{_sql_qual_group_col(INST1_TABLE_SQL_ALIAS[d["table"]], d["table"], d["column"])} '
        f'AS "{d["column"]}"'
        for d in group_by_details
    )
    group_expr = ", ".join(
        _sql_qual_group_col(INST1_TABLE_SQL_ALIAS[d["table"]], d["table"], d["column"])
        for d in group_by_details
    )
    order_expr = ", ".join(f'"{d["column"]}"' for d in group_by_details)
    group_cols = [d["column"] for d in group_by_details]
    where_parts, _ = _join_where_sql(
        primary_alias,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=True,
        group_by_columns=group_cols,
    )

    from_sql = f"FROM {TABLE_SQL_FQN[ordered[0]]} {primary_alias}"
    for table in ordered[1:]:
        alias = INST1_TABLE_SQL_ALIAS[table]
        from_sql += (
            f'\nINNER JOIN {TABLE_SQL_FQN[table]} {alias} '
            f"ON {_join_on_sql(primary_alias, alias)}"
        )

    where_clause = f'WHERE {" AND ".join(where_parts)}\n' if where_parts else ""
    return (
        f"SELECT {select_cols},\n"
        f'       COUNT(DISTINCT {primary_alias}."그룹고객식별자") AS "고객수"\n'
        f"{from_sql}\n"
        f"{where_clause}"
        f"GROUP BY {group_expr}\n"
        f"ORDER BY {order_expr};"
    )


def _fetch_join_aggregate(
    join_tables: list[str],
    group_by_details: list[dict[str, str]],
    *,
    month: str,
    group_company: str,
    customer_id: str | None,
) -> tuple[list[dict[str, Any]], str]:
    display_sql = build_join_aggregate_query(
        join_tables,
        group_by_details,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
    )
    ordered = [t for t in INST1_TABLE_ORDER if t in join_tables]
    primary = ordered[0]
    primary_alias = INST1_TABLE_SQL_ALIAS[primary]

    select_cols = ", ".join(
        f'{_sql_qual_group_col(INST1_TABLE_SQL_ALIAS[d["table"]], d["table"], d["column"])} '
        f'AS "{d["column"]}"'
        for d in group_by_details
    )
    group_expr = ", ".join(
        _sql_qual_group_col(INST1_TABLE_SQL_ALIAS[d["table"]], d["table"], d["column"])
        for d in group_by_details
    )
    order_expr = ", ".join(f'"{d["column"]}"' for d in group_by_details)
    group_cols = [d["column"] for d in group_by_details]
    where_parts, params = _join_where_sql(
        primary_alias,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=False,
        group_by_columns=group_cols,
    )

    from_sql = f"FROM {TABLE_SQL_FQN[ordered[0]]} {primary_alias}"
    for table in ordered[1:]:
        alias = INST1_TABLE_SQL_ALIAS[table]
        from_sql += (
            f" INNER JOIN {TABLE_SQL_FQN[table]} {alias} "
            f"ON {_join_on_sql(primary_alias, alias)}"
        )

    where_sql = f"WHERE {' AND '.join(where_parts)} " if where_parts else ""
    exec_sql = (
        f"SELECT {select_cols}, "
        f'COUNT(DISTINCT {primary_alias}."그룹고객식별자") AS "고객수" '
        f"{from_sql} "
        f"{where_sql}"
        f"GROUP BY {group_expr} "
        f"ORDER BY {order_expr}"
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(exec_sql, params)
            cols = [d[0] for d in cur.description]
            rows = [_row_to_dict(cols, row) for row in cur.fetchall()]
    return rows, display_sql


def inst1_result_label(result_key: str) -> str:
    """결과 키 → 한글명(테이블명) 표시."""
    if result_key in INST1_TABLE_KOREAN_NAMES:
        korean = INST1_TABLE_KOREAN_NAMES[result_key]
        return f"{korean}({result_key})"
    if result_key.startswith("JOIN_"):
        tables = [t for t in INST1_TABLE_ORDER if t in result_key]
        if tables:
            korean = "·".join(INST1_TABLE_KOREAN_NAMES[t] for t in tables)
            tech = "·".join(tables)
            return f"{korean}({tech})"
    for table in INST1_TABLE_ORDER:
        if result_key.startswith(f"{table}_"):
            korean = INST1_TABLE_KOREAN_NAMES[table]
            return f"{korean}({table})"
    return result_key


def build_inst1_result_labels(result_keys: list[str]) -> dict[str, str]:
    return {key: inst1_result_label(key) for key in result_keys}


def _join_result_key(join_tables: list[str], group_by: list[str]) -> str:
    table_part = "_".join(join_tables)
    col_part = "_".join(group_by)
    return f"JOIN_{table_part}_{col_part}별고객수"


def _result_key(table: str, analysis: dict[str, Any]) -> str:
    cols = _normalize_group_by(analysis.get("group_by"))
    if (
        analysis.get("query_type") == "aggregate"
        and analysis.get("aggregate_table") == table
        and cols
    ):
        return f"{table}_{'_'.join(cols)}별고객수"
    return table


def extract_inst1_data(analysis: dict[str, Any]) -> dict[str, Any]:
    """데이터 추출 전용 에이전트."""
    month = (analysis.get("month") or "").strip()
    group = (analysis.get("group_company") or DEFAULT_GROUP).strip()
    customer_id = analysis.get("customer_id")
    tables = list(analysis.get("tables") or ["TSHDEOA01", "TSHDEOA02"])
    if analysis.get("unlimited_rows"):
        limit: int | None = None
    else:
        limit = int(analysis.get("limit") or MAX_ROWS)
    zcd_only = (
        tables == [TSHDE0ZCD_TABLE]
        or (
            TSHDE0ZCD_TABLE in tables
            and TSHDEOA01_TABLE not in tables
            and TSHDEOA02_TABLE not in tables
        )
    )
    query_type = analysis.get("query_type") or "select"
    group_by = _normalize_group_by(analysis.get("group_by"))
    group_by_details = list(analysis.get("group_by_details") or [])
    aggregate_table = analysis.get("aggregate_table")
    join_tables = list(analysis.get("join_tables") or [])

    result: dict[str, list[dict[str, Any]]] = {}
    queries: dict[str, str] = {}
    errors: list[str] = []

    if zcd_only:
        result_key = TSHDE0ZCD_TABLE
        try:
            rows, sql = _fetch_zcd_table(
                TSHDE0ZCD_SCHEMA,
                TSHDE0ZCD_TABLE,
                group_company=group,
                limit=limit,
            )
            result[result_key] = rows
            queries[result_key] = sql
        except Exception as e:
            errors.append(f"TSHDE0ZCD: {e}")
            queries[result_key] = build_zcd_select_query(
                TSHDE0ZCD_SCHEMA,
                TSHDE0ZCD_TABLE,
                group_company=group,
                limit=limit,
            )
        total = sum(len(v) for v in result.values())
        if total == 0 and not errors:
            errors.append(
                f"조건(그룹회사={group})에 맞는 인스턴스 목록 데이터가 없습니다."
            )
        decoded = decode_inst1_data(result, group)
        inst1_data, inst1_column_orders = apply_column_order_to_results(decoded, analysis)
        result_keys = list(dict.fromkeys([*queries, *inst1_data]))
        return {
            "inst1_data": inst1_data,
            "inst1_column_orders": inst1_column_orders,
            "inst1_result_labels": build_inst1_result_labels(result_keys),
            "inst1_queries": queries,
            "month": month,
            "group_company": group,
            "customer_id": customer_id,
            "errors": errors,
            "total_rows": total,
        }

    if query_type == "join_aggregate" and join_tables and group_by_details:
        result_key = _join_result_key(join_tables, group_by)
        try:
            rows, sql = _fetch_join_aggregate(
                join_tables,
                group_by_details,
                month=month,
                group_company=group,
                customer_id=customer_id,
            )
            result[result_key] = rows
            queries[result_key] = sql
        except Exception as e:
            errors.append(f"조인 집계: {e}")
            queries[result_key] = build_join_aggregate_query(
                join_tables,
                group_by_details,
                month=month,
                group_company=group,
                customer_id=customer_id,
            )
        total = sum(len(v) for v in result.values())
        if total == 0 and not errors:
            errors.append(
                f"조건({_filter_condition_text(month=month, group=group, customer_id=customer_id)})"
                "에 맞는 조인 집계 데이터가 없습니다."
            )
        decoded = decode_inst1_data(result, group)
        inst1_data, inst1_column_orders = apply_column_order_to_results(decoded, analysis)
        result_keys = list(dict.fromkeys([*queries, *inst1_data]))
        return {
            "inst1_data": inst1_data,
            "inst1_column_orders": inst1_column_orders,
            "inst1_result_labels": build_inst1_result_labels(result_keys),
            "inst1_queries": queries,
            "month": month,
            "group_company": group,
            "customer_id": customer_id,
            "errors": errors,
            "total_rows": total,
        }

    if "TSHDEOA01" in tables:
        result_key = _result_key("TSHDEOA01", analysis)
        try:
            if query_type == "aggregate" and group_by and aggregate_table == "TSHDEOA01":
                rows, sql = _fetch_aggregate(
                    TSHDEOA01_SCHEMA,
                    TSHDEOA01_TABLE,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    group_by=group_by,
                    logical_table="TSHDEOA01",
                )
            else:
                rows, sql = _fetch_table(
                    TSHDEOA01_SCHEMA,
                    TSHDEOA01_TABLE,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    limit=limit,
                )
            result[result_key] = rows
            queries[result_key] = sql
        except Exception as e:
            errors.append(f"TSHDEOA01: {e}")
            if query_type == "aggregate" and group_by and aggregate_table == "TSHDEOA01":
                queries[result_key] = build_aggregate_query(
                    TSHDEOA01_SCHEMA,
                    TSHDEOA01_TABLE,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    group_by=group_by,
                    logical_table="TSHDEOA01",
                )
            else:
                queries[result_key] = build_select_query(
                    TSHDEOA01_SCHEMA,
                    TSHDEOA01_TABLE,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    limit=limit,
                )

    if "TSHDEOA02" in tables:
        result_key = _result_key("TSHDEOA02", analysis)
        try:
            if query_type == "aggregate" and group_by and aggregate_table == "TSHDEOA02":
                rows, sql = _fetch_aggregate(
                    TSHDEOA02_SCHEMA,
                    TSHDEOA02_TABLE,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    group_by=group_by,
                    logical_table="TSHDEOA02",
                )
            else:
                rows, sql = _fetch_table(
                    TSHDEOA02_SCHEMA,
                    TSHDEOA02_TABLE,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    limit=limit,
                )
                result_key = "TSHDEOA02"
            result[result_key] = rows
            queries[result_key] = sql
        except Exception as e:
            errors.append(f"TSHDEOA02: {e}")
            if query_type == "aggregate" and group_by and aggregate_table == "TSHDEOA02":
                queries[result_key] = build_aggregate_query(
                    TSHDEOA02_SCHEMA,
                    TSHDEOA02_TABLE,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    group_by=group_by,
                    logical_table="TSHDEOA02",
                )
            else:
                queries["TSHDEOA02"] = build_select_query(
                    TSHDEOA02_SCHEMA,
                    TSHDEOA02_TABLE,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    limit=limit,
                )

    total = sum(len(v) for v in result.values())
    if total == 0 and not errors:
        errors.append(
            f"조건({_filter_condition_text(month=month, group=group, customer_id=customer_id)})"
            "에 맞는 데이터가 없습니다."
        )

    decoded = decode_inst1_data(result, group)
    inst1_data, inst1_column_orders = apply_column_order_to_results(decoded, analysis)
    result_keys = list(dict.fromkeys([*queries, *inst1_data]))
    return {
        "inst1_data": inst1_data,
        "inst1_column_orders": inst1_column_orders,
        "inst1_result_labels": build_inst1_result_labels(result_keys),
        "inst1_queries": queries,
        "month": month,
        "group_company": group,
        "customer_id": customer_id,
        "errors": errors,
        "total_rows": total,
    }


def _format_rows_table(rows: list[dict[str, Any]], max_cols: int = 8) -> str:
    if not rows:
        return "(데이터 없음)"
    cols = list(rows[0].keys())[:max_cols]
    if len(rows[0]) > max_cols:
        cols.append("…")
    lines = [" | ".join(cols), " | ".join(["---"] * len(cols))]
    for row in rows[:20]:
        vals = []
        for c in cols:
            if c == "…":
                vals.append("…")
            else:
                v = row.get(c, "")
                vals.append(str(v) if v is not None else "")
        lines.append(" | ".join(vals))
    if len(rows) > 20:
        lines.append(f"… 외 {len(rows) - 20}건")
    return "\n".join(lines)


def format_inst1_reply(
    analysis: dict[str, Any],
    extract_result: dict[str, Any],
) -> str:
    """추출 결과를 채팅 응답 텍스트로 포맷."""
    month = extract_result.get("month", "")
    group = extract_result.get("group_company", "")
    customer_id = extract_result.get("customer_id")
    data: dict[str, list] = extract_result.get("inst1_data") or {}
    queries: dict[str, str] = extract_result.get("inst1_queries") or {}
    errors: list[str] = extract_result.get("errors") or []

    parts = [
        format_agent_banner(analysis),
        "",
        "[질문 분석]",
        f"- 판단: {analysis.get('reason', '')}",
        "",
        "[데이터 추출]",
        f"- 그룹회사코드: {group}",
    ]
    if month:
        parts.append(f"- 기준년월: {month} ({format_yyyymm(month)})")
    if customer_id:
        parts.append(f"- 그룹고객식별자: {customer_id}")
    group_cols = _normalize_group_by(analysis.get("group_by"))
    labels: dict[str, str] = extract_result.get("inst1_result_labels") or {}
    if analysis.get("query_type") == "join_aggregate" and group_cols:
        join_names = analysis.get("join_tables") or []
        join_labels = [labels.get(t, inst1_result_label(t)) for t in join_names]
        parts.append(f"- 조인 테이블: {', '.join(join_labels)}")
        parts.append(f"- 집계 유형: {', '.join(group_cols)}별 고객수")
    elif analysis.get("query_type") == "aggregate" and group_cols:
        parts.append(f"- 집계 유형: {', '.join(group_cols)}별 고객수")

    tables = list(dict.fromkeys([*(queries or {}), *(data or {})]))
    if tables:
        table_labels = [labels.get(t, inst1_result_label(t)) for t in tables]
        parts.append(f"- 대상 테이블: {', '.join(table_labels)}")
        for table in tables:
            row_count = len(data.get(table, []))
            if row_count:
                display = labels.get(table, inst1_result_label(table))
                parts.append(f"- {display}: {row_count}건 조회")
        parts.append("- 생성된 SQL과 조회 결과는 아래에 표시됩니다.")

    if errors:
        parts.extend(["", "[알림]", *[f"- {e}" for e in errors]])

    parts.append("")
    parts.append(
        f"※ {TSHDEOA01_KOREAN_NAME}=TSHDEOA01, {TSHDEOA02_KOREAN_NAME}=TSHDEOA02. "
        "코드 컬럼은 TSHDE0ZCD 인스턴스내용으로 표시됩니다."
    )
    return "\n".join(parts)
