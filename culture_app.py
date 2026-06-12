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
from supabase.members_auth import authenticate_member
from supabase.members_setup import setup_members
from supabase.table_config import (
    MEMBER_TABLE_NAME,
    TABLE_NAME,
    inst1_schema_table_display_items,
)
from supabase.tshdeoa01_setup import ensure_tshdeoa01_table
from supabase.tshdeoa02_setup import ensure_tshdeoa02_table
from supabase.tshde0zcd_setup import ensure_tshde0zcd_table

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
_tshde0zcd_initialized = False
APP_BOOT_ID = uuid.uuid4().hex


def get_db_url() -> str:
    global _db_url_cache
    if _db_url_cache is not None:
        return _db_url_cache
    raw = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not raw:
        raise RuntimeError("`SUPABASE_DB_URL` 환경 변수를 설정해야 합니다.")
    if "sslmode=" not in raw:
        raw = raw + ("&" if "?" in raw else "?") + "sslmode=require"
    _db_url_cache = raw
    return _db_url_cache


def supabase_configured() -> bool:
    return bool(os.environ.get("SUPABASE_DB_URL", "").strip())


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
def ensure_supabase_tables_ready():
    global _tchdhc001_initialized, _members_initialized
    global _tshdeoa01_initialized, _tshdeoa02_initialized, _tshde0zcd_initialized
    if request.endpoint in ("api_health", "static_files"):
        return
    if request.endpoint == "index" and request.method == "GET" and not is_logged_in():
        return
    if request.endpoint == "login" and request.method == "GET":
        return
    if os.environ.get("VERCEL"):
        return
    if not supabase_configured():
        return
    if (
        _tchdhc001_initialized
        and _members_initialized
        and _tshdeoa01_initialized
        and _tshdeoa02_initialized
        and _tshde0zcd_initialized
    ):
        return
    with _db_init_lock:
        if (
            _tchdhc001_initialized
            and _members_initialized
            and _tshdeoa01_initialized
            and _tshdeoa02_initialized
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
                    ensure_tshdeoa01_table(conn)
                    _tshdeoa01_initialized = True
                if not _tshdeoa02_initialized:
                    ensure_tshdeoa02_table(conn)
                    _tshdeoa02_initialized = True
                if not _tshde0zcd_initialized:
                    ensure_tshde0zcd_table(conn)
                    _tshde0zcd_initialized = True
                conn.commit()
        except Exception:
            app.logger.exception("Supabase 테이블 초기화 실패")
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
    return psycopg2.connect(get_db_url(), connect_timeout=15)


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
    inst1_data = dict(final.get("inst1_data") or {})
    inst1_column_orders = dict(final.get("inst1_column_orders") or {})
    inst1_result_labels = dict(final.get("inst1_result_labels") or {})
    inst1_queries = dict(final.get("inst1_queries") or {})
    follow_up_questions = list(final.get("follow_up_questions") or [])
    excel_export = dict(final.get("excel_export") or {})
    report_export = dict(final.get("report_export") or {})
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
  <meta name="theme-color" content="#7c3aed" />
  <title>KB AI 데이터 리터러시 — 로그인</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100dvh;
      font-family: system-ui, -apple-system, 'Malgun Gothic', 'Noto Sans KR', sans-serif;
      background: linear-gradient(160deg, #f5f3ff 0%, #ede9fe 40%, #f0f4f8 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }
    .card {
      width: 100%;
      max-width: 400px;
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 4px 24px rgba(124, 58, 237, 0.15);
      padding: 28px 24px;
    }
    h1 { margin: 0 0 6px; font-size: 1.4rem; color: #5b21b6; }
    .sub { color: #64748b; font-size: 14px; margin: 0 0 20px; }
    label { display: block; font-size: 14px; font-weight: 600; color: #334155; margin-bottom: 6px; }
    input {
      width: 100%;
      padding: 12px 14px;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      font-size: 16px;
      margin-bottom: 14px;
    }
    input:focus { outline: 2px solid #a78bfa; border-color: #7c3aed; }
    button {
      width: 100%;
      border: 0;
      padding: 14px;
      border-radius: 12px;
      background: #7c3aed;
      color: #fff;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      margin-top: 4px;
    }
    button:active { background: #5b21b6; }
    .error {
      background: #fee2e2;
      color: #991b1b;
      border: 1px solid #fecaca;
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 14px;
      margin-bottom: 14px;
    }
    .hint { font-size: 12px; color: #94a3b8; margin-top: 16px; line-height: 1.5; }
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
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5, viewport-fit=cover" />
  <meta name="theme-color" content="#7c3aed" />
  <meta name="mobile-web-app-capable" content="yes" />
  <meta name="format-detection" content="telephone=no" />
  <title>KB AI 데이터 리터러시</title>
  <style>
    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
    html {
      -webkit-text-size-adjust: 100%;
      text-size-adjust: 100%;
    }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, 'Segoe UI', 'Malgun Gothic', 'Noto Sans KR', sans-serif;
      background: linear-gradient(160deg, #f5f3ff 0%, #ede9fe 40%, #f0f4f8 100%);
      min-height: 100dvh;
      min-height: 100vh;
      padding: max(12px, env(safe-area-inset-top, 0px))
               max(12px, env(safe-area-inset-right, 0px))
               max(12px, env(safe-area-inset-bottom, 0px))
               max(12px, env(safe-area-inset-left, 0px));
    }
    .page-wrap {
      max-width: 720px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: calc(100dvh - 24px);
      min-height: calc(100vh - 24px);
    }
    .banner {
      padding: 12px 14px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.55;
      word-break: keep-all;
      overflow-wrap: break-word;
    }
    .banner-warn { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
    .banner-err { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
    .panel {
      flex: 1;
      display: flex;
      flex-direction: column;
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 4px 24px rgba(124, 58, 237, 0.12);
      padding: 16px;
      min-height: 0;
    }
    .panel-header { flex-shrink: 0; }
    h1 {
      margin: 0 0 4px;
      font-size: clamp(1.15rem, 4.5vw, 1.35rem);
      color: #5b21b6;
      letter-spacing: -0.02em;
    }
    .sub {
      color: #64748b;
      font-size: clamp(13px, 3.6vw, 14px);
      margin: 0;
      line-height: 1.55;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }
    .sub em { font-style: normal; color: #475569; }
    .suggested-prompts {
      margin-top: 10px;
      padding: 10px 12px;
      background: #f5f3ff;
      border: 1px solid #ddd6fe;
      border-radius: 10px;
      font-size: 13px;
      color: #4c1d95;
      line-height: 1.55;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }
    .suggested-prompts .suggested-label {
      margin: 0 0 8px;
      font-size: 13px;
      font-weight: 700;
      color: #5b21b6;
    }
    .suggested-prompts .suggested-item {
      margin: 0;
      color: #475569;
      font-size: clamp(13px, 3.6vw, 14px);
    }
    .suggested-prompts .suggested-item + .suggested-item {
      margin-top: 6px;
    }
    .inst1-tables {
      margin-top: 8px;
    }
    .chat-box {
      flex: 1;
      min-height: 200px;
      max-height: none;
      overflow-y: auto;
      overflow-x: hidden;
      -webkit-overflow-scrolling: touch;
      overscroll-behavior: contain;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 10px;
      margin: 12px 0 0;
      background: #fafafa;
      scroll-padding-bottom: 12px;
    }
    .msg {
      padding: 12px 14px;
      border-radius: 14px;
      margin-bottom: 10px;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-wrap: anywhere;
      line-height: 1.6;
      font-size: 16px;
      max-width: 100%;
    }
    .msg.user {
      background: #ede9fe;
      margin-left: clamp(0px, 4vw, 20px);
      border-bottom-right-radius: 4px;
    }
    .msg.assistant {
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      margin-right: clamp(0px, 4vw, 20px);
      border-bottom-left-radius: 4px;
    }
    .composer {
      flex-shrink: 0;
      padding-top: 8px;
      padding-bottom: max(4px, env(safe-area-inset-bottom, 0px));
      background: #fff;
      border-top: 1px solid #f1f5f9;
      margin: 0 -4px;
      padding-left: 4px;
      padding-right: 4px;
    }
    textarea {
      width: 100%;
      min-height: 52px;
      max-height: 140px;
      resize: none;
      padding: 14px 14px;
      border-radius: 12px;
      border: 1px solid #cbd5e1;
      font-family: inherit;
      font-size: 16px;
      line-height: 1.5;
      -webkit-appearance: none;
      appearance: none;
    }
    textarea:focus {
      outline: 2px solid #a78bfa;
      outline-offset: 1px;
      border-color: #7c3aed;
    }
    .row {
      margin-top: 10px;
      display: flex;
      gap: 10px;
      align-items: stretch;
    }
    button, .btn {
      border: 0;
      padding: 14px 18px;
      min-height: 48px;
      border-radius: 12px;
      cursor: pointer;
      font-size: 16px;
      font-weight: 600;
      text-decoration: none;
      text-align: center;
      touch-action: manipulation;
      -webkit-user-select: none;
      user-select: none;
    }
    button {
      flex: 1;
      background: #7c3aed;
      color: #fff;
    }
    button:active { background: #5b21b6; }
    .btn-secondary {
      flex: 0 0 auto;
      min-width: 108px;
      background: #64748b;
      color: #fff;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .btn-secondary:active { background: #475569; }
    .notice { color: #059669; font-size: 14px; margin-top: 8px; font-weight: 600; }
    .msg.assistant.streaming { border-color: #86efac; }
    .msg.assistant.streaming::after {
      content: "▋";
      animation: blink 1s step-end infinite;
      margin-left: 2px;
      color: #16a34a;
    }
    @keyframes blink { 50% { opacity: 0; } }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .status-line {
      font-size: 13px;
      color: #64748b;
      margin: 6px 0 0;
      min-height: 1.2em;
      line-height: 1.4;
    }
    .chat-hint {
      color: #94a3b8;
      font-size: 15px;
      line-height: 1.55;
      margin: 0;
      padding: 8px 4px;
    }
    .msg-text { white-space: pre-wrap; word-break: break-word; }
    .msg-follow-up {
      margin-top: 14px;
      padding: 12px 14px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
    }
    .msg-follow-up .follow-up-label {
      font-size: 13px;
      font-weight: 700;
      color: #475569;
      margin: 0 0 8px;
    }
    .msg-follow-up .follow-up-item {
      font-size: 14px;
      color: #1e293b;
      margin: 0;
      line-height: 1.5;
    }
    .msg-follow-up .follow-up-item + .follow-up-item { margin-top: 6px; }
    .chart-block {
      margin-top: 14px;
      padding: 12px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
    }
    .chart-title {
      font-size: 13px;
      font-weight: 700;
      color: #475569;
      margin: 0 0 8px;
    }
    .excel-export-wrap {
      margin-top: 14px;
      padding: 10px 12px;
      background: #f0fdf4;
      border: 1px solid #86efac;
      border-radius: 12px;
    }
    .btn-excel-export {
      border: 0;
      padding: 10px 18px;
      min-height: 40px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 600;
      background: #16a34a;
      color: #fff;
      touch-action: manipulation;
    }
    .btn-excel-export:active { background: #15803d; }
    .btn-excel-export:disabled { opacity: 0.6; cursor: not-allowed; }
    .excel-save-path {
      margin: 8px 0 0;
      font-size: 12px;
      color: #166534;
      word-break: break-all;
      line-height: 1.4;
    }
    .report-export-wrap {
      margin-top: 10px;
      padding: 10px 12px;
      background: #eff6ff;
      border: 1px solid #93c5fd;
      border-radius: 12px;
    }
    .btn-report-export {
      border: 0;
      padding: 10px 18px;
      min-height: 40px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 600;
      background: #2563eb;
      color: #fff;
      touch-action: manipulation;
    }
    .btn-report-export:active { background: #1d4ed8; }
    .btn-report-export:disabled { opacity: 0.6; cursor: not-allowed; }
    .report-save-path {
      margin: 8px 0 0;
      font-size: 12px;
      color: #1e40af;
      word-break: break-all;
      line-height: 1.4;
    }
    .chart-canvas-wrap {
      position: relative;
      width: 100%;
      height: min(280px, 42vh);
    }
    .pdf-link-wrap {
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px dashed #cbd5e1;
    }
    .pdf-link {
      display: inline-block;
      font-size: 14px;
      font-weight: 600;
      color: #6d28d9;
      word-break: break-all;
    }
    .inst1-table-block {
      margin-top: 12px;
      overflow-x: auto;
    }
    .inst1-sql-block {
      margin-top: 10px;
    }
    .inst1-sql-label {
      font-size: 12px;
      font-weight: 700;
      color: #475569;
      margin: 0 0 6px;
    }
    .inst1-sql {
      margin: 0;
      padding: 10px 12px;
      background: #0f172a;
      color: #e2e8f0;
      border-radius: 8px;
      font-size: 12px;
      line-height: 1.5;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-all;
    }
    .inst1-table-wrap { max-width: 100%; }
    .inst1-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    .inst1-table th, .inst1-table td {
      border: 1px solid #e2e8f0;
      padding: 6px 8px;
      text-align: left;
      white-space: nowrap;
    }
    .inst1-table th {
      background: #f1f5f9;
      font-weight: 700;
    }
    .member-bar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 12px;
      margin-top: 10px;
      padding: 10px 12px;
      background: #f5f3ff;
      border: 1px solid #ddd6fe;
      border-radius: 10px;
      font-size: 13px;
      color: #4c1d95;
    }
    .member-bar strong { font-weight: 700; }
    .member-bar .meta { color: #64748b; }
    .member-bar .logout {
      margin-left: auto;
      font-size: 13px;
      font-weight: 600;
      color: #6d28d9;
      text-decoration: none;
      padding: 6px 10px;
      border-radius: 8px;
      background: #ede9fe;
    }
    .member-bar .logout:active { background: #ddd6fe; }

    @media (max-width: 520px) {
      body {
        padding: max(8px, env(safe-area-inset-top, 0px))
                 max(8px, env(safe-area-inset-right, 0px))
                 max(8px, env(safe-area-inset-bottom, 0px))
                 max(8px, env(safe-area-inset-left, 0px));
      }
      .page-wrap {
        min-height: 100dvh;
        min-height: 100vh;
        gap: 8px;
      }
      .panel {
        border-radius: 14px 14px 0 0;
        padding: 14px 12px 10px;
        box-shadow: 0 -2px 16px rgba(124, 58, 237, 0.08);
      }
      .chat-box {
        min-height: min(42dvh, 360px);
        margin-top: 10px;
      }
      .row { gap: 8px; }
      .btn-secondary { min-width: 96px; padding-left: 12px; padding-right: 12px; }
    }

    @media (max-height: 520px) and (orientation: landscape) {
      .chat-box { min-height: 120px; max-height: 40vh; }
      textarea { min-height: 44px; }
    }
  </style>
</head>
<body>
  <div class="page-wrap">
  {% if not db_configured %}
  <div class="banner banner-warn">
    <strong>DB 미연결:</strong> <code>SUPABASE_DB_URL</code> 설정 시 요약이 동작합니다.
  </div>
  {% endif %}
  {% if not aws_configured %}
  <div class="banner banner-err">
    <strong>AI 미설정:</strong> AWS 자격 증명이 필요합니다.
  </div>
  {% endif %}
  <section class="panel">
    <header class="panel-header">
      <h1>KB AI 데이터 리터러시</h1>
      <div class="suggested-prompts">
        <p class="suggested-label">추천질문</p>
        <p class="suggested-item">26.04월 그룹고객기본정보의 KB스타클럽그룹최고등급별, 성별구분별 고객수 집계해줘</p>
        <p class="suggested-item">26.04월 그룹고객기본정보, 그룹고객거래기본의 연령코드별, 수신잔액별 고객수 집계해줘</p>
      </div>
      <div class="suggested-prompts inst1-tables">
        <p class="suggested-label">분석가능 테이블</p>
        {% for item in inst1_tables %}
        <p class="suggested-item">{{ item.label }}</p>
        {% endfor %}
      </div>
      {% if member %}
      <div class="member-bar">
        <span><strong>{{ member.회원명 }}</strong> ({{ member.아이디 }})</span>
        {% if member.부서명 %}<span class="meta">{{ member.부서명 }}</span>{% endif %}
        {% if member.이메일 %}<span class="meta">{{ member.이메일 }}</span>{% endif %}
        <a class="logout" href="{{ url_for('logout') }}">로그아웃</a>
      </div>
      {% endif %}
    </header>
    <div class="chat-box" id="chatBox" role="log" aria-live="polite"></div>
    <div class="composer">
      <form id="chatForm" action="#" method="post" onsubmit="return false;">
        <textarea id="messageInput" name="message" rows="2"
          placeholder="메시지 입력 (Enter 전송, Shift+Enter 줄바꿈)" required
          enterkeyhint="send" autocomplete="off" autocapitalize="sentences"></textarea>
        <div class="row">
          <button type="button" id="sendBtn" onclick="window.cultureSend && window.cultureSend()">전송</button>
          <a class="btn btn-secondary" href="{{ url_for('clear_chat') }}">비우기</a>
        </div>
      </form>
      <p class="status-line" id="statusLine"></p>
      <div class="notice" id="chatNotice" style="display:none;"></div>
    </div>
  </section>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <script src="/static/culture_chat.js?v=30"></script>
  <script>
    document.addEventListener("DOMContentLoaded", function () {
      if (window.CultureChat) {
        CultureChat.init({ history: {{ chat_history | tojson }}, preferStream: false });
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
        download_name=saved_path.name,
    )
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
        download_name=saved_path.name,
    )
    resp.headers["X-Saved-Path"] = str(saved_path)
    resp.headers["Access-Control-Expose-Headers"] = "X-Saved-Path"
    return resp


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
                "excel_export": excel_export,
                "report_export": report_export,
            }
        )
        session["chat_history"] = history
        session.modified = True
        return jsonify(
            {
                "ok": True,
                "reply": reply,
                "notice": notice or "",
                "charts": charts,
                "pdf_url": pdf_url,
                "inst1_data": inst1_data,
                "inst1_column_orders": inst1_column_orders,
                "inst1_result_labels": inst1_result_labels,
                "inst1_queries": inst1_queries,
                "follow_up_questions": follow_up_questions,
                "excel_export": excel_export,
                "report_export": report_export,
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
    if _members_initialized or not supabase_configured():
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

    if not supabase_configured():
        return render_login_page(
            error="회원 DB(SUPABASE_DB_URL)가 설정되지 않았습니다.",
            next_url=next_url,
        ), 503

    _ensure_members_for_login()
    try:
        with get_conn() as conn:
            member = authenticate_member(conn, member_id, password)
    except Exception as e:
        app.logger.exception("로그인 DB 오류")
        return render_login_page(
            error=f"로그인 처리 중 오류: {type(e).__name__}",
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
        db_configured=supabase_configured(),
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

    _NODE_STATUS = {
        "analyze": "질문 분석 에이전트…",
        "table_prompt": "테이블 추천 질문 생성…",
        "aggregate_prompt": "집계 컬럼 선택 안내…",
        "column_desc": "컬럼 설명 생성…",
        "data_summary": "데이터 요약 생성…",
        "chart": "집계 데이터 차트 생성…",
        "fetch_inst1": "SQL 생성 및 INST1 데이터 추출…",
        "format_inst1": "추출 결과 포맷…",
        "general": "일반 대화 응답 생성…",
        "reply": "최종 응답 조립…",
    }

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
            }
            final: dict[str, Any] = {}
            for chunk in executor.stream(initial, stream_mode="updates"):
                for node_name, update in chunk.items():
                    status = _NODE_STATUS.get(node_name, f"{node_name}…")
                    yield _sse_event({"type": "status", "text": status, "node": node_name})
                    yield _sse_pad()
                    if isinstance(update, dict):
                        final.update(update)

            if not final.get("reply"):
                final = executor.invoke(initial)

            full_text = (final.get("reply") or "").strip()
            if not full_text:
                full_text = "(모델이 빈 응답을 반환했습니다.)"
            notice = final.get("notice") or ""
            charts = list(final.get("chart_specs") or [])
            pdf_url = (final.get("pdf_url") or "").strip()
            inst1_data = dict(final.get("inst1_data") or {})
            inst1_column_orders = dict(final.get("inst1_column_orders") or {})
            inst1_result_labels = dict(final.get("inst1_result_labels") or {})
            inst1_queries = dict(final.get("inst1_queries") or {})
            follow_up_questions = list(final.get("follow_up_questions") or [])
            excel_export = dict(final.get("excel_export") or {})
            report_export = dict(final.get("report_export") or {})
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
                    "excel_export": excel_export,
                    "report_export": report_export,
                }
            )
            session["chat_history"] = history
            _sync_pending_aggregate_session(session, final)
            _sync_pending_chart_session(session, final)
            session.modified = True
            yield _sse_event({"type": "chunk", "text": full_text})
            yield _sse_pad()
            yield _sse_event(
                {
                    "type": "done",
                    "text": full_text,
                    "notice": notice,
                    "charts": charts,
                    "pdf_url": pdf_url,
                    "inst1_data": inst1_data,
                    "inst1_column_orders": inst1_column_orders,
                    "inst1_result_labels": inst1_result_labels,
                    "inst1_queries": inst1_queries,
                    "follow_up_questions": follow_up_questions,
                    "excel_export": excel_export,
                    "report_export": report_export,
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
        "has_supabase_url": supabase_configured(),
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
    if supabase_configured():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(f'SELECT COUNT(*) FROM public."{MEMBER_TABLE_NAME}"')
                    out["member_count"] = cur.fetchone()[0]
        except Exception as e:
            out["member_count"] = None
            out["member_error"] = f"{type(e).__name__}: {e}"
    if request.args.get("db") == "1" and supabase_configured():
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
