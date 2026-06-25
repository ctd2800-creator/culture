"""
Culture — AI 채팅 + LangGraph 워크플로우 (Fetch → Summarize → Reply).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

import psycopg2
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_file,
    send_from_directory,
    session,
    stream_with_context,
    url_for,
)
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    from dotenv import load_dotenv

    _root = Path(__file__).resolve().parent
    load_dotenv(_root / ".env.local", override=False)
    load_dotenv(_root / ".env", override=False)
except ImportError:
    pass

from culture_inst1_agents import (
    build_aggregate_chart_specs,
    build_workflow_status_event,
    format_chart_agent_reply,
    mask_excel_export_for_display,
    mask_inst1_data_for_display,
)
from culture_excel import build_excel_bytes, export_has_data, save_excel_to_disk
from culture_pdf_s3 import (
    build_agent_report_pdf_bytes,
    report_has_data,
    save_report_to_disk,
    s3_configured,
)
from culture_workflow import (
    aws_credentials_configured,
    aws_session_token_configured,
    aws_session_token_env_name,
    bedrock_region,
    format_aws_error,
    get_executor,
    get_model_id,
    run_workflow,
)
from supabase.culture_db import (
    culture_db_backend,
    culture_db_configured,
    get_culture_db_url,
)
from supabase.members_auth import authenticate_member
from supabase.members_setup import setup_members
from supabase.table_config import (
    MEMBER_TABLE_NAME,
    TABLE_NAME,
    inst1_schema_table_display_items,
)
from supabase.aurora_setup import ensure_tshde0zcd_table as ensure_tshde0zcd_table_aurora
from supabase.aurora_setup import ensure_tshdeoa_tables

PUBLIC_ENDPOINTS = frozenset(
    {
        "login",
        "logout",
        "static_files",
        "api_health",
    }
)

_db_url_cache: str | None = None
_db_init_lock = threading.Lock()
_tchdhc001_initialized = False
_members_initialized = False
_tshdeoa01_initialized = False
_tshdeoa02_initialized = False
_tshdeoa04_initialized = False
_tshde0zcd_initialized = False
APP_BOOT_ID = uuid.uuid4().hex


def get_db_url() -> str:
    global _db_url_cache
    if _db_url_cache is not None:
        return _db_url_cache
    _db_url_cache = get_culture_db_url()
    return _db_url_cache


def db_configured() -> bool:
    return culture_db_configured()


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "culture-dev-secret-change-me")
if os.environ.get("VERCEL"):
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
logging.basicConfig(level=logging.INFO)

try:
    from culture_zcd_lookup import clear_lookup_cache

    clear_lookup_cache()
except Exception:
    pass


def is_logged_in() -> bool:
    return bool(session.get("member_id"))


def current_member() -> dict[str, Any] | None:
    if not is_logged_in():
        return None
    return {
        "아이디": session.get("member_id", ""),
        "회원명": session.get("member_name", ""),
        "이메일": session.get("member_email", ""),
        "부서명": session.get("member_dept", ""),
    }


def login_member(member: dict[str, Any]) -> None:
    session["member_id"] = member["아이디"]
    session["member_name"] = member["회원명"]
    session["member_email"] = member.get("이메일", "")
    session["member_dept"] = member.get("부서명", "")
    session["chat_history"] = []
    session.modified = True


def logout_member() -> None:
    session.clear()


def render_login_page(*, error: str | None = None, next_url: str | None = None):
    dest = (next_url or "/").strip()
    if not dest.startswith("/") or dest.startswith("//"):
        dest = "/"
    return render_template_string(
        LOGIN_PAGE,
        error=error,
        next_url=dest,
    )


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS:
        return
    if is_logged_in():
        return
    # 비로그인 시 `/` 에서 로그인 화면 표시 (리다이렉트만 쓰면 배포/캐시 이슈 시 빈 화면 가능)
    if request.endpoint == "index" and request.method == "GET":
        return
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "로그인이 필요합니다."}), 401
    return redirect(url_for("index", next=request.path))


@app.before_request
def ensure_db_tables_ready():
    global _tchdhc001_initialized, _members_initialized
    global _tshdeoa01_initialized, _tshdeoa02_initialized, _tshdeoa04_initialized, _tshde0zcd_initialized
    if request.endpoint in ("api_health", "static_files"):
        return
    if request.endpoint == "index" and request.method == "GET" and not is_logged_in():
        return
    if request.endpoint == "login" and request.method == "GET":
        return
    if os.environ.get("VERCEL"):
        return
    if not db_configured():
        return
    if (
        _tchdhc001_initialized
        and _members_initialized
        and _tshdeoa01_initialized
        and _tshdeoa02_initialized
        and _tshdeoa04_initialized
        and _tshde0zcd_initialized
    ):
        return
    with _db_init_lock:
        if (
            _tchdhc001_initialized
            and _members_initialized
            and _tshdeoa01_initialized
            and _tshdeoa02_initialized
            and _tshdeoa04_initialized
            and _tshde0zcd_initialized
        ):
            return
        try:
            with get_conn() as conn:
                if not _tchdhc001_initialized:
                    ensure_tchdhc001_table(conn)
                    _tchdhc001_initialized = True
                if not _members_initialized:
                    setup_members(conn, seed=True, force_seed=False)
                    _members_initialized = True
                if not _tshdeoa01_initialized:
                    ensure_tshdeoa_tables(conn)
                    _tshdeoa01_initialized = True
                    _tshdeoa02_initialized = True
                    _tshdeoa04_initialized = True
                if not _tshde0zcd_initialized:
                    ensure_tshde0zcd_table_aurora(conn)
                    _tshde0zcd_initialized = True
                conn.commit()
        except Exception:
            app.logger.exception("DB 테이블 초기화 실패")
            raise


@app.errorhandler(Exception)
def handle_unexpected_exception(e):
    if isinstance(e, HTTPException):
        return e
    app.logger.exception("요청 처리 중 예외")
    if os.environ.get("CULTURE_DEBUG") == "1":
        return (
            f"<pre>{type(e).__name__}: {e!r}</pre>",
            500,
            {"Content-Type": "text/html; charset=utf-8"},
        )
    hint = (
        " Vercel Runtime Logs를 확인하세요."
        if os.environ.get("VERCEL")
        else " 로그를 확인하세요."
    )
    return (
        f"<p>KB AI 데이터 리터러시 서버 오류입니다.{hint}</p>",
        500,
        {"Content-Type": "text/html; charset=utf-8"},
    )


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def get_conn():
    from supabase.culture_db import connect_culture_db

    return connect_culture_db(connect_timeout=15)


def ensure_tchdhc001_table(conn) -> None:
    sql_path = os.path.join(os.path.dirname(__file__), "supabase", "tchdhc001.sql")
    with open(sql_path, encoding="utf-8") as f:
        ddl = f.read()
    with conn.cursor() as cur:
        cur.execute(ddl)


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_pad() -> str:
    """Flask 개발 서버 버퍼링 완화용 SSE 주석 패딩."""
    return ":" + (" " * 2048) + "\n\n"


def _chart_available_from_final(final: dict[str, Any]) -> bool:
    return bool(final.get("chart_available"))


def _client_report_export(report: dict[str, Any]) -> dict[str, Any]:
    """UI 보고서 버튼 — 데이터 요약 에이전트 결과만 노출."""
    if (report.get("agent") or "") == "inst1_data_summary":
        return dict(report)
    return {}


def run_chat(
    raw: str,
    history: list[dict],
    *,
    table_name: str | None = None,
) -> tuple[
    str,
    str | None,
    list[dict[str, Any]],
    str,
    dict[str, list],
    dict[str, list[str]],
    dict[str, str],
    dict[str, str],
    list[str],
    dict[str, Any],
    dict[str, Any],
    bool,
    list[str],
    str,
    str,
    str,
]:
    """LangGraph Executor로 질문 분석 → INST1 추출/일반 대화 → 응답 실행."""
    final = run_workflow(
        raw,
        table_name=table_name,
        history=history,
        pending_aggregate=session.get("pending_aggregate"),
        pending_chart=session.get("pending_chart"),
    )
    _sync_pending_aggregate_session(session, final)
    _sync_pending_chart_session(session, final)
    reply = (final.get("reply") or "").strip()
    if final.get("error") and not reply:
        raise RuntimeError(final["error"])
    notice = final.get("notice") or None
    charts = list(final.get("chart_specs") or [])
    pdf_url = (final.get("pdf_url") or "").strip()
    inst1_data = mask_inst1_data_for_display(dict(final.get("inst1_data") or {}))
    inst1_column_orders = dict(final.get("inst1_column_orders") or {})
    inst1_result_labels = dict(final.get("inst1_result_labels") or {})
    inst1_queries = dict(final.get("inst1_queries") or {})
    follow_up_questions = list(final.get("follow_up_questions") or [])
    aggregate_column_options = list(final.get("aggregate_column_options") or [])
    aggregate_column_label = (final.get("aggregate_column_label") or "").strip()
    aggregate_column_pick_mode = (
        final.get("aggregate_column_pick_mode") or "append"
    ).strip()
    excel_export = mask_excel_export_for_display(dict(final.get("excel_export") or {}))
    report_export = _client_report_export(dict(final.get("report_export") or {}))
    chart_available = _chart_available_from_final(final)
    schema_pipeline_notice = (final.get("schema_pipeline_notice") or "").strip()
    return (
        reply,
        notice,
        charts,
        pdf_url,
        inst1_data,
        inst1_column_orders,
        inst1_result_labels,
        inst1_queries,
        follow_up_questions,
        excel_export,
        report_export,
        chart_available,
        aggregate_column_options,
        aggregate_column_label,
        aggregate_column_pick_mode,
        schema_pipeline_notice,
    )


def ensure_session_lists():
    if "chat_history" not in session:
        session["chat_history"] = []


LOGIN_PAGE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#FFCC00" />
  <title>KB AI 데이터 리터러시 — 로그인</title>
  <style>
    :root {
      --kb-yellow: #ffcc00;
      --kb-yellow-dark: #e6b800;
      --kb-yellow-light: #fff8e1;
      --kb-brown: #5c4b3c;
      --kb-brown-dark: #3d3228;
      --kb-brown-darker: #2c2419;
      --kb-text: #111111;
      --kb-text-muted: #4a4038;
      --kb-border: #d9cbb8;
      --kb-bg: #ffffff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100dvh;
      font-family: system-ui, -apple-system, 'Malgun Gothic', 'Noto Sans KR', sans-serif;
      font-size: 16px;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
      background: linear-gradient(165deg, #fff8e1 0%, #faf7f2 45%, #f3ebe0 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      color: var(--kb-text);
    }
    .card {
      width: 100%;
      max-width: 400px;
      background: #fff;
      border-radius: 16px;
      border: 1px solid var(--kb-border);
      box-shadow: 0 8px 32px rgba(44, 36, 25, 0.1);
      padding: 28px 24px;
    }
    h1 { margin: 0 0 6px; font-size: 1.5rem; font-weight: 800; color: var(--kb-brown-darker); }
    .sub { color: var(--kb-text-muted); font-size: 15px; margin: 0 0 20px; }
    label { display: block; font-size: 15px; font-weight: 700; color: var(--kb-brown-darker); margin-bottom: 6px; }
    input {
      width: 100%;
      padding: 12px 14px;
      border: 1px solid var(--kb-border);
      border-radius: 10px;
      font-size: 16px;
      margin-bottom: 14px;
      background: #fff;
    }
    input:focus { outline: 2px solid rgba(255, 204, 0, 0.55); border-color: var(--kb-yellow); }
    button {
      width: 100%;
      border: 0;
      padding: 14px;
      border-radius: 12px;
      background: var(--kb-yellow);
      color: var(--kb-brown-darker);
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
      margin-top: 4px;
    }
    button:active { background: var(--kb-yellow-dark); }
    .error {
      background: #fee2e2;
      color: #991b1b;
      border: 1px solid #fecaca;
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 14px;
      margin-bottom: 14px;
    }
    .hint { font-size: 13px; color: var(--kb-text-muted); margin-top: 16px; line-height: 1.55; }
  </style>
</head>
<body>
  <div class="card">
    <h1>KB AI 데이터 리터러시</h1>
    <p class="sub">아이디와 비밀번호로 로그인하세요.</p>
    {% if error %}
    <div class="error">{{ error }}</div>
    {% endif %}
    <form method="post" action="{{ url_for('login') }}">
      <input type="hidden" name="next" value="{{ next_url }}" />
      <label for="member_id">아이디</label>
      <input id="member_id" name="member_id" type="text" autocomplete="username" required autofocus />
      <label for="password">비밀번호</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required />
      <button type="submit">로그인</button>
    </form>
    <p class="hint">예: culture01 / Pass01!culture</p>
  </div>
</body>
</html>
"""


PAGE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#FFCC00" />
  <title>KB AI 데이터 리터러시</title>
  <style>
    :root {
      --kb-yellow: #ffcc00;
      --kb-yellow-dark: #e6b800;
      --kb-yellow-light: #fff8e1;
      --kb-yellow-soft: #fff6d6;
      --kb-brown: #5c4b3c;
      --kb-brown-dark: #3d3228;
      --kb-brown-darker: #2c2419;
      --kb-text: #111111;
      --kb-text-secondary: #3d3228;
      --kb-text-muted: #4a4038;
      --kb-border: #d9cbb8;
      --kb-bg: #f7f3ec;
      --kb-sidebar-text: #ffffff;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, 'Segoe UI', 'Malgun Gothic', 'Noto Sans KR', sans-serif;
      font-size: 16px;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
      background: var(--kb-bg);
      color: var(--kb-text);
      overflow: hidden;
    }
    .app-shell {
      display: flex;
      height: 100vh;
      min-width: 960px;
    }
    .sidebar {
      width: 300px;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      background: linear-gradient(180deg, var(--kb-brown-darker) 0%, var(--kb-brown-dark) 100%);
      color: var(--kb-sidebar-text);
      border-right: 1px solid #4a3f34;
    }
    .sidebar-brand {
      padding: 22px 20px 16px;
      border-bottom: 1px solid rgba(255, 204, 0, 0.2);
    }
    .sidebar-brand h1 {
      margin: 0;
      font-size: 1.25rem;
      font-weight: 800;
      color: var(--kb-yellow);
      letter-spacing: -0.02em;
      line-height: 1.4;
    }
    .sidebar-brand p {
      margin: 8px 0 0;
      font-size: 14px;
      color: #f2ebe2;
      line-height: 1.5;
    }
    .sidebar-body {
      flex: 1;
      overflow-y: auto;
      padding: 16px 16px 12px;
    }
    .sidebar-section {
      margin-bottom: 18px;
    }
    .sidebar-section-title {
      margin: 0 0 10px;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: var(--kb-yellow);
    }
    .prompt-chip {
      margin: 0;
      padding: 11px 13px;
      background: rgba(255, 204, 0, 0.12);
      border: 1px solid rgba(255, 204, 0, 0.3);
      border-radius: 10px;
      font-size: 14px;
      font-weight: 500;
      line-height: 1.55;
      color: #ffffff;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
    }
    .prompt-chip:hover {
      background: rgba(255, 204, 0, 0.16);
      border-color: rgba(255, 204, 0, 0.45);
    }
    .prompt-chip + .prompt-chip { margin-top: 8px; }
    .table-chip {
      margin: 0;
      padding: 9px 13px;
      background: rgba(0, 0, 0, 0.22);
      border: 1px solid rgba(255, 255, 255, 0.16);
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      color: #ffffff;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
    }
    .table-chip:hover {
      background: rgba(255, 204, 0, 0.12);
      border-color: rgba(255, 204, 0, 0.35);
    }
    .table-chip + .table-chip { margin-top: 6px; }
    .sidebar-footer {
      padding: 14px 16px 18px;
      border-top: 1px solid rgba(255, 204, 0, 0.15);
      background: rgba(0, 0, 0, 0.15);
    }
    .member-card {
      font-size: 14px;
      line-height: 1.55;
      color: var(--kb-sidebar-text);
    }
    .member-card strong {
      display: block;
      font-size: 15px;
      font-weight: 700;
      color: #fff;
      margin-bottom: 4px;
    }
    .member-card .meta {
      display: block;
      color: #e8ddd0;
      font-size: 13px;
    }
    .member-card .logout {
      display: inline-block;
      margin-top: 10px;
      padding: 8px 13px;
      border-radius: 8px;
      background: rgba(255, 204, 0, 0.2);
      color: var(--kb-yellow);
      font-size: 13px;
      font-weight: 700;
      text-decoration: none;
    }
    .member-card .logout:hover { background: rgba(255, 204, 0, 0.25); }
    .main {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      background: var(--kb-bg);
    }
    .main-alerts {
      flex-shrink: 0;
      padding: 6px 12px 0;
    }
    .banner {
      padding: 10px 14px;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 600;
      line-height: 1.55;
      margin-bottom: 8px;
    }
    .banner-warn { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
    .banner-err { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
    .chat-panel {
      flex: 1;
      min-height: 0;
      display: flex;
      flex-direction: column;
      margin: 4px 10px 6px;
      background: #fff;
      border: 1px solid var(--kb-border);
      border-radius: 14px;
      box-shadow: 0 6px 24px rgba(44, 36, 25, 0.05);
      overflow: hidden;
    }
    .chat-box {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      padding: 20px 22px;
      background: #ffffff;
    }
    .composer {
      flex-shrink: 0;
      padding: 8px 12px 8px;
      background: #fff;
      border-top: 1px solid var(--kb-border);
    }
    .composer-input-row {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .composer-input-row textarea {
      flex: 1;
      min-width: 0;
      min-height: 56px;
      max-height: 88px;
      resize: none;
    }
    .composer-actions {
      display: flex;
      flex-direction: column;
      gap: 6px;
      flex-shrink: 0;
    }
    .composer-actions button,
    .composer-actions .btn {
      min-width: 76px;
      padding: 8px 12px;
      min-height: 36px;
      font-size: 14px;
    }
    .msg {
      padding: 14px 16px;
      border-radius: 14px;
      margin-bottom: 12px;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-wrap: anywhere;
      line-height: 1.7;
      font-size: 16px;
      color: var(--kb-text);
      max-width: 92%;
    }
    .msg.user {
      background: var(--kb-yellow-soft);
      border: 1px solid rgba(255, 204, 0, 0.45);
      color: var(--kb-brown-darker);
      margin-left: auto;
      border-bottom-right-radius: 4px;
    }
    .msg.assistant {
      background: #fff;
      border: 1px solid #cfc0ad;
      color: var(--kb-text);
      margin-right: auto;
      border-bottom-left-radius: 4px;
    }
    textarea {
      width: 100%;
      min-height: 72px;
      max-height: 180px;
      resize: vertical;
      padding: 14px 16px;
      border-radius: 12px;
      border: 1px solid #bfb09c;
      font-family: inherit;
      font-size: 16px;
      line-height: 1.6;
      color: var(--kb-text);
      background: #fff;
    }
    textarea:focus {
      outline: 2px solid rgba(255, 204, 0, 0.45);
      outline-offset: 1px;
      border-color: var(--kb-yellow);
    }
    .row {
      margin-top: 12px;
      display: flex;
      gap: 10px;
      align-items: center;
    }
    button, .btn {
      border: 0;
      padding: 12px 20px;
      min-height: 44px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 16px;
      font-weight: 700;
      text-decoration: none;
      text-align: center;
    }
    button {
      background: var(--kb-yellow);
      color: var(--kb-brown-darker);
      min-width: 96px;
    }
    button:hover { background: var(--kb-yellow-dark); }
    .btn-secondary {
      background: var(--kb-brown);
      color: #fff;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .btn-secondary:hover { background: var(--kb-brown-dark); }
    .notice { color: var(--kb-brown-darker); font-size: 14px; margin-top: 8px; font-weight: 700; }
    .schema-pipeline-notice {
      font-size: 13px;
      line-height: 1.55;
      color: #3d5a3a;
      background: rgba(76, 120, 68, 0.08);
      border-left: 3px solid #4c7844;
      padding: 10px 12px;
      margin-bottom: 10px;
      border-radius: 6px;
    }
    .msg.assistant.streaming { border-color: rgba(255, 204, 0, 0.5); }
    .msg.assistant.generating .msg-text {
      color: var(--kb-text-secondary);
      line-height: 1.75;
    }
    .msg.assistant.streaming::after {
      content: "▋";
      animation: blink 1s step-end infinite;
      margin-left: 2px;
      color: var(--kb-brown);
    }
    @keyframes blink { 50% { opacity: 0; } }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .status-line {
      font-size: 13px;
      color: var(--kb-text-secondary);
      margin: 4px 0 0;
      min-height: 0;
      font-weight: 500;
    }
    .chat-hint {
      color: var(--kb-text-muted);
      font-size: 16px;
      line-height: 1.6;
      margin: 0;
      padding: 8px 4px;
    }
    .msg-text {
      white-space: pre-wrap;
      word-break: break-word;
      color: inherit;
    }
    .msg-follow-up {
      margin-top: 12px;
      padding: 0;
      background: none;
      border: 0;
    }
    .msg-follow-up .follow-up-label {
      font-size: 14px;
      font-weight: 800;
      color: var(--kb-brown-darker);
      margin: 0 0 6px;
    }
    .msg-follow-up .follow-up-chip {
      display: block;
      width: 100%;
      margin: 0;
      padding: 4px 0;
      border: 0;
      border-radius: 0;
      background: none;
      color: var(--kb-brown-darker);
      font: inherit;
      font-size: 15px;
      font-weight: 500;
      line-height: 1.6;
      text-align: left;
      cursor: pointer;
      word-break: keep-all;
    }
    .msg-follow-up .follow-up-chip::before {
      content: "- ";
      color: var(--kb-text-muted);
    }
    .msg-follow-up .follow-up-chip:hover {
      color: var(--kb-brown-darker);
      text-decoration: underline;
      background: none;
    }
    .msg-follow-up .follow-up-chip + .follow-up-chip { margin-top: 0; }
    .chart-block {
      margin-top: 14px;
      padding: 12px;
      background: var(--kb-yellow-light);
      border: 1px solid var(--kb-border);
      border-radius: 12px;
    }
    .chart-title {
      font-size: 14px;
      font-weight: 800;
      color: var(--kb-brown-darker);
      margin: 0 0 8px;
    }
    .excel-export-wrap,
    .report-export-wrap,
    .msg-action-bar {
      margin-top: 14px;
      padding: 10px 12px;
      background: var(--kb-yellow-light);
      border: 1px solid var(--kb-border);
      border-radius: 12px;
    }
    .msg-action-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .excel-export-wrap,
    .report-export-wrap {
      display: contents;
    }
    .btn-excel-export {
      border: 0;
      padding: 10px 18px;
      min-height: 40px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 15px;
      font-weight: 700;
      background: var(--kb-brown);
      color: #fff;
    }
    .btn-excel-export:hover { background: var(--kb-brown-dark); }
    .btn-excel-export:disabled { opacity: 0.6; cursor: not-allowed; }
    .excel-save-path {
      margin: 8px 0 0;
      font-size: 13px;
      font-weight: 600;
      color: var(--kb-brown-darker);
      word-break: break-all;
      flex-basis: 100%;
    }
    .btn-report-export {
      border: 0;
      padding: 10px 18px;
      min-height: 40px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 15px;
      font-weight: 700;
      background: var(--kb-brown-dark);
      color: #fff;
    }
    .btn-report-export:hover { background: var(--kb-brown-darker); }
    .btn-report-export:disabled { opacity: 0.6; cursor: not-allowed; }
    .btn-chart-generate {
      border: 0;
      padding: 10px 18px;
      min-height: 40px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 15px;
      font-weight: 800;
      background: var(--kb-yellow);
      color: var(--kb-brown-darker);
    }
    .btn-chart-generate:hover { background: var(--kb-yellow-dark); }
    .btn-chart-generate:disabled { opacity: 0.6; cursor: not-allowed; }
    .report-save-path {
      margin: 8px 0 0;
      font-size: 13px;
      font-weight: 600;
      color: var(--kb-brown-darker);
      word-break: break-all;
      flex-basis: 100%;
    }
    .chart-canvas-wrap {
      position: relative;
      width: 100%;
      height: 320px;
    }
    .pdf-link-wrap {
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px dashed #cbd5e1;
    }
    .pdf-link {
      display: inline-block;
      font-size: 15px;
      font-weight: 700;
      color: var(--kb-brown-darker);
      word-break: break-all;
    }
    .inst1-table-block { margin-top: 12px; overflow-x: auto; }
    .inst1-sql-block { margin-top: 10px; }
    .inst1-sql-label {
      font-size: 14px;
      font-weight: 800;
      color: var(--kb-brown-darker);
      margin: 0 0 6px;
    }
    .inst1-sql {
      margin: 0;
      padding: 10px 12px;
      background: var(--kb-brown-darker);
      color: #f1f5f9;
      border-radius: 8px;
      font-size: 13px;
      line-height: 1.55;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-all;
    }
    .inst1-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
      color: var(--kb-text);
    }
    .inst1-table th, .inst1-table td {
      border: 1px solid #bfb09c;
      padding: 9px 11px;
      text-align: left;
      white-space: nowrap;
    }
    .inst1-table th {
      background: var(--kb-yellow-light);
      font-weight: 700;
      color: var(--kb-brown-darker);
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <h1>KB AI 데이터 리터러시</h1>
        <p>그룹고객 데이터 분석 채팅</p>
      </div>
      <div class="sidebar-body">
        <section class="sidebar-section">
          <p class="sidebar-section-title">추천질문</p>
          <p class="prompt-chip">26.04월 그룹고객기본정보의 KB스타클럽그룹최고등급별, 성별구분별 고객수 집계해줘</p>
          <p class="prompt-chip">26.04월 그룹고객기본정보, 그룹고객거래기본의 연령코드별, 거래기간구분별 고객수 집계해줘</p>
        </section>
        <section class="sidebar-section">
          <p class="sidebar-section-title">분석가능 테이블</p>
          {% for item in inst1_tables %}
          <p class="table-chip" data-table="{{ item.table }}">{{ item.label }}</p>
          {% endfor %}
        </section>
      </div>
      {% if member %}
      <div class="sidebar-footer">
        <div class="member-card">
          <strong>{{ member.회원명 }} ({{ member.아이디 }})</strong>
          {% if member.부서명 %}<span class="meta">{{ member.부서명 }}</span>{% endif %}
          {% if member.이메일 %}<span class="meta">{{ member.이메일 }}</span>{% endif %}
          <a class="logout" href="{{ url_for('logout') }}">로그아웃</a>
        </div>
      </div>
      {% endif %}
    </aside>

    <main class="main">
      <div class="main-alerts">
        {% if not db_configured %}
        <div class="banner banner-warn">
          <strong>DB 미연결:</strong> <code>AURORA_DB_URL</code> 설정이 필요합니다.
        </div>
        {% endif %}
        {% if not aws_configured %}
        <div class="banner banner-err">
          <strong>AI 미설정:</strong> AWS 자격 증명이 필요합니다.
        </div>
        {% endif %}
      </div>

      <section class="chat-panel">
        <div class="chat-box" id="chatBox" role="log" aria-live="polite"></div>
        <div class="composer">
          <form id="chatForm" action="#" method="post" onsubmit="return false;">
            <div class="composer-input-row">
              <textarea id="messageInput" name="message" rows="2"
                placeholder="질문을 입력하세요 (Enter 전송, Shift+Enter 줄바꿈)" required
                autocomplete="off"></textarea>
              <div class="composer-actions">
                <button type="button" id="sendBtn" onclick="window.cultureSend && window.cultureSend()">질문</button>
                <a class="btn btn-secondary" href="{{ url_for('clear_chat') }}">비우기</a>
              </div>
            </div>
          </form>
          <p class="status-line" id="statusLine"></p>
          <div class="notice" id="chatNotice" style="display:none;"></div>
        </div>
      </section>
    </main>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <script src="/static/culture_chat.js?v=50"></script>
  <script>
    document.addEventListener("DOMContentLoaded", function () {
      if (window.CultureChat) {
        CultureChat.init({
          history: {{ chat_history | tojson }},
          preferStream: false,
          inst1Tables: {{ inst1_tables | tojson }},
        });
      } else {
        console.error("culture_chat.js 로드 실패");
      }
    });
  </script>
</body>
</html>
"""


@app.route("/static/<path:filename>")
def static_files(filename: str):
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return send_from_directory(static_dir, filename)


@app.route("/api/export/excel", methods=["POST"])
def export_excel_api():
    """차트·집계 조회 데이터를 엑셀(.xlsx)로 다운로드 + culture/exports 저장."""
    data = request.get_json(silent=True) or {}
    export = data.get("export") if isinstance(data.get("export"), dict) else data
    if not isinstance(export, dict) or not export_has_data(export):
        return jsonify({"ok": False, "error": "저장할 데이터가 없습니다."}), 400
    try:
        content = build_excel_bytes(export)
        if len(content) < 100:
            raise ValueError("생성된 엑셀 파일이 비어 있습니다.")
        filename = str(export.get("filename") or "culture_export.xlsx")
        if not filename.lower().endswith(".xlsx"):
            filename += ".xlsx"
        # ASCII 파일명만 사용 (한글 파일명은 Windows 다운로드 실패 원인)
        filename = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "culture_export.xlsx"
        saved_path = save_excel_to_disk(content, filename)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    buf = BytesIO(content)
    buf.seek(0)
    resp = send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=saved_path.name if saved_path else filename,
    )
    if saved_path:
        resp.headers["X-Saved-Path"] = str(saved_path)
        resp.headers["Access-Control-Expose-Headers"] = "X-Saved-Path"
    return resp


@app.route("/api/export/report", methods=["POST"])
def export_report_api():
    """차트·요약 에이전트 응답 → PDF 보고서 다운로드 + culture/reports 저장."""
    data = request.get_json(silent=True) or {}
    report = data.get("report") if isinstance(data.get("report"), dict) else data
    if not isinstance(report, dict) or not report_has_data(report):
        return jsonify({"ok": False, "error": "보고서로 저장할 내용이 없습니다."}), 400
    try:
        content = build_agent_report_pdf_bytes(report)
        if len(content) < 100:
            raise ValueError("생성된 PDF 파일이 비어 있습니다.")
        filename = str(report.get("filename") or "culture_report.pdf")
        filename = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "culture_report.pdf"
        saved_path = save_report_to_disk(content, filename)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    buf = BytesIO(content)
    buf.seek(0)
    resp = send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=saved_path.name if saved_path else filename,
    )
    if saved_path:
        resp.headers["X-Saved-Path"] = str(saved_path)
        resp.headers["Access-Control-Expose-Headers"] = "X-Saved-Path"
    return resp


@app.route("/api/generate/chart", methods=["POST"])
def generate_chart_api():
    """세션 pending_chart 기반 막대 차트 생성."""
    ensure_session_lists()
    pending = session.get("pending_chart") or {}
    if not pending.get("rows"):
        return jsonify(
            {"ok": False, "error": "차트로 그릴 집계 데이터가 없습니다. 먼저 집계 데이터를 조회해 주세요."}
        ), 400
    try:
        specs = build_aggregate_chart_specs(pending)
        if not specs:
            raise ValueError("차트 데이터가 비어 있습니다.")
        display = pending.get("display_label") or "집계 데이터"
        analysis = {"intent": "inst1_chart", "reason": "집계 데이터 차트 생성"}
        text = format_chart_agent_reply(analysis, pending, specs)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    history = list(session.get("chat_history", []))
    for i in range(len(history) - 1, -1, -1):
        item = history[i]
        if item.get("role") == "assistant" and item.get("chart_available"):
            item["charts"] = specs
            item["chart_available"] = False
            history[i] = item
            break
    session["chat_history"] = history
    session.pop("pending_chart", None)
    session.modified = True

    return jsonify(
        {
            "ok": True,
            "charts": specs,
            "reply": text,
        }
    )


@app.route("/api/chat", methods=["POST"])
def chat_api():
    """동기 JSON 채팅 (스트리밍 실패 시 폴백·안정 응답)."""
    ensure_session_lists()
    data = request.get_json(silent=True) or {}
    raw = (data.get("message") or "").strip()
    table_name = (data.get("table_name") or "").strip() or None
    if not raw:
        return jsonify({"ok": False, "error": "message required"}), 400

    history = list(session.get("chat_history", []))
    history.append({"role": "user", "content": raw})
    try:
        (
            reply,
            notice,
            charts,
            pdf_url,
            inst1_data,
            inst1_column_orders,
            inst1_result_labels,
            inst1_queries,
            follow_up_questions,
            excel_export,
            report_export,
            chart_available,
            aggregate_column_options,
            aggregate_column_label,
            aggregate_column_pick_mode,
            schema_pipeline_notice,
        ) = run_chat(
            raw, history, table_name=table_name
        )
        if not reply.strip():
            reply = "(모델이 빈 응답을 반환했습니다.)"
        history.append(
            {
                "role": "assistant",
                "content": reply,
                "charts": charts,
                "pdf_url": pdf_url,
                "inst1_data": inst1_data,
                "inst1_column_orders": inst1_column_orders,
                "inst1_result_labels": inst1_result_labels,
                "inst1_queries": inst1_queries,
                "follow_up_questions": follow_up_questions,
                "aggregate_column_options": aggregate_column_options,
                "aggregate_column_label": aggregate_column_label,
                "aggregate_column_pick_mode": aggregate_column_pick_mode,
                "excel_export": excel_export,
                "report_export": report_export,
                "chart_available": chart_available,
                "schema_pipeline_notice": schema_pipeline_notice,
            }
        )
        session["chat_history"] = history
        session.modified = True
        return jsonify(
            {
                "ok": True,
                "reply": reply,
                "notice": notice or "",
                "schema_pipeline_notice": schema_pipeline_notice,
                "charts": charts,
                "pdf_url": pdf_url,
                "inst1_data": inst1_data,
                "inst1_column_orders": inst1_column_orders,
                "inst1_result_labels": inst1_result_labels,
                "inst1_queries": inst1_queries,
                "follow_up_questions": follow_up_questions,
                "aggregate_column_options": aggregate_column_options,
                "aggregate_column_label": aggregate_column_label,
                "aggregate_column_pick_mode": aggregate_column_pick_mode,
                "excel_export": excel_export,
                "report_export": report_export,
                "chart_available": chart_available,
            }
        )
    except Exception as e:
        err = format_aws_error(e)
        history.append({"role": "assistant", "content": f"(처리 실패: {err})"})
        session["chat_history"] = history
        session.modified = True
        return jsonify({"ok": False, "error": err}), 500


def _ensure_members_for_login() -> None:
    """로그인 전 회원 테이블만 준비 (실패해도 로그인 화면은 유지)."""
    global _members_initialized
    if _members_initialized or not db_configured():
        return
    if os.environ.get("VERCEL"):
        return
    with _db_init_lock:
        if _members_initialized:
            return
        try:
            with get_conn() as conn:
                setup_members(conn, seed=True, force_seed=False)
                conn.commit()
                _members_initialized = True
        except Exception:
            app.logger.exception("회원 테이블 초기화 실패 (로그인은 계속 가능)")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if is_logged_in():
            return redirect(url_for("index"))
        return redirect(url_for("index", next=request.args.get("next")))

    if is_logged_in():
        return redirect(url_for("index"))

    next_url = (request.form.get("next") or "/").strip()
    member_id = (request.form.get("member_id") or "").strip()
    password = request.form.get("password") or ""
    if not member_id or not password:
        return render_login_page(
            error="아이디와 비밀번호를 입력하세요.",
            next_url=next_url,
        ), 400

    if not db_configured():
        return render_login_page(
            error="회원 DB(AURORA_DB_URL)가 설정되지 않았습니다.",
            next_url=next_url,
        ), 503

    _ensure_members_for_login()
    try:
        with get_conn() as conn:
            member = authenticate_member(conn, member_id, password)
    except Exception as e:
        app.logger.exception("로그인 DB 오류")
        detail = str(e).strip()
        if len(detail) > 120:
            detail = detail[:117] + "..."
        if "connection to database not available" in detail.lower():
            user_msg = (
                "회원 DB(Aurora)에 연결할 수 없습니다. "
                "AURORA_DB_URL과 네트워크/보안 그룹 설정을 확인하세요."
            )
        elif os.environ.get("VERCEL") and "timeout" in detail.lower():
            user_msg = (
                "회원 DB 연결 시간이 초과되었습니다. "
                "Aurora 보안 그룹에 Vercel 접속 IP 허용이 필요할 수 있습니다."
            )
        else:
            hint = (
                f" ({detail})"
                if os.environ.get("CULTURE_DEBUG") == "1" and detail
                else ""
            )
            user_msg = f"로그인 처리 중 오류: {type(e).__name__}{hint}"
        return render_login_page(
            error=user_msg,
            next_url=next_url,
        ), 500

    if not member:
        return render_login_page(
            error="아이디 또는 비밀번호가 올바르지 않습니다.",
            next_url=next_url,
        ), 401

    login_member(member)
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/"
    return redirect(next_url)


@app.route("/logout")
def logout():
    logout_member()
    return redirect(url_for("index"))


def reset_chat_session() -> None:
    session["chat_history"] = []
    session.pop("chat_notice", None)
    session.pop("pending_aggregate", None)
    session.pop("pending_chart", None)
    session["app_boot_id"] = APP_BOOT_ID
    session.modified = True


def _sync_pending_chart_session(session_obj, final: dict[str, Any]) -> None:
    if "pending_chart" in final:
        pending = final.get("pending_chart") or {}
        if pending:
            session_obj["pending_chart"] = pending
        else:
            session_obj.pop("pending_chart", None)
        return
    if (final.get("question_analysis") or {}).get("intent") == "inst1_chart":
        session_obj.pop("pending_chart", None)


def _sync_pending_aggregate_session(session_obj, final: dict[str, Any]) -> None:
    if "pending_aggregate" in final:
        pending = final.get("pending_aggregate") or {}
        if pending:
            session_obj["pending_aggregate"] = pending
        else:
            session_obj.pop("pending_aggregate", None)
        return
    analysis = final.get("question_analysis") or {}
    if (
        analysis.get("intent") == "inst1_extract"
        and analysis.get("query_type") == "aggregate"
    ):
        session_obj.pop("pending_aggregate", None)


@app.route("/", methods=["GET"])
def index():
    if not is_logged_in():
        next_url = (request.args.get("next") or "/").strip()
        return render_login_page(next_url=next_url)

    reset_chat_session()
    return render_template_string(
        PAGE,
        chat_history=[],
        table_name=TABLE_NAME,
        inst1_tables=inst1_schema_table_display_items(),
        db_configured=db_configured(),
        aws_configured=aws_credentials_configured(),
        member=current_member(),
    )


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """SSE — LangGraph 노드 진행 상태 + 최종 reply."""
    ensure_session_lists()
    data = request.get_json(silent=True) or {}
    raw = (data.get("message") or "").strip()
    table_name = (data.get("table_name") or "").strip() or None
    if not raw:
        return jsonify({"ok": False, "error": "message required"}), 400

    history = list(session.get("chat_history", []))
    history.append({"role": "user", "content": raw})
    session["chat_history"] = history
    session.modified = True

    def generate():
        try:
            executor = get_executor()
            initial: dict[str, Any] = {
                "user_message": raw,
                "table_name": (table_name or "").strip(),
                "history": history,
                "summary": "",
                "reply": "",
                "notice": "",
                "error": "",
                "question_analysis": {},
                "inst1_data": {},
                "inst1_column_orders": {},
                "inst1_result_labels": {},
                "inst1_queries": {},
                "extract_tables": [],
                "pending_aggregate": session.get("pending_aggregate") or {},
                "pending_chart": session.get("pending_chart") or {},
                "chart_specs": [],
                "chart_available": False,
                "schema_pipeline_notice": "",
            }
            final: dict[str, Any] = {}
            for chunk in executor.stream(initial, stream_mode="updates"):
                for node_name, update in chunk.items():
                    if node_name == "analyze" and isinstance(update, dict):
                        pipe_notice = (update.get("schema_pipeline_notice") or "").strip()
                        if pipe_notice:
                            yield _sse_event(
                                {
                                    "type": "status",
                                    "text": pipe_notice,
                                    "schema_pipeline": True,
                                }
                            )
                            yield _sse_pad()
                    yield _sse_event(build_workflow_status_event(node_name))
                    yield _sse_pad()
                    if isinstance(update, dict):
                        final.update(update)

            if not final.get("reply"):
                final = executor.invoke(initial)

            full_text = (final.get("reply") or "").strip()
            if not full_text:
                full_text = "(모델이 빈 응답을 반환했습니다.)"
            notice = final.get("notice") or ""
            schema_pipeline_notice = (final.get("schema_pipeline_notice") or "").strip()
            charts = list(final.get("chart_specs") or [])
            pdf_url = (final.get("pdf_url") or "").strip()
            inst1_data = mask_inst1_data_for_display(dict(final.get("inst1_data") or {}))
            inst1_column_orders = dict(final.get("inst1_column_orders") or {})
            inst1_result_labels = dict(final.get("inst1_result_labels") or {})
            inst1_queries = dict(final.get("inst1_queries") or {})
            follow_up_questions = list(final.get("follow_up_questions") or [])
            aggregate_column_options = list(final.get("aggregate_column_options") or [])
            aggregate_column_label = (final.get("aggregate_column_label") or "").strip()
            aggregate_column_pick_mode = (
                final.get("aggregate_column_pick_mode") or "append"
            ).strip()
            excel_export = mask_excel_export_for_display(dict(final.get("excel_export") or {}))
            report_export = _client_report_export(dict(final.get("report_export") or {}))
            _sync_pending_aggregate_session(session, final)
            _sync_pending_chart_session(session, final)
            chart_available = _chart_available_from_final(final)
            history.append(
                {
                    "role": "assistant",
                    "content": full_text,
                    "charts": charts,
                    "pdf_url": pdf_url,
                    "inst1_data": inst1_data,
                    "inst1_column_orders": inst1_column_orders,
                    "inst1_result_labels": inst1_result_labels,
                    "inst1_queries": inst1_queries,
                    "follow_up_questions": follow_up_questions,
                    "aggregate_column_options": aggregate_column_options,
                    "aggregate_column_label": aggregate_column_label,
                    "aggregate_column_pick_mode": aggregate_column_pick_mode,
                    "excel_export": excel_export,
                    "report_export": report_export,
                    "chart_available": chart_available,
                    "schema_pipeline_notice": schema_pipeline_notice,
                }
            )
            session["chat_history"] = history
            session.modified = True
            yield _sse_event({"type": "chunk", "text": full_text})
            yield _sse_pad()
            yield _sse_event(
                {
                    "type": "done",
                    "text": full_text,
                    "notice": notice,
                    "schema_pipeline_notice": schema_pipeline_notice,
                    "charts": charts,
                    "pdf_url": pdf_url,
                    "inst1_data": inst1_data,
                    "inst1_column_orders": inst1_column_orders,
                    "inst1_result_labels": inst1_result_labels,
                    "inst1_queries": inst1_queries,
                    "follow_up_questions": follow_up_questions,
                    "aggregate_column_options": aggregate_column_options,
                    "aggregate_column_label": aggregate_column_label,
                    "aggregate_column_pick_mode": aggregate_column_pick_mode,
                    "excel_export": excel_export,
                    "report_export": report_export,
                    "chart_available": chart_available,
                }
            )
        except Exception as e:
            err = format_aws_error(e)
            history.append({"role": "assistant", "content": f"(처리 실패: {err})"})
            session["chat_history"] = history
            session.modified = True
            yield _sse_event({"type": "error", "text": err})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/clear-chat")
def clear_chat():
    reset_chat_session()
    return redirect(url_for("index"))


@app.route("/api/health", methods=["GET"])
def api_health():
    out: dict = {
        "ok": True,
        "app": "culture",
        "has_db_url": db_configured(),
        "db_backend": culture_db_backend(),
        "aws_ready_for_bedrock": aws_credentials_configured(),
        "has_aws_session_token": aws_session_token_configured(),
        "aws_session_token_env": aws_session_token_env_name(),
        "bedrock_region": bedrock_region(),
        "bedrock_model_id": get_model_id(),
        "workflow": "langgraph",
        "nodes": [
            "analyze",
            "table_prompt",
            "aggregate_prompt",
            "column_desc",
            "data_summary",
            "chart",
            "fetch_inst1",
            "format_inst1",
            "general",
            "reply",
        ],
        "s3_configured": s3_configured(),
        "member_table": MEMBER_TABLE_NAME,
    }
    try:
        from schema_vector.config import opensearch_index, schema_vector_enabled

        out["schema_vector_enabled"] = schema_vector_enabled()
        if schema_vector_enabled():
            out["opensearch_index"] = opensearch_index()
    except Exception:
        out["schema_vector_enabled"] = False
    if db_configured():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(f'SELECT COUNT(*) FROM public."{MEMBER_TABLE_NAME}"')
                    out["member_count"] = cur.fetchone()[0]
        except Exception as e:
            out["member_count"] = None
            out["member_error"] = f"{type(e).__name__}: {e}"
    if request.args.get("db") == "1" and db_configured():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                    cur.execute(f'SELECT COUNT(*) FROM public."{TABLE_NAME}"')
                    out["table_row_count"] = cur.fetchone()[0]
                    out["table_name"] = TABLE_NAME
            out["db_ok"] = True
        except Exception as e:
            out["db_ok"] = False
            out["db_error"] = f"{type(e).__name__}: {e}"
    return jsonify(out)


if __name__ == "__main__":
    host = os.environ.get("CULTURE_HOST", "127.0.0.1")
    env_port = os.environ.get("CULTURE_PORT", "5051").strip()
    port = int(env_port) if env_port.isdigit() else 5051
    print(f"\n[KB AI 데이터 리터러시] http://{host}:{port}\n", flush=True)
    app.run(host=host, port=port, debug=False, threaded=True)
