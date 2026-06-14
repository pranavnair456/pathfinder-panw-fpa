"""
Calibration constants for the Pathfinder synthetic data generator.

Every number here traces to PANW's *public* disclosures (see docs/assumptions.md). The synthetic
generator (data/generate.py) builds a customer-level ledger whose AGGREGATES reproduce these
anchors. Splitting the calibration out keeps the "what we calibrate to" auditable and separate
from the "how we simulate it".

PANW fiscal year ends July 31.
  FQ1 = Aug-Oct,  FQ2 = Nov-Jan,  FQ3 = Feb-Apr,  FQ4 = May-Jul.
"""
from __future__ import annotations

RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Time span
# ---------------------------------------------------------------------------
# History (synthetic "actuals"): FY2021 .. FY2026  -> Aug 2020 .. Jul 2026 (72 months).
# Forecast / plan horizon extends the date spine to Jul 2030 (FY2030) for the $20B target.
HISTORY_START = "2020-08-01"   # FY2021 FQ1
HISTORY_END = "2026-07-01"     # FY2026 FQ4 (month start)
SPINE_END = "2030-07-01"       # FY2030 FQ4 — forecast/plan horizon

# ---------------------------------------------------------------------------
# NGS ARR — quarter-end anchors ($B)
# ---------------------------------------------------------------------------
# ORGANIC NGS ARR by fiscal quarter. Recent quarters (FY24Q4 onward) are PANW-disclosed and
# verified; FY21-FY23 are a documented smooth high-growth BACK-CAST (NGS ARR's exact early-year
# values are not all cleanly disclosed). See docs/assumptions.md §2 / §8.
# Key disclosed checkpoints: FY24Q4 $4.2B(+43%), FY25 Q1-Q4 4.5/4.8/5.1/5.6, FY26 Q2 ~6.3,
# FY26 Q3 organic ~6.55 (+28-30% vs FY25Q3 5.09), FY26 Q4 organic ~6.95 (=> ~$8.9B w/ inorganic).
NGS_ARR_ORGANIC_B = {
    # FY: [Q1, Q2, Q3, Q4]
    2021: [0.55, 0.70, 0.90, 1.18],   # back-cast
    2022: [1.30, 1.45, 1.65, 1.90],   # back-cast
    2023: [2.15, 2.40, 2.65, 2.95],   # back-cast
    2024: [3.23, 3.49, 3.95, 4.22],   # FY24Q4 disclosed $4.2B
    2025: [4.50, 4.80, 5.09, 5.60],   # disclosed
    2026: [5.95, 6.30, 6.55, 6.95],   # FY26Q2 disclosed ~6.3; Q3/Q4 organic modeled
}

# Per-platform allocation of ORGANIC NGS ARR (fractions per fiscal year; must sum to 1.0).
# [MODELED] — PANW reports NGS ARR only in aggregate. Strata largest & slowest; Cortex fastest.
PLATFORM_FRACTIONS = {
    # FY:  Strata, PrismaCloud, Cortex
    2021: (0.50, 0.22, 0.28),
    2022: (0.48, 0.23, 0.29),
    2023: (0.46, 0.24, 0.30),
    2024: (0.44, 0.25, 0.31),
    2025: (0.42, 0.26, 0.32),
    2026: (0.40, 0.27, 0.33),
}

# ---------------------------------------------------------------------------
# Inorganic NGS ARR (acquisitions) — appear as step-changes at close
# ---------------------------------------------------------------------------
# Chronosphere: >$160M ARR (Sep 2025), triple-digit growth, closed H2 FY26 (~Jan 2026).
# CyberArk: ~$25B deal, closed 2026-02-11; contributes the bulk of the ~$1.6B Q3FY26 inorganic NGS
#   ARR (incl. the IBM QRadar SaaS migration to Cortex XSIAM bundled into the inorganic call-out).
# Calibration target: Q3FY26 total NGS ARR ~ $8.1B = organic 6.55 + inorganic ~1.6.
INORGANIC_DEALS = {
    "Chronosphere": {
        "platform": "Observability",
        "close_month": "2026-01-01",
        "arr_at_close_b": 0.175,      # >$160M Sep 2025, grown to ~$175M by close
        "monthly_growth": 0.06,       # triple-digit YoY -> ~6%/mo
    },
    "CyberArk": {
        "platform": "Identity",
        "close_month": "2026-02-01",
        "arr_at_close_b": 1.40,       # bulk of the ~$1.6B inorganic call-out
        "monthly_growth": 0.025,
    },
}

# ---------------------------------------------------------------------------
# Retention / platformization dynamics
# ---------------------------------------------------------------------------
NRR_PLATFORMIZED = 1.20            # ~120% net retention for platformized/strategic cohort
NRR_NONPLATFORM = 1.05            # weaker for single-product customers
CHURN_MONTHLY_PLATFORM = 0.0035    # ~4.2%/yr  (single-digit churn)
CHURN_MONTHLY_NONPLATFORM = 0.012  # ~13.5%/yr
CONTRACTION_MONTHLY = 0.0030

# Platformized customer count trajectory (quarter-end). ~110 net new/qtr recently; ~2,280 by Q3FY26.
# 4,000+ target by FY2030. [MODELED] back-cast for early quarters.
PLATFORMIZED_COUNT = {
    (2024, 4): 1200, (2025, 1): 1320, (2025, 2): 1430, (2025, 3): 1540, (2025, 4): 1700,
    (2026, 1): 2060, (2026, 2): 2170, (2026, 3): 2280, (2026, 4): 2400,
}

# ---------------------------------------------------------------------------
# Customer dimension distributions
# ---------------------------------------------------------------------------
SEGMENTS = {  # name: (share_of_logos, mean_initial_acv_usd, relative_expansion)
    # ACVs sized so the NGS customer base lands in the tens-of-thousands with a realistic ARPU
    # (~$0.3-0.5M; enterprise-skewed but not pure-strategic). See docs/methodology.md.
    "SMB":              (0.55, 10_000,   0.8),
    "Commercial":       (0.30, 40_000,   1.0),
    "Enterprise":       (0.12, 180_000,  1.3),
    "Strategic-Global": (0.03, 1_000_000, 1.6),
}
REGIONS = {"Americas": 0.55, "EMEA": 0.27, "APAC": 0.13, "JAPAC": 0.05}
INDUSTRIES = {
    "Financial Services": 0.18, "Technology": 0.17, "Public Sector": 0.15,
    "Healthcare": 0.12, "Manufacturing": 0.12, "Retail": 0.10,
    "Energy/Utilities": 0.08, "Telecom": 0.08,
}

# ---------------------------------------------------------------------------
# Financials (P&L / FCF) calibration  — GAAP revenue/RPO/deferred come from the SEC backbone CSV.
# These ratios shape the modeled COGS / opex / FCF (non-GAAP-style). See docs/assumptions.md §3.
# ---------------------------------------------------------------------------
PRODUCT_REV_SHARE = {  # hardware/product as a share of total revenue, declining (real Q3FY26 ~19.8%)
    2021: 0.36, 2022: 0.31, 2023: 0.27, 2024: 0.24, 2025: 0.21, 2026: 0.20,
}
NONGAAP_GROSS_MARGIN = 0.765       # subscription-heavy non-GAAP gross margin
NONGAAP_OPMARGIN_PATH = {          # toward ~29% FY26
    2021: 0.155, 2022: 0.185, 2023: 0.215, 2024: 0.255, 2025: 0.275, 2026: 0.290,
}
ADJ_FCF_MARGIN_PATH = {            # toward 37.5% FY26, 40% by FY28
    2021: 0.305, 2022: 0.335, 2023: 0.36, 2024: 0.37, 2025: 0.375, 2026: 0.375,
}

# Long-range company targets (used by trajectory/plan modules)
TARGET_NGS_ARR_FY2030_B = 20.0
TARGET_PLATFORMIZATIONS_FY2030 = 4000
TARGET_FCF_MARGIN_FY2028 = 0.40
