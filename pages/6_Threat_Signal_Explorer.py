"""Threat-Signal Explorer — leading indicators, lagged correlation, and the honest ablation."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import appkit as ak
from src import db

ak.page_header("Threat-Signal Explorer", "Do external cyber-threat signals predict demand? "
               "An honest ablation.", icon="🛰️")

sig = db.table("fact_threat_signals").sort_values("month")
st.subheader("External threat indicators over time")
fig = go.Figure()
fig.add_trace(go.Scatter(x=sig["month"], y=sig["ai_threat_index"], name="AI-threat index",
                         line=dict(color=ak.ACCENT)))
fig.add_trace(go.Scatter(x=sig["month"], y=sig["cve_count"] / 20, name="CVE volume (÷20)",
                         line=dict(color=ak.BLUE)))
fig.add_trace(go.Scatter(x=sig["month"], y=sig["disclosed_breach_count"], name="Disclosed breaches",
                         line=dict(color=ak.GREY)))
ak._base_layout(fig, height=320)
st.plotly_chart(fig, use_container_width=True)
ak.teach("The AI-threat index is a constructed leading indicator echoing PANW's thesis that AI is "
         "weaponizing attacks — rising threat activity should pull forward security demand.")

cache = ak.threat_cached()
if not cache:
    st.warning("Run `python -m src.threat_signals` to generate the cached ablation results.")
    st.stop()

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("Lagged correlation with demand")
    corr = pd.DataFrame(cache["correlation"])
    figc = go.Figure(go.Bar(x=corr["lead_months"], y=corr["correlation"],
                            marker_color=[ak.GREEN if v > 0.3 else ak.GREY for v in corr["correlation"]]))
    ak._base_layout(figc, height=300, legend=False)
    figc.update_xaxes(title="Lead (months)"); figc.update_yaxes(title="corr with net-adds")
    st.plotly_chart(figc, use_container_width=True)
    peak = corr.loc[corr["correlation"].idxmax()]
    st.caption(f"Peak correlation at a **{int(peak['lead_months'])}-month lead** "
               f"(r = {peak['correlation']:.2f}).")

with col2:
    st.subheader("Feature importance (with threat)")
    fi = pd.Series(cache["feature_importance"]).sort_values(ascending=True).tail(10)
    figf = go.Figure(go.Bar(x=fi.values, y=fi.index, orientation="h",
                            marker_color=[ak.ACCENT if "lag" in n and ("cve" in n or "threat" in n
                                          or "breach" in n) else ak.BLUE for n in fi.index]))
    ak._base_layout(figf, height=300, legend=False)
    st.plotly_chart(figf, use_container_width=True)
    st.caption("Orange bars are threat-derived features.")

st.divider()
st.subheader("Ablation — does the threat layer actually help?")
abl = cache["ablation"]
m = st.columns(4)
m[0].metric("WAPE — no threat", f"{abl['wape_no_threat']:.3f}")
m[1].metric("WAPE — with threat", f"{abl['wape_with_threat']:.3f}",
            f"{abl['threat_lift_pct']:+.0f}% lift", delta_color="inverse")
m[2].metric("WAPE — seasonal-naive", f"{abl['wape_seasonal_naive']:.3f}")
m[3].metric("Beats baseline?", "Yes ✅" if abl["beats_seasonal_naive"] else "No")

fold = pd.DataFrame(cache["per_fold"])
figa = go.Figure()
figa.add_trace(go.Scatter(x=fold["cutoff"], y=fold["actual_add"] / 1e6, name="Actual net-add",
                          line=dict(color="white")))
figa.add_trace(go.Scatter(x=fold["cutoff"], y=fold["no_threat"] / 1e6, name="Forecast (no threat)",
                          line=dict(color=ak.GREY, dash="dot")))
figa.add_trace(go.Scatter(x=fold["cutoff"], y=fold["with_threat"] / 1e6, name="Forecast (with threat)",
                          line=dict(color=ak.GREEN)))
ak._base_layout(figa, height=340)
figa.update_yaxes(title="Monthly net-new ARR ($M)")
st.plotly_chart(figa, use_container_width=True)
st.success(cache.get("summary", ""))
ak.teach("This is the honest test: same model, identical folds, with vs without the lagged threat "
         "features. The lift is real but **bounded** — the ~2-month lead helps the near-term demand "
         "read (and finally beats the naive baseline), but it cannot inform the multi-year $20B "
         "trajectory, because you can't observe future threat activity. Reporting both the win and "
         "its limits is the point.")
