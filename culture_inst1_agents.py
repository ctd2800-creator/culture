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
from culture_db.table_config import (
    INST1_AGGREGATE_COLUMNS,
    INST1_COLUMN_DEFINITIONS,
    INST1_GROUP_ALIASES,
    INST1_JOIN_KEYS,
    INST1_DATA_TABLES,
    INST1_NUMERIC_COLUMNS,
    INST1_TABLE_ALIASES,
    INST1_TABLE_COLUMNS,
    INST1_TABLE_KOREAN_NAMES,
    INST1_TABLE_ORDER,
    INST1_TABLE_SQL_ALIAS,
    inst1_join_keys_between,
    inst1_table_has_group_company,
    TSHDEOA01_KOREAN_NAME,
    TSHDEOA01_SCHEMA,
    TSHDEOA01_TABLE,
    TSHDEOA02_KOREAN_NAME,
    TSHDEOA02_SCHEMA,
    TSHDEOA02_TABLE,
    TSHDEOA04_KOREAN_NAME,
    TSHDEOA04_SCHEMA,
    TSHDEOA04_TABLE,
    TSHDEOA03_KOREAN_NAME,
    TSHDEOA03_SCHEMA,
    TSHDEOA03_TABLE,
    TSHDEOA05_KOREAN_NAME,
    TSHDEOA05_SCHEMA,
    TSHDEOA05_TABLE,
    TSHDEOA06_KOREAN_NAME,
    TSHDEOA06_SCHEMA,
    TSHDEOA06_TABLE,
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
- inst1_extract: TSHDEOA01·TSHDEOA02·TSHDEOA03·TSHDEOA04·TSHDEOA05·TSHDEOA06·TSHDE0ZCD 테이블에서 데이터 조회·추출 요청
- inst1_chart: 직전 집계 조회 결과 차트 — 유형 선택 후 시각화
- inst1_external_insight: 직전 집계 결과를 경제·정책·시장 동향 등과 결합해 분석 (분석 에이전트, 데이터 재조회 없음)
- general_chat: 일반 대화

JSON 스키마:
{
  "intent": "inst1_table_prompt|inst1_aggregate_prompt|inst1_column_desc|inst1_data_summary|inst1_extract|inst1_chart|inst1_external_insight|general_chat",
  "query_type": "select|aggregate|join_aggregate",
  "tables": ["TSHDEOA01", "TSHDEOA02"],
  "month": "YYYYMM 또는 빈 문자열",
  "group_company": "KFG 등 또는 빈 문자열",
  "customer_id": "10자리 그룹고객식별자 또는 null",
  "group_by": ["집계 기준 컬럼명"] 또는 null,
  "reason": "판단 근거 한 줄"
}

테이블 한글명: 그룹고객기본정보=TSHDEOA01, 그룹고객거래기본=TSHDEOA02, 그룹고객연락처정보=TSHDEOA03, 그룹고객소득대출정보=TSHDEOA04, 그룹계열사마케팅정보=TSHDEOA05, 그룹신용등급정보=TSHDEOA06, 그룹고객분석인스턴스목록=TSHDE0ZCD
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
TSHDEOA01(그룹고객기본정보)·TSHDEOA02(그룹고객거래기본)·TSHDEOA03(그룹고객연락처정보)·TSHDEOA04(그룹고객소득대출정보)·TSHDEOA05(그룹계열사마케팅정보)·TSHDEOA06(그룹신용등급정보) 모두 컬럼별 고객수 집계 가능.
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
    "TSHDEOA03": (
        "TSHDEOA03",
        "TSHDE0A03",
        TSHDEOA03_KOREAN_NAME,
        "그룹 고객 연락처정보",
        "연락처",
        "마케팅동의",
        "이메일",
        "휴대폰",
    ),
    "TSHDEOA04": (
        "TSHDEOA04",
        "TSHDE0A04",
        TSHDEOA04_KOREAN_NAME,
        "그룹 고객 소득대출정보",
        "그룹고객 소득대출정보",
        "소득대출",
        "연소득",
        "급여이체",
        "대출잔액",
        "연체",
        "직업분류",
    ),
    "TSHDEOA05": (
        "TSHDEOA05",
        "TSHDE0A05",
        TSHDEOA05_KOREAN_NAME,
        "그룹 계열사 마케팅정보",
        "계열사마케팅",
        "마케팅동의",
    ),
    "TSHDEOA06": (
        "TSHDEOA06",
        "TSHDE0A06",
        TSHDEOA06_KOREAN_NAME,
        "그룹 신용등급정보",
        "신용등급",
        "세그먼트",
        "결합평점",
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
# '별'·'집계' 같은 명시 키워드가 없어도 추이/변동/분포 분석이면 집계로 간주
TREND_HINTS = ("변동", "추이", "추세", "트렌드", "분포", "현황", "변화")
# '변동/증감' 요청이면 고객수 뒤에 전월대비 증감 컬럼을 추가
DELTA_HINTS = ("변동", "증감", "증감현황", "변화")
DELTA_COLUMN = "전월대비증감"
JOIN_HINTS = ("참조", "조인", "join", "JOIN")

TABLE_SQL_FQN: dict[str, str] = {
    "TSHDEOA01": f'"{TSHDEOA01_SCHEMA}"."{TSHDEOA01_TABLE}"',
    "TSHDEOA02": f'"{TSHDEOA02_SCHEMA}"."{TSHDEOA02_TABLE}"',
    "TSHDEOA03": f'"{TSHDEOA03_SCHEMA}"."{TSHDEOA03_TABLE}"',
    "TSHDEOA04": f'"{TSHDEOA04_SCHEMA}"."{TSHDEOA04_TABLE}"',
    "TSHDEOA05": f'"{TSHDEOA05_SCHEMA}"."{TSHDEOA05_TABLE}"',
    "TSHDEOA06": f'"{TSHDEOA06_SCHEMA}"."{TSHDEOA06_TABLE}"',
    "TSHDE0ZCD": f'"{TSHDE0ZCD_SCHEMA}"."{TSHDE0ZCD_TABLE}"',
}

INST1_TABLE_SCHEMA: dict[str, str] = {
    TSHDEOA01_TABLE: TSHDEOA01_SCHEMA,
    TSHDEOA02_TABLE: TSHDEOA02_SCHEMA,
    TSHDEOA03_TABLE: TSHDEOA03_SCHEMA,
    TSHDEOA04_TABLE: TSHDEOA04_SCHEMA,
    TSHDEOA05_TABLE: TSHDEOA05_SCHEMA,
    TSHDEOA06_TABLE: TSHDEOA06_SCHEMA,
    TSHDE0ZCD_TABLE: TSHDE0ZCD_SCHEMA,
}

_INST1_EXTRACT_SPECS: tuple[tuple[str, str, str], ...] = (
    (TSHDEOA01_TABLE, TSHDEOA01_SCHEMA, TSHDEOA01_TABLE),
    (TSHDEOA02_TABLE, TSHDEOA02_SCHEMA, TSHDEOA02_TABLE),
    (TSHDEOA03_TABLE, TSHDEOA03_SCHEMA, TSHDEOA03_TABLE),
    (TSHDEOA04_TABLE, TSHDEOA04_SCHEMA, TSHDEOA04_TABLE),
    (TSHDEOA05_TABLE, TSHDEOA05_SCHEMA, TSHDEOA05_TABLE),
    (TSHDEOA06_TABLE, TSHDEOA06_SCHEMA, TSHDEOA06_TABLE),
)

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
EXTERNAL_INSIGHT_HINTS = (
    "외부요인",
    "외부 요인",
    "외부정보",
    "외부 정보",
    "시장 동향",
    "시장동향",
    "경제 동향",
    "정책 동향",
    "결합해 분석",
    "결합하여 분석",
    "결합 분석",
    "인사이트",
    "외부요인과 결합",
)
AGGREGATE_CHART_FOLLOW_UP = "조회한 집계 데이터로 차트를 그려드릴까요?"
EXTERNAL_INSIGHT_FOLLOW_UP = "결과를 외부요인과 결합해 분석해줘"

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "inst1_table_prompt": "테이블 추천 질문 에이전트",
    "inst1_aggregate_prompt": "집계 컬럼 선택 에이전트",
    "inst1_column_desc": "컬럼 설명 에이전트",
    "inst1_data_summary": "데이터 요약 에이전트",
    "inst1_extract": "데이터 추출 에이전트",
    "inst1_chart": "차트 에이전트",
    "inst1_external_insight": "분석 에이전트",
    "inst1_excel": "엑셀 저장 에이전트",
    "inst1_report": "보고서 PDF 에이전트",
    "general_chat": "일반 대화 에이전트",
}

WORKFLOW_NODE_STATUS: dict[str, dict[str, str]] = {
    "analyze": {
        "agent": "질문 분석 에이전트",
        "description": "질문 의도를 파악하고, 조회·집계·요약 중 어떤 분석이 필요한지 판단하고 있습니다.",
    },
    "table_prompt": {
        "agent": AGENT_DISPLAY_NAMES["inst1_table_prompt"],
        "description": "분석 가능한 테이블을 안내하고 추천 질문을 준비하고 있습니다.",
    },
    "aggregate_prompt": {
        "agent": AGENT_DISPLAY_NAMES["inst1_aggregate_prompt"],
        "description": "조회 항목·집계 항목을 단계별로 안내하고 있습니다.",
    },
    "column_desc": {
        "agent": AGENT_DISPLAY_NAMES["inst1_column_desc"],
        "description": "테이블 컬럼의 의미와 활용 방법을 설명하고 있습니다.",
    },
    "data_summary": {
        "agent": AGENT_DISPLAY_NAMES["inst1_data_summary"],
        "description": "조회된 데이터를 분석하여 핵심 내용을 요약하고 있습니다.",
    },
    "chart": {
        "agent": AGENT_DISPLAY_NAMES["inst1_chart"],
        "description": "집계 결과 차트 유형 선택을 안내하고 있습니다.",
    },
    "external_insight": {
        "agent": AGENT_DISPLAY_NAMES["inst1_external_insight"],
        "description": "직전 집계 결과를 바탕으로 경제·정책·시장 동향과 결합해 분석하고 있습니다.",
    },
    "fetch_inst1": {
        "agent": AGENT_DISPLAY_NAMES["inst1_extract"],
        "description": "SQL을 생성하고 그룹고객 데이터를 조회하고 있습니다.",
    },
    "format_inst1": {
        "agent": AGENT_DISPLAY_NAMES["inst1_extract"],
        "description": "조회 결과를 표 형식으로 정리하고 있습니다.",
    },
    "general": {
        "agent": AGENT_DISPLAY_NAMES["general_chat"],
        "description": "AI가 질문에 맞는 답변을 생성하고 있습니다.",
    },
    "reply": {
        "agent": "응답 조립",
        "description": "분석 결과를 모아 최종 답변을 완성하고 있습니다.",
    },
}


def build_workflow_status_event(node_name: str) -> dict[str, str]:
    info = WORKFLOW_NODE_STATUS.get(node_name)
    if info:
        agent = info["agent"]
        description = info["description"]
    else:
        agent = node_name
        description = f"{node_name} 단계를 처리하고 있습니다."
    return {
        "type": "status",
        "node": node_name,
        "agent": agent,
        "description": description,
        "text": f"[호출 에이전트: {agent}]\n{description}",
    }

_AGGREGATE_PROMPT_SKIP_COLUMNS = frozenset({"그룹회사코드", "그룹고객식별자"})
VIRTUAL_AGGREGATE_MEASURE = "고객수"
AGGREGATE_FUNC_OPTIONS: tuple[str, ...] = ("합계", "최대값", "최소값", "평균")
_AGGREGATE_FUNC_SQL: dict[str, str] = {
    "합계": "SUM",
    "총합": "SUM",
    "총계": "SUM",
    "합산": "SUM",
    "토탈": "SUM",
    "sum": "SUM",
    "최대값": "MAX",
    "최댓값": "MAX",
    "최대": "MAX",
    "max": "MAX",
    "최소값": "MIN",
    "최솟값": "MIN",
    "최소": "MIN",
    "min": "MIN",
    "평균값": "AVG",
    "평균": "AVG",
    "avg": "AVG",
}

INST1_SUMMARY_SYSTEM_PROMPT = """당신은 금융·그룹고객 INST1 데이터 분석가입니다.
주어진 테이블 조회 결과만 근거로 한국어로 요약하세요.
- 조회 건수, 주요 수치·분포, 눈에 띄는 패턴을 3~6문장으로 정리하세요.
- 통계 요약이 있으면 활용하세요.
- 데이터에 없는 내용은 추측하지 마세요."""

INST1_EXTERNAL_INSIGHT_SYSTEM_PROMPT = """당신은 금융지주 그룹고객 데이터와 거시경제를 연결하는 시니어 애널리스트입니다.
직전 집계 데이터를 근거로, 경제·금융정책·시장 동향 등 외부 요인과 결합한 인사이트를 한국어로 작성하세요.

작성 원칙:
- 집계 데이터에서 읽히는 패턴·특이점을 먼저 짚으세요.
- 2024~2026년대 한국 금융·거시경제 맥락(금리, 규제, 소비, 디지털 전환 등)과 연결하세요.
- 외부 요인은 일반적으로 알려진 수준에서 서술하고, 집계 수치와의 연관을 명확히 하세요.
- 데이터에 없는 수치를 만들지 마세요.
- 가장 첫 줄에는 반드시 아래 형식으로 보고서 제목을 한 줄 작성하세요.
  보고서 제목: <집계 대상·기준·기간을 반영한 간결한 분석 제목 (예: KB스타클럽 등급별 고객 추이 분석 (2026년 2~4월))>
- 제목 다음 줄부터는 반드시 아래 세 소제목을 각각 한 줄로 그대로 사용하세요(번호 포함, 다른 머리표·마크다운 금지):
  1. 집계 핵심 요약
  2. 외부 환경 연결
  3. 시사점·제언
- '3. 시사점·제언'은 3~5개 bullet로 작성하세요.
- 보고서 본문으로 쓸 수 있게 완결된 문장으로 작성하세요."""

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

from culture_db.culture_db import connect_culture_db

_db_url_cache: str | None = None


def get_conn():
    return connect_culture_db(connect_timeout=15)


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


def parse_recent_months(text: str) -> int:
    """'최근 N개월/N년/N분기' → 최신 데이터 N개월 수. 없으면 0.

    '최근 3개월'은 DB에 적재된 가장 최신 기준년월 3개를 의미한다.
    """
    msg = text.strip()
    if "최근" not in msg and "최신" not in msg:
        return 0
    m = re.search(r"(?:최근|최신)\s*(\d{1,2})\s*개?\s*월", msg)
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"(?:최근|최신)\s*(\d{1,2})\s*분기", msg)
    if m:
        return max(1, int(m.group(1)) * 3)
    m = re.search(r"(?:최근|최신)\s*(\d{1,2})\s*년", msg)
    if m:
        return max(1, int(m.group(1)) * 12)
    return 0


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
    columns = set(INST1_AGGREGATE_COLUMNS.get(table, ()))
    columns.update(INST1_TABLE_COLUMNS.get(table, ()))
    columns.add(VIRTUAL_AGGREGATE_MEASURE)
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
    data_named = any(
        name in msg
        for table in INST1_TABLE_ORDER
        for name in (
            table,
            INST1_TABLE_KOREAN_NAMES.get(table, ""),
            f"TSHDE0A{table[-2:]}",
        )
        if name
    )
    if zcd_named and not data_named:
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


def _clean_table_label_remainder(remainder: str, table: str) -> str:
    """테이블 라벨 괄호·별칭만 남은 remainder 정리."""
    cleaned = remainder.strip()
    tokens = {
        table,
        table.upper(),
        INST1_TABLE_KOREAN_NAMES.get(table, ""),
        *INST1_TABLE_ALIASES.get(table, ()),
        f"TSHDE0A{table[-2:]}",
        f"TSHDE0A{table[-2:]}".upper(),
    }
    for token in sorted((t for t in tokens if t), key=len, reverse=True):
        cleaned = cleaned.replace(token, "")
    return re.sub(r"[()\s（）,，·]", "", cleaned).strip()


def _detect_table_name_only(message: str) -> tuple[str | None, str | None]:
    """테이블명만 입력된 경우 (logical_table, korean_name)."""
    msg = message.strip()
    if not msg:
        return None, None

    tables = _resolve_query_tables(msg, _tables_from_hints(msg))
    if len(tables) != 1:
        return None, None

    table = tables[0]
    remainder = _clean_table_label_remainder(
        _strip_table_names_from_message(msg, table),
        table,
    )
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


def _wants_external_insight(msg: str) -> bool:
    m = msg.strip()
    if any(h in m for h in EXTERNAL_INSIGHT_HINTS):
        return True
    if re.search(r"결합.{0,12}분석", m):
        return True
    if re.search(r"외부.{0,8}(요인|정보).{0,12}분석", m):
        return True
    return False


CUSTOMER_ID_COLUMN = "그룹고객식별자"


def _normalize_column_name(name: Any) -> str:
    return str(name or "").strip()


def _is_customer_id_column(name: Any) -> bool:
    col = _normalize_column_name(name)
    return col == CUSTOMER_ID_COLUMN or col.endswith("고객식별자")


def mask_customer_id(value: Any) -> str:
    """그룹고객식별자 표시용 마스킹 (예: 1234567890 → 12*******0)."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if len(s) <= 2:
        return "*" * len(s)
    if len(s) <= 4:
        return s[0] + "*" * (len(s) - 2) + s[-1]
    return s[:2] + "*" * (len(s) - 3) + s[-1]


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in row.items():
        if isinstance(val, Decimal):
            out[key] = float(val)
        else:
            out[key] = val
    return out


def mask_row_for_display(row: dict[str, Any]) -> dict[str, Any]:
    out = _json_safe_row(row)
    for key, val in list(out.items()):
        if _is_customer_id_column(key) and val not in (None, ""):
            out[key] = mask_customer_id(val)
    return out


def mask_excel_export_for_display(export: dict[str, Any]) -> dict[str, Any]:
    if not export:
        return export
    out = dict(export)
    if out.get("rows"):
        out["rows"] = [mask_row_for_display(r) for r in out["rows"]]
    sheets = out.get("sheets")
    if sheets:
        masked_sheets = []
        for sheet in sheets:
            if not isinstance(sheet, dict):
                masked_sheets.append(sheet)
                continue
            s = dict(sheet)
            if s.get("rows"):
                s["rows"] = [mask_row_for_display(r) for r in s["rows"]]
            masked_sheets.append(s)
        out["sheets"] = masked_sheets
    return out


def mask_inst1_data_for_display(
    data: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    return {key: [mask_row_for_display(r) for r in rows] for key, rows in data.items()}


def _aggregate_chart_label(row: dict[str, Any], group_by: list[str]) -> str:
    parts = []
    for col in group_by:
        val = row.get(col, "") or "-"
        if _is_customer_id_column(col):
            val = mask_customer_id(val)
        parts.append(str(val).strip())
    return " / ".join(parts) if parts else "-"


def _coerce_chart_number(val: Any) -> float | None:
    """차트 값으로 쓸 수 있는 숫자면 float, 아니면 None."""
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, str):
        text = val.strip().replace(",", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _chartable_measure_columns(
    rows: list[dict[str, Any]],
    group_by: list[str],
) -> list[str]:
    """집계 결과에서 차트로 그릴 수 있는 숫자 측정 컬럼 목록.

    GROUP BY 축과 전월대비증감 컬럼을 제외한, 값이 숫자인 컬럼을 반환한다.
    고객수 집계뿐 아니라 수신잔액 합계 등 임의 숫자 집계도 차트 대상이 된다.
    """
    if not rows:
        return []
    group_set = set(group_by)
    measures: list[str] = []
    for key in rows[0].keys():
        if key in group_set or key == DELTA_COLUMN:
            continue
        if any(_coerce_chart_number(row.get(key)) is not None for row in rows):
            measures.append(key)
    return measures


CHART_TYPE_OPTIONS: tuple[dict[str, str], ...] = (
    {"id": "bar", "label": "막대차트"},
    {"id": "line", "label": "선차트"},
    {"id": "pie", "label": "원형차트"},
    {"id": "doughnut", "label": "도넛차트"},
)

_CHART_SLICE_COLORS = (
    "rgba(255, 204, 0, 0.88)",
    "rgba(92, 75, 60, 0.88)",
    "rgba(255, 159, 64, 0.88)",
    "rgba(75, 192, 192, 0.88)",
    "rgba(153, 102, 255, 0.88)",
    "rgba(255, 99, 132, 0.88)",
    "rgba(54, 162, 235, 0.88)",
    "rgba(201, 203, 207, 0.88)",
)


def build_chart_type_options() -> list[dict[str, str]]:
    return [dict(opt) for opt in CHART_TYPE_OPTIONS]


def _chart_slice_colors(count: int) -> list[str]:
    if count <= 0:
        return []
    colors = list(_CHART_SLICE_COLORS)
    out: list[str] = []
    for i in range(count):
        out.append(colors[i % len(colors)])
    return out


_SERIES_RGB = (
    (255, 204, 0),
    (92, 75, 60),
    (255, 159, 64),
    (75, 192, 192),
    (153, 102, 255),
    (255, 99, 132),
    (54, 162, 235),
    (201, 203, 207),
)


def _series_color(idx: int, *, alpha: float = 1.0) -> str:
    r, g, b = _SERIES_RGB[idx % len(_SERIES_RGB)]
    return f"rgba({r}, {g}, {b}, {alpha})"


def _series_fill(idx: int) -> str:
    return _series_color(idx, alpha=0.25)


def _chart_type_label(chart_type: str) -> str:
    for opt in CHART_TYPE_OPTIONS:
        if opt["id"] == chart_type:
            return opt["label"]
    return chart_type


def _series_values(rows: list[dict[str, Any]], col: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        num = _coerce_chart_number(row.get(col))
        values.append(num if num is not None else 0.0)
    return values


def build_aggregate_chart_specs(
    pending_chart: dict[str, Any],
    *,
    chart_type: str = "bar",
) -> list[dict[str, Any]]:
    """집계 결과 pending_chart → Chart.js 스펙.

    고객수뿐 아니라 수신잔액 합계 등 임의 숫자 집계 컬럼을 차트로 그린다.
    측정 컬럼이 여러 개면 막대·선차트는 컬럼별 데이터셋으로, 원형·도넛은
    집계 항목마다 별도의 차트를 생성해 모든 항목을 시각화한다.
    """
    rows = list(pending_chart.get("rows") or [])
    group_by = _normalize_group_by(pending_chart.get("group_by"))
    if not rows or not group_by:
        return []
    measures = list(pending_chart.get("measures") or []) or _chartable_measure_columns(
        rows, group_by
    )
    if not measures:
        return []

    chart_type = (chart_type or "bar").strip().lower()
    valid_ids = {opt["id"] for opt in CHART_TYPE_OPTIONS}
    if chart_type not in valid_ids:
        chart_type = "bar"

    display = pending_chart.get("display_label") or "집계"
    month = (pending_chart.get("month") or "").strip()
    month_suffix = f" · {format_yyyymm(month)}" if month else ""
    group_cols_label = ", ".join(group_by)
    type_label = _chart_type_label(chart_type)

    sorted_rows = sorted(
        rows,
        key=lambda r: _aggregate_chart_label(r, group_by),
    )
    labels = [_aggregate_chart_label(r, group_by) for r in sorted_rows]
    measures_label = ", ".join(measures)

    title = (
        f"{display} · {group_cols_label}별 {measures_label} "
        f"({type_label}){month_suffix}"
    )

    if chart_type in ("pie", "doughnut"):
        # 원형·도넛은 한 차트에 하나의 시리즈만 표현 가능하므로
        # 집계 항목마다 별도의 차트를 생성한다.
        specs: list[dict[str, Any]] = []
        for col in measures:
            values = _series_values(sorted_rows, col)
            pie_title = (
                f"{display} · {group_cols_label}별 {col} "
                f"({type_label}){month_suffix}"
            )
            specs.append(
                {
                    "type": chart_type,
                    "title": pie_title,
                    "labels": labels,
                    "datasets": [
                        {
                            "label": col,
                            "data": values,
                            "backgroundColor": _chart_slice_colors(len(values)),
                            "borderColor": "#fff",
                            "borderWidth": 1,
                        }
                    ],
                }
            )
        return specs

    if chart_type == "line":
        datasets = []
        for idx, col in enumerate(measures):
            color = _series_color(idx)
            datasets.append(
                {
                    "label": col,
                    "data": _series_values(sorted_rows, col),
                    "borderColor": color,
                    "backgroundColor": _series_fill(idx),
                    "borderWidth": 2,
                    "pointBackgroundColor": color,
                    "pointBorderColor": "rgba(92, 75, 60, 1)",
                    "tension": 0.2,
                    "fill": False,
                }
            )
        return [
            {
                "type": "line",
                "title": title,
                "labels": labels,
                "datasets": datasets,
            }
        ]

    datasets = []
    for idx, col in enumerate(measures):
        datasets.append(
            {
                "label": col,
                "data": _series_values(sorted_rows, col),
                "backgroundColor": _series_color(idx, alpha=0.82),
                "borderColor": "rgba(92, 75, 60, 1)",
                "borderWidth": 1,
            }
        )
    return [
        {
            "type": "bar",
            "title": title,
            "labels": labels,
            "datasets": datasets,
        }
    ]


def build_pending_chart_payload(
    analysis: dict[str, Any],
    extract_result: dict[str, Any],
) -> dict[str, Any]:
    """집계 조회 성공 시 차트·외부요인 follow-up용 세션 데이터."""
    query_type = analysis.get("query_type") or ""
    if query_type not in ("aggregate", "join_aggregate"):
        return {}
    group_by = _normalize_group_by(analysis.get("group_by"))
    if not group_by:
        return {}
    data: dict[str, list] = extract_result.get("inst1_data") or {}
    labels: dict[str, str] = extract_result.get("inst1_result_labels") or {}
    column_orders: dict[str, list] = extract_result.get("inst1_column_orders") or {}
    queries: dict[str, str] = extract_result.get("inst1_queries") or {}
    for key, rows in data.items():
        if not rows:
            continue
        safe_rows = [_json_safe_row(r) for r in rows]
        measures = _chartable_measure_columns(safe_rows, group_by)
        payload = {
            "result_key": key,
            "rows": safe_rows,
            "group_by": group_by,
            "display_label": labels.get(key, inst1_result_label(key)),
            "column_order": list(column_orders.get(key) or []),
            "query": queries.get(key, ""),
            "month": (extract_result.get("month") or "").strip(),
            "group_company": (extract_result.get("group_company") or "").strip(),
            "measures": measures,
            "chartable": bool(measures),
        }
        return payload
    return {}


def format_chart_agent_reply(
    analysis: dict[str, Any],
    pending_chart: dict[str, Any],
    *,
    chart_type: str | None = None,
) -> str:
    display = pending_chart.get("display_label") or "집계 데이터"
    group_by = ", ".join(_normalize_group_by(pending_chart.get("group_by")))
    row_count = len(pending_chart.get("rows") or [])
    measures = list(pending_chart.get("measures") or []) or _chartable_measure_columns(
        list(pending_chart.get("rows") or []),
        _normalize_group_by(pending_chart.get("group_by")),
    )
    measures_label = ", ".join(measures) if measures else "집계값"
    if chart_type:
        type_label = _chart_type_label(chart_type)
        tail = f"아래 {type_label}에서 {measures_label}을(를) 확인하세요."
    else:
        type_labels = ", ".join(opt["label"] for opt in CHART_TYPE_OPTIONS)
        tail = "\n".join(
            [
                "아래에서 차트 유형을 선택해 주세요.",
                f"선택 가능: {type_labels}",
            ]
        )
    body = "\n".join(
        [
            "[집계 데이터 차트]",
            f"- 대상: {display}",
            f"- 집계 기준: {group_by}",
            f"- 집계 항목: {measures_label}",
            f"- 표시 건수: {row_count}건",
            "",
            tail,
        ]
    )
    return with_agent_banner(body, analysis)


def _detect_external_insight_followup(
    message: str,
    pending_chart: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not _wants_external_insight(message.strip()):
        return None
    pending = pending_chart or {}
    if not pending.get("rows"):
        return None
    return {
        "intent": "inst1_external_insight",
        "query_type": "analysis",
        "tables": [],
        "month": pending.get("month") or "",
        "group_company": pending.get("group_company") or "",
        "customer_id": None,
        "group_by": list(pending.get("group_by") or []),
        "reason": "직전 집계 결과 분석 요청",
    }


def _build_analysis_agent_payload(
    pending_chart: dict[str, Any] | None,
    *,
    reason: str,
) -> dict[str, Any]:
    """분석 에이전트 라우팅 — 데이터 추출(fetch) 없이 직전 집계 스냅샷 사용."""
    pending = pending_chart or {}
    return {
        "intent": "inst1_external_insight",
        "query_type": "analysis",
        "tables": [],
        "month": pending.get("month") or "",
        "group_company": pending.get("group_company") or "",
        "customer_id": None,
        "group_by": list(pending.get("group_by") or []),
        "reason": reason,
    }


def _resolve_analysis_agent_intent(
    message: str,
    pending_chart: dict[str, Any] | None,
    *,
    reason: str = "직전 집계 결과 분석 요청",
) -> dict[str, Any]:
    followup = _detect_external_insight_followup(message, pending_chart)
    if followup:
        return followup
    return _build_analysis_agent_payload(
        pending_chart,
        reason=reason,
    )


def analyze_aggregate_external_insight(
    pending_chart: dict[str, Any],
    user_message: str,
    analysis: dict[str, Any],
    *,
    bedrock_ask=None,
) -> str:
    """직전 집계 결과 기반 분석."""
    rows = list(pending_chart.get("rows") or [])
    if not rows:
        raise ValueError(
            "분석할 집계 데이터가 없습니다. 먼저 집계 데이터를 조회해 주세요."
        )
    group_by = _normalize_group_by(pending_chart.get("group_by"))
    display = pending_chart.get("display_label") or "집계 데이터"
    month = (pending_chart.get("month") or "").strip()
    group = (pending_chart.get("group_company") or "").strip()

    sample_rows = [_json_safe_row(r) for r in rows[:50]]
    data_json = json.dumps(sample_rows, ensure_ascii=False, indent=2, default=str)

    header_lines = [
        "[분석]",
        f"- 대상: {display}",
        f"- 집계 기준: {', '.join(group_by) if group_by else '-'}",
        f"- 데이터 건수: {len(rows)}건",
    ]
    if month:
        header_lines.append(f"- 기준년월: {month} ({format_yyyymm(month)})")
    if group:
        header_lines.append(f"- 그룹회사코드: {group}")

    request_text = user_message.strip() or EXTERNAL_INSIGHT_FOLLOW_UP
    prompt = (
        f"집계 대상: {display}\n"
        f"기준년월: {month or '-'} ({format_yyyymm(month) if month else '-'})\n"
        f"그룹회사코드: {group or '-'}\n"
        f"집계 기준: {', '.join(group_by) if group_by else '-'}\n"
        f"전체 {len(rows)}건 (JSON 최대 {len(sample_rows)}건):\n{data_json}\n\n"
        f"사용자 요청: {request_text}\n\n"
        "위 집계 결과를 경제·금융정책·시장 동향과 결합해 인사이트를 작성하세요."
    )

    if bedrock_ask is None:
        body = "\n".join([*header_lines, "", "(Bedrock 미연결 — 분석 본문 생략)"])
        return with_agent_banner(body, analysis)

    insight = bedrock_ask(
        INST1_EXTERNAL_INSIGHT_SYSTEM_PROMPT,
        [{"role": "user", "content": prompt}],
        4096,
    )
    body = "\n".join(
        [
            *header_lines,
            "",
            insight.strip(),
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
    """분석 에이전트 응답 → Word 보고서 버튼 노출용 payload."""
    from culture_ppt_report import ascii_report_filename

    text = (content or "").strip()
    if not text:
        return {}
    return {
        "agent": agent,
        "content": text,
        "table_label": table_label,
        "month": (month or "").strip(),
        "chart_specs": list(chart_specs or []),
        "filename": ascii_report_filename("culture_report", ext="docx"),
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
                "rows": [mask_row_for_display(r) for r in rows],
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
    if _wants_external_insight(msg):
        return False
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


def build_table_prompt_follow_up_questions(korean: str) -> list[str]:
    return [
        f"{korean}의 데이터를 보여드릴까요?",
        f"{korean}의 집계 데이터를 보여드릴까요?",
        f"{korean}의 컬럼을 설명해 드릴까요?",
        f"{korean}의 데이터를 요약해 드릴까요?",
    ]


def build_aggregate_follow_up_questions(*, chart_available: bool = False) -> list[str]:
    """집계 조회 성공 후 추천 질문."""
    questions = [EXTERNAL_INSIGHT_FOLLOW_UP]
    if chart_available:
        questions.insert(0, AGGREGATE_CHART_FOLLOW_UP)
    return questions


def format_inst1_table_prompt_reply(analysis: dict[str, Any]) -> str:
    """테이블명만 언급된 경우 추천 질문 응답."""
    table = (analysis.get("tables") or [None])[0]
    korean = analysis.get("table_korean") or INST1_TABLE_KOREAN_NAMES.get(
        table or "", table or ""
    )
    parts = [
        f"[{korean}] 테이블을 선택하셨습니다.",
        "아래 추천 질문을 선택하거나 원하는 내용을 입력해 주세요.",
    ]
    return with_agent_banner("\n".join(parts), analysis)


def _build_aggregate_prompt_payload(
    table: str,
    korean: str,
    *,
    reason: str,
    aggregate_stage: str = "group_by",
    group_by: list[str] | None = None,
    aggregate_measures: list[str] | None = None,
    aggregate_func: str = "",
    aggregate_measure_funcs: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "intent": "inst1_aggregate_prompt",
        "query_type": "aggregate_prompt",
        "tables": [table],
        "table_korean": korean,
        "month": "",
        "group_company": "",
        "customer_id": None,
        "group_by": list(group_by or []),
        "group_by_details": [],
        "join_tables": [],
        "aggregate_table": None,
        "mentioned_columns": [],
        "aggregate_measures": list(aggregate_measures or []),
        "aggregate_func": (aggregate_func or "").strip(),
        "aggregate_measure_funcs": dict(aggregate_measure_funcs or {}),
        "limit": MAX_ROWS,
        "unlimited_rows": False,
        "aggregate_stage": aggregate_stage,
        "reason": reason,
    }


def _build_aggregate_measure_prompt_payload(
    table: str,
    korean: str,
    group_by: list[str],
    *,
    reason: str,
) -> dict[str, Any]:
    return _build_aggregate_prompt_payload(
        table,
        korean,
        reason=reason,
        aggregate_stage="measure",
        group_by=group_by,
    )


def _build_aggregate_func_prompt_payload(
    table: str,
    korean: str,
    group_by: list[str],
    aggregate_measures: list[str],
    *,
    reason: str,
    aggregate_measure_funcs: dict[str, str] | None = None,
) -> dict[str, Any]:
    return _build_aggregate_prompt_payload(
        table,
        korean,
        reason=reason,
        aggregate_stage="aggregate_func",
        group_by=group_by,
        aggregate_measures=aggregate_measures,
        aggregate_measure_funcs=aggregate_measure_funcs,
    )


def format_inst1_aggregate_group_by_prompt_reply(analysis: dict[str, Any]) -> str:
    """집계 1단계 — GROUP BY 조회 항목 선택 안내."""
    table = (analysis.get("tables") or [None])[0]
    korean = analysis.get("table_korean") or INST1_TABLE_KOREAN_NAMES.get(
        table or "", table or ""
    )
    suggest_cols = build_group_by_column_options(analysis)
    parts = [
        f"[{korean}] 집계 데이터 조회 — 1단계",
        "GROUP BY에 사용할 조회 항목을 선택해 주세요.",
        "",
        "입력 예: 성별구분, 연령코드  또는  성별구분별, 연령코드별",
    ]
    if suggest_cols:
        parts.extend(
            [
                "",
                "아래 조회 항목을 클릭하면 입력란에 추가됩니다. 여러 개를 차례로 선택할 수 있습니다.",
            ]
        )
    return with_agent_banner("\n".join(parts), analysis)


def format_inst1_aggregate_measure_prompt_reply(analysis: dict[str, Any]) -> str:
    """집계 2단계 — 집계(수·액·소득) 항목 선택 안내."""
    table = (analysis.get("tables") or [None])[0]
    korean = analysis.get("table_korean") or INST1_TABLE_KOREAN_NAMES.get(
        table or "", table or ""
    )
    group_by = _normalize_group_by(analysis.get("group_by"))
    suggest_cols = build_aggregate_measure_column_options(analysis)
    parts = [
        f"[{korean}] 집계 데이터 조회 — 2단계",
    ]
    if group_by:
        parts.append(f"선택하신 조회 항목: {', '.join(group_by)}")
    parts.extend(
        [
            "집계할 항목을 선택해 주세요.",
            "「고객수」는 그룹고객식별자 건수이며, 다른 항목과 함께 선택할 수 없습니다.",
            "고객수만 선택하면 바로 조회되고, 그 외 항목은 3단계에서 항목별 집계 함수를 선택합니다.",
            "",
            "입력 예: 고객수  또는  보유수신상품계약수, 수신잔액, 연본인근로소득",
        ]
    )
    if suggest_cols:
        parts.extend(
            [
                "",
                "아래 집계 항목을 클릭하면 입력란에 추가됩니다.",
            ]
        )
    return with_agent_banner("\n".join(parts), analysis)


_AGGREGATE_FUNC_LABEL: dict[str, str] = {
    "SUM": "합계",
    "MAX": "최대값",
    "MIN": "최소값",
    "AVG": "평균",
}


def _next_measure_without_func(
    measures: list[str],
    measure_funcs: dict[str, str],
) -> str | None:
    for col in measures:
        if col not in measure_funcs:
            return col
    return None


def _func_label_korean(func_sql: str) -> str:
    return _AGGREGATE_FUNC_LABEL.get(func_sql.upper(), func_sql)


def format_inst1_aggregate_func_prompt_reply(analysis: dict[str, Any]) -> str:
    """집계 3단계 — 항목별 집계 함수 선택 안내."""
    table = (analysis.get("tables") or [None])[0]
    korean = analysis.get("table_korean") or INST1_TABLE_KOREAN_NAMES.get(
        table or "", table or ""
    )
    group_by = _normalize_group_by(analysis.get("group_by"))
    measures = list(analysis.get("aggregate_measures") or [])
    measure_funcs = dict(analysis.get("aggregate_measure_funcs") or {})
    target = _next_measure_without_func(measures, measure_funcs)
    parts = [
        f"[{korean}] 집계 데이터 조회 — 3단계",
    ]
    if group_by:
        parts.append(f"선택하신 조회 항목: {', '.join(group_by)}")
    if measures:
        parts.append(f"선택하신 집계 항목: {', '.join(measures)}")
    if measure_funcs:
        assigned = ", ".join(
            f"{col}→{_func_label_korean(func)}"
            for col, func in measure_funcs.items()
        )
        parts.append(f"지정 완료: {assigned}")
    if target:
        parts.extend(
            [
                f"「{target}」에 적용할 집계 함수를 선택해 주세요.",
                "",
                "입력 예: 합계  또는  수신잔액:합계, 보유수신상품계약수:평균",
            ]
        )
    parts.extend(
        [
            "",
            "아래 집계 함수를 클릭하면 입력란에 채워집니다.",
        ]
    )
    return with_agent_banner("\n".join(parts), analysis)


def format_inst1_aggregate_prompt_reply(analysis: dict[str, Any]) -> str:
    """집계 컬럼 선택 안내 응답."""
    stage = (analysis.get("aggregate_stage") or "group_by").strip()
    if stage == "aggregate_func":
        return format_inst1_aggregate_func_prompt_reply(analysis)
    if stage == "measure":
        return format_inst1_aggregate_measure_prompt_reply(analysis)
    return format_inst1_aggregate_group_by_prompt_reply(analysis)


def _is_aggregate_measure_column(col: str) -> bool:
    return col.endswith("수") or col.endswith("액") or col.endswith("소득")


def _aggregate_prompt_columns_for_table(table: str) -> list[str]:
    return [
        col
        for col in INST1_AGGREGATE_COLUMNS.get(table, ())
        if col not in _AGGREGATE_PROMPT_SKIP_COLUMNS
    ]


def build_group_by_column_options(analysis: dict[str, Any]) -> list[str]:
    table = (analysis.get("tables") or [None])[0]
    if not table:
        return []
    cols = [
        col
        for col in _aggregate_prompt_columns_for_table(table)
        if not _is_aggregate_measure_column(col)
    ]
    return cols


def build_aggregate_measure_column_options(analysis: dict[str, Any]) -> list[str]:
    table = (analysis.get("tables") or [None])[0]
    if not table:
        return [VIRTUAL_AGGREGATE_MEASURE]
    numeric_cols = [
        col
        for col in _aggregate_prompt_columns_for_table(table)
        if _is_aggregate_measure_column(col)
    ]
    return [VIRTUAL_AGGREGATE_MEASURE, *numeric_cols]


def build_aggregate_func_column_options(_analysis: dict[str, Any]) -> list[str]:
    return list(AGGREGATE_FUNC_OPTIONS)


def build_aggregate_column_options(analysis: dict[str, Any]) -> list[str]:
    stage = (analysis.get("aggregate_stage") or "group_by").strip()
    if stage == "aggregate_func":
        return build_aggregate_func_column_options(analysis)
    if stage == "measure":
        return build_aggregate_measure_column_options(analysis)
    return build_group_by_column_options(analysis)


def aggregate_column_options_label(analysis: dict[str, Any]) -> str:
    stage = (analysis.get("aggregate_stage") or "group_by").strip()
    if stage == "aggregate_func":
        measures = list(analysis.get("aggregate_measures") or [])
        measure_funcs = dict(analysis.get("aggregate_measure_funcs") or {})
        target = _next_measure_without_func(measures, measure_funcs)
        if target:
            return f"「{target}」 집계 함수:"
        return "집계 함수:"
    if stage == "measure":
        return "집계 항목 예:"
    return "조회 항목 예:"


def aggregate_column_pick_mode(analysis: dict[str, Any]) -> str:
    stage = (analysis.get("aggregate_stage") or "group_by").strip()
    if stage == "aggregate_func":
        return "replace"
    if stage == "measure":
        return "measure"
    return "append"


def _parse_aggregate_func(message: str) -> str | None:
    msg = message.strip()
    if not msg:
        return None
    lowered = msg.lower()
    for token, sql_func in _AGGREGATE_FUNC_SQL.items():
        if token in msg or token.lower() in lowered:
            return sql_func
    return None


def _normalize_aggregate_func(value: Any) -> str:
    raw = (value or "").strip()
    if not raw:
        return "SUM"
    return _AGGREGATE_FUNC_SQL.get(raw, _AGGREGATE_FUNC_SQL.get(raw.lower(), raw.upper()))


def _match_measure_column(token: str, measures: list[str]) -> str | None:
    name = (token or "").strip()
    if not name:
        return None
    return name if name in measures else None


def _parse_measure_func_assignments(
    message: str,
    measures: list[str],
    existing: dict[str, str],
) -> dict[str, str]:
    """항목별 집계 함수 지정 파싱 (단일 함수 또는 col:func 형식)."""
    result = dict(existing)
    msg = message.strip()
    if not msg:
        return result
    assigned = False
    for chunk in re.split(r"[,，、\n]+", msg):
        chunk = chunk.strip()
        if not chunk:
            continue
        matched = False
        for sep in (":", " "):
            if sep not in chunk:
                continue
            left, right = chunk.split(sep, 1)
            col = _match_measure_column(left.strip(), measures)
            func = _parse_aggregate_func(right.strip())
            if col and func:
                result[col] = func
                assigned = True
                matched = True
                break
        if matched:
            continue
        func = _parse_aggregate_func(chunk)
        if func:
            target = _next_measure_without_func(measures, result)
            if target:
                result[target] = func
                assigned = True
    if not assigned:
        func = _parse_aggregate_func(msg)
        if func:
            target = _next_measure_without_func(measures, result)
            if target:
                result[target] = func
    return result


def _parse_aggregate_column_list(
    message: str,
    table: str,
    *,
    allowed: set[str] | None = None,
) -> list[str]:
    """집계 follow-up 메시지에서 컬럼 목록 추출."""
    msg = message.strip()
    details = [d for d in _parse_group_by_details(msg) if d["table"] == table]
    if details:
        columns = [d["column"] for d in details]
    else:
        allowed_cols = allowed or set(INST1_AGGREGATE_COLUMNS.get(table, ()))
        mentioned = [c for c in parse_mentioned_columns(msg) if c in allowed_cols]
        if mentioned:
            columns = mentioned
        else:
            columns = []
            seen: set[str] = set()
            for chunk in re.split(r"[,，、\n]+", msg):
                token = chunk.strip().rstrip("별").strip()
                if not token:
                    continue
                if token == VIRTUAL_AGGREGATE_MEASURE and (
                    allowed is None or VIRTUAL_AGGREGATE_MEASURE in allowed
                ):
                    if VIRTUAL_AGGREGATE_MEASURE not in seen:
                        columns.append(VIRTUAL_AGGREGATE_MEASURE)
                        seen.add(VIRTUAL_AGGREGATE_MEASURE)
                    continue
                col = _resolve_group_column(token, table)
                if col and col not in seen:
                    columns.append(col)
                    seen.add(col)
    if allowed is not None and VIRTUAL_AGGREGATE_MEASURE in allowed and "고객수" in msg:
        if VIRTUAL_AGGREGATE_MEASURE not in columns:
            columns.append(VIRTUAL_AGGREGATE_MEASURE)
    if allowed is not None:
        columns = [col for col in columns if col in allowed]
    return _normalize_measure_selection(columns)


def _normalize_measure_selection(measure_cols: list[str]) -> list[str]:
    """고객수는 다른 집계 항목과 동시에 선택할 수 없음."""
    if VIRTUAL_AGGREGATE_MEASURE in measure_cols:
        return [VIRTUAL_AGGREGATE_MEASURE]
    return measure_cols


def _build_aggregate_extract_payload(
    table: str,
    korean: str,
    group_by: list[str],
    aggregate_measures: list[str],
    message: str,
    *,
    aggregate_func: str = "",
    aggregate_measure_funcs: dict[str, str] | None = None,
) -> dict[str, Any]:
    msg = message.strip()
    group_by_details = [{"table": table, "column": col} for col in group_by]
    measures = _normalize_measure_selection(aggregate_measures)
    measure_funcs = dict(aggregate_measure_funcs or {})
    if measures == [VIRTUAL_AGGREGATE_MEASURE]:
        measure_funcs = {VIRTUAL_AGGREGATE_MEASURE: "SUM"}
    elif not measure_funcs:
        func_sql = _normalize_aggregate_func(aggregate_func or "SUM")
        measure_funcs = {col: func_sql for col in measures}
    func_summary = ", ".join(
        f"{col}:{_func_label_korean(func)}" for col, func in measure_funcs.items()
    )
    return {
        "intent": "inst1_extract",
        "query_type": "aggregate",
        "tables": [table],
        "table_korean": korean,
        "month": parse_month(msg) or "",
        "group_company": _parse_group_company(msg),
        "customer_id": _parse_customer_id(msg),
        "group_by": group_by,
        "group_by_details": group_by_details,
        "join_tables": [],
        "aggregate_table": table,
        "aggregate_measures": measures,
        "aggregate_func": "",
        "aggregate_measure_funcs": measure_funcs,
        "mentioned_columns": group_by + measures,
        "limit": _resolve_row_limit(msg),
        "unlimited_rows": _wants_all_rows(msg),
        "reason": (
            f"집계 실행 (조회: {', '.join(group_by)}, "
            f"집계: {func_summary})"
        ),
    }


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


def _reprompt_current_aggregate_stage(
    pending: dict[str, Any],
) -> dict[str, Any] | None:
    """집계 컬럼 선택 진행 중 입력을 인식 못했을 때, 같은 단계를 다시 안내(재시작 방지)."""
    table = (pending.get("table") or "").strip()
    if not table:
        return None
    stage = (pending.get("stage") or "group_by").strip()
    korean = pending.get("korean") or INST1_TABLE_KOREAN_NAMES.get(table, table)
    if stage == "measure":
        group_by = _normalize_group_by(pending.get("group_by"))
        if not group_by:
            return None
        return _build_aggregate_measure_prompt_payload(
            table, korean, group_by,
            reason="집계 항목 선택 대기 — 입력을 인식하지 못해 다시 안내",
        )
    if stage == "aggregate_func":
        group_by = _normalize_group_by(pending.get("group_by"))
        measures = _normalize_measure_selection(
            list(pending.get("aggregate_measures") or [])
        )
        if not group_by or not measures:
            return None
        return _build_aggregate_func_prompt_payload(
            table, korean, group_by, measures,
            aggregate_measure_funcs=dict(pending.get("aggregate_measure_funcs") or {}),
            reason="집계 함수 선택 대기 — 입력을 인식하지 못해 다시 안내",
        )
    return _build_aggregate_prompt_payload(
        table, korean,
        reason="집계 조회 항목 선택 대기 — 입력을 인식하지 못해 다시 안내",
        aggregate_stage="group_by",
    )


def _detect_aggregate_followup(
    message: str,
    pending: dict[str, Any],
) -> dict[str, Any] | None:
    table = (pending.get("table") or "").strip()
    if not table:
        return None
    stage = (pending.get("stage") or "group_by").strip()
    korean = pending.get("korean") or INST1_TABLE_KOREAN_NAMES.get(table, table)
    msg = message.strip()

    if stage == "group_by":
        allowed = set(build_group_by_column_options({"tables": [table]}))
        cols = _parse_aggregate_column_list(message, table, allowed=allowed)
        if not cols:
            return None
        return _build_aggregate_measure_prompt_payload(
            table,
            korean,
            cols,
            reason=f"집계 조회 항목 지정 ({', '.join(cols)}) — 집계 항목 선택 대기",
        )

    if stage == "measure":
        group_by = _normalize_group_by(pending.get("group_by"))
        if not group_by:
            return None
        allowed = set(build_aggregate_measure_column_options({"tables": [table]}))
        measure_cols = _parse_aggregate_column_list(message, table, allowed=allowed)
        if not measure_cols:
            return None
        if measure_cols == [VIRTUAL_AGGREGATE_MEASURE]:
            return _build_aggregate_extract_payload(
                table,
                korean,
                group_by,
                measure_cols,
                msg,
            )
        return _build_aggregate_func_prompt_payload(
            table,
            korean,
            group_by,
            measure_cols,
            reason=f"집계 항목 지정 ({', '.join(measure_cols)}) — 집계 함수 선택 대기",
        )

    if stage == "aggregate_func":
        group_by = _normalize_group_by(pending.get("group_by"))
        measures = _normalize_measure_selection(
            list(pending.get("aggregate_measures") or [])
        )
        if not group_by or not measures:
            return None
        existing_funcs = dict(pending.get("aggregate_measure_funcs") or {})
        measure_funcs = _parse_measure_func_assignments(msg, measures, existing_funcs)
        if measure_funcs == existing_funcs:
            return None
        missing = _next_measure_without_func(measures, measure_funcs)
        if missing:
            return _build_aggregate_func_prompt_payload(
                table,
                korean,
                group_by,
                measures,
                aggregate_measure_funcs=measure_funcs,
                reason=(
                    f"집계 함수 지정 ({len(measure_funcs)}/{len(measures)}) — "
                    f"「{missing}」 선택 대기"
                ),
            )
        return _build_aggregate_extract_payload(
            table,
            korean,
            group_by,
            measures,
            msg,
            aggregate_measure_funcs=measure_funcs,
        )

    return None


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
    defs = INST1_COLUMN_DEFINITIONS.get(table, {})
    if rows:
        return [
            (name, defs.get(name) or _parse_column_comment(desc, name))
            for name, desc in rows
        ]
    fallback = INST1_TABLE_COLUMNS.get(table, ())
    return [(col, defs.get(col, col)) for col in fallback]


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
        ]
    )
    return with_agent_banner(body, analysis)


def _format_rows_preview(rows: list[dict[str, Any]], limit: int = 5) -> str:
    if not rows:
        return "(데이터 없음)"
    cols = list(rows[0].keys())
    lines = [" | ".join(cols)]
    for row in rows[:limit]:
        masked = mask_row_for_display(row)
        lines.append(" | ".join(str(masked.get(c, "")) for c in cols))
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
    recent_months = parse_recent_months(msg)
    trend_request = recent_months > 0 or any(h in msg for h in TREND_HINTS)
    delta_request = any(h in msg for h in DELTA_HINTS)
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
    elif trend_request:
        # '별'·'집계' 키워드는 없지만 변동/추이/현황 등 추이 분석 요청.
        # 메시지에 직접 언급된 집계 가능 컬럼(별칭 포함)을 찾아 집계로 처리.
        aggregate_table, group_by = _detect_aggregate_table(tables, msg)
        if group_by:
            query_type = "aggregate"
    korean_tables = _mentioned_korean_tables(msg)
    if korean_tables:
        labels = dict(INST1_TABLE_KOREAN_NAMES)
        alias_note = ", ".join(
            f"{labels.get(table, table)}→{table}" for table in korean_tables
        )
        reason = f"{reason} ({alias_note})"

    if recent_months:
        # '최근 N개월' → 최신 N개월 추이/변동 분석이므로 기준년월을 집계 축에 추가
        if query_type == "aggregate" and group_by and "기준년월" not in group_by:
            group_by = ["기준년월", *group_by]
        elif query_type == "join_aggregate" and group_by_details:
            primary = next(
                (t for t in INST1_TABLE_ORDER if t in join_tables),
                join_tables[0] if join_tables else None,
            )
            if primary and not any(
                d["column"] == "기준년월" for d in group_by_details
            ):
                group_by_details = [
                    {"table": primary, "column": "기준년월"},
                    *group_by_details,
                ]

    has_month_axis = "기준년월" in group_by or any(
        d["column"] == "기준년월" for d in group_by_details
    )
    delta = bool(
        delta_request
        and has_month_axis
        and query_type in ("aggregate", "join_aggregate")
    )

    return {
        "intent": "inst1_extract",
        "query_type": query_type,
        "tables": tables,
        "month": parse_month(msg) or "",
        "recent_months": recent_months,
        "delta": delta,
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
    if _wants_external_insight(msg):
        return _resolve_analysis_agent_intent(msg, pending_chart)
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
    if len(tables) == 1 and (
        parse_month(msg) or _parse_customer_id(msg) or _parse_group_company(msg)
    ):
        if not (
            _wants_column_description(msg)
            or _wants_data_summary(msg)
            or _wants_aggregate_data_prompt(msg)
            or _wants_chart(msg)
            or _wants_external_insight(msg)
            or _is_aggregate_request(msg)
        ):
            return _build_analysis_payload(
                msg,
                tables=tables,
                reason="테이블·필터 지정 데이터 조회",
            )
    wants_extract = _wants_data_extract(msg)
    if not tables and wants_extract:
        if TSHDE0ZCD_KOREAN_NAME in msg or "TSHDE0ZCD" in msg.upper():
            tables = [TSHDE0ZCD_TABLE]
        else:
            hinted = _tables_from_hints(msg)
            if len(hinted) == 1:
                tables = hinted
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
            ) and not hinted:
                tables = ["TSHDEOA01", "TSHDEOA02"]
    if not tables or not wants_extract:
        # 집계 컬럼 선택 진행 중이면 다른 의도로 새지 않도록 같은 단계를 다시 안내
        # (데이터 추출 대신 집계 프롬프트가 재시작되는 문제 방지).
        if pending_aggregate:
            reprompt = _reprompt_current_aggregate_stage(pending_aggregate)
            if reprompt:
                return reprompt
        return None
    return _build_analysis_payload(
        msg,
        tables=tables if tables else ["TSHDEOA01", "TSHDEOA02"],
        reason="키워드 기반 INST1 데이터 추출 요청",
    )


def predict_rule_based_intent(
    message: str,
    *,
    pending_aggregate: dict[str, Any] | None = None,
    pending_chart: dict[str, Any] | None = None,
) -> str:
    """Bedrock 호출 없이 규칙 기반으로 의도만 예측 (스키마 검색 스킵 판단용)."""
    ruled = _rule_based_analysis(
        message,
        pending_aggregate=pending_aggregate,
        pending_chart=pending_chart,
    )
    if isinstance(ruled, dict):
        return (ruled.get("intent") or "").strip()
    return ""


def analyze_question(
    message: str,
    *,
    bedrock_ask=None,
    pending_aggregate: dict[str, Any] | None = None,
    pending_chart: dict[str, Any] | None = None,
    schema_context: str | None = None,
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
    user_content = message
    if schema_context:
        user_content = f"{message}\n\n[스키마 검색 힌트]\n{schema_context}"
    try:
        raw = bedrock_ask(
            ANALYZE_SYSTEM_PROMPT,
            [{"role": "user", "content": user_content}],
            512,
        )
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(raw[start : end + 1])
            if _wants_external_insight(message):
                analysis = _resolve_analysis_agent_intent(
                    message,
                    pending_chart,
                    reason=parsed.get("reason") or "직전 집계 결과 분석 요청",
                )
                return analysis
            if parsed.get("intent") == "inst1_extract":
                hinted = _tables_from_hints(message)
                tables = parsed.get("tables") or hinted or list(INST1_TABLE_ORDER[:2])
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
            if parsed.get("intent") == "inst1_external_insight":
                ruled_external = _resolve_analysis_agent_intent(
                    message,
                    pending_chart,
                    reason=parsed.get("reason") or "직전 집계 결과 분석 요청",
                )
                return ruled_external
            if parsed.get("intent") not in (
                "inst1_table_prompt",
                "inst1_aggregate_prompt",
                "inst1_column_desc",
                "inst1_data_summary",
                "inst1_chart",
                "inst1_external_insight",
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


def _find_non_overlapping_column_mentions(
    msg: str,
    *,
    skip_cols: set[str] | None = None,
    used_spans: list[tuple[int, int]] | None = None,
) -> list[str]:
    """메시지에서 겹치지 않게 컬럼명을 찾는다 (긴 이름 우선).

    '최근5년최고여신잔액'만 있을 때 '여신잔액'이 중복 매칭되지 않고,
    '최근5년최고여신잔액, 여신잔액'처럼 의도적으로 둘 다 적었을 때는 각각 인식한다.
    """
    skip_cols = skip_cols or set()
    spans = list(used_spans or [])
    found: list[tuple[int, str]] = []
    seen: set[str] = set(skip_cols)

    for hint, col in _column_match_candidates():
        if col in seen:
            continue
        pos = 0
        while pos <= len(msg) - len(hint):
            idx = msg.find(hint, pos)
            if idx < 0:
                break
            end = idx + len(hint)
            if _match_inside_table_name(msg, idx, hint):
                pos = idx + 1
                continue
            if any(not (end <= u0 or idx >= u1) for u0, u1 in spans):
                pos = idx + 1
                continue
            spans.append((idx, end))
            found.append((idx, col))
            seen.add(col)
            break

    return [col for _, col in sorted(found, key=lambda item: item[0])]


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

    used_spans: list[tuple[int, int]] = []
    for col in ordered:
        pos = msg.find(col)
        if pos >= 0:
            used_spans.append((pos, pos + len(col)))

    for col in _find_non_overlapping_column_mentions(
        msg, skip_cols=seen, used_spans=used_spans
    ):
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
        for table in INST1_TABLE_ORDER:
            if result_key.startswith(table) and analysis.get("aggregate_table") == table:
                return group_by
        if "별고객수" in result_key:
            return group_by

    if TSHDE0ZCD_TABLE in result_key:
        return INST1_TABLE_COLUMNS.get(TSHDE0ZCD_TABLE, ())
    for table in reversed(INST1_TABLE_ORDER):
        if table in result_key:
            return INST1_TABLE_COLUMNS.get(table, ())
    return INST1_TABLE_COLUMNS.get(TSHDEOA01_TABLE, ())


def _reorder_rows(rows: list[dict[str, Any]], column_order: list[str]) -> list[dict[str, Any]]:
    return [{col: row[col] for col in column_order if col in row} for row in rows]


def apply_column_order_to_results(
    result: dict[str, list[dict[str, Any]]],
    analysis: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[str]]]:
    query_type = analysis.get("query_type") or "select"
    group_by = _normalize_group_by(analysis.get("group_by"))
    aggregate_measures = analysis.get("aggregate_measures")
    if query_type in ("aggregate", "join_aggregate") and group_by:
        measure_cols = list(aggregate_measures or [])
        mentioned = group_by + measure_cols
    elif query_type == "select":
        mentioned = list(analysis.get("mentioned_columns") or [])
    else:
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
        ordered[key] = [mask_row_for_display(r) for r in _reorder_rows(rows, col_order)]
        column_orders[key] = col_order
    return ordered, column_orders


_TRAILING_MEASURE_ORDER = (VIRTUAL_AGGREGATE_MEASURE, DELTA_COLUMN)


def _order_result_columns(cols: list[str]) -> list[str]:
    trailing = [c for c in _TRAILING_MEASURE_ORDER if c in cols]
    if not trailing:
        return cols
    head = [c for c in cols if c not in trailing]
    return head + trailing


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


def _recent_months_filter(
    *,
    logical_table: str,
    group_company: str,
    has_grp: bool,
    recent_months: int,
    for_display: bool,
    column_ref: str = '"기준년월"',
) -> tuple[str, list[Any]]:
    """최신 N개월(기준년월) IN-서브쿼리 조건 생성."""
    n = int(recent_months)
    fqn = TABLE_SQL_FQN[logical_table]
    params: list[Any] = []
    if has_grp:
        if for_display:
            grp = f"WHERE trim(\"그룹회사코드\") = '{group_company}' "
        else:
            grp = 'WHERE trim("그룹회사코드") = %s '
            params.append(group_company)
    else:
        grp = ""
    sub = (
        f'{column_ref} IN (SELECT DISTINCT "기준년월" FROM {fqn} '
        f'{grp}ORDER BY "기준년월" DESC LIMIT {n})'
    )
    return sub, params


def _base_where_parts(
    *,
    table: str,
    month: str,
    group_company: str,
    customer_id: str | None,
    for_display: bool,
    group_by: list[str] | None = None,
    recent_months: int = 0,
) -> tuple[list[str], list[Any]]:
    filter_month = _should_filter_month_in_where(month, group_by)
    has_grp = inst1_table_has_group_company(table)
    recent_n = int(recent_months or 0)
    if for_display:
        where_parts: list[str] = []
        if recent_n > 0:
            sub, _ = _recent_months_filter(
                logical_table=table,
                group_company=group_company,
                has_grp=has_grp,
                recent_months=recent_n,
                for_display=True,
            )
            where_parts.append(sub)
        elif filter_month:
            where_parts.append(f'"기준년월" = \'{month}\'')
        if has_grp:
            where_parts.append(f'trim("그룹회사코드") = \'{group_company}\'')
        if customer_id:
            where_parts.append(f'trim("그룹고객식별자") = \'{customer_id}\'')
        return where_parts, []

    where_parts: list[str] = []
    params: list[Any] = []
    if recent_n > 0:
        sub, sub_params = _recent_months_filter(
            logical_table=table,
            group_company=group_company,
            has_grp=has_grp,
            recent_months=recent_n,
            for_display=False,
        )
        where_parts.append(sub)
        params.extend(sub_params)
    elif filter_month:
        where_parts.append('"기준년월" = %s')
        params.append(month)
    if has_grp:
        where_parts.append('trim("그룹회사코드") = %s')
        params.append(group_company)
    if customer_id:
        where_parts.append('trim("그룹고객식별자") = %s')
        params.append(customer_id)
    return where_parts, params


def _resolve_aggregate_measures(
    aggregate_measures: list[str] | None,
    *,
    explicit: bool = False,
) -> list[str]:
    if aggregate_measures is not None:
        measures = [m for m in aggregate_measures if m]
        if not measures:
            raise ValueError("집계 항목을 하나 이상 선택해 주세요.")
        return measures
    if explicit:
        raise ValueError("집계 항목을 하나 이상 선택해 주세요.")
    return [VIRTUAL_AGGREGATE_MEASURE]


def _sql_agg_measure_expr(col: str, func_sql: str) -> str:
    if col == VIRTUAL_AGGREGATE_MEASURE:
        return f'COUNT("그룹고객식별자") AS "{VIRTUAL_AGGREGATE_MEASURE}"'
    return f'{func_sql}("{col}") AS "{col}"'


def _build_agg_select_exprs(
    measures: list[str],
    measure_funcs: dict[str, str],
    *,
    default_func: str = "SUM",
) -> list[str]:
    exprs: list[str] = []
    for col in measures:
        func_sql = _normalize_aggregate_func(
            measure_funcs.get(col) or default_func
        )
        exprs.append(_sql_agg_measure_expr(col, func_sql))
    return exprs


def build_aggregate_query(
    schema: str,
    table: str,
    *,
    month: str,
    group_company: str,
    customer_id: str | None,
    group_by: list[str],
    logical_table: str,
    aggregate_measures: list[str] | None = None,
    aggregate_func: str = "SUM",
    aggregate_measure_funcs: dict[str, str] | None = None,
    explicit_measures: bool = False,
    recent_months: int = 0,
) -> str:
    """집계용 GROUP BY + 집계 함수 SELECT 쿼리 문자열 생성 (표시용)."""
    cols = _normalize_group_by(group_by)
    if not cols:
        raise ValueError("집계 기준 컬럼이 없습니다.")
    measures = _resolve_aggregate_measures(
        aggregate_measures,
        explicit=explicit_measures,
    )
    measure_funcs = dict(aggregate_measure_funcs or {})
    if not measure_funcs:
        func_sql = _normalize_aggregate_func(aggregate_func)
        measure_funcs = {col: func_sql for col in measures}
    where_parts, _ = _base_where_parts(
        table=logical_table,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=True,
        group_by=cols,
        recent_months=recent_months,
    )
    select_cols = ",\n       ".join(
        f'{_sql_group_col(logical_table, col)} AS "{col}"' for col in cols
    )
    agg_cols = ",\n       ".join(
        _build_agg_select_exprs(measures, measure_funcs)
    )
    group_expr = ", ".join(_sql_group_col(logical_table, col) for col in cols)
    order_expr = ", ".join(f'"{col}"' for col in cols)
    where_clause = f'WHERE {" AND ".join(where_parts)}\n' if where_parts else ""
    return (
        f"SELECT {select_cols},\n"
        f"       {agg_cols}\n"
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
    logical_table: str | None = None,
    recent_months: int = 0,
) -> str:
    """추출 조건에 맞는 SELECT 쿼리 문자열 생성 (표시용)."""
    logical = logical_table or table
    where_parts, _ = _base_where_parts(
        table=logical,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=True,
        recent_months=recent_months,
    )
    where_clause = f'WHERE {" AND ".join(where_parts)}\n' if where_parts else ""
    return (
        f'SELECT *\n'
        f'FROM "{schema}"."{table}"\n'
        f'{where_clause}'
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
    logical_table: str | None = None,
    recent_months: int = 0,
) -> tuple[list[dict[str, Any]], str]:
    logical = logical_table or table
    display_sql = build_select_query(
        schema,
        table,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        limit=limit,
        logical_table=logical,
        recent_months=recent_months,
    )
    where, params = _base_where_parts(
        table=logical,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=False,
        recent_months=recent_months,
    )
    where_sql = f"WHERE {' AND '.join(where)} " if where else ""
    exec_sql = (
        f'SELECT * FROM "{schema}"."{table}" '
        f"{where_sql}"
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
    aggregate_measures: list[str] | None = None,
    aggregate_func: str = "SUM",
    aggregate_measure_funcs: dict[str, str] | None = None,
    explicit_measures: bool = False,
    recent_months: int = 0,
) -> tuple[list[dict[str, Any]], str]:
    cols = _normalize_group_by(group_by)
    measures = _resolve_aggregate_measures(
        aggregate_measures,
        explicit=explicit_measures,
    )
    measure_funcs = dict(aggregate_measure_funcs or {})
    if not measure_funcs:
        func_sql = _normalize_aggregate_func(aggregate_func)
        measure_funcs = {col: func_sql for col in measures}
    display_sql = build_aggregate_query(
        schema,
        table,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        group_by=cols,
        logical_table=logical_table,
        aggregate_measures=measures,
        aggregate_measure_funcs=measure_funcs,
        explicit_measures=explicit_measures,
        recent_months=recent_months,
    )
    where, params = _base_where_parts(
        table=logical_table,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=False,
        group_by=cols,
        recent_months=recent_months,
    )
    select_cols = ", ".join(
        f'{_sql_group_col(logical_table, col)} AS "{col}"' for col in cols
    )
    agg_cols = ", ".join(_build_agg_select_exprs(measures, measure_funcs))
    group_expr = ", ".join(_sql_group_col(logical_table, col) for col in cols)
    order_expr = ", ".join(f'"{col}"' for col in cols)
    where_sql = f"WHERE {' AND '.join(where)} " if where else ""
    exec_sql = (
        f"SELECT {select_cols}, {agg_cols} "
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


def _join_on_sql(table_a: str, alias_a: str, table_b: str, alias_b: str) -> str:
    parts: list[str] = []
    for key in inst1_join_keys_between(table_a, table_b):
        if key in ("그룹회사코드", "그룹고객식별자"):
            parts.append(f'trim({alias_a}."{key}") = trim({alias_b}."{key}")')
        else:
            parts.append(f'{alias_a}."{key}" = {alias_b}."{key}"')
    return " AND ".join(parts)


def _join_where_sql(
    primary_alias: str,
    *,
    primary_table: str,
    month: str,
    group_company: str,
    customer_id: str | None,
    for_display: bool,
    group_by_columns: list[str] | None = None,
    recent_months: int = 0,
) -> tuple[list[str], list[Any]]:
    filter_month = _should_filter_month_in_where(month, group_by_columns)
    has_grp = inst1_table_has_group_company(primary_table)
    recent_n = int(recent_months or 0)
    if for_display:
        where_parts: list[str] = []
        if recent_n > 0:
            sub, _ = _recent_months_filter(
                logical_table=primary_table,
                group_company=group_company,
                has_grp=has_grp,
                recent_months=recent_n,
                for_display=True,
                column_ref=f'{primary_alias}."기준년월"',
            )
            where_parts.append(sub)
        elif filter_month:
            where_parts.append(f'{primary_alias}."기준년월" = \'{month}\'')
        if has_grp:
            where_parts.append(f'trim({primary_alias}."그룹회사코드") = \'{group_company}\'')
        if customer_id:
            where_parts.append(
                f'trim({primary_alias}."그룹고객식별자") = \'{customer_id}\''
            )
        return where_parts, []

    where_parts: list[str] = []
    params: list[Any] = []
    if recent_n > 0:
        sub, sub_params = _recent_months_filter(
            logical_table=primary_table,
            group_company=group_company,
            has_grp=has_grp,
            recent_months=recent_n,
            for_display=False,
            column_ref=f'{primary_alias}."기준년월"',
        )
        where_parts.append(sub)
        params.extend(sub_params)
    elif filter_month:
        where_parts.append(f'{primary_alias}."기준년월" = %s')
        params.append(month)
    if has_grp:
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
    recent_months: int = 0,
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
        primary_table=primary,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=True,
        group_by_columns=group_cols,
        recent_months=recent_months,
    )

    from_sql = f"FROM {TABLE_SQL_FQN[ordered[0]]} {primary_alias}"
    for table in ordered[1:]:
        alias = INST1_TABLE_SQL_ALIAS[table]
        from_sql += (
            f'\nINNER JOIN {TABLE_SQL_FQN[table]} {alias} '
            f"ON {_join_on_sql(primary, primary_alias, table, alias)}"
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
    recent_months: int = 0,
) -> tuple[list[dict[str, Any]], str]:
    display_sql = build_join_aggregate_query(
        join_tables,
        group_by_details,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        recent_months=recent_months,
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
        primary_table=primary,
        month=month,
        group_company=group_company,
        customer_id=customer_id,
        for_display=False,
        group_by_columns=group_cols,
        recent_months=recent_months,
    )

    from_sql = f"FROM {TABLE_SQL_FQN[ordered[0]]} {primary_alias}"
    for table in ordered[1:]:
        alias = INST1_TABLE_SQL_ALIAS[table]
        from_sql += (
            f" INNER JOIN {TABLE_SQL_FQN[table]} {alias} "
            f"ON {_join_on_sql(primary, primary_alias, table, alias)}"
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


def _add_month_over_month_delta(
    rows: list[dict[str, Any]],
    group_cols: list[str],
    *,
    measure: str = VIRTUAL_AGGREGATE_MEASURE,
) -> list[dict[str, Any]]:
    """집계 결과에 전월대비 증감(measure 기준) 컬럼을 추가.

    기준년월이 집계 축에 있어야 하며, 같은 (기준년월 제외) 그룹 키 내에서
    직전(가장 가까운 이전) 기준년월 대비 증감을 계산한다.
    가장 이른 달은 비교 대상이 없어 None.
    """
    if not rows or "기준년월" not in group_cols or measure not in rows[0]:
        return rows
    dims = [c for c in group_cols if c != "기준년월"]
    months = sorted({str(r.get("기준년월")) for r in rows})
    prev_of = {m: (months[i - 1] if i > 0 else None) for i, m in enumerate(months)}
    value_map: dict[tuple[str, tuple], Any] = {}
    for r in rows:
        key = (str(r.get("기준년월")), tuple(str(r.get(d)) for d in dims))
        value_map[key] = r.get(measure)
    for r in rows:
        cur_month = str(r.get("기준년월"))
        dim_key = tuple(str(r.get(d)) for d in dims)
        prev_month = prev_of.get(cur_month)
        cur_val = r.get(measure)
        delta: Any = None
        if prev_month is not None:
            prev_val = value_map.get((prev_month, dim_key))
            if isinstance(prev_val, (int, float)) and isinstance(cur_val, (int, float)):
                delta = cur_val - prev_val
        r[DELTA_COLUMN] = delta
    return rows


def extract_inst1_data(analysis: dict[str, Any]) -> dict[str, Any]:
    """데이터 추출 전용 에이전트."""
    month = (analysis.get("month") or "").strip()
    recent_months = int(analysis.get("recent_months") or 0)
    want_delta = bool(analysis.get("delta"))
    group = (analysis.get("group_company") or DEFAULT_GROUP).strip()
    customer_id = analysis.get("customer_id")
    tables = list(analysis.get("tables") or ["TSHDEOA01", "TSHDEOA02"])
    if analysis.get("unlimited_rows"):
        limit: int | None = None
    else:
        limit = int(analysis.get("limit") or MAX_ROWS)
    zcd_only = tables == [TSHDE0ZCD_TABLE] or (
        TSHDE0ZCD_TABLE in tables
        and not any(t in tables for t in INST1_DATA_TABLES)
    )
    query_type = analysis.get("query_type") or "select"
    group_by = _normalize_group_by(analysis.get("group_by"))
    group_by_details = list(analysis.get("group_by_details") or [])
    aggregate_table = analysis.get("aggregate_table")
    aggregate_measures = analysis.get("aggregate_measures")
    aggregate_func = analysis.get("aggregate_func") or "SUM"
    aggregate_measure_funcs = dict(analysis.get("aggregate_measure_funcs") or {})
    explicit_measures = aggregate_measures is not None
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
                recent_months=recent_months,
            )
            if want_delta:
                rows = _add_month_over_month_delta(
                    rows, [d["column"] for d in group_by_details]
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
                recent_months=recent_months,
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

    for logical_table, schema, table_name in _INST1_EXTRACT_SPECS:
        if logical_table not in tables:
            continue
        result_key = _result_key(logical_table, analysis)
        try:
            if query_type == "aggregate" and group_by and aggregate_table == logical_table:
                rows, sql = _fetch_aggregate(
                    schema,
                    table_name,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    group_by=group_by,
                    logical_table=logical_table,
                    aggregate_measures=aggregate_measures,
                    aggregate_func=aggregate_func,
                    aggregate_measure_funcs=aggregate_measure_funcs,
                    explicit_measures=explicit_measures,
                    recent_months=recent_months,
                )
                if want_delta:
                    rows = _add_month_over_month_delta(rows, group_by)
            else:
                rows, sql = _fetch_table(
                    schema,
                    table_name,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    limit=limit,
                    logical_table=logical_table,
                    recent_months=recent_months,
                )
                if query_type != "aggregate":
                    result_key = logical_table
            result[result_key] = rows
            queries[result_key] = sql
        except Exception as e:
            errors.append(f"{logical_table}: {e}")
            if query_type == "aggregate" and group_by and aggregate_table == logical_table:
                queries[result_key] = build_aggregate_query(
                    schema,
                    table_name,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    group_by=group_by,
                    logical_table=logical_table,
                    aggregate_measures=aggregate_measures,
                    aggregate_func=aggregate_func,
                    aggregate_measure_funcs=aggregate_measure_funcs,
                    explicit_measures=explicit_measures,
                    recent_months=recent_months,
                )
            else:
                queries[logical_table] = build_select_query(
                    schema,
                    table_name,
                    month=month,
                    group_company=group,
                    customer_id=customer_id,
                    limit=limit,
                    logical_table=logical_table,
                    recent_months=recent_months,
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
        masked = mask_row_for_display(row)
        vals = []
        for c in cols:
            if c == "…":
                vals.append("…")
            else:
                v = masked.get(c, "")
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
        parts.append(f"- 그룹고객식별자: {mask_customer_id(customer_id)}")
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

    if extract_result.get("total_rows", 0) > 0:
        parts.append("")
        qt = analysis.get("query_type") or ""
        if qt in ("aggregate", "join_aggregate"):
            parts.append("아래 엑셀 저장 버튼으로 조회 결과를 저장할 수 있습니다.")
            parts.append(
                f"「{AGGREGATE_CHART_FOLLOW_UP}」 또는 「{EXTERNAL_INSIGHT_FOLLOW_UP}」 "
                "추천 질문으로 차트·분석을 이어갈 수 있습니다."
            )
        else:
            parts.append("아래 엑셀 저장 버튼으로 조회 결과를 저장할 수 있습니다.")

    parts.append("")
    table_notes = ", ".join(
        f"{INST1_TABLE_KOREAN_NAMES[t]}={t}" for t in INST1_TABLE_ORDER
    )
    parts.append(
        f"※ {table_notes}. "
        "코드 컬럼은 TSHDE0ZCD 인스턴스내용으로 표시됩니다."
    )
    return "\n".join(parts)
