"""Reconciliation tests: the ARR roll-forward identity and sub-ledger <-> GL tie."""
from src import db, governance


def test_governance_reconciliation_passes():
    recon = governance.run_reconciliation()
    assert recon["passed"].all(), recon[~recon["passed"]].to_dict("records")


def test_roll_forward_identity_ties_to_the_penny():
    breaks = db.query("""
        SELECT COUNT(*) FROM v_arr_rollforward
        WHERE ABS((beginning_arr + new_arr + expansion_arr + platformization_arr
                   + inorganic_arr + contraction_arr + churn_arr) - ending_arr) > 1.0
    """).iloc[0, 0]
    assert breaks == 0


def test_subledger_ties_to_gl():
    df = db.query("""
        SELECT f.month, f.ngs_arr_total AS gl, s.total_ngs_arr AS sub
        FROM fact_financials f JOIN v_ngs_arr_summary s ON s.month = f.month
    """)
    df["pct"] = (df["gl"] - df["sub"]).abs() / df["sub"]
    assert df["pct"].max() <= 0.01, f"max diff {df['pct'].max():.4%}"


def test_revenue_components_sum_to_total():
    off = db.query("""
        SELECT COUNT(*) FROM fact_financials
        WHERE ABS((product_revenue + subscription_revenue) - total_revenue) > 1.0
    """).iloc[0, 0]
    assert off == 0
