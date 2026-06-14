"""M&A & Organic Growth — decomposition, integration ramps, accretion/dilution + NPV."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import plotly.graph_objects as go
import streamlit as st

from src import appkit as ak
from src import ma

ak.page_header("M&A & Organic Growth", "Separating organic from acquired growth, and the math of "
               "the next deal.", icon="🤝")

dec = ak.ma_decomposition()
split = dec.iloc[-1]
c = st.columns(4)
c[0].metric("Total NGS ARR", ak.fmt_b(split["total_ngs_arr"]))
c[1].metric("Organic", ak.fmt_b(split["organic_ngs_arr"]), f"{ak.fmt_pct(split['organic_yoy'],0)} YoY")
c[2].metric("Inorganic (M&A)", ak.fmt_b(split["inorganic_ngs_arr"]),
            f"{ak.fmt_pct(split['inorganic_share'],0)} of total")
c[3].metric("Total YoY", ak.fmt_pct(split["total_yoy"], 0))

st.subheader("Organic vs inorganic NGS ARR")
fig = go.Figure()
fig.add_trace(go.Scatter(x=dec["month"], y=dec["organic_ngs_arr"] / 1e9, name="Organic",
                         stackgroup="one", line=dict(color=ak.BLUE)))
fig.add_trace(go.Scatter(x=dec["month"], y=dec["inorganic_ngs_arr"] / 1e9, name="Inorganic",
                         stackgroup="one", line=dict(color=ak.PURPLE)))
ak._base_layout(fig, height=340)
fig.update_yaxes(title="NGS ARR ($B)")
st.plotly_chart(fig, use_container_width=True)
ak.teach("Headline NGS ARR growth (~60% YoY) mixes organic momentum with bought growth. Stripping "
         "out the ~$1.6B from CyberArk + Chronosphere, organic is ~25-30% — still excellent, and "
         "the number management is really judged on.")

st.divider()
st.subheader("Integration ramp & synergy realization")
deal = st.selectbox("Acquisition", ["CyberArk", "Chronosphere"])
ramp = ak.ma_integration_ramp(deal)
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=ramp["month"], y=ramp["acquired_arr"] / 1e9, name="Acquired ARR ($B)",
                          line=dict(color=ak.PURPLE)))
fig2.add_trace(go.Scatter(x=ramp["month"], y=ramp["pct_synergies_realized"] * 100,
                          name="% synergies realized", yaxis="y2", line=dict(color=ak.GREEN)))
fig2.update_layout(template="plotly_dark", height=360, paper_bgcolor="rgba(0,0,0,0)",
                   margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
                   yaxis=dict(title="Acquired ARR ($B)"),
                   yaxis2=dict(title="% synergies", overlaying="y", side="right", range=[0, 100]),
                   legend=dict(orientation="h", y=1.05))
st.plotly_chart(fig2, use_container_width=True)
ak.teach("Synergies don't switch on at close — they phase in along an S-curve as teams, products "
         "and go-to-market integrate. Acquired ARR keeps compounding in parallel.")

st.divider()
st.subheader("🧮 Hypothetical next tuck-in: accretion/dilution + NPV")
col = st.columns(3)
with col[0]:
    dv = st.slider("Deal value ($B)", 0.5, 10.0, 2.0, 0.5)
    cashp = st.slider("Cash %", 0.0, 1.0, 0.60, 0.05)
    tarr = st.slider("Target ARR ($M)", 50, 1000, 120, 10)
with col[1]:
    margin = st.slider("Target net margin", -0.40, 0.30, -0.10, 0.05)
    growth = st.slider("Target ARR growth", 0.10, 1.50, 0.70, 0.05)
    rev_syn = st.slider("Revenue synergy ARR ($M)", 0, 200, 30, 5)
with col[2]:
    cost_syn = st.slider("Cost synergy ($M/yr)", 0, 100, 15, 5)
    wacc = st.slider("WACC", 0.06, 0.15, 0.10, 0.01)
    price = st.slider("Acquirer share price ($)", 120, 300, 190, 5)

a = ma.DealAssumptions(
    deal_value=dv * 1e9, cash_pct=cashp, equity_pct=1 - cashp, target_arr=tarr * 1e6,
    target_revenue=tarr * 1e6, target_net_margin=margin, target_arr_growth=growth,
    revenue_synergy_arr=rev_syn * 1e6, cost_synergy=cost_syn * 1e6, wacc=wacc, acq_price=price)
ad = ma.accretion_dilution(a)
npv = ma.deal_npv(a)

m = st.columns(4)
verdict = "ACCRETIVE ✅" if ad["is_accretive"] else "DILUTIVE ⚠️"
m[0].metric("Yr-1 EPS impact", ak.fmt_pct(ad["eps_accretion_dilution_pct"], 1), verdict)
m[1].metric("Pro-forma EPS", f"${ad['proforma_eps']:.2f}", f"vs ${ad['standalone_eps']:.2f}")
m[2].metric("Deal NPV", ak.fmt_money(npv["npv"]),
            f"{npv['value_creation_multiple']:.2f}x value creation")
m[3].metric("Implied ARR multiple", f"{npv['implied_arr_multiple']:.0f}x",
            f"payback {npv['payback_years']}y" if npv["payback_years"] else "payback >7y")
ak.teach("The classic corp-dev tension: a fast-growing tuck-in can be **EPS-dilutive in year 1** "
         "(the target loses money and you pay financing) yet **NPV-positive** over time. Good deals "
         "are judged on strategic fit + DCF, not just next year's EPS. Try pushing target margin "
         "positive or raising cost synergies to flip it accretive.")
