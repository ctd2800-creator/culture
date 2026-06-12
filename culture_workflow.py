"""
Culture LangGraph 워크플로우
  analyze → (table_prompt | column_desc | data_summary | fetch_inst1 | general) → reply
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal, TypedDict

import boto3
from botocore.exceptions import ClientError
from langgraph.graph import END, START, StateGraph

from culture_inst1_agents import (
    AGGREGATE_CHART_FOLLOW_UP,
    INST1_TABLE_KOREAN_NAMES,
    analyze_question,
    build_aggregate_chart_specs,
    build_inst1_excel_export,
    build_pending_chart_payload,
    build_report_export,
    explain_inst1_columns,
    extract_inst1_data,
    format_chart_agent_reply,
    format_inst1_aggregate_prompt_reply,
    format_inst1_reply,
    format_inst1_table_prompt_reply,
    summarize_inst1_table_data,
    with_agent_banner,
)

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

GENERAL_SYSTEM_PROMPT = """당신은 Culture 앱의 한국어 AI 어시스턴트입니다.
사용자와 자연스럽게 대화하세요."""


class CultureState(TypedDict, total=False):
    """워크플로우 공유 State."""

    user_message: str
    table_name: str
    month: str
    summary: str
    reply: str
    notice: str
    error: str
    history: list[dict[str, str]]
    question_analysis: dict[str, Any]
    inst1_data: dict[str, list[dict[str, Any]]]
    inst1_column_orders: dict[str, list[str]]
    inst1_result_labels: dict[str, str]
    inst1_queries: dict[str, str]
    extract_tables: list[str]
    pending_aggregate: dict[str, Any]
    pending_chart: dict[str, Any]
    chart_specs: list[dict[str, Any]]
    excel_export: dict[str, Any]
    report_export: dict[str, Any]
    follow_up_questions: list[str]


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


def format_yyyymm(yyyymm: str) -> str:
    if len(yyyymm) == 6 and yyyymm.isdigit():
        return f"{yyyymm[:4]}년 {int(yyyymm[4:6])}월"
    return yyyymm


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


def analyze_question_node(state: CultureState) -> dict[str, Any]:
    """질문 분석 에이전트 — INST1 추출 vs 테이블 추천 vs 일반 대화."""
    msg = state.get("user_message", "")
    analysis = analyze_question(
        msg,
        bedrock_ask=ask_bedrock,
        pending_aggregate=state.get("pending_aggregate") or None,
        pending_chart=state.get("pending_chart") or None,
    )
    return {"question_analysis": analysis}


def table_prompt_node(state: CultureState) -> dict[str, Any]:
    """테이블명만 언급된 경우 추천 질문 응답."""
    analysis = state.get("question_analysis") or {}
    text = format_inst1_table_prompt_reply(analysis)
    return {"summary": text, "reply": text}


def aggregate_prompt_node(state: CultureState) -> dict[str, Any]:
    """집계 컬럼 선택 안내 에이전트."""
    analysis = state.get("question_analysis") or {}
    text = format_inst1_aggregate_prompt_reply(analysis)
    table = (analysis.get("tables") or [None])[0]
    korean = analysis.get("table_korean") or ""
    pending: dict[str, Any] = {}
    if table:
        pending = {"table": table, "korean": korean}
    return {"summary": text, "reply": text, "pending_aggregate": pending}


def column_desc_node(state: CultureState) -> dict[str, Any]:
    """테이블 컬럼 설명 에이전트."""
    analysis = state.get("question_analysis") or {}
    try:
        text = explain_inst1_columns(analysis)
    except Exception as e:
        return {"error": str(e)}
    return {"summary": text, "reply": text}


def chart_node(state: CultureState) -> dict[str, Any]:
    """집계 데이터 막대 차트 에이전트."""
    analysis = state.get("question_analysis") or {}
    pending = state.get("pending_chart") or {}
    try:
        specs = build_aggregate_chart_specs(pending)
        if not specs:
            raise ValueError(
                "차트로 그릴 집계 데이터가 없습니다. 먼저 집계 데이터를 조회해 주세요."
            )
        text = format_chart_agent_reply(analysis, pending, specs)
    except Exception as e:
        return {"error": str(e)}
    display = pending.get("display_label") or "집계 데이터"
    report_export = build_report_export(
        agent="inst1_chart",
        content=text,
        table_label=display,
        month=str(pending.get("month") or ""),
        chart_specs=specs,
    )
    return {
        "summary": text,
        "reply": text,
        "chart_specs": specs,
        "excel_export": {},
        "report_export": report_export,
        "pending_chart": {},
    }


def data_summary_node(state: CultureState) -> dict[str, Any]:
    """테이블 데이터 요약 에이전트."""
    analysis = state.get("question_analysis") or {}
    try:
        text = summarize_inst1_table_data(analysis, bedrock_ask=ask_bedrock)
        table = (analysis.get("tables") or [None])[0] or ""
        table_label = (
            analysis.get("table_korean")
            or INST1_TABLE_KOREAN_NAMES.get(table, table)
            or "데이터 요약"
        )
        report_export = build_report_export(
            agent="inst1_data_summary",
            content=text,
            table_label=table_label,
            month=str(analysis.get("month") or ""),
        )
    except Exception as e:
        return {"error": str(e)}
    return {"summary": text, "reply": text, "report_export": report_export}


def fetch_inst1_node(state: CultureState) -> dict[str, Any]:
    """TSHDEOA01·TSHDEOA02 데이터 추출 전용 에이전트."""
    analysis = state.get("question_analysis") or {}
    try:
        result = extract_inst1_data(analysis)
    except Exception as e:
        return {"error": str(e)}
    if result.get("errors") and result.get("total_rows", 0) == 0:
        return {
            "error": "; ".join(result["errors"]),
            "inst1_data": result.get("inst1_data") or {},
            "inst1_column_orders": result.get("inst1_column_orders") or {},
            "inst1_result_labels": result.get("inst1_result_labels") or {},
            "inst1_queries": result.get("inst1_queries") or {},
        }
    return {
        "inst1_data": result.get("inst1_data") or {},
        "inst1_column_orders": result.get("inst1_column_orders") or {},
        "inst1_result_labels": result.get("inst1_result_labels") or {},
        "inst1_queries": result.get("inst1_queries") or {},
        "month": result.get("month", ""),
        "extract_tables": list((result.get("inst1_data") or {}).keys()),
        "notice": "; ".join(result.get("errors") or []) or "",
    }


def format_inst1_node(state: CultureState) -> dict[str, Any]:
    if state.get("error"):
        return {}
    analysis = state.get("question_analysis") or {}
    extract_result = {
        "inst1_data": state.get("inst1_data") or {},
        "inst1_result_labels": state.get("inst1_result_labels") or {},
        "inst1_queries": state.get("inst1_queries") or {},
        "month": state.get("month") or analysis.get("month"),
        "group_company": analysis.get("group_company"),
        "customer_id": analysis.get("customer_id"),
        "errors": [state["error"]] if state.get("error") else [],
        "total_rows": sum(len(v) for v in (state.get("inst1_data") or {}).values()),
    }
    text = format_inst1_reply(analysis, extract_result)
    out: dict[str, Any] = {"summary": text, "reply": text}
    if analysis.get("query_type") == "aggregate":
        out["pending_aggregate"] = {}
    pending_chart = build_pending_chart_payload(analysis, extract_result)
    if pending_chart:
        out["pending_chart"] = pending_chart
        out["follow_up_questions"] = [AGGREGATE_CHART_FOLLOW_UP]
    if analysis.get("intent") == "inst1_extract" and extract_result.get("total_rows", 0) > 0:
        excel_export = build_inst1_excel_export(extract_result, analysis)
        if excel_export:
            out["excel_export"] = excel_export
    return out


def route_after_analyze(
    state: CultureState,
) -> Literal[
    "fetch_inst1",
    "general",
    "table_prompt",
    "aggregate_prompt",
    "column_desc",
    "data_summary",
    "chart",
]:
    analysis = state.get("question_analysis") or {}
    if analysis.get("intent") == "inst1_table_prompt":
        return "table_prompt"
    if analysis.get("intent") == "inst1_aggregate_prompt":
        return "aggregate_prompt"
    if analysis.get("intent") == "inst1_column_desc":
        return "column_desc"
    if analysis.get("intent") == "inst1_data_summary":
        return "data_summary"
    if analysis.get("intent") == "inst1_chart":
        return "chart"
    if analysis.get("intent") == "inst1_extract":
        return "fetch_inst1"
    return "general"


def general_chat_node(state: CultureState) -> dict[str, Any]:
    history = list(state.get("history") or [])
    msg = state.get("user_message", "")
    if not history or history[-1].get("content") != msg:
        history.append({"role": "user", "content": msg})
    text = ask_bedrock(GENERAL_SYSTEM_PROMPT, history, 1024)
    analysis = state.get("question_analysis") or {
        "intent": "general_chat",
        "reason": "일반 대화로 분류",
    }
    text = with_agent_banner(text, analysis)
    return {"summary": text, "reply": text}


def reply_node(state: CultureState) -> dict[str, Any]:
    if state.get("error"):
        err = state["error"]
        analysis = state.get("question_analysis") or {}
        if analysis.get("intent"):
            err_text = with_agent_banner(f"(처리 실패: {err})", analysis)
            return {"reply": err_text, "summary": ""}
        return {"reply": f"(처리 실패: {err})", "summary": ""}
    preset = (state.get("reply") or "").strip()
    summary = (state.get("summary") or "").strip()
    charts = list(state.get("chart_specs") or [])
    excel_export = dict(state.get("excel_export") or {})
    report_export = dict(state.get("report_export") or {})
    follow_up = list(state.get("follow_up_questions") or [])
    if preset:
        return {
            "reply": preset,
            "summary": summary or preset,
            "notice": (state.get("notice") or "").strip(),
            "chart_specs": charts,
            "excel_export": excel_export,
            "report_export": report_export,
            "follow_up_questions": follow_up,
        }
    if not summary:
        return {
            "reply": "(응답이 비어 있습니다.)",
            "summary": "",
            "notice": "",
            "chart_specs": charts,
            "excel_export": excel_export,
            "report_export": report_export,
            "follow_up_questions": follow_up,
        }
    return {
        "reply": summary,
        "summary": summary,
        "notice": (state.get("notice") or "").strip(),
        "chart_specs": charts,
        "excel_export": excel_export,
        "report_export": report_export,
        "follow_up_questions": follow_up,
    }


def build_culture_graph():
    graph = StateGraph(CultureState)
    graph.add_node("analyze", analyze_question_node)
    graph.add_node("table_prompt", table_prompt_node)
    graph.add_node("aggregate_prompt", aggregate_prompt_node)
    graph.add_node("column_desc", column_desc_node)
    graph.add_node("data_summary", data_summary_node)
    graph.add_node("chart", chart_node)
    graph.add_node("fetch_inst1", fetch_inst1_node)
    graph.add_node("format_inst1", format_inst1_node)
    graph.add_node("general", general_chat_node)
    graph.add_node("reply", reply_node)

    graph.add_edge(START, "analyze")
    graph.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {
            "fetch_inst1": "fetch_inst1",
            "general": "general",
            "table_prompt": "table_prompt",
            "aggregate_prompt": "aggregate_prompt",
            "column_desc": "column_desc",
            "data_summary": "data_summary",
            "chart": "chart",
        },
    )
    graph.add_edge("table_prompt", "reply")
    graph.add_edge("aggregate_prompt", "reply")
    graph.add_edge("column_desc", "reply")
    graph.add_edge("data_summary", "reply")
    graph.add_edge("chart", "reply")
    graph.add_edge("fetch_inst1", "format_inst1")
    graph.add_edge("format_inst1", "reply")
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


reset_executor()


def run_workflow(
    user_message: str,
    *,
    table_name: str | None = None,
    history: list[dict[str, str]] | None = None,
    pending_aggregate: dict[str, Any] | None = None,
    pending_chart: dict[str, Any] | None = None,
) -> CultureState:
    """워크플로우 전체 실행 → 최종 State 반환."""
    initial: CultureState = {
        "user_message": user_message,
        "table_name": (table_name or "").strip(),
        "history": history or [],
        "summary": "",
        "reply": "",
        "notice": "",
        "error": "",
        "question_analysis": {},
        "inst1_data": {},
        "inst1_queries": {},
        "extract_tables": [],
        "pending_aggregate": pending_aggregate or {},
        "pending_chart": pending_chart or {},
        "chart_specs": [],
        "excel_export": {},
        "report_export": {},
        "follow_up_questions": [],
    }
    try:
        return get_executor().invoke(initial)
    except Exception as e:
        initial["error"] = format_aws_error(e)
        initial["reply"] = f"(처리 실패: {initial['error']})"
        return initial
