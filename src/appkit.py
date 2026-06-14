"""
Streamlit app toolkit: cached data loaders, formatting, and Plotly chart helpers.

All warehouse/model access from the app goes through the @st.cache_data wrappers here so pages stay
responsive (the DuckDB queries and model fits run once per input, then serve from cache).
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

ACCENT = "#FA582D"      # PANW-ish orange
BLUE = "#2E86FF"
GREEN = "#21BA72"
RED = "#E0245E"
PURPLE = "#9B5DE5"
GREY = "#8B93A7"
PLATFORM_COLORS = {
    "Strata": "#2E86FF", "Prisma Cloud": "#21BA72", "Cortex": "#FA582D",
    "Identity": "#9B5DE5", "Observability": "#F4B400",
}


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def fmt_b(x: float) -> str:
    return f"${x/1e9:.2f}B"


def fmt_m(x: float) -> str:
    return f"${x/1e6:.1f}M"


def fmt_money(x: float) -> str:
    ax = abs(x)
    if ax >= 1e9:
        return f"${x/1e9:.2f}B"
    if ax >= 1e6:
        return f"${x/1e6:.1f}M"
    if ax >= 1e3:
        return f"${x/1e3:.0f}K"
    return f"${x:,.0f}"


def fmt_pct(x: float, dp: int = 1) -> str:
    return f"{x*100:.{dp}f}%"


# ---------------------------------------------------------------------------
# Page chrome
# ---------------------------------------------------------------------------
def page_header(title: str, subtitle: str = "", icon: str = "🧭"):
    st.set_page_config(page_title=f"Pathfinder · {title}", page_icon=icon, layout="wide")
    st.title(f"{icon} {title}")
    if subtitle:
        st.caption(subtitle)
    st.markdown(
        "<div style='background:#1A1D24;border-left:3px solid #FA582D;padding:6px 12px;"
        "border-radius:4px;font-size:0.8em;color:#8B93A7;margin-bottom:8px'>"
        "⚠️ All data is <b>synthetic</b>, calibrated to PANW public filings. Educational portfolio "
        "project — not affiliated with Palo Alto Networks.</div>", unsafe_allow_html=True)


def teach(text: str):
    """A 'why this matters' teaching callout."""
    st.markdown(
        f"<div style='background:#11151c;border:1px solid #2a2f3a;padding:10px 14px;"
        f"border-radius:6px;font-size:0.9em'>💡 {text}</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def kpi():
    from src import metrics
    return metrics.kpi_snapshot()


@st.cache_data(show_spinner=False)
def arr_summary():
    from src import metrics
    return metrics.ngs_arr_summary()


@st.cache_data(show_spinner=False)
def arr_by_platform():
    from src import metrics
    return metrics.arr_by_platform()


@st.cache_data(show_spinner=False)
def rollforward_total():
    from src import metrics
    return metrics.arr_rollforward_total()


@st.cache_data(show_spinner=False)
def nrr_grr():
    from src import metrics
    return metrics.nrr_grr()


@st.cache_data(show_spinner=False)
def nrr_by_platformization():
    from src import metrics
    return metrics.nrr_by_platformization()


@st.cache_data(show_spinner=False)
def cohort_retention():
    from src import metrics
    return metrics.cohort_retention()


@st.cache_data(show_spinner=False)
def rpo_deferred():
    from src import metrics
    return metrics.rpo_deferred()


@st.cache_data(show_spinner=False)
def rule_of_40():
    from src import metrics
    return metrics.rule_of_40()


@st.cache_data(show_spinner=False)
def magic_number():
    from src import metrics
    return metrics.magic_number()


@st.cache_data(show_spinner=False)
def unit_economics():
    from src import metrics
    return metrics.unit_economics()


@st.cache_data(show_spinner=False)
def platformized_count():
    from src import metrics
    return metrics.platformized_count()


@st.cache_data(show_spinner=False)
def backtest_results():
    from src.forecast import backtest
    return backtest.load_cached()


@st.cache_data(show_spinner=True)
def trajectory_project(scenario: str):
    from src.forecast import trajectory
    return trajectory.project(scenario)


@st.cache_data(show_spinner=False)
def trajectory_scenarios():
    from src.forecast import trajectory
    return trajectory.scenario_table()


@st.cache_data(show_spinner=False)
def threat_cached():
    from src import threat_signals
    return threat_signals.load_cached()


@st.cache_data(show_spinner=False)
def variance_table():
    from src import variance
    return variance.quarterly_variance()


@st.cache_data(show_spinner=False)
def arr_bridge():
    from src import variance
    return variance.arr_bridge()


@st.cache_data(show_spinner=True)
def data_quality():
    from src import governance
    return governance.build_data_quality_report()


@st.cache_data(show_spinner=False)
def narrative(kind: str):
    from src import narrative as nv
    return nv.get_narrative(kind)


@st.cache_data(show_spinner=False)
def ma_decomposition():
    from src import ma
    return ma.decomposition()


@st.cache_data(show_spinner=False)
def ma_integration_ramp(deal: str):
    from src import ma
    return ma.integration_ramp(deal)


@st.cache_data(show_spinner=False)
def ma_deals():
    from src import db
    return db.table("fact_ma_deals")


# ---------------------------------------------------------------------------
# Plotly helpers
# ---------------------------------------------------------------------------
def _base_layout(fig, height=380, legend=True):
    fig.update_layout(
        template="plotly_dark", height=height, margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0) if legend else dict(),
        hovermode="x unified")
    return fig


def waterfall(labels, values, title=""):
    measures = ["absolute"] + ["relative"] * (len(values) - 2) + ["total"]
    fig = go.Figure(go.Waterfall(
        x=labels, y=values, measure=measures,
        increasing=dict(marker_color=GREEN), decreasing=dict(marker_color=RED),
        totals=dict(marker_color=BLUE), connector=dict(line=dict(color=GREY))))
    fig.update_layout(title=title)
    return _base_layout(fig, legend=False)
