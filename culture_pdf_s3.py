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
_KOREAN_FONT_PROP: Any = None


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


_FONT_DIR = Path(__file__).resolve().parent / "fonts"
_FONT_CACHE_DIR = Path(
    os.environ.get("CULTURE_FONT_CACHE_DIR", os.environ.get("TMPDIR", "/tmp"))
) / "culture-fonts"
_FONT_DOWNLOAD_URLS = (
    "https://hangeul.pstatic.net/hangeul_static/webfont/NanumGothic/NanumGothic.ttf",
)


def _bundled_font_candidates() -> list[Path]:
    return [
        _FONT_DIR / "NanumGothic.ttf",
        _FONT_DIR / "NotoSansKR-Regular.ttf",
    ]


def _download_font_to(path: Path) -> None:
    import urllib.request

    path.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for url in _FONT_DOWNLOAD_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Culture/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            if len(data) < 100_000:
                raise RuntimeError(f"폰트 파일 크기 비정상 ({len(data)} bytes)")
            path.write_bytes(data)
            return
        except Exception as e:
            last_err = e
    raise RuntimeError(f"한글 폰트 다운로드 실패: {last_err}") from last_err


def _ensure_font_file() -> Path:
    for candidate in _bundled_font_candidates():
        if candidate.is_file() and candidate.stat().st_size > 100_000:
            return candidate
    cached = _FONT_CACHE_DIR / "NanumGothic.ttf"
    if cached.is_file() and cached.stat().st_size > 100_000:
        return cached
    _download_font_to(cached)
    return cached


def _find_korean_font() -> str:
    custom = os.environ.get("CULTURE_PDF_FONT", "").strip()
    if custom and Path(custom).is_file():
        return custom
    try:
        return str(_ensure_font_file())
    except Exception:
        pass
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
        "culture/fonts/NotoSansKR-Regular.ttf 를 확인하거나 "
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


def _korean_font_properties():
    global _KOREAN_FONT_PROP
    if _KOREAN_FONT_PROP is None:
        from matplotlib.font_manager import FontProperties

        _KOREAN_FONT_PROP = FontProperties(fname=_find_korean_font())
    return _KOREAN_FONT_PROP


def _ensure_matplotlib() -> None:
    global _MPL_READY
    if _MPL_READY:
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _korean_font_properties()
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


def _chart_slice_colors_mpl(count: int) -> list:
    """원형차트용 팔레트 — 화면 차트(Chart.js)와 동일한 다채로운 색상."""
    palette = [
        "#FFCC00", "#5C4B3C", "#FF9F40", "#4BC0C0", "#9966FF",
        "#FF6384", "#36A2EB", "#C9CBCF", "#8BC34A", "#E91E63",
    ]
    if count <= 0:
        return []
    return [palette[i % len(palette)] for i in range(count)]


def _render_chart_png(spec: dict[str, Any], *, show_title: bool = True) -> bytes:
    """Chart.js 스펙(type: bar/line/pie/doughnut)을 PNG로 렌더."""
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
    chart_type = str(spec.get("type") or "bar").strip().lower()
    y_label = str(ds0.get("label") or "값")
    title = str(spec.get("title") or "차트")
    ko_font = _korean_font_properties()
    multi = len(datasets) > 1

    if chart_type in ("pie", "doughnut"):
        fig, ax = plt.subplots(figsize=(7.0, 5.0), dpi=120)
        colors = _chart_slice_colors_mpl(len(values))
        wedge_args = {"width": 0.42} if chart_type == "doughnut" else {}
        wedges, _texts, autotexts = ax.pie(
            values,
            colors=colors,
            autopct=lambda p: f"{p:.1f}%" if p >= 3 else "",
            startangle=90,
            counterclock=False,
            wedgeprops={"edgecolor": "white", "linewidth": 1, **wedge_args},
        )
        for at in autotexts:
            at.set_fontsize(8)
            at.set_fontproperties(ko_font)
        ax.legend(
            wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
            fontsize=8, prop=ko_font,
        )
        ax.axis("equal")
        if show_title:
            ax.set_title(title, fontsize=11, pad=12, fontproperties=ko_font)
        fig.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    label_count = max(len(labels), 1)
    fig_w = max(8.0, min(14.0, label_count * 0.55))
    fig, ax = plt.subplots(figsize=(fig_w, 4.2), dpi=120)
    x = range(len(labels))

    def _dataset_values(ds: dict[str, Any]) -> list[float]:
        vals = [float(v) for v in (ds.get("data") or [])]
        if len(vals) != len(labels):
            n = min(len(vals), len(labels))
            vals = vals[:n] + [0.0] * (len(labels) - n)
        return vals

    _palette = ("#FFCC00", "#5C4B3C", "#FF9F40", "#4BC0C0", "#9966FF", "#FF6384")

    if chart_type == "line":
        for idx, ds in enumerate(datasets):
            line_color = _rgba_to_mpl(
                str(ds.get("borderColor") or ""), _palette[idx % len(_palette)]
            )
            point_color = _rgba_to_mpl(
                str(ds.get("pointBackgroundColor") or ""), line_color
            )
            ax.plot(
                list(x), _dataset_values(ds), color=line_color, linewidth=2,
                marker="o", markersize=5, markerfacecolor=point_color,
                markeredgecolor=line_color,
                label=str(ds.get("label") or f"항목 {idx + 1}"),
            )
    else:
        n_ds = len(datasets)
        total_width = 0.8
        bar_width = total_width / n_ds if n_ds else total_width
        for idx, ds in enumerate(datasets):
            bar_color = _rgba_to_mpl(
                str(ds.get("backgroundColor") or ""), _palette[idx % len(_palette)]
            )
            edge_color = _rgba_to_mpl(str(ds.get("borderColor") or ""), "#5C4B3C")
            offset = (idx - (n_ds - 1) / 2) * bar_width
            positions = [xi + offset for xi in x]
            ax.bar(
                positions, _dataset_values(ds), width=bar_width,
                color=bar_color, edgecolor=edge_color, linewidth=0.8,
                label=str(ds.get("label") or f"항목 {idx + 1}"),
            )

    ax.set_xticks(list(x))
    ax.set_xticklabels(
        labels, rotation=45, ha="right", fontsize=8, fontproperties=ko_font
    )
    ax.set_ylabel("값" if multi else y_label, fontsize=9, fontproperties=ko_font)
    if multi:
        ax.legend(fontsize=8, prop=ko_font)
    if show_title:
        ax.set_title(title, fontsize=11, pad=12, fontproperties=ko_font)
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
    # TTF(TrueType)만 사용 — PostScript OTF는 fpdf2에서 한글이 깨질 수 있음
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
                pdf.set_font("CultureKR", size=11)
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


REPORT_DIR = Path(__file__).resolve().parent / "reports"


def ascii_report_filename(prefix: str = "culture_report") -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", (prefix or "culture_report").strip()) or "culture_report"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe}_{ts}.pdf"


def report_has_data(report: dict[str, Any]) -> bool:
    return bool((report.get("content") or report.get("summary") or "").strip())


def save_report_to_disk(content: bytes, filename: str) -> Path | None:
    """로컬 PC culture/reports에 보고서 저장. Vercel 등 읽기 전용 FS에서는 None."""
    if os.environ.get("VERCEL"):
        return None
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "culture_report.docx"
    lower = name.lower()
    if not (lower.endswith(".docx") or lower.endswith(".pptx") or lower.endswith(".pdf")):
        name += ".docx"
    path = REPORT_DIR / name
    path.write_bytes(content)
    return path.resolve()


def build_agent_report_pdf_bytes(report: dict[str, Any]) -> bytes:
    """차트·요약 에이전트 응답 → PDF bytes."""
    content = (report.get("content") or report.get("summary") or "").strip()
    if not content:
        raise ValueError("보고서 내용이 비어 있습니다.")
    return build_summary_pdf_bytes(
        summary=content,
        table=str(report.get("table_label") or report.get("table") or "보고서"),
        month=str(report.get("month") or ""),
        chart_specs=list(report.get("chart_specs") or []),
    )
