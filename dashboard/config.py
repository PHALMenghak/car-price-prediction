"""
dashboard/config.py
===================
Central configuration: thresholds, colors, chart helpers, and KPI card components.
Imported by all view modules and app.py.
"""

from __future__ import annotations
import pandas as pd

# ── Data Quality Thresholds ───────────────────────────────────────────────────
MISSING_THRESHOLDS = {
    "good":     5.0,    # < 5% missing → Good
    "warning":  20.0,   # 5-20% missing → Warning
    # > 20% → Critical
}

# ── DHI Thresholds ────────────────────────────────────────────────────────────
DHI_THRESHOLDS = {
    "excellent":  97.0,
    "acceptable": 92.0,
    "degraded":   85.0,
}


def dhi_status(score: float) -> tuple[str, str]:
    """Return (label, streamlit delta_color) for a DHI score."""
    if score >= DHI_THRESHOLDS["excellent"]:
        return "Excellent", "normal"
    elif score >= DHI_THRESHOLDS["acceptable"]:
        return "Acceptable", "off"
    elif score >= DHI_THRESHOLDS["degraded"]:
        return "Degraded", "inverse"
    else:
        return "Critical — Action Required", "inverse"


def missing_status(pct: float) -> tuple[str, str]:
    """Return (label, hex_color) for a missing percentage value."""
    if pct < MISSING_THRESHOLDS["good"]:
        return "Good", "#166534"
    elif pct < MISSING_THRESHOLDS["warning"]:
        return "Warning", "#92400e"
    else:
        return "Critical", "#991b1b"


def missing_color(pct: float) -> str:
    """Return hex color for a missing percentage."""
    if pct < MISSING_THRESHOLDS["good"]:
        return "#16a34a"
    elif pct < MISSING_THRESHOLDS["warning"]:
        return "#d97706"
    else:
        return "#dc2626"


def missing_bg(pct: float) -> str:
    """Return background hex for a missing percentage badge."""
    if pct < MISSING_THRESHOLDS["good"]:
        return "#dcfce7"
    elif pct < MISSING_THRESHOLDS["warning"]:
        return "#fef9c3"
    else:
        return "#fee2e2"


# ── SLA Targets ───────────────────────────────────────────────────────────────
SLA_MIN_RECORDS_PER_DAY  = 1_000
SLA_MAX_FRESHNESS_HOURS  = 6.0
SLA_MAX_QUARANTINE_PCT   = 1.0     # %
SLA_MIN_DHI              = 95.0
SLA_MIN_DETAIL_ENRICH_PCT = 98.0   # %

# ── DHI Penalty Weighting ─────────────────────────────────────────────────────
# In Cambodia used car markets ~85% of listings do not disclose mileage.
# Weighting WARNING at 0.03 reflects informational incompleteness without
# flagging a healthy pipeline as degraded.
DHI_WEIGHTS = {
    "quarantined": 1.0,
    "invalid":     0.7,
    "suspicious":  0.3,
    "warning":     0.03,
}

# ── Quality Status System (GDDE Standard) ────────────────────────────────────
STATUS_COLORS = {
    "VALID":       "#059669",   # GDDE verified emerald
    "WARNING":     "#c59b27",   # Cambodian royal gold
    "SUSPICIOUS":  "#ea580c",   # market outlier amber
    "INVALID":     "#dc2626",   # administrative red
    "QUARANTINED": "#64748b",   # slate gray
}

STATUS_BG = {
    "VALID":       "#ecfdf5",
    "WARNING":     "#fefce8",
    "SUSPICIOUS":  "#fff7ed",
    "INVALID":     "#fef2f2",
    "QUARANTINED": "#f1f5f9",
}

STATUS_ORDER = ["VALID", "WARNING", "SUSPICIOUS", "INVALID", "QUARANTINED"]

STATUS_DOT = {
    "VALID":       "🟢",
    "WARNING":     "🟡",
    "SUSPICIOUS":  "🟠",
    "INVALID":     "🔴",
    "QUARANTINED": "⚫",
}


def evaluate_sla_gates(
    dhi_score: float,
    total: int,
    freshness_hrs: float | None,
    quar_pct: float,
    dbt_status: dict,
    enrich_pct: float | None = None,
) -> list[dict]:
    """
    Unified evaluation of all 6 SLA gates.
    Consumed by both the status banner and the SLA scorecard to guarantee consistency.
    """
    dbt_ok = dbt_status.get("failed", 0) == 0 if dbt_status.get("available") else False
    fresh_ok = freshness_hrs is not None and freshness_hrs <= SLA_MAX_FRESHNESS_HOURS
    dhi_ok = dhi_score >= SLA_MIN_DHI
    vol_ok = total >= SLA_MIN_RECORDS_PER_DAY
    quar_ok = quar_pct <= SLA_MAX_QUARANTINE_PCT
    enrich_ok = enrich_pct is not None and enrich_pct >= SLA_MIN_DETAIL_ENRICH_PCT

    return [
        {
            "id": "dhi",
            "name": "Data Health Index",
            "target": f">= {SLA_MIN_DHI:.0f}%",
            "passed": dhi_ok,
            "actual": f"{dhi_score:.1f}%",
            "critical": True,
        },
        {
            "id": "volume",
            "name": "Daily Ingestion SLA",
            "target": f">= {SLA_MIN_RECORDS_PER_DAY:,}",
            "passed": vol_ok,
            "actual": f"{total:,} recs",
            "critical": False,
        },
        {
            "id": "freshness",
            "name": "Pipeline Freshness",
            "target": f"< {SLA_MAX_FRESHNESS_HOURS:.0f}h",
            "passed": fresh_ok,
            "actual": f"{freshness_hrs:.1f}h ago" if freshness_hrs is not None else "—",
            "critical": True,
        },
        {
            "id": "quarantine",
            "name": "Quarantine Ratio",
            "target": f"< {SLA_MAX_QUARANTINE_PCT}%",
            "passed": quar_ok,
            "actual": f"{quar_pct:.2f}%",
            "critical": True,
        },
        {
            "id": "dbt",
            "name": "dbt Contract Tests",
            "target": "All pass",
            "passed": dbt_ok,
            "actual": f"{dbt_status.get('passed', 0)}/{dbt_status.get('total', 0)}" if dbt_status.get("available") else "Not run",
            "critical": True,
        },
        {
            "id": "enrichment",
            "name": "Detail Enrichment",
            "target": f">= {SLA_MIN_DETAIL_ENRICH_PCT:.0f}%",
            "passed": enrich_ok,
            "actual": f"{enrich_pct:.1f}%" if enrich_pct is not None else "N/A",
            "critical": False,
        },
    ]


# ── Issue severity ────────────────────────────────────────────────────────────
SEVERITY_ORDER  = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
SEVERITY_COLORS = {
    "CRITICAL": "#dc2626",
    "HIGH":     "#ea580c",
    "MEDIUM":   "#c59b27",
    "LOW":      "#059669",
    "INFO":     "#0284c7",
}
SEVERITY_BG = {
    "CRITICAL": "#fef2f2",
    "HIGH":     "#fff7ed",
    "MEDIUM":   "#fefce8",
    "LOW":      "#ecfdf5",
    "INFO":     "#f0f9ff",
}

# ── Priority ordering for completeness table ──────────────────────────────────
PRIORITY_ORDER = ["🔴 Critical", "🟠 High", "🟡 Medium", "🟢 Low"]

# ── GDDE Institutional Theme & Chart Colors ───────────────────────────────────
THEME = {
    "navy":       "#0f2b5c",   # GDDE Royal Navy (Primary Authority)
    "gold":       "#c59b27",   # Cambodian Royal Gold (Prestige & Tax Paper)
    "gold_deep":  "#b45309",   # Deep Amber Gold
    "blue":       "#0284c7",   # Innovation Tech Blue
    "green":      "#059669",   # Verified Emerald (Compliance)
    "red":        "#dc2626",   # Administrative Crimson
    "gray":       "#64748b",   # Neutral Slate
    "light_gray": "#f1f5f9",   # Light Gray Tint
    "surface":    "#ffffff",   # Card Surface
    "canvas":     "#f8fafc",   # Dashboard Canvas Background
    "border":     "#e2e8f0",   # Border Color
    "grid":       "rgba(148, 163, 184, 0.18)",
}

CHART_COLORS = [
    "#0f2b5c",  # GDDE Navy
    "#c59b27",  # Royal Gold
    "#0284c7",  # Innovation Blue
    "#059669",  # Verified Emerald
    "#b45309",  # Deep Amber
    "#6366f1",  # Tech Indigo
    "#dc2626",  # Alert Red
]

# ── Standard Chart Height Constants ──────────────────────────────────────────
CHART_H_SMALL   = 260   # mini charts in dense 3-col layouts
CHART_H_MEDIUM  = 340   # standard single or dual-column charts
CHART_H_LARGE   = 420   # full-width or featured charts
CHART_H_SCATTER = 480   # scatter plots (need more vertical space)
CHART_H_TREND   = 300   # compact time-series trend lines


def apply_plot_theme(
    fig,
    height: int = 320,
    show_legend: bool = True,
    legend_orientation: str = "h",
    xaxis_title: str = "",
    yaxis_title: str = "",
    title: str = "",
) -> None:
    """
    Applies unified professional chart styling:
    clean white backgrounds, subtle gridlines, Inter font.
    Optional axis labels and title to reduce update_layout() repetition.
    """
    bottom_margin = 42 if (show_legend and legend_orientation == "h") else 14
    layout_kwargs: dict = dict(
        font=dict(
            family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            size=12,
            color="#334155",
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=12, r=16, t=32 if title else 18, b=bottom_margin),
        showlegend=show_legend,
    )
    if title:
        layout_kwargs["title"] = dict(
            text=title, font=dict(size=12, color="#334155"), x=0.0, xanchor="left"
        )
    if xaxis_title:
        layout_kwargs["xaxis_title"] = xaxis_title
    if yaxis_title:
        layout_kwargs["yaxis_title"] = yaxis_title
    fig.update_layout(**layout_kwargs)
    if show_legend:
        if legend_orientation == "h":
            fig.update_layout(
                legend=dict(
                    orientation="h",
                    y=-0.22,
                    x=0.0,
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11),
                )
            )
        else:
            fig.update_layout(
                legend=dict(
                    orientation="v",
                    y=1.0,
                    x=1.02,
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11),
                )
            )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=THEME["grid"],
        linecolor="rgba(148, 163, 184, 0.3)",
        zeroline=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=THEME["grid"],
        linecolor="rgba(148, 163, 184, 0.3)",
        zeroline=False,
    )


def section_header(title: str, subtitle: str = "") -> str:
    """Render a professional section title block with GDDE Royal Navy indicator."""
    sub = f"<div style='font-size:0.82rem; color:#475569; margin-top:2px;'>{subtitle}</div>" if subtitle else ""
    return (
        f"<div style='border-left:4px solid #0f2b5c; padding-left:12px; margin-bottom:12px;'>"
        f"<div style='font-size:1.0rem; font-weight:700; color:#0f2b5c;'>{title}</div>"
        f"{sub}"
        f"</div>"
    )


def status_badge(status: str) -> str:
    """Return HTML badge for a quality status string."""
    color = STATUS_COLORS.get(status, "#64748b")
    bg = STATUS_BG.get(status, "#f1f5f9")
    dot = STATUS_DOT.get(status, "●")
    return (
        f"<span style='background:{bg}; color:{color}; padding:2px 8px; "
        f"border-radius:4px; font-size:0.72rem; font-weight:700;'>{dot} {status}</span>"
    )


def severity_badge(severity: str) -> str:
    """Return HTML badge for an issue severity string."""
    color = SEVERITY_COLORS.get(severity, "#64748b")
    bg    = SEVERITY_BG.get(severity, "#f1f5f9")
    return (
        f"<span style='background:{bg}; color:{color}; padding:2px 8px; "
        f"border-radius:4px; font-size:0.72rem; font-weight:700;'>{severity}</span>"
    )


def kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
    delta: str = "",
    delta_color: str = "normal",
    accent_color: str = "#0f2b5c",
    icon: str = "",
    trend: str = "",
    trend_up: bool | None = None,
) -> str:
    """
    Render a clean, high-impact executive KPI card with modern typography.
    trend: optional trend indicator string e.g. '▲ 3.2%' or '▼ 1.1%'
    trend_up: True = green, False = red, None = neutral gray
    """
    delta_html = ""
    if delta:
        if delta_color == "normal":
            d_bg, d_fg = "#ecfdf5", "#065f46"
        elif delta_color == "inverse":
            d_bg, d_fg = "#fef2f2", "#991b1b"
        elif delta_color == "amber":
            d_bg, d_fg = "#fefce8", "#854d0e"
        else:
            d_bg, d_fg = "#f1f5f9", "#475569"
        delta_html = (
            f"<span style='background:{d_bg}; color:{d_fg}; padding:2px 7px; "
            f"border-radius:4px; font-size:0.72rem; font-weight:700; margin-left:6px;'>{delta}</span>"
        )

    trend_html = ""
    if trend:
        t_color = "#059669" if trend_up is True else "#dc2626" if trend_up is False else "#64748b"
        trend_html = (
            f"<span style='font-size:0.72rem; color:{t_color}; font-weight:700; "
            f"margin-left:6px;'>{trend}</span>"
        )

    icon_html = f"<span style='margin-right:4px;'>{icon}</span>" if icon else ""
    sub_html = (
        f"<div style='font-size:0.75rem; color:#64748b; font-weight:500; margin-top:5px; line-height:1.3;'>{subtitle}</div>"
        if subtitle else ""
    )

    return (
        f"<div style='background:#ffffff; border:1px solid #e2e8f0; border-top:3.5px solid {accent_color}; "
        f"border-radius:8px; padding:14px 16px 12px; box-shadow:0 1px 3px rgba(15,43,92,0.05); "
        f"margin-bottom:8px; min-height:104px; display:flex; flex-direction:column; justify-content:space-between;'>"
        f"<div>"
        f"<div style='font-size:0.70rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.5px;'>"
        f"{icon_html}{title}"
        f"</div>"
        f"<div style='display:flex; align-items:baseline; margin-top:4px; flex-wrap:wrap; gap:4px;'>"
        f"<span style='font-size:1.75rem; font-weight:800; color:#0f172a; line-height:1.15;'>{value}</span>"
        f"{delta_html}{trend_html}"
        f"</div>"
        f"</div>"
        f"{sub_html}"
        f"</div>"
    )


def insight_card(icon: str, text: str, color: str = "#0284c7") -> str:
    """Render a styled auto-insight callout card (data-driven, no hard-coded values)."""
    bg = color + "0f"  # 6% opacity background tint
    return (
        f"<div style='background:{bg}; border:1px solid {color}30; border-left:3px solid {color}; "
        f"border-radius:6px; padding:8px 12px; margin-bottom:8px; font-size:0.80rem; color:#1e293b;'>"
        f"<span style='margin-right:6px;'>{icon}</span>{text}"
        f"</div>"
    )


# ── Backward-compatibility aliases ────────────────────────────────────────────
STATUS_EMOJI = STATUS_DOT  # legacy alias for STATUS_DOT
THEME_COLORS = THEME       # legacy alias for THEME


# ── Automotive Standard Formatters ───────────────────────────────────────────

def format_currency(val: float | int | None) -> str:
    """Format numeric value as USD currency: $25,500."""
    if val is None or pd.isna(val):
        return "—"
    return f"${float(val):,.0f}"


def format_number(val: float | int | None) -> str:
    """Format count or integer: 12,450."""
    if val is None or pd.isna(val):
        return "0"
    return f"{int(val):,}"


def format_percentage(val: float | int | None, decimals: int = 1) -> str:
    """Format decimal or percentage: 5.8%."""
    if val is None or pd.isna(val):
        return "—"
    return f"{float(val):.{decimals}f}%"


def format_mileage(val: float | int | None) -> str:
    """Format odometer reading in km: 45,000 km."""
    if val is None or pd.isna(val) or val <= 0:
        return "Not Disclosed"
    return f"{int(val):,} km"


def format_engine(val: float | int | None) -> str:
    """Format engine capacity in cc: 2,500 cc."""
    if val is None or pd.isna(val) or val <= 0:
        return "Not Specified"
    return f"{int(val):,} cc"

