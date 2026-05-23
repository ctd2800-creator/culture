"""요약 응답 PDF 생성 및 S3 업로드."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import boto3
from fpdf import FPDF

from culture_workflow import format_yyyymm

# matplotlib는 PDF 차트 렌더 시에만 로드 (서버리스 콜드스타트 완화)
_MPL_READY = False


def s3_bucket() -> str:
    return os.environ.get("CULTURE_S3_BUCKET", "").strip()


def s3_configured() -> bool:
    return bool(s3_bucket())


def _s3_prefix() -> str:
    raw = os.environ.get("CULTURE_S3_PREFIX", "culture-summaries/").strip()
    if raw and not raw.endswith("/"):
        raw += "/"
    return raw


def _presigned_expires() -> int:
    raw = os.environ.get("CULTURE_S3_PRESIGNED_EXPIRES", "604800").strip()
    try:
        return max(60, int(raw))
    except ValueError:
        return 604800


def _find_korean_font() -> str:
    custom = os.environ.get("CULTURE_PDF_FONT", "").strip()
    if custom and Path(custom).is_file():
        return custom
    for candidate in (
        Path(r"C:\Windows\Fonts\malgun.ttf"),
        Path(r"C:\Windows\Fonts\malgunsl.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ):
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(
        "한글 PDF 폰트를 찾을 수 없습니다. "
        "CULTURE_PDF_FONT 환경 변수에 TTF/OTF 경로를 지정하세요."
    )


def _safe_key_part(value: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", value.strip())
    return cleaned[:80] or "summary"


def _s3_client():
    region = (
        os.environ.get("CULTURE_S3_REGION", "").strip()
        or os.environ.get("AWS_REGION", "").strip()
        or "ap-northeast-2"
    )
    key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    token = (
        os.environ.get("AWS_SESSION_TOKEN", "").strip()
        or os.environ.get("AWS_SECURITY_TOKEN", "").strip()
    )
    if key and secret:
        kwargs: dict[str, str] = {
            "aws_access_key_id": key,
            "aws_secret_access_key": secret,
        }
        if token:
            kwargs["aws_session_token"] = token
        return boto3.client("s3", region_name=region, **kwargs)
    profile = os.environ.get("AWS_PROFILE", "default")
    return boto3.Session(profile_name=profile, region_name=region).client("s3")


def _write_block(pdf: FPDF, text: str, *, line_h: float) -> None:
    """페이지 넘김 후에도 안전하게 본문을 출력 (w=0 오류 방지)."""
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, line_h, text or "")


def _ensure_matplotlib() -> None:
    global _MPL_READY
    if _MPL_READY:
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    font_path = _find_korean_font()
    font_manager.fontManager.addfont(font_path)
    family = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams["font.family"] = family
    plt.rcParams["axes.unicode_minus"] = False
    _MPL_READY = True


def _rgba_to_mpl(color: str, fallback: str) -> str:
    if not color or not isinstance(color, str):
        return fallback
    color = color.strip()
    if color.startswith("#"):
        return color
    m = re.match(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)",
        color,
    )
    if m:
        r, g, b = (int(m.group(i)) / 255.0 for i in range(1, 4))
        return (r, g, b)
    return fallback


def _render_chart_png(spec: dict[str, Any]) -> bytes:
    """Chart.js 스펙과 동일한 막대그래프를 PNG로 렌더."""
    _ensure_matplotlib()
    import matplotlib.pyplot as plt

    labels = list(spec.get("labels") or [])
    datasets = spec.get("datasets") or []
    if not labels or not datasets:
        raise ValueError("차트 데이터가 비어 있습니다.")
    values = [float(v) for v in (datasets[0].get("data") or [])]
    if len(values) != len(labels):
        n = min(len(values), len(labels))
        labels, values = labels[:n], values[:n]

    ds0 = datasets[0]
    bar_color = _rgba_to_mpl(str(ds0.get("backgroundColor") or ""), "#7c3aed")
    edge_color = _rgba_to_mpl(str(ds0.get("borderColor") or ""), "#6d28d9")
    y_label = str(ds0.get("label") or "값")
    title = str(spec.get("title") or "막대그래프")

    label_count = max(len(labels), 1)
    fig_w = max(8.0, min(14.0, label_count * 0.55))
    fig, ax = plt.subplots(figsize=(fig_w, 4.2), dpi=120)
    x = range(len(labels))
    ax.bar(x, values, color=bar_color, edgecolor=edge_color, linewidth=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel(y_label, fontsize=9)
    ax.set_title(title, fontsize=11, pad=12)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _embed_chart(pdf: FPDF, spec: dict[str, Any]) -> None:
    """막대그래프 PNG를 PDF 페이지에 삽입."""
    png = _render_chart_png(spec)
    img_w = pdf.epw
    with BytesIO(png) as buf:
        pdf.image(buf, w=img_w)
    pdf.ln(4)


def build_summary_pdf_bytes(
    *,
    summary: str,
    table: str,
    month: str,
    chart_specs: list[dict[str, Any]] | None = None,
) -> bytes:
    font_path = _find_korean_font()
    month_label = format_yyyymm(month) if month else ""
    title = f"{table} 데이터 요약"
    if month_label:
        title += f" ({month_label})"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.add_font("CultureKR", "", font_path)
    pdf.set_font("CultureKR", size=14)
    _write_block(pdf, title, line_h=9)
    pdf.ln(4)
    pdf.set_font("CultureKR", size=11)
    for paragraph in (summary or "").split("\n"):
        _write_block(pdf, paragraph.strip() or " ", line_h=7)
        pdf.ln(2)

    specs = chart_specs or []
    if specs:
        pdf.ln(6)
        pdf.set_font("CultureKR", size=12)
        _write_block(pdf, "시각화 차트", line_h=8)
        pdf.ln(2)
        for spec in specs:
            labels = spec.get("labels") or []
            datasets = spec.get("datasets") or []
            if not labels or not datasets:
                continue
            # 차트 높이(약 55mm) + 여백 확보 후 페이지 넘김
            if pdf.get_y() > pdf.h - 70:
                pdf.add_page()
            try:
                _embed_chart(pdf, spec)
            except Exception:
                pdf.set_font("CultureKR", size=10)
                _write_block(
                    pdf,
                    f"(차트 렌더 실패: {spec.get('title') or '막대그래프'})",
                    line_h=7,
                )

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.ln(4)
    pdf.set_font("CultureKR", size=9)
    _write_block(pdf, f"생성 시각: {generated}", line_h=6)

    out = pdf.output()
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return out.encode("latin-1", errors="ignore")


def upload_summary_pdf(
    *,
    summary: str,
    table: str,
    month: str,
    chart_specs: list[dict[str, Any]] | None = None,
) -> str:
    """PDF를 S3에 저장하고 다운로드 URL(프리사인)을 반환."""
    if not s3_configured():
        raise RuntimeError(
            "PDF 저장을 위해 CULTURE_S3_BUCKET 환경 변수를 설정하세요."
        )

    pdf_bytes = build_summary_pdf_bytes(
        summary=summary,
        table=table,
        month=month,
        chart_specs=chart_specs,
    )
    bucket = s3_bucket()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = (
        f"{_s3_prefix()}"
        f"{_safe_key_part(table)}_{month or 'unknown'}_{ts}_{uuid.uuid4().hex[:8]}.pdf"
    )
    client = _s3_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
        ContentDisposition=f'inline; filename="culture-summary-{month or "report"}.pdf"',
    )
    if os.environ.get("CULTURE_S3_PUBLIC", "").strip().lower() in ("1", "true", "yes"):
        region = client.meta.region_name or "ap-northeast-2"
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=_presigned_expires(),
    )
