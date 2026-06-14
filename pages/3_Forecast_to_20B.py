"""Forecast to $20B — model comparison, scenario trajectory, platformization solver."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import appkit as ak
from src.forecast import trajectory

ak.page_header("Forecast to $20B", "Backtested models, scenarios, and the path to FY2030.",
               icon="🎯")

# ---------------------------------------------------------------------------
# A) Model comparison (cached backtest)
# ---------------------------------------------------------------------------
st.subheader("Model comparison — rolling-origin backtest")
bt = ak.backtest_results()
if bt:
    summ = pd.DataFrame(bt["summary"])
    show = summ[["model", "flow_WAPE", "level_WAPE", "skill_vs_baseline_%"]].copy()
    show.columns = ["Model", "Flow WAPE", "Level WAPE", "Skill vs baseline %"]
    st.dataframe(
        show.style.format({"Flow WAPE": "{:.3f}", "Level WAPE": "{:.3f}",
                           "Skill vs baseline %": "{:+.1f}"}),
        use_container_width=True, hide_index=True)
    st.caption(f"{bt['n_folds']} folds · {bt['horizon']}-month horizon · baseline = Seasonal-Naive ·"
               f" best on the flow = **{bt['best_model']}**.")
    ak.teach("Honest finding: on a large, smooth ARR base the *level* is dominated by the existing "
             "book, so level error is tiny for everyone — the discriminating test is the **flow** "
             "(net-new ARR). There, simple methods are strong (a well-known result). The "
             "Threat-Signal page shows how a leading indicator finally beats the baseline near-term. "
             "For the strategic path below we use the **driver-based** model: slightly less accurate "
             "but interpretable and scenario-able — what an FP&A team actually defends to a CFO.")

st.divider()

# ---------------------------------------------------------------------------
# B) Scenario trajectory to FY2030
# ---------------------------------------------------------------------------
st.subheader("Trajectory to the $20B FY2030 target")
scens = st.multiselect("Scenarios to show", ["Base", "Bull", "Bear"], default=["Base", "Bull", "Bear"])
colors = {"Base": ak.BLUE, "Bull": ak.GREEN, "Bear": ak.RED}

base_proj = ak.trajectory_project("Base")
hist = base_proj[base_proj["kind"] == "actual"]
fig = go.Figure()
fig.add_trace(go.Scatter(x=hist["month"], y=hist["total"] / 1e9, name="Actual",
                         line=dict(color="white", width=2)))
for sc in scens:
    proj = ak.trajectory_project(sc)
    fc = proj[proj["kind"] == "forecast"]
    fig.add_trace(go.Scatter(x=fc["month"], y=fc["total"] / 1e9, name=f"{sc} forecast",
                             line=dict(color=colors[sc], dash="dot")))
fig.add_hline(y=20, line_dash="dash", line_color=ak.ACCENT,
              annotation_text="$20B FY2030 target", annotation_position="top left")
ak._base_layout(fig, height=440)
fig.update_yaxes(title="Total NGS ARR ($B)")
st.plotly_chart(fig, use_container_width=True)

stab = ak.trajectory_scenarios()
cols = st.columns(3)
for i, r in enumerate(stab.itertuples()):
    cols[i].metric(f"{r.scenario}: NGS ARR FY2030", ak.fmt_b(r.ngs_arr_2030),
                   f"{ak.fmt_pct(r.pct_of_target,0)} of target · {ak.fmt_pct(r.implied_cagr_to_2030,0)} CAGR")
ak.teach("The base case lands below $20B — extrapolating today's (decelerating) growth isn't "
         "enough. Hitting $20B needs sustained above-trend execution (the bull case) plus "
         "platformization and further M&A. That gap is the strategic story, stated honestly.")

st.divider()

# ---------------------------------------------------------------------------
# C) Required-platformizations solver
# ---------------------------------------------------------------------------
st.subheader("🔧 Solver: how many platformizations to close the gap?")
colA, colB = st.columns([1, 2])
with colA:
    scen = st.selectbox("Scenario", ["Base", "Bull", "Bear"], index=0)
    target_b = st.slider("Target NGS ARR by FY2030 ($B)", 15.0, 25.0, 20.0, 0.5)
sol = trajectory.required_platformizations(scen, target=target_b * 1e9)
with colB:
    c = st.columns(2)
    c[0].metric("Gap to target", ak.fmt_b(sol["gap_to_target"]))
    c[0].metric("Incremental ARR per platformization", ak.fmt_money(
        sol["incremental_arr_per_platformization"]))
    c[1].metric("Additional platformizations needed", f"{sol['additional_platformizations_needed']:,}")
    c[1].metric("Implied total platformized", f"{sol['implied_total_platformized']:,}",
                f"company target 4,000+")
ak.teach("The solver inverts the question: given the gap, and the observed ARR uplift of a "
         "platformized vs non-platformized customer, how many conversions are required? When the "
         "answer exceeds the 4,000 target, it's telling you platformization alone can't get there — "
         "new-logo growth and M&A must carry the rest.")
