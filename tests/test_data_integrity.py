"""Data-integrity tests: schemas, referential integrity, basic shape."""
from src import db, governance


def test_schemas_pass():
    res = governance.run_schema_checks()
    assert res["passed"].all(), res[~res["passed"]].to_dict("records")


def test_referential_integrity():
    ri = governance.run_referential_integrity()
    assert ri["passed"].all(), ri[~ri["passed"]].to_dict("records")
    assert (ri["violations"] == 0).all()


def test_core_tables_nonempty():
    for t, min_rows in [("dim_customer", 5000), ("fact_subscription_events", 50000),
                        ("fact_financials", 60), ("dim_date", 100), ("dim_platform", 10)]:
        n = db.query(f"SELECT COUNT(*) c FROM {t}").iloc[0, 0]
        assert n >= min_rows, f"{t} has only {n} rows"


def test_no_orphan_customers_in_events():
    n = db.query("""
        SELECT COUNT(*) FROM fact_subscription_events e
        LEFT JOIN dim_customer c USING(customer_id) WHERE c.customer_id IS NULL
    """).iloc[0, 0]
    assert n == 0


def test_platformization_dates_consistent():
    bad = db.query("""
        SELECT COUNT(*) FROM dim_customer
        WHERE platformized_flag AND platformization_date IS NULL
    """).iloc[0, 0]
    assert bad == 0
