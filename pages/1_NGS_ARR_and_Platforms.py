"""NGS ARR & Platforms — ARR by platform, organic/inorganic, roll-forward waterfall."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import plotly.graph_objects as go
import streamlit as st

from src import appkit as ak

ak.page_header("NGS ARR & Platforms", "How Next-Gen Security ARR builds by platform and motion.",
               icon="📈")

byp = ak.arr_by_platform()
summary = ak.arr_summary()

st.subheader("NGS ARR by platform over time")
fig = go.Figure()
for plat in ["Strata", "Prisma Cloud", "Cortex", "Identity", "Observability"]:
    d = byp[byp["platform"] == plat]
    fig.add_trace(go.Scatter(x=d["month"], y=d["ending_arr"] / 1e9, name=plat, stackgroup="one",
                             line=dict(color=ak.PLATFORM_COLORS[plat])))
ak._base_layout(fig, height=420)
fig.update_yaxes(title="NGS ARR ($B)")
st.plotly_chart(fig, use_container_width=True)
ak.teach("Strata (network security) is the largest base; Prisma Cloud and Cortex grow fastest. "
         "Identity (CyberArk) and Observability (Chronosphere) appear as step-changes when the "
         "deals close — these are the *inorganic* platforms.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Latest platform mix")
    latest = byp[byp["month"] == byp["month"].max()]
    pie = go.Figure(go.Pie(labels=latest["platform"], values=latest["ending_arr"],
                           marker=dict(colors=[ak.PLATFORM_COLORS[p] for p in latest["platform"]]),
                           hole=0.5))
    pie.update_layout(template="plotly_dark", height=340, paper_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(pie, use_container_width=True)

with col2:
    st.subheader("Organic vs inorganic")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=summary["month"], y=summary["organic_ngs_arr"] / 1e9,
                              name="Organic", stackgroup="one", line=dict(color=ak.BLUE)))
    fig2.add_trace(go.Scatter(x=summary["month"], y=summary["inorganic_ngs_arr"] / 1e9,
                              name="Inorganic", stackgroup="one", line=dict(color=ak.PURPLE)))
    ak._base_layout(fig2, height=340)
    fig2.update_yaxes(title="NGS ARR ($B)")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()
st.subheader("ARR roll-forward — the bridge (latest quarter)")
bridge = ak.arr_bridge()
st.plotly_chart(
    ak.waterfall(bridge["motion"].tolist(), bridge["value"].tolist(),
                 f"{bridge.attrs['fiscal_year']}-{bridge.attrs['fiscal_quarter']} ARR bridge ($)"),
    use_container_width=True)
ak.teach("The ARR roll-forward is the core FP&A identity: **Beginning + New + Expansion + "
         "Platformization + Inorganic − Contraction − Churn = Ending**. Every dollar is traced to a "
         "motion, and (per the Data Quality page) this ties out to the penny for every month.")
