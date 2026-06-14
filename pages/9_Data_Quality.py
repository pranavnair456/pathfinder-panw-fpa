"""Data Quality — the governance report surfaced for the reviewer."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from src import appkit as ak

ak.page_header("Data Quality & Governance", "Schema validation, referential integrity, and "
               "sub-ledger ↔ GL reconciliation.", icon="✅")

rep = ak.data_quality()


def status_badge(passed: bool) -> str:
    return "✅ PASS" if passed else "❌ FAIL"


schema_ok = bool(rep["schema"]["passed"].all())
ri_ok = bool(rep["referential_integrity"]["passed"].all())
recon_ok = bool(rep["reconciliation"]["passed"].all())
overall = schema_ok and ri_ok and recon_ok

c = st.columns(4)
c[0].metric("Overall", status_badge(overall))
c[1].metric("Schema checks", status_badge(schema_ok))
c[2].metric("Referential integrity", status_badge(ri_ok))
c[3].metric("Reconciliation", status_badge(recon_ok))

st.divider()
st.subheader("Table profile")
st.dataframe(rep["profile"], use_container_width=True, hide_index=True)

st.subheader("Schema validation (pandera)")
st.dataframe(rep["schema"], use_container_width=True, hide_index=True)

st.subheader("Referential integrity")
st.dataframe(rep["referential_integrity"], use_container_width=True, hide_index=True)

st.subheader("Reconciliation")
st.dataframe(rep["reconciliation"], use_container_width=True, hide_index=True)
ak.teach("Governance is a real FP&A-engineering requirement, not decoration: the sub-ledger "
         "(subscription events) must tie to the GL (financials), every fact key must resolve to a "
         "dimension, and the ARR roll-forward identity must hold. All three pass here — which is "
         "what lets you trust every other number in the app.")

st.divider()
st.caption("Lineage: data/generate.py → data/raw/*.csv → src/etl.py → data/warehouse.duckdb → "
           "sql/views.sql → src/* models → this app. See docs/data_dictionary.md.")
