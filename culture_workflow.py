"""
Culture LangGraph 워크플로우
  Fetch → Summarize → Reply
  State: month → raw_data → summary → reply
"""

from __future__ import annotations

import json
import os
import re
from decimal import Decimal
from typing import Any, Literal, TypedDict

import boto3
import psycopg2
from botocore.exceptions import ClientError
from langgraph.graph import END, START, StateGraph

from supabase.table_config import TABLE_NAME, TABLE_QUERY_KEYWORDS

# Claude Sonnet 최신 (Bedrock) — BEDROCK_MODEL_ID 로 덮어쓸 수 있음
MODEL_ID = "anthropic.claude-sonnet-4-5-20250929-v1:0"
MODEL_ID_FALLBACK = "anthropic.claude-sonnet-4-20250514-v1:0"
US_CRIS_SONNET_45 = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
# foundation-model 직접 호출용 (us-east-1 우선)
BEDROCK_REGIONAL_FALLBACK_REGIONS = (
    "us-east-1",
    "ap-northeast-1",
    "ap-northeast-2",
)
# apac.* 모델용 리전 순서
BEDROCK_APAC_FALLBACK_REGIONS = (
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-southeast-1",
)
BEDROCK_US_FALLBACK_REGIONS = ("us-east-1", "us-west-2")
# 모델/리전 불일치 시 다음 시도로 넘어감
_BEDROCK_RETRY_ERROR_CODES = frozenset(
    {
        "AccessDeniedException",
        "UnauthorizedException",
        "ValidationException",
        "ResourceNotFoundException",
    }
)

SUMMARY_SYSTEM_PROMPT = """당신은 금융·계열사 고객지표 데이터 분석가입니다.
주어진 JSON 데이터만 근거로 한국어로 요약·분석하세요.
반드시 다음 세 가지 관점을 포함하세요.
1. 수치: 주요 지표의 규모·증감
2. 비중: 고객수비율·구성 비율
3. 특이점: 눈에 띄는 등급·그룹별 이상 패턴
- 계열사그룹구분(KBO, KCO 등)별로 구분해 설명하세요.
- NULL은 데이터 없음으로 해석하세요.
- 핵심 인사이트 3~6문장 + 필요 시 짧은 bullet로 정리하세요."""

GENERAL_SYSTEM_PROMPT = """당신은 Culture 앱의 한국어 AI 어시스턴트입니다.
사용자와 자연스럽게 대화하세요."""

GUIDE_MISSING_INPUT = "테이블명, 기준년월을 포함해 주세요."


class CultureState(TypedDict, total=False):
    """워크플로우 공유 State."""

    user_message: str
    table_name: str
    month: str
    raw_data: list[dict[str, Any]]
    summary: str
    reply: str
    chart_specs: list[dict[str, Any]]
    pdf_url: str
    notice: str
    error: str
    is_summary_request: bool
    needs_input: bool
    history: list[dict[str, str]]


_db_url_cache: str | None = None
_graph_executor = None
_bedrock_clients: dict[str, Any] = {}


def get_model_id() -> str:
    return os.environ.get("BEDROCK_MODEL_ID", "").strip() or MODEL_ID


def bedrock_models_to_try() -> list[str]:
    """Sonnet 4.5 → Sonnet 4 → US CRIS 프로필."""
    primary = get_model_id()
    out: list[str] = []
    seen: set[str] = set()
    for m in (
        primary,
        os.environ.get("BEDROCK_MODEL_ID_FALLBACK", "").strip() or MODEL_ID_FALLBACK,
        US_CRIS_SONNET_45,
    ):
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def bedrock_regions_for_model(model_id: str) -> list[str]:
    """모델 ID에 맞는 Runtime 리전 순서."""
    explicit = os.environ.get("AWS_BEDROCK_REGION", "").strip()
    if explicit:
        return [explicit]
    if model_id.startswith(("us.", "global.", "eu.")):
        return ["us-east-1"]
    if model_id.startswith("apac."):
        return list(BEDROCK_APAC_FALLBACK_REGIONS)
    env_default = os.environ.get("AWS_REGION", "").strip()
    regions: list[str] = list(BEDROCK_REGIONAL_FALLBACK_REGIONS)
    if env_default and env_default not in regions:
        regions.insert(0, env_default)
    for r in BEDROCK_US_FALLBACK_REGIONS:
        if r not in regions:
            regions.append(r)
    return regions


def bedrock_region() -> str:
    """헬스/오류 메시지용 대표 리전."""
    explicit = os.environ.get("AWS_BEDROCK_REGION", "").strip()
    if explicit:
        return explicit
    if get_model_id().startswith("apac."):
        return BEDROCK_APAC_FALLBACK_REGIONS[0]
    return os.environ.get("AWS_REGION", "").strip() or "ap-northeast-2"


def bedrock_regions_to_try() -> list[str]:
    """(하위 호환) 첫 모델 기준 리전 목록."""
    primary_model = bedrock_models_to_try()[0]
    return bedrock_regions_for_model(primary_model)


def get_db_url() -> str:
    global _db_url_cache
    if _db_url_cache is not None:
        return _db_url_cache
    raw = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not raw:
        raise RuntimeError("`SUPABASE_DB_URL` 환경 변수를 설정해야 합니다.")
    if "sslmode=" not in raw:
        raw += ("&" if "?" in raw else "?") + "sslmode=require"
    _db_url_cache = raw
    return _db_url_cache


def get_conn():
    return psycopg2.connect(get_db_url(), connect_timeout=15)


def _get_aws_session_token() -> str:
    """AWS 표준: AWS_SESSION_TOKEN. Vercel 오타 대응: AWS_SECURITY_TOKEN."""
    for name in ("AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _bedrock_env_credentials() -> dict[str, str] | None:
    """Vercel STS/MFA: ACCESS_KEY + SECRET + SESSION_TOKEN."""
    key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    if not key or not secret:
        return None
    creds: dict[str, str] = {
        "aws_access_key_id": key,
        "aws_secret_access_key": secret,
    }
    token = _get_aws_session_token()
    if token:
        creds["aws_session_token"] = token
    return creds


def aws_session_token_configured() -> bool:
    return bool(_get_aws_session_token())


def aws_session_token_env_name() -> str | None:
    for name in ("AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"):
        if os.environ.get(name, "").strip():
            return name
    return None


def _create_bedrock_client(region: str):
    creds = _bedrock_env_credentials()
    if creds:
        return boto3.client("bedrock-runtime", region_name=region, **creds)
    profile = os.environ.get("AWS_PROFILE", "default")
    return boto3.Session(profile_name=profile, region_name=region).client(
        "bedrock-runtime"
    )


def get_bedrock_runtime(region: str | None = None):
    """Vercel: 환경 변수 자격 증명. 로컬: AWS_PROFILE 또는 환경 변수."""
    region = region or bedrock_region()
    if region not in _bedrock_clients:
        _bedrock_clients[region] = _create_bedrock_client(region)
    return _bedrock_clients[region]


def aws_credentials_configured() -> bool:
    if _bedrock_env_credentials() is not None:
        return True
    if os.environ.get("VERCEL"):
        return False
    try:
        return boto3.Session().get_credentials() is not None
    except Exception:
        return False


def _unwrap_client_error(exc: BaseException) -> ClientError | None:
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, ClientError):
            return cur
        cur = cur.__cause__ or cur.__context__  # type: ignore[assignment]
    return None


def format_aws_error(
    exc: Exception,
    *,
    attempt_model: str | None = None,
    attempt_region: str | None = None,
) -> str:
    ce = exc if isinstance(exc, ClientError) else _unwrap_client_error(exc)
    model = attempt_model or get_model_id()
    region = attempt_region or bedrock_region()
    if isinstance(ce, ClientError):
        err = ce.response.get("Error", {}) or {}
        code = err.get("Code", type(ce).__name__)
        msg = err.get("Message", str(ce))
        if code in ("ExpiredTokenException",) or "ExpiredToken" in code:
            return (
                "AWS 임시 보안 토큰이 만료되었습니다. "
                "Vercel 환경 변수 AWS_ACCESS_KEY_ID·AWS_SECRET_ACCESS_KEY·"
                "AWS_SESSION_TOKEN(또는 AWS_SECURITY_TOKEN) 을 한 세트로 갱신한 뒤 Redeploy 하세요."
            )
        if code in ("UnrecognizedClientException",) or (
            "security token" in msg.lower() and "invalid" in msg.lower()
        ):
            token_env = aws_session_token_env_name() or "(미설정)"
            return (
                f"AWS 자격 증명이 유효하지 않습니다 ({code}). "
                f"리전={region}. "
                "ACCESS_KEY·SECRET·SESSION_TOKEN 은 같은 STS/MFA 세션에서 "
                "동시에 발급한 값이어야 합니다. "
                f"세션 토큰 환경 변수: {token_env} "
                "(표준 이름은 AWS_SESSION_TOKEN, AWS_SECURITY_TOKEN 도 읽습니다). "
                "만료·오타·키 불일치면 Vercel에서 세 값을 모두 갱신 후 Redeploy. "
                f"AWS 메시지: {msg}"
            )
        if code in (
            "AccessDeniedException",
            "UnauthorizedException",
            "AccessDenied",
        ):
            if "explicit deny" in msg.lower():
                return (
                    f"Bedrock IAM 거부 ({code}): identity 정책에 "
                    "Effect: Deny 가 있어 InvokeModel 이 막혔습니다. "
                    f"마지막 시도: 리전={region}, 모델ID={model}. "
                    "AWS IAM → 사용자 → 권한에서 bedrock / inference-profile Deny 를 확인·수정한 뒤 Redeploy. "
                    f"AWS 메시지: {msg}"
                )
            return (
                f"Bedrock 호출이 거부되었습니다 ({code}). "
                f"마지막 시도: 리전={region}, 모델ID={model}. "
                "① IAM: bedrock:InvokeModel "
                "② Resource: foundation-model 및 (apac 사용 시) inference-profile ARNs "
                "③ Bedrock 콘솔 → Model access 에서 사용 모델 승인. "
                f"AWS 메시지: {msg}"
            )
        if code == "ResourceNotFoundException" and (
            "end of its life" in msg.lower() or "eol" in msg.lower()
        ):
            return (
                f"Bedrock 모델이 해당 리전에서 종료(EOL)되었거나 없습니다 ({code}). "
                f"마지막 시도: 리전={region}, 모델ID={model}. "
                "Bedrock 콘솔에서 Claude Sonnet 4.5 모델 액세스를 확인하세요. "
                f"AWS 메시지: {msg}"
            )
        return f"Bedrock 오류 ({code}, 리전={region}): {msg}"
    name = type(exc).__name__
    msg = str(exc)
    if "ExpiredToken" in name or "ExpiredToken" in msg:
        return (
            "AWS 임시 보안 토큰이 만료되었습니다. "
            "MFA/세션 갱신 후 Culture 앱을 재시작하세요."
        )
    if "AccessDenied" in name or "AccessDenied" in msg:
        return (
            f"Bedrock 호출이 거부되었습니다. 마지막 시도: 리전={region}, 모델ID={model}. "
            "IAM bedrock:InvokeModel·모델 액세스·리전을 확인하세요. "
            f"원문: {msg}"
        )
    return f"{name}: {msg}"


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)


def format_yyyymm(yyyymm: str) -> str:
    if len(yyyymm) == 6 and yyyymm.isdigit():
        return f"{yyyymm[:4]}년 {int(yyyymm[4:6])}월"
    return yyyymm


def parse_month(text: str) -> str | None:
    m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월", text)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}"
    m = re.search(r"\b(20\d{4})\b", text)
    if m:
        return m.group(1)
    return None


def has_summary_intent(text: str) -> bool:
    return any(k in text for k in ("요약", "정리", "분석", "리포트", "summary"))


def has_table_reference(text: str, api_table: str | None = None) -> bool:
    if api_table and api_table.strip():
        return True
    if TABLE_NAME in text:
        return True
    return any(kw in text for kw in TABLE_QUERY_KEYWORDS)


def is_summary_request(text: str, api_table: str | None = None) -> bool:
    """요약 의도이며 테이블명·기준년월이 모두 있는 경우."""
    return (
        has_summary_intent(text)
        and has_table_reference(text, api_table)
        and bool(parse_month(text))
    )


def _numeric(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def build_chart_specs(
    rows: list[dict[str, Any]],
    *,
    month: str,
    table: str,
) -> list[dict[str, Any]]:
    """요약 응답용 Chart.js 막대그래프 스펙 (고객수비율·고객수)."""
    if not rows:
        return []

    sorted_rows = sorted(
        rows,
        key=lambda r: (
            str(r.get("계열사그룹구분") or ""),
            str(r.get("계열사등급구분내용") or ""),
        ),
    )
    labels = [
        f"{r.get('계열사그룹구분')}-등급{r.get('계열사등급구분내용')}"
        for r in sorted_rows
    ]
    ratio_data = [_numeric(r.get("고객수비율")) for r in sorted_rows]
    count_data = [_numeric(r.get("고객수")) for r in sorted_rows]
    month_label = format_yyyymm(month)

    return [
        {
            "type": "bar",
            "title": f"{table} · 고객수비율 (%) — {month_label}",
            "labels": labels,
            "datasets": [
                {
                    "label": "고객수비율 (%)",
                    "data": ratio_data,
                    "backgroundColor": "rgba(124, 58, 237, 0.78)",
                    "borderColor": "rgba(109, 40, 217, 1)",
                    "borderWidth": 1,
                }
            ],
        },
        {
            "type": "bar",
            "title": f"{table} · 고객수 — {month_label}",
            "labels": labels,
            "datasets": [
                {
                    "label": "고객수",
                    "data": count_data,
                    "backgroundColor": "rgba(16, 185, 129, 0.78)",
                    "borderColor": "rgba(5, 150, 105, 1)",
                    "borderWidth": 1,
                }
            ],
        },
    ]


def fetch_table_rows(table_name: str, yyyymm: str) -> list[dict[str, Any]]:
    sql = f"""
        SELECT
          "그룹회사코드", "기준년월", "계열사그룹구분", "계열사등급구분내용",
          "고객수", "고객수비율", "고객수증감비율",
          "합계계열사등급환산점수", "합계계열사등급환산점수증감비율",
          "합계계열사자체점수", "합계계열사자체점수증감비율",
          "최소계열사등급환산점수", "최대계열사등급환산점수",
          "최소계열사자체점수", "최대계열사자체점수",
          "시스템최초등록일시", "시스템최종처리일시", "시스템최종사용자번호"
        FROM public."{table_name}"
        WHERE "기준년월" = %s
        ORDER BY "계열사그룹구분", "계열사등급구분내용"
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (yyyymm,))
            cols = [d[0] for d in cur.description]
            return [
                {c: (float(v) if isinstance(v, Decimal) else v) for c, v in zip(cols, row)}
                for row in cur.fetchall()
            ]


def ask_bedrock(system: str, messages: list[dict], max_tokens: int = 2048) -> str:
    if not aws_credentials_configured():
        cred_hint = (
            "Vercel에 AWS_ACCESS_KEY_ID·AWS_SECRET_ACCESS_KEY·"
            "AWS_SESSION_TOKEN(임시 자격 증명, AWS_SECURITY_TOKEN 이름도 가능)을 설정하세요."
            if os.environ.get("VERCEL")
            else "AWS_ACCESS_KEY_ID·AWS_SECRET_ACCESS_KEY를 두거나, "
            "로컬에서는 ~/.aws/credentials 의 프로필(AWS_PROFILE)을 사용하세요."
        )
        raise RuntimeError(f"AWS 자격 증명이 없습니다. {cred_hint}")
    key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    if key.startswith("ASIA") and not _get_aws_session_token():
        raise RuntimeError(
            "임시 Access Key(ASIA…)에는 세션 토큰이 필요합니다. "
            "Vercel에 AWS_SESSION_TOKEN(또는 AWS_SECURITY_TOKEN)을 "
            "ACCESS_KEY·SECRET과 같은 세션에서 발급한 값으로 설정하세요."
        )
    bedrock_messages = [
        {"role": m["role"], "content": [{"type": "text", "text": m["content"]}]}
        for m in messages
    ]
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": system,
            "messages": bedrock_messages,
        }
    )
    last_error: Exception | None = None
    last_client: ClientError | None = None
    last_model_attempt = ""
    last_region_attempt = ""
    for model_id in bedrock_models_to_try():
        for region in bedrock_regions_for_model(model_id):
            last_model_attempt = model_id
            last_region_attempt = region
            try:
                response = get_bedrock_runtime(region).invoke_model(
                    modelId=model_id,
                    body=body,
                    accept="application/json",
                    contentType="application/json",
                )
                response_body = json.loads(response["body"].read())
                return response_body["content"][0]["text"].strip()
            except ClientError as e:
                last_client = e
                last_error = e
                err_body = e.response.get("Error") or {}
                code = err_body.get("Code", "")
                aws_msg = err_body.get("Message", "")
                if (
                    "explicit deny" in aws_msg.lower()
                    and model_id.startswith("apac.")
                ):
                    break
                if code not in _BEDROCK_RETRY_ERROR_CODES:
                    raise RuntimeError(
                        format_aws_error(
                            e,
                            attempt_model=model_id,
                            attempt_region=region,
                        )
                    ) from e
            except Exception as e:
                last_error = e
                if "AccessDenied" not in type(e).__name__ and "AccessDenied" not in str(e):
                    raise
    if last_client is not None:
        raise RuntimeError(
            format_aws_error(
                last_client,
                attempt_model=last_model_attempt,
                attempt_region=last_region_attempt,
            )
        ) from last_client
    if last_error:
        raise RuntimeError(
            format_aws_error(
                last_error,
                attempt_model=last_model_attempt or get_model_id(),
                attempt_region=last_region_attempt or bedrock_region(),
            )
        ) from last_error
    raise RuntimeError("Bedrock 호출에 실패했습니다.")


# --- LangGraph nodes ---


def parse_node(state: CultureState) -> dict[str, Any]:
    msg = state.get("user_message", "")
    api_table = (state.get("table_name") or "").strip()
    month = parse_month(msg) or ""
    has_table = has_table_reference(msg, api_table or None)
    wants_summary = has_summary_intent(msg)

    if wants_summary and (not has_table or not month):
        return {
            "table_name": api_table or TABLE_NAME,
            "month": month,
            "is_summary_request": False,
            "needs_input": True,
            "summary": GUIDE_MISSING_INPUT,
            "reply": GUIDE_MISSING_INPUT,
        }

    return {
        "table_name": api_table or TABLE_NAME,
        "month": month,
        "is_summary_request": wants_summary and has_table and bool(month),
        "needs_input": False,
    }


def fetch_node(state: CultureState) -> dict[str, Any]:
    table = state.get("table_name") or TABLE_NAME
    month = state.get("month", "")
    if not month:
        return {"error": "기준년월을 찾을 수 없습니다. 예: 2026년 4월"}
    rows = fetch_table_rows(table, month)
    if not rows:
        return {
            "error": (
                f'{table} 테이블에 기준년월 {month}({format_yyyymm(month)}) '
                "데이터가 없습니다."
            )
        }
    return {"raw_data": rows}


def summarize_node(state: CultureState) -> dict[str, Any]:
    if state.get("error"):
        return {}
    rows = state.get("raw_data") or []
    month = state.get("month", "")
    table = state.get("table_name") or TABLE_NAME
    user_message = state.get("user_message", "")
    data_json = json.dumps(rows, ensure_ascii=False, indent=2, default=_json_default)
    prompt = (
        f"테이블: {table}\n"
        f"기준년월: {month} ({format_yyyymm(month)})\n"
        f"조회 건수: {len(rows)}건\n\n"
        f"데이터(JSON):\n{data_json}\n\n"
        f"사용자 요청: {user_message}\n\n"
        "위 데이터의 수치·비중·특이점을 한국어로 요약하세요."
    )
    summary = ask_bedrock(SUMMARY_SYSTEM_PROMPT, [{"role": "user", "content": prompt}], 2048)
    charts = build_chart_specs(rows, month=month, table=table)
    return {"summary": summary, "chart_specs": charts}


def export_pdf_node(state: CultureState) -> dict[str, Any]:
    """요약 응답을 PDF로 만들어 S3에 저장."""
    if state.get("error") or state.get("needs_input"):
        return {}
    if not state.get("is_summary_request"):
        return {}
    summary = (state.get("summary") or "").strip()
    if not summary:
        return {}
    try:
        from culture_pdf_s3 import upload_summary_pdf

        url = upload_summary_pdf(
            summary=summary,
            table=state.get("table_name") or TABLE_NAME,
            month=state.get("month") or "",
            chart_specs=state.get("chart_specs") or [],
        )
        return {"pdf_url": url}
    except Exception as e:
        prev = (state.get("notice") or "").strip()
        msg = f"PDF S3 저장 실패: {e}"
        return {"notice": f"{prev}\n{msg}".strip() if prev else msg}


def general_chat_node(state: CultureState) -> dict[str, Any]:
    history = list(state.get("history") or [])
    msg = state.get("user_message", "")
    if not history or history[-1].get("content") != msg:
        history.append({"role": "user", "content": msg})
    text = ask_bedrock(GENERAL_SYSTEM_PROMPT, history, 1024)
    return {"summary": text, "reply": text}


def reply_node(state: CultureState) -> dict[str, Any]:
    if state.get("error"):
        err = state["error"]
        return {"reply": f"(처리 실패: {err})", "summary": ""}
    preset = (state.get("reply") or "").strip()
    if state.get("needs_input") and preset:
        return {"reply": preset, "summary": preset, "notice": ""}
    summary = (state.get("summary") or "").strip()
    charts = list(state.get("chart_specs") or [])
    if not summary:
        return {"reply": "(요약 결과가 비어 있습니다.)", "summary": "", "chart_specs": charts}
    pdf_url = (state.get("pdf_url") or "").strip()
    return {
        "reply": summary,
        "summary": summary,
        "chart_specs": charts,
        "pdf_url": pdf_url,
        "notice": (state.get("notice") or "").strip(),
    }


def route_after_parse(state: CultureState) -> Literal["fetch", "general", "reply"]:
    if state.get("needs_input"):
        return "reply"
    if state.get("is_summary_request"):
        return "fetch"
    return "general"


def build_culture_graph():
    graph = StateGraph(CultureState)
    graph.add_node("parse", parse_node)
    graph.add_node("fetch", fetch_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("export_pdf", export_pdf_node)
    graph.add_node("general", general_chat_node)
    graph.add_node("reply", reply_node)

    graph.add_edge(START, "parse")
    graph.add_conditional_edges(
        "parse",
        route_after_parse,
        {"fetch": "fetch", "general": "general", "reply": "reply"},
    )
    graph.add_edge("fetch", "summarize")
    graph.add_edge("summarize", "export_pdf")
    graph.add_edge("export_pdf", "reply")
    graph.add_edge("general", "reply")
    graph.add_edge("reply", END)
    return graph


def get_executor():
    """LangGraph Executor (compile된 그래프)."""
    global _graph_executor
    if _graph_executor is None:
        _graph_executor = build_culture_graph().compile()
    return _graph_executor


def reset_executor() -> None:
    global _graph_executor
    _graph_executor = None


def run_workflow(
    user_message: str,
    *,
    table_name: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> CultureState:
    """워크플로우 전체 실행 → 최종 State 반환."""
    initial: CultureState = {
        "user_message": user_message,
        "table_name": (table_name or "").strip(),
        "history": history or [],
        "raw_data": [],
        "summary": "",
        "reply": "",
        "chart_specs": [],
        "pdf_url": "",
        "notice": "",
        "error": "",
        "needs_input": False,
    }
    try:
        return get_executor().invoke(initial)
    except Exception as e:
        initial["error"] = format_aws_error(e)
        initial["reply"] = f"(처리 실패: {initial['error']})"
        return initial
