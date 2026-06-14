"""Methodology & Model Card — the choices, the backtest, and the teaching layer."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from src import appkit as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ak.page_header("Methodology & Model Card", "Why each choice was made — partly here so you can learn "
               "the domain.", icon="🧪")

st.subheader("Model comparison (cached backtest)")
bt = ak.backtest_results()
if bt:
    summ = pd.DataFrame(bt["summary"])[["model", "flow_WAPE", "level_WAPE", "skill_vs_baseline_%"]]
    summ.columns = ["Model", "Flow WAPE", "Level WAPE", "Skill vs baseline %"]
    st.dataframe(summ.style.format({"Flow WAPE": "{:.3f}", "Level WAPE": "{:.3f}",
                                    "Skill vs baseline %": "{:+.1f}"}),
                 use_container_width=True, hide_index=True)
    st.caption(f"Baseline = Seasonal-Naive · {bt['n_folds']} rolling-origin folds · "
               f"{bt['horizon']}-month horizon.")

st.divider()
# Surface the long-form docs if present (written in Phase 13), else an inline summary.
for title, fname, fallback in [
    ("Methodology", "methodology.md",
     "Forecasting targets ORGANIC NGS ARR (inorganic is a known M&A step, added separately). Models "
     "work on the monthly net-add flow, then integrate to a level. We compare a seasonal-naive "
     "baseline against ETS, an auto-ARIMA grid, XGBoost, and an interpretable driver-based model "
     "via rolling-origin CV. Honest finding: on a smooth ARR aggregate, simple methods are strong; "
     "the driver-based model is chosen for the strategic trajectory for its interpretability."),
    ("Model Card", "model_card.md",
     "Chosen production model: driver-based roll-forward projection with scenario levers. "
     "pmdarima/prophet were intentionally omitted (fragile on py3.12 / heavy for Streamlit Cloud) "
     "in favour of statsmodels + a custom auto-ARIMA grid. Threat features add a bounded near-term "
     "lift (see Threat-Signal page)."),
]:
    st.subheader(title)
    path = os.path.join(ROOT, "docs", fname)
    if os.path.exists(path):
        with open(path) as fh:
            st.markdown(fh.read())
    else:
        st.markdown(fallback)
    st.divider()

st.subheader("Key assumptions")
st.markdown(
    "- **All data synthetic**, calibrated to PANW public filings (SEC XBRL GAAP backbone + earnings "
    "releases). See `docs/assumptions.md`.\n"
    "- PANW fiscal year ends July 31; history FY2021–FY2026 monthly; horizon to FY2030.\n"
    "- NGS ARR reconciles by construction to a calibrated curve; the ARR roll-forward ties to the "
    "penny (Data Quality page).\n"
    "- Unit economics (CAC/LTV) are illustrative; lifetime capped at 10y; see `src/metrics.py`.\n"
    "- M&A accretion/dilution uses illustrative acquirer figures anchored to PANW's public scale.")
ak.teach("This page is deliberately written to teach. If a term is unfamiliar (NRR, RPO, Rule of 40, "
         "accretion/dilution), the repo's LEARN.md explains each one in plain English.")
