"""Pathfinder — Executive Summary (app entry point)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plotly.graph_objects as go
import streamlit as st

from src import appkit as ak

ak.page_header("Pathfinder — PANW FP&A Engine",
               "A predictive FP&A + data-science product modelling Palo Alto Networks' path to "
               "$20B Next-Gen Security ARR by FY2030.", icon="🧭")

snap = ak.kpi()

# ---- Headline KPIs ----
c = st.columns(4)
c[0].metric("NGS ARR", ak.fmt_b(snap["ngs_arr"]), f"{ak.fmt_pct(snap['ngs_arr_yoy'],0)} YoY")
c[1].metric("Net Revenue Retention", ak.fmt_pct(snap["nrr"], 0))
c[2].metric("Rule of 40", f"{snap['rule_of_40']:.0f}", "growth + FCF margin")
c[3].metric("Adj. FCF Margin", ak.fmt_pct(snap["fcf_margin"], 1))
c = st.columns(4)
c[0].metric("Organic NGS ARR", ak.fmt_b(snap["ngs_arr_organic"]))
c[1].metric("Inorganic (M&A)", ak.fmt_b(snap["ngs_arr_inorganic"]),
            f"{ak.fmt_pct(snap['ngs_arr_inorganic']/snap['ngs_arr'],0)} of total")
c[2].metric("RPO", ak.fmt_b(snap["rpo"]))
c[3].metric("Platformized customers", f"{snap['platformized']:,}", "target 4,000+ by FY2030")

st.divider()

left, right = st.columns([1, 1.3])

with left:
    st.subheader("Progress to the $20B FY2030 target")
    gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=snap["ngs_arr"] / 1e9,
        number={"suffix": "B", "prefix": "$"},
        delta={"reference": 20, "position": "bottom"},
        gauge={"axis": {"range": [0, 20]},
               "bar": {"color": ak.ACCENT},
               "steps": [{"range": [0, 8.9], "color": "#1A1D24"},
                         {"range": [8.9, 20], "color": "#11151c"}],
               "threshold": {"line": {"color": ak.GREEN, "width": 3}, "value": 20}}))
    gauge.update_layout(template="plotly_dark", height=300,
                        margin=dict(l=20, r=20, t=10, b=10),
                        paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(gauge, use_container_width=True)
    st.caption(f"At **{ak.fmt_pct(snap['progress_to_20b'],0)}** of the $20B goal.")

with right:
    st.subheader("📝 Auto-generated executive commentary")
    st.info(ak.narrative("executive_summary"))
    st.caption("Pre-generated & cached (no API key needed to view). Live LLM regeneration is "
               "available locally behind `st.secrets` — see src/narrative.py.")

st.divider()

# ---- NGS ARR trend: organic vs inorganic ----
st.subheader("NGS ARR — organic vs inorganic")
df = ak.arr_summary()
fig = go.Figure()
fig.add_trace(go.Scatter(x=df["month"], y=df["organic_ngs_arr"] / 1e9, name="Organic",
                         stackgroup="one", line=dict(color=ak.BLUE)))
fig.add_trace(go.Scatter(x=df["month"], y=df["inorganic_ngs_arr"] / 1e9, name="Inorganic (M&A)",
                         stackgroup="one", line=dict(color=ak.PURPLE)))
ak._base_layout(fig, height=360)
fig.update_yaxes(title="NGS ARR ($B)")
st.plotly_chart(fig, use_container_width=True)
ak.teach("The step-up in the inorganic band is when CyberArk and Chronosphere close — exactly the "
         "moment organic-vs-inorganic decomposition (the M&A page) becomes essential to read "
         "'real' growth.")

st.divider()
st.subheader("What's inside")
cols = st.columns(3)
cols[0].markdown("**📈 Forecast to $20B**\nDriver-based + statistical models, backtested, with "
                 "scenarios and a platformization solver.")
cols[0].markdown("**🔗 Platformization ROI**\nWhy platformized customers are worth more, and the "
                 "NPV/IRR of incentive spend.")
cols[1].markdown("**🤝 M&A & Organic Growth**\nIntegration ramps, synergies, and an "
                 "accretion/dilution + NPV model for a next tuck-in.")
cols[1].markdown("**🛰️ Threat-Signal Explorer**\nDo external cyber-threat signals predict demand? "
                 "An honest ablation.")
cols[2].markdown("**📊 Variance Analysis**\nActual vs plan, the ARR bridge, and written commentary.")
cols[2].markdown("**🧪 Data Quality & Methodology**\nGovernance checks, model card, and a "
                 "plain-English teaching layer.")
st.caption("Use the sidebar to navigate. New to SaaS FP&A? Read LEARN.md in the repo.")
