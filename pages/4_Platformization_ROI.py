"""Platformization ROI — cohort economics + interactive incentive NPV/IRR calculator."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import plotly.graph_objects as go
import streamlit as st

from src import appkit as ak
from src.platformization import (IncentiveAssumptions, cohort_economics,
                                 default_assumptions_from_data, incentive_roi, tornado)

ak.page_header("Platformization ROI", "Why platformized customers are worth more — and the ROI of "
               "paying to convert them.", icon="🔗")

st.subheader("Cohort economics (observed)")
eco = cohort_economics()
c = st.columns(len(eco))
for i, r in enumerate(eco.itertuples()):
    c[i].metric(r.platformized_flag, ak.fmt_money(r.avg_arr) + " avg ARR",
                f"NRR {ak.fmt_pct(r.nrr,0)} · {int(r.customers):,} customers")
ak.teach("Platformized customers carry higher average ARR *and* expand faster (higher NRR). The "
         "calculator below turns that durable gap into the value of spending to convert a customer.")

st.divider()
st.subheader("💰 Incentive ROI calculator")
d = default_assumptions_from_data()
col = st.columns(3)
with col[0]:
    target = st.slider("Eligible accounts in campaign", 200, 5000, d.target_customers, 100)
    conv = st.slider("Conversion rate", 0.05, 0.80, d.conversion_rate, 0.05)
    cost = st.slider("Incentive $ / conversion", 20_000, 400_000,
                     int(d.incentive_cost_per_conversion), 5_000)
with col[1]:
    start_arr = st.slider("Starting ARR / account ($)", 100_000, 2_000_000,
                          int(d.starting_arr_per_customer), 20_000)
    nrr_p = st.slider("NRR if platformized", 1.05, 1.50, float(d.nrr_platformized), 0.01)
    nrr_c = st.slider("NRR if NOT platformized (counterfactual)", 0.90, 1.25,
                      float(d.nrr_counterfactual), 0.01)
with col[2]:
    gm = st.slider("Gross margin", 0.50, 0.90, d.gross_margin, 0.01)
    disc = st.slider("Discount rate", 0.05, 0.20, d.discount_rate, 0.01)
    yrs = st.slider("Horizon (years)", 3, 8, d.horizon_years, 1)

a = IncentiveAssumptions(target_customers=target, conversion_rate=conv,
                         incentive_cost_per_conversion=cost, starting_arr_per_customer=start_arr,
                         nrr_platformized=nrr_p, nrr_counterfactual=nrr_c, gross_margin=gm,
                         discount_rate=disc, horizon_years=yrs)
res = incentive_roi(a)

m = st.columns(5)
m[0].metric("Converted accounts", f"{res['converted_customers']:.0f}")
m[1].metric("Incentive spend", ak.fmt_money(res["total_incentive_spend"]))
m[2].metric("NPV", ak.fmt_money(res["npv"]))
m[3].metric("IRR", ak.fmt_pct(res["irr"], 0) if res["irr"] else "n/a")
m[4].metric("Payback", f"{res['payback_years']:.1f} yrs" if res["payback_years"] else "n/a")

sched = res["schedule"]
fig = go.Figure()
fig.add_trace(go.Bar(x=sched["year"], y=sched["net_cash"] / 1e6, name="Net cash ($M)",
                     marker_color=[ak.RED if v < 0 else ak.GREEN for v in sched["net_cash"]]))
fig.add_trace(go.Scatter(x=sched["year"], y=sched["net_cash"].cumsum() / 1e6, name="Cumulative ($M)",
                         line=dict(color=ak.BLUE)))
ak._base_layout(fig, height=320)
fig.update_xaxes(title="Year"); fig.update_yaxes(title="$M")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Tornado — what moves the NPV")
tor = tornado(a)
figt = go.Figure()
base_npv = res["npv"]
for r in tor.itertuples():
    figt.add_trace(go.Bar(y=[r.driver], x=[r.npv_high / 1e6 - base_npv / 1e6], base=base_npv / 1e6,
                          orientation="h", marker_color=ak.GREEN, showlegend=False))
    figt.add_trace(go.Bar(y=[r.driver], x=[r.npv_low / 1e6 - base_npv / 1e6], base=base_npv / 1e6,
                          orientation="h", marker_color=ak.RED, showlegend=False))
figt.add_vline(x=base_npv / 1e6, line_color="white", line_dash="dash")
figt.update_layout(template="plotly_dark", height=320, barmode="overlay",
                   paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10),
                   xaxis_title="NPV ($M)")
st.plotly_chart(figt, use_container_width=True)
ak.teach("The NPV swings most on the **NRR gap** (platformized vs counterfactual). That's the honest "
         "core of the thesis: the value of platformization is the retention/expansion difference — "
         "if that gap is real and durable, the incentives pay for themselves many times over.")
