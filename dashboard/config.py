"""
dashboard/config.py
===================
Central configuration: thresholds, colors, and chart helpers.
Imported by all view modules and app.py.
"""

# ── Data Quality Thresholds ───────────────────────────────────────────────────
# Missingness severity thresholds (configurable)
MISSING_THRESHOLDS = {
    "good":     5.0,    # < 5% missing → Good
    "warning":  20.0,   # 5–20% missing → Warning
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

# ── Quality Status System ─────────────────────────────────────────────────────
# Record-level status (dbt int_cars_cleaned output)
STATUS_COLORS = {
    "VALID":       "#166534",   # dark green
    "WARNING":     "#92400e",   # amber/brown
    "SUSPICIOUS":  "#c2410c",   # orange-red
    "INVALID":     "#991b1b",   # dark red
    "QUARANTINED": "#374151",   # dark gray
}

STATUS_BG = {
    "VALID":       "#dcfce7",
    "WARNING":     "#fef9c3",
    "SUSPICIOUS":  "#ffedd5",
    "INVALID":     "#fee2e2",
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

# ── Issue severity ────────────────────────────────────────────────────────────
SEVERITY_ORDER  = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
SEVERITY_COLORS = {
    "CRITICAL": "#991b1b",
    "HIGH":     "#c2410c",
    "MEDIUM":   "#92400e",
    "LOW":      "#166534",
    "INFO":     "#1d4ed8",
}
SEVERITY_BG = {
    "CRITICAL": "#fee2e2",
    "HIGH":     "#ffedd5",
    "MEDIUM":   "#fef9c3",
    "LOW":      "#dcfce7",
    "INFO":     "#dbeafe",
}

# ── Priority ordering for completeness table ───────────────────────────────────
PRIORITY_ORDER = ["🔴 Critical", "🟠 High", "🟡 Medium", "🟢 Low"]

# ── Chart / Plot Colors ───────────────────────────────────────────────────────
THEME = {
    "navy":       "#1e3a8a",
    "blue":       "#0284c7",
    "green":      "#16a34a",
    "amber":      "#d97706",
    "red":        "#dc2626",
    "gray":       "#64748b",
    "light_gray": "#f1f5f9",
    "grid":       "rgba(148, 163, 184, 0.2)",
}

# Chart color sequences
CHART_COLORS = ["#1e3a8a", "#0284c7", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#db2777"]


def apply_plot_theme(
    fig,
    height: int = 320,
    show_legend: bool = True,
    legend_orientation: str = "h",
) -> None:
    """
    Applies unified professional chart styling:
    clean white backgrounds, subtle gridlines, Inter font.
    """
    fig.update_layout(
        font=dict(
            family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            size=12,
            color="#334155",
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=12, r=16, t=28, b=12),
        showlegend=show_legend,
    )
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
    """Render a professional section title block."""
    sub = f"<div style='font-size:0.82rem; color:#64748b; margin-top:2px;'>{subtitle}</div>" if subtitle else ""
    return f"""
    <div style='border-left:4px solid #1e3a8a; padding-left:12px; margin-bottom:12px;'>
        <div style='font-size:1.0rem; font-weight:700; color:#0f172a;'>{title}</div>
        {sub}
    </div>
    """


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
    accent_color: str = "#1e3a8a",
    icon: str = "",
) -> str:
    """Render a clean, high-impact executive KPI card with modern typography."""
    delta_html = ""
    if delta:
        if delta_color == "normal":
            d_bg, d_fg = "#dcfce7", "#166534"
        elif delta_color == "inverse":
            d_bg, d_fg = "#fee2e2", "#991b1b"
        elif delta_color == "amber":
            d_bg, d_fg = "#fef9c3", "#854d0e"
        else:
            d_bg, d_fg = "#f1f5f9", "#475569"
        delta_html = (
            f"<span style='background:{d_bg}; color:{d_fg}; padding:2px 7px; "
            f"border-radius:4px; font-size:0.72rem; font-weight:700; margin-left:6px;'>{delta}</span>"
        )

    icon_html = f"<span style='margin-right:4px;'>{icon}</span>" if icon else ""
    sub_html = (
        f"<div style='font-size:0.75rem; color:#64748b; font-weight:500; margin-top:5px; line-height:1.3;'>{subtitle}</div>"
        if subtitle else ""
    )

    return f"""
    <div style='background:#ffffff; border:1px solid #e2e8f0; border-top:3.5px solid {accent_color};
                border-radius:8px; padding:14px 16px 12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);
                margin-bottom:8px; min-height:104px; display:flex; flex-direction:column; justify-content:space-between;'>
        <div>
            <div style='font-size:0.70rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.5px;'>
                {icon_html}{title}
            </div>
            <div style='display:flex; align-items:baseline; margin-top:4px; flex-wrap:wrap; gap:4px;'>
                <span style='font-size:1.75rem; font-weight:800; color:#0f172a; line-height:1.15;'>{value}</span>
                {delta_html}
            </div>
        </div>
        {sub_html}
    </div>
    """


# ── Backward-compatibility aliases (used by data_loader.py) ───────────────────
STATUS_EMOJI = STATUS_DOT  # original name → alias for STATUS_DOT

# ML constants kept for forward-compatibility (Gold/ML layer — not yet implemented)
ML_CRITICAL_FEATURES = [
    "vehicle_brand", "vehicle_model", "vehicle_year", "vehicle_age",
    "province", "brand_tier", "seller_type", "price",
]

LEAKAGE_COLUMNS = [
    "days_on_market", "price_drop_amount", "initial_price", "has_price_drop",
]

# Theme Colors dict (legacy alias for THEME)
THEME_COLORS = THEME
