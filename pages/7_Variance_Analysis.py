"""Variance Analysis — actual vs plan, the ARR bridge, and written commentary."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import plotly.graph_objects as go
import streamlit as st

from src import appkit as ak

ak.page_header("Variance Analysis", "Actual vs plan, the ARR bridge, and the auto-written CFO note.",
               icon="📊")

vt = ak.variance_table().dropna(subset=["actual_ngs_arr"])
vt["period"] = vt["fiscal_year"] + "-" + vt["fiscal_quarter"]

st.subheader("NGS ARR: actual vs plan")
fig = go.Figure()
fig.add_trace(go.Bar(x=vt["period"], y=vt["plan_ngs_arr"] / 1e9, name="Plan", marker_color=ak.GREY))
fig.add_trace(go.Bar(x=vt["period"], y=vt["actual_ngs_arr"] / 1e9, name="Actual",
                     marker_color=ak.ACCENT))
ak._base_layout(fig, height=340)
fig.update_layout(barmode="group")
fig.update_yaxes(title="NGS ARR ($B)")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Variance table")
show = vt[["period", "actual_ngs_arr", "plan_ngs_arr", "ngs_arr_var_pct",
           "revenue_var_pct", "op_margin_var_bps"]].copy()
show.columns = ["Period", "Actual NGS ARR", "Plan NGS ARR", "NGS ARR var %", "Rev var %", "Op margin var (bps)"]
st.dataframe(
    show.style.format({"Actual NGS ARR": lambda v: ak.fmt_b(v), "Plan NGS ARR": lambda v: ak.fmt_b(v),
                       "NGS ARR var %": "{:+.1%}", "Rev var %": "{:+.1%}",
                       "Op margin var (bps)": "{:+.0f}"}),
    use_container_width=True, hide_index=True)

st.divider()
st.subheader("ARR bridge — latest quarter")
bridge = ak.arr_bridge()
st.plotly_chart(
    ak.waterfall(bridge["motion"].tolist(), bridge["value"].tolist(),
                 f"{bridge.attrs['fiscal_year']}-{bridge.attrs['fiscal_quarter']} ($)"),
    use_container_width=True)

st.subheader("📝 Auto-generated variance commentary")
st.info(ak.narrative("variance"))
ak.teach("This is the FP&A core loop: compare actuals to the board plan, decompose the change with "
         "the ARR bridge, then explain it in plain English. The commentary is LLM-style narrative "
         "(cached here; live-generatable behind an API key) — the 'explain the variance to a CFO' "
         "skill, automated.")
