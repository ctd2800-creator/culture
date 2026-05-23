"""
Culture — AI 채팅 + LangGraph 워크플로우 (Fetch → Summarize → Reply).
"""

from __future__ import annotations

import json
import logging
import os
import threading
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

from culture_workflow import (
    aws_credentials_configured,
    aws_session_token_configured,
    aws_session_token_env_name,
    bedrock_region,
    format_aws_error,
    get_executor,
    get_model_id,
    is_summary_request,
    run_workflow,
)
from supabase.table_config import TABLE_NAME

_db_url_cache: str | None = None
_tchdhc001_init_lock = threading.Lock()
_tchdhc001_initialized = False


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
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
logging.basicConfig(level=logging.INFO)


@app.before_request
def ensure_tchdhc001_ready():
    global _tchdhc001_initialized
    if request.endpoint in ("api_health", "chat_api", "chat_stream", "static_files"):
        return
    if os.environ.get("VERCEL"):
        return
    if not supabase_configured():
        return
    if _tchdhc001_initialized:
        return
    with _tchdhc001_init_lock:
        if _tchdhc001_initialized:
            return
        try:
            ensure_tchdhc001_table()
        except Exception:
            app.logger.exception("ensure_tchdhc001_table 실패")
            raise
        _tchdhc001_initialized = True


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
        f"<p>Culture 서버 오류입니다.{hint}</p>",
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


def ensure_tchdhc001_table() -> None:
    sql_path = os.path.join(os.path.dirname(__file__), "supabase", "tchdhc001.sql")
    with open(sql_path, encoding="utf-8") as f:
        ddl = f.read()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()


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
) -> tuple[str, str | None]:
    """LangGraph Executor로 Fetch → Summarize → Reply 실행."""
    if is_summary_request(raw) and not supabase_configured():
        raise RuntimeError(
            f"{TABLE_NAME} 데이터를 조회하려면 SUPABASE_DB_URL 환경 변수가 필요합니다."
        )
    final = run_workflow(raw, table_name=table_name, history=history)
    reply = (final.get("reply") or "").strip()
    if final.get("error") and not reply:
        raise RuntimeError(final["error"])
    notice = final.get("notice") or None
    return reply, notice


def ensure_session_lists():
    if "chat_history" not in session:
        session["chat_history"] = []


PAGE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5, viewport-fit=cover" />
  <meta name="theme-color" content="#7c3aed" />
  <meta name="mobile-web-app-capable" content="yes" />
  <meta name="format-detection" content="telephone=no" />
  <title>Culture — AI 데이터 요약</title>
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
      <h1>Culture AI 채팅</h1>
      <p class="sub">
        예시 : <em>그룹멤버십계열사기초데이터검증 2026년 4월 데이터를 요약해줘</em>
      </p>
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
  <script src="/static/culture_chat.js?v=7"></script>
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
        reply, notice = run_chat(raw, history, table_name=table_name)
        if not reply.strip():
            reply = "(모델이 빈 응답을 반환했습니다.)"
        history.append({"role": "assistant", "content": reply})
        session["chat_history"] = history
        session.modified = True
        return jsonify({"ok": True, "reply": reply, "notice": notice or ""})
    except Exception as e:
        err = format_aws_error(e)
        history.append({"role": "assistant", "content": f"(처리 실패: {err})"})
        session["chat_history"] = history
        session.modified = True
        return jsonify({"ok": False, "error": err}), 500


@app.route("/", methods=["GET"])
def index():
    ensure_session_lists()
    return render_template_string(
        PAGE,
        chat_history=session.get("chat_history", []),
        table_name=TABLE_NAME,
        db_configured=supabase_configured(),
        aws_configured=aws_credentials_configured(),
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
        "parse": "요청 분석 (State: month)…",
        "fetch": "Fetch — Supabase 데이터 추출…",
        "summarize": "Summarize — Claude Sonnet 3.5 요약…",
        "general": "일반 대화 응답 생성…",
        "reply": "Reply — 최종 응답 조립…",
    }

    def generate():
        try:
            executor = get_executor()
            initial: dict[str, Any] = {
                "user_message": raw,
                "table_name": (table_name or "").strip(),
                "history": history,
                "raw_data": [],
                "summary": "",
                "reply": "",
                "notice": "",
                "error": "",
                "needs_input": False,
            }
            if is_summary_request(raw) and not supabase_configured():
                raise RuntimeError(
                    f"{TABLE_NAME} 조회에 SUPABASE_DB_URL이 필요합니다."
                )

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
            history.append({"role": "assistant", "content": full_text})
            session["chat_history"] = history
            session.modified = True
            yield _sse_event({"type": "chunk", "text": full_text})
            yield _sse_pad()
            yield _sse_event({"type": "done", "text": full_text, "notice": notice})
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
    session["chat_history"] = []
    session.pop("chat_notice", None)
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
        "nodes": ["parse", "fetch", "summarize", "reply", "general"],
    }
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
    print(f"\n[Culture] http://{host}:{port}\n", flush=True)
    app.run(host=host, port=port, debug=False, threaded=True)
