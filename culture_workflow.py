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
    INST1_TABLE_KOREAN_NAMES,
    analyze_question,
    aggregate_column_options_label,
    aggregate_column_pick_mode,
    analyze_aggregate_external_insight,
    build_aggregate_follow_up_questions,
    build_aggregate_chart_specs,
    build_aggregate_column_options,
    build_chart_type_options,
    build_inst1_excel_export,
    build_pending_chart_payload,
    build_report_export,
    build_table_prompt_follow_up_questions,
    explain_inst1_columns,
    extract_inst1_data,
    format_chart_agent_reply,
    format_inst1_aggregate_prompt_reply,
    format_inst1_reply,
    format_inst1_table_prompt_reply,
    predict_rule_based_intent,
    summarize_inst1_table_data,
    with_agent_banner,
    AGGREGATE_CHART_FOLLOW_UP,
    EXTERNAL_INSIGHT_FOLLOW_UP,
    _normalize_group_by,
    _resolve_analysis_agent_intent,
    _wants_chart,
    _wants_external_insight,
)

# 데이터 사전 파이프라인 UI — 스키마 검색 결과를 질문 분석에 쓰는 에이전트만
# 데이터 사전(스키마 검색) 안내를 노출할 의도.
# 테이블 추천·집계 컬럼 선택 에이전트는 데이터 사전 기반 분석이 아니므로 제외.
SCHEMA_PIPELINE_UI_INTENTS = frozenset(
    {
        "inst1_extract",
    }
)

# 데이터 사전(스키마 검색) 자체를 호출하지 않을 의도 — 규칙 기반으로 미리 판별.
SCHEMA_PIPELINE_SKIP_INTENTS = frozenset(
    {
        "inst1_table_prompt",
        "inst1_aggregate_prompt",
        "inst1_column_desc",
        "inst1_data_summary",
    }
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
    chart_type_options: list[dict[str, str]]
    excel_export: dict[str, Any]
    report_export: dict[str, Any]
    follow_up_questions: list[str]
    aggregate_column_options: list[str]
    aggregate_column_label: str
    aggregate_column_pick_mode: str
    chart_available: bool
    schema_pipeline_notice: str
    schema_pipeline_ran: bool
    allowed_tables: list[str] | None


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


def clear_bedrock_clients() -> None:
    """만료된 세션 토큰 갱신 후 클라이언트 재생성용."""
    _bedrock_clients.clear()


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
            if os.environ.get("VERCEL"):
                return (
                    "AWS 임시 보안 토큰이 만료되었습니다. "
                    "Vercel 환경 변수 AWS_ACCESS_KEY_ID·AWS_SECRET_ACCESS_KEY·"
                    "AWS_SESSION_TOKEN(또는 AWS_SECURITY_TOKEN) 을 한 세트로 갱신한 뒤 Redeploy 하세요."
                )
            return (
                "AWS 임시 보안 토큰이 만료되었습니다. "
                "MFA/STS 세션을 갱신한 뒤 ~/.aws/credentials 또는 .env.local 의 "
                "ACCESS_KEY·SECRET·SESSION_TOKEN 을 한 세트로 맞추고 Culture 앱을 재시작하세요."
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
                if code in ("ExpiredTokenException",) or "ExpiredToken" in code:
                    clear_bedrock_clients()
                    try:
                        response = get_bedrock_runtime(region).invoke_model(
                            modelId=model_id,
                            body=body,
                            accept="application/json",
                            contentType="application/json",
                        )
                        response_body = json.loads(response["body"].read())
                        return response_body["content"][0]["text"].strip()
                    except ClientError as retry_err:
                        last_client = retry_err
                        last_error = retry_err
                        raise RuntimeError(
                            format_aws_error(
                                retry_err,
                                attempt_model=model_id,
                                attempt_region=region,
                            )
                        ) from retry_err
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


def _should_run_schema_pipeline(state: CultureState) -> bool:
    """직전 집계 follow-up(차트·분석)·테이블 추천·집계 컬럼 선택은 스키마 검색 불필요."""
    msg = (state.get("user_message") or "").strip()
    pending = state.get("pending_chart") or {}
    if pending.get("rows") and (_wants_chart(msg) or _wants_external_insight(msg)):
        return False
    # 테이블 추천·집계 컬럼 선택 에이전트는 데이터 사전을 호출하지 않는다.
    predicted = predict_rule_based_intent(
        msg,
        pending_aggregate=state.get("pending_aggregate") or None,
        pending_chart=state.get("pending_chart") or None,
    )
    if predicted in SCHEMA_PIPELINE_SKIP_INTENTS:
        return False
    return True


def _schema_notice_for_reply(state: CultureState) -> str:
    """실제 스키마 파이프라인을 탄 질문 분석 응답에만 안내 문구 노출."""
    if not state.get("schema_pipeline_ran"):
        return ""
    analysis = state.get("question_analysis") or {}
    intent = (analysis.get("intent") or "").strip()
    if intent not in SCHEMA_PIPELINE_UI_INTENTS:
        return ""
    return (state.get("schema_pipeline_notice") or "").strip()


def analyze_question_node(state: CultureState) -> dict[str, Any]:
    """질문 분석 에이전트 — INST1 추출 vs 테이블 추천 vs 일반 대화."""
    msg = state.get("user_message", "")
    schema_context = ""
    schema_pipeline_notice = ""
    schema_pipeline_ran = False
    try:
        from schema_vector.config import schema_vector_enabled
        from schema_vector.retriever import (
            build_schema_pipeline_notice,
            hits_to_schema_context,
            search_schema,
        )

        if schema_vector_enabled() and _should_run_schema_pipeline(state):
            hits = search_schema(msg, k=6)
            schema_pipeline_ran = True
            schema_context = hits_to_schema_context(hits)
            schema_pipeline_notice = build_schema_pipeline_notice(msg, hits)
    except Exception:
        logging.getLogger(__name__).debug("schema vector search skipped", exc_info=True)
    analysis = analyze_question(
        msg,
        bedrock_ask=ask_bedrock,
        pending_aggregate=state.get("pending_aggregate") or None,
        pending_chart=state.get("pending_chart") or None,
        schema_context=schema_context or None,
    )
    out: dict[str, Any] = {
        "question_analysis": analysis,
        "schema_pipeline_ran": schema_pipeline_ran,
    }
    if schema_context:
        out["schema_search_context"] = schema_context
    if schema_pipeline_ran and schema_pipeline_notice:
        out["schema_pipeline_notice"] = schema_pipeline_notice
    elif not schema_pipeline_ran:
        out["schema_pipeline_notice"] = ""
    return out


def table_prompt_node(state: CultureState) -> dict[str, Any]:
    """테이블명만 언급된 경우 추천 질문 응답."""
    analysis = state.get("question_analysis") or {}
    text = format_inst1_table_prompt_reply(analysis)
    table = (analysis.get("tables") or [None])[0]
    korean = analysis.get("table_korean") or INST1_TABLE_KOREAN_NAMES.get(
        table or "", table or ""
    )
    return {
        "summary": text,
        "reply": text,
        "follow_up_questions": build_table_prompt_follow_up_questions(korean),
    }


def aggregate_prompt_node(state: CultureState) -> dict[str, Any]:
    """집계 컬럼 선택 안내 에이전트 (1단계 조회 → 2단계 집계 항목 → 3단계 집계 함수)."""
    analysis = state.get("question_analysis") or {}
    stage = (analysis.get("aggregate_stage") or "group_by").strip()
    text = format_inst1_aggregate_prompt_reply(analysis)
    table = (analysis.get("tables") or [None])[0]
    korean = analysis.get("table_korean") or ""
    pending: dict[str, Any] = {}
    if table:
        if stage == "aggregate_func":
            pending = {
                "table": table,
                "korean": korean,
                "stage": "aggregate_func",
                "group_by": _normalize_group_by(analysis.get("group_by")),
                "aggregate_measures": list(analysis.get("aggregate_measures") or []),
                "aggregate_measure_funcs": dict(
                    analysis.get("aggregate_measure_funcs") or {}
                ),
            }
        elif stage == "measure":
            pending = {
                "table": table,
                "korean": korean,
                "stage": "measure",
                "group_by": _normalize_group_by(analysis.get("group_by")),
            }
        else:
            pending = {"table": table, "korean": korean, "stage": "group_by"}
    return {
        "summary": text,
        "reply": text,
        "pending_aggregate": pending,
        "aggregate_column_options": build_aggregate_column_options(analysis),
        "aggregate_column_label": aggregate_column_options_label(analysis),
        "aggregate_column_pick_mode": aggregate_column_pick_mode(analysis),
    }


def column_desc_node(state: CultureState) -> dict[str, Any]:
    """테이블 컬럼 설명 에이전트."""
    analysis = state.get("question_analysis") or {}
    try:
        text = explain_inst1_columns(analysis)
    except Exception as e:
        return {"error": str(e)}
    return {"summary": text, "reply": text}


def chart_node(state: CultureState) -> dict[str, Any]:
    """집계 데이터 차트 에이전트 — 차트 유형 선택 단계."""
    analysis = state.get("question_analysis") or {}
    pending = state.get("pending_chart") or {}
    try:
        if not pending.get("rows"):
            raise ValueError(
                "차트로 그릴 집계 데이터가 없습니다. 먼저 집계 데이터를 조회해 주세요."
            )
        if not pending.get("chartable"):
            raise ValueError(
                "차트로 시각화할 숫자 집계 항목이 없습니다. 집계 데이터를 다시 조회해 주세요."
            )
        text = format_chart_agent_reply(analysis, pending)
        options = build_chart_type_options()
    except Exception as e:
        return {"error": str(e)}
    return {
        "summary": text,
        "reply": text,
        "chart_specs": [],
        "chart_type_options": options,
        "follow_up_questions": [EXTERNAL_INSIGHT_FOLLOW_UP],
    }


def route_from_start(
    state: CultureState,
) -> Literal["analyze", "external_insight"]:
    """직전 집계 결과가 있으면 분석 요청은 질문 분석 없이 분석 에이전트로 직행."""
    msg = (state.get("user_message") or "").strip()
    pending = state.get("pending_chart") or {}
    if pending.get("rows") and _wants_external_insight(msg):
        return "external_insight"
    return "analyze"


def external_insight_node(state: CultureState) -> dict[str, Any]:
    """분석 에이전트 — 직전 집계 결과만 사용(데이터 추출 없음)."""
    pending = state.get("pending_chart") or {}
    analysis = state.get("question_analysis") or {}
    if analysis.get("intent") != "inst1_external_insight":
        analysis = _resolve_analysis_agent_intent(
            state.get("user_message", ""),
            pending,
        )
    try:
        text = analyze_aggregate_external_insight(
            pending,
            state.get("user_message", ""),
            analysis,
            bedrock_ask=ask_bedrock,
        )
        report_export = build_report_export(
            agent="inst1_external_insight",
            content=text,
            table_label=pending.get("display_label") or "분석",
            month=str(pending.get("month") or ""),
        )
    except Exception as e:
        return {"error": str(e)}
    out: dict[str, Any] = {
        "summary": text,
        "reply": text,
        "report_export": report_export,
        "question_analysis": analysis,
    }
    # 분석 결과 강화 — 직전 데이터 추출 표와 차트 에이전트가 만든 차트를 함께 표시
    result_key = pending.get("result_key") or "집계결과"
    rows = list(pending.get("rows") or [])
    if rows:
        out["inst1_data"] = {result_key: rows}
        out["inst1_result_labels"] = {
            result_key: pending.get("display_label") or result_key
        }
        column_order = list(pending.get("column_order") or [])
        if column_order:
            out["inst1_column_orders"] = {result_key: column_order}
        query = (pending.get("query") or "").strip()
        if query:
            out["inst1_queries"] = {result_key: query}
    charts = list(pending.get("charts") or [])
    if charts:
        out["chart_specs"] = charts
    return out


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
    """TSHDEOA01~06 데이터 추출 전용 에이전트."""
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
        "inst1_column_orders": state.get("inst1_column_orders") or {},
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
    chartable = bool(pending_chart.get("chartable"))
    if pending_chart:
        out["pending_chart"] = pending_chart
    query_type = analysis.get("query_type") or ""
    if (
        query_type in ("aggregate", "join_aggregate")
        and extract_result.get("total_rows", 0) > 0
    ):
        out["follow_up_questions"] = build_aggregate_follow_up_questions(
            chart_available=chartable,
        )
    if analysis.get("intent") == "inst1_extract" and extract_result.get("total_rows", 0) > 0:
        excel_export = build_inst1_excel_export(extract_result, analysis)
        if excel_export:
            out["excel_export"] = excel_export
    return out


# 테이블 접근 권한을 검사해야 하는 intent (실제 테이블 데이터·메타에 접근)
_TABLE_ACCESS_INTENTS = {
    "inst1_extract",
    "inst1_table_prompt",
    "inst1_aggregate_prompt",
    "inst1_column_desc",
    "inst1_data_summary",
}


def _analysis_referenced_tables(analysis: dict[str, Any]) -> set[str]:
    """질문 분석이 가리키는 모든 INST1 테이블 코드."""
    refs: set[str] = set()
    for t in analysis.get("tables") or []:
        if t:
            refs.add(t)
    for t in analysis.get("join_tables") or []:
        if t:
            refs.add(t)
    agg = analysis.get("aggregate_table")
    if agg:
        refs.add(agg)
    return refs


def denied_tables_for_state(state: CultureState) -> set[str]:
    """현재 사용자 권한으로 접근 불가한, 질문이 가리키는 테이블 집합."""
    allowed = state.get("allowed_tables")
    if allowed is None:
        return set()  # 제한 없음(전체 접근)
    allowed_set = {t for t in allowed if t}
    analysis = state.get("question_analysis") or {}
    if (analysis.get("intent") or "") not in _TABLE_ACCESS_INTENTS:
        return set()
    referenced = _analysis_referenced_tables(analysis)
    return {t for t in referenced if t not in allowed_set}


def permission_denied_node(state: CultureState) -> dict[str, Any]:
    """권한 없는 테이블 조회 요청 거부 응답."""
    analysis = state.get("question_analysis") or {}
    denied = sorted(denied_tables_for_state(state))
    labels = ", ".join(
        f"{INST1_TABLE_KOREAN_NAMES.get(t, t)}({t})" for t in denied
    ) or "요청하신 테이블"
    text = (
        f"요청하신 {labels} 에 대한 접근 권한이 없습니다.\n"
        "현재 계정으로 조회할 수 있는 테이블만 질문해 주세요. "
        "(권한이 필요하면 관리자에게 문의하세요.)"
    )
    text = with_agent_banner(text, analysis)
    return {"summary": text, "reply": text}


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
    "external_insight",
    "permission_denied",
]:
    analysis = state.get("question_analysis") or {}
    if denied_tables_for_state(state):
        return "permission_denied"
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
    if analysis.get("intent") == "inst1_external_insight":
        return "external_insight"
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
    chart_type_options = list(state.get("chart_type_options") or [])
    excel_export = dict(state.get("excel_export") or {})
    report_export = dict(state.get("report_export") or {})
    follow_up = list(state.get("follow_up_questions") or [])
    aggregate_columns = list(state.get("aggregate_column_options") or [])
    aggregate_label = (state.get("aggregate_column_label") or "").strip()
    aggregate_pick_mode = (state.get("aggregate_column_pick_mode") or "append").strip()
    chart_available = bool(state.get("chart_available"))
    schema_pipeline_notice = _schema_notice_for_reply(state)
    if preset:
        return {
            "reply": preset,
            "summary": summary or preset,
            "notice": (state.get("notice") or "").strip(),
            "schema_pipeline_notice": schema_pipeline_notice,
            "chart_specs": charts,
            "chart_type_options": chart_type_options,
            "excel_export": excel_export,
            "report_export": report_export,
            "follow_up_questions": follow_up,
            "aggregate_column_options": aggregate_columns,
            "aggregate_column_label": aggregate_label,
            "aggregate_column_pick_mode": aggregate_pick_mode,
            "chart_available": chart_available,
        }
    if not summary:
        return {
            "reply": "(응답이 비어 있습니다.)",
            "summary": "",
            "notice": "",
            "schema_pipeline_notice": schema_pipeline_notice,
            "chart_specs": charts,
            "chart_type_options": chart_type_options,
            "excel_export": excel_export,
            "report_export": report_export,
            "follow_up_questions": follow_up,
            "aggregate_column_options": aggregate_columns,
            "aggregate_column_label": aggregate_label,
            "aggregate_column_pick_mode": aggregate_pick_mode,
            "chart_available": chart_available,
        }
    return {
        "reply": summary,
        "summary": summary,
        "notice": (state.get("notice") or "").strip(),
        "schema_pipeline_notice": schema_pipeline_notice,
        "chart_specs": charts,
        "chart_type_options": chart_type_options,
        "excel_export": excel_export,
        "report_export": report_export,
        "follow_up_questions": follow_up,
        "aggregate_column_options": aggregate_columns,
        "aggregate_column_label": aggregate_label,
        "aggregate_column_pick_mode": aggregate_pick_mode,
        "chart_available": chart_available,
    }


def build_culture_graph():
    graph = StateGraph(CultureState)
    graph.add_node("analyze", analyze_question_node)
    graph.add_node("table_prompt", table_prompt_node)
    graph.add_node("aggregate_prompt", aggregate_prompt_node)
    graph.add_node("column_desc", column_desc_node)
    graph.add_node("data_summary", data_summary_node)
    graph.add_node("chart", chart_node)
    graph.add_node("external_insight", external_insight_node)
    graph.add_node("fetch_inst1", fetch_inst1_node)
    graph.add_node("format_inst1", format_inst1_node)
    graph.add_node("general", general_chat_node)
    graph.add_node("permission_denied", permission_denied_node)
    graph.add_node("reply", reply_node)

    graph.add_conditional_edges(
        START,
        route_from_start,
        {
            "analyze": "analyze",
            "external_insight": "external_insight",
        },
    )
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
            "external_insight": "external_insight",
            "permission_denied": "permission_denied",
        },
    )
    graph.add_edge("permission_denied", "reply")
    graph.add_edge("table_prompt", "reply")
    graph.add_edge("aggregate_prompt", "reply")
    graph.add_edge("column_desc", "reply")
    graph.add_edge("data_summary", "reply")
    graph.add_edge("chart", "reply")
    graph.add_edge("external_insight", "reply")
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
    allowed_tables: list[str] | None = None,
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
        "chart_type_options": [],
        "excel_export": {},
        "report_export": {},
        "follow_up_questions": [],
        "aggregate_column_options": [],
        "aggregate_column_label": "",
        "aggregate_column_pick_mode": "append",
        "chart_available": False,
        "schema_pipeline_notice": "",
        "schema_pipeline_ran": False,
        "allowed_tables": allowed_tables,
    }
    try:
        return get_executor().invoke(initial)
    except Exception as e:
        initial["error"] = format_aws_error(e)
        initial["reply"] = f"(처리 실패: {initial['error']})"
        return initial
