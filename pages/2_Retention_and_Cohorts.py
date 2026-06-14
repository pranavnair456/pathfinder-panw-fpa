"""Retention & Cohorts — NRR/GRR, platformized vs not, cohort heatmap."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from src import appkit as ak

ak.page_header("Retention & Cohorts", "Net/gross revenue retention and cohort durability.",
               icon="🔁")

nrr = ak.nrr_grr()
latest = nrr.iloc[-1]
c = st.columns(3)
c[0].metric("Net Revenue Retention", ak.fmt_pct(latest["nrr"], 0),
            help="Existing customers' ARR a year later ÷ their ARR a year ago. >100% = the base "
                 "grows even before new logos.")
c[1].metric("Gross Revenue Retention", ak.fmt_pct(latest["grr"], 0),
            help="Same, but expansion is capped — pure retention floor.")
c[2].metric("Logo retention", ak.fmt_pct(latest["logo_retention"], 0))

st.subheader("NRR & GRR over time")
fig = go.Figure()
fig.add_trace(go.Scatter(x=nrr["month"], y=nrr["nrr"] * 100, name="NRR", line=dict(color=ak.GREEN)))
fig.add_trace(go.Scatter(x=nrr["month"], y=nrr["grr"] * 100, name="GRR", line=dict(color=ak.BLUE)))
fig.add_hline(y=100, line_dash="dash", line_color=ak.GREY)
ak._base_layout(fig, height=340)
fig.update_yaxes(title="%")
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("The platformization retention gap")
byp = ak.nrr_by_platformization()
byp["cohort"] = byp["platformized_flag"].map({True: "Platformized", False: "Non-platformized"})
fig2 = go.Figure()
for name, color in [("Platformized", ak.ACCENT), ("Non-platformized", ak.GREY)]:
    d = byp[byp["cohort"] == name]
    fig2.add_trace(go.Scatter(x=d["month"], y=d["nrr"] * 100, name=name, line=dict(color=color)))
fig2.add_hline(y=100, line_dash="dash", line_color=ak.GREY)
ak._base_layout(fig2, height=340)
fig2.update_yaxes(title="NRR %")
st.plotly_chart(fig2, use_container_width=True)
ak.teach("This single chart is the economic engine of the whole strategy: platformized customers "
         "expand well above 100% NRR while single-product customers barely hold. Monetizing that "
         "gap is exactly what the Platformization ROI page models.")

st.divider()
st.subheader("Cohort dollar retention heatmap")
coh = ak.cohort_retention()
coh = coh[coh["cohort_logos"] >= 20]          # drop tiny cohorts
pivot = coh.pivot_table(index="cohort_label", columns="age_q", values="dollar_retention")
pivot = pivot.reindex(sorted(pivot.index, key=lambda s: (s[2:6], s[-1])))
fig3 = go.Figure(go.Heatmap(
    z=pivot.values * 100, x=[f"+{int(c)}Q" for c in pivot.columns], y=pivot.index,
    colorscale="RdYlGn", zmid=100, colorbar=dict(title="$ ret %"),
    hovertemplate="cohort %{y}, age %{x}: %{z:.0f}%<extra></extra>"))
fig3.update_layout(template="plotly_dark", height=460, paper_bgcolor="rgba(0,0,0,0)",
                   margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Quarters since cohort start")
st.plotly_chart(fig3, use_container_width=True)
ak.teach("Each row is a cohort (the quarter customers first appeared); moving right shows how their "
         "dollars evolve. Green to the right of 100% means cohorts that *grow* over time — the SaaS "
         "land-and-expand signature.")
