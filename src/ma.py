"""
Option C — M&A: organic-vs-inorganic decomposition, integration ramps, and accretion/dilution.

Three pieces an FP&A/corp-dev team owns:
  1. DECOMPOSITION — separate organic momentum from acquired (inorganic) NGS ARR, so the board can
     see "real" growth vs bought growth. (CyberArk + Chronosphere added ~$1.6B at close.)
  2. INTEGRATION RAMP — acquired ARR keeps growing and synergies (cost + revenue) phase in along an
     S-curve over the integration window.
  3. ACCRETION / DILUTION + NPV — the deal-decision math for a *hypothetical next tuck-in*: does
     issuing shares + spending cash to buy $X of ARR raise or lower pro-forma EPS, and is the NPV
     positive? This is the interactive model on the M&A page.

All acquirer baseline figures are illustrative, anchored to PANW's public scale (see
docs/assumptions.md). Educational model — not investment advice.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src import db

# ---- Acquirer (PANW) baseline, illustrative & anchored to public scale ----
ACQ_SHARES = 700_000_000           # ~700M diluted shares
ACQ_NET_INCOME = 2_650_000_000     # non-GAAP NI ~ EPS 3.78 x shares
ACQ_EPS = ACQ_NET_INCOME / ACQ_SHARES
ACQ_PRICE = 190.0                  # illustrative share price
TAX_RATE = 0.21
INTEREST_RATE = 0.045              # foregone interest on cash / cost of debt
WACC = 0.10
ACQ_GROSS_MARGIN = 0.765


# ---------------------------------------------------------------------------
# 1) Organic vs inorganic decomposition
# ---------------------------------------------------------------------------
def decomposition() -> pd.DataFrame:
    df = db.query("SELECT * FROM v_ngs_arr_summary ORDER BY month")
    df["inorganic_share"] = df["inorganic_ngs_arr"] / df["total_ngs_arr"]
    df["organic_yoy"] = df["organic_ngs_arr"] / df["organic_ngs_arr"].shift(12) - 1
    df["total_yoy"] = df["total_ngs_arr"] / df["total_ngs_arr"].shift(12) - 1
    return df


def latest_split() -> dict:
    d = decomposition().iloc[-1]
    return {"month": d["month"], "total": float(d["total_ngs_arr"]),
            "organic": float(d["organic_ngs_arr"]), "inorganic": float(d["inorganic_ngs_arr"]),
            "inorganic_share": float(d["inorganic_share"]),
            "organic_yoy": float(d["organic_yoy"]), "total_yoy": float(d["total_yoy"])}


# ---------------------------------------------------------------------------
# 2) Integration ramp + synergy realization (S-curve)
# ---------------------------------------------------------------------------
def _s_curve(n: int) -> np.ndarray:
    """Logistic 0->1 realization curve over n months (synergies phase in, not switch on)."""
    x = np.linspace(-6, 6, n)
    s = 1 / (1 + np.exp(-x))
    return (s - s.min()) / (s.max() - s.min())


def integration_ramp(deal_name: str, months: int | None = None) -> pd.DataFrame:
    """Per-month acquired ARR, cost & revenue synergies realized over the integration window."""
    deal = db.query("SELECT * FROM fact_ma_deals WHERE deal_name = ?", [deal_name]).iloc[0]
    n = int(months or deal["integration_ramp_months"])
    arr0 = float(deal["target_arr_usd"])
    g_m = (1 + float(deal["target_arr_growth"])) ** (1 / 12) - 1
    realized = _s_curve(n)
    full_cost_syn = float(deal["cost_synergy_pct"]) * arr0
    full_rev_syn = float(deal["revenue_synergy_pct"]) * arr0
    close = pd.Timestamp(deal["close_date"])
    rows = []
    for t in range(n):
        arr = arr0 * (1 + g_m) ** t
        rows.append({
            "month": (close + pd.DateOffset(months=t)).strftime("%Y-%m"),
            "month_index": t,
            "acquired_arr": arr,
            "cost_synergy_realized": full_cost_syn * realized[t],
            "revenue_synergy_realized": full_rev_syn * realized[t],
            "pct_synergies_realized": realized[t],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3) Accretion / dilution + NPV for a hypothetical next tuck-in
# ---------------------------------------------------------------------------
@dataclass
class DealAssumptions:
    deal_value: float = 2_000_000_000
    cash_pct: float = 0.60
    equity_pct: float = 0.40
    target_arr: float = 120_000_000
    target_revenue: float = 120_000_000      # ARR-like for a subscription target
    target_net_margin: float = -0.10         # high-growth targets often run at a loss
    target_arr_growth: float = 0.70
    revenue_synergy_arr: float = 30_000_000  # cross-sell ARR unlocked
    cost_synergy: float = 15_000_000         # annual run-rate cost takeout
    # acquirer context (overridable)
    acq_shares: float = ACQ_SHARES
    acq_net_income: float = ACQ_NET_INCOME
    acq_price: float = ACQ_PRICE
    tax_rate: float = TAX_RATE
    interest_rate: float = INTEREST_RATE
    wacc: float = WACC
    gross_margin: float = ACQ_GROSS_MARGIN
    npv_years: int = 7
    terminal_growth: float = 0.03


def accretion_dilution(a: DealAssumptions) -> dict:
    """Year-1 pro-forma EPS accretion/dilution from the financing + earnings + synergies."""
    new_shares = a.deal_value * a.equity_pct / a.acq_price
    cash_used = a.deal_value * a.cash_pct
    after_tax_financing = -cash_used * a.interest_rate * (1 - a.tax_rate)  # foregone interest

    target_ni = a.target_revenue * a.target_net_margin
    # synergies: cost takeout flows ~fully; revenue synergy earns gross margin
    pretax_syn = a.cost_synergy + a.revenue_synergy_arr * a.gross_margin
    after_tax_syn = pretax_syn * (1 - a.tax_rate)

    proforma_ni = a.acq_net_income + target_ni + after_tax_syn + after_tax_financing
    proforma_shares = a.acq_shares + new_shares
    proforma_eps = proforma_ni / proforma_shares
    standalone_eps = a.acq_net_income / a.acq_shares
    accretion = proforma_eps / standalone_eps - 1
    return {
        "new_shares_issued": new_shares,
        "cash_used": cash_used,
        "standalone_eps": standalone_eps,
        "proforma_eps": proforma_eps,
        "eps_accretion_dilution_pct": accretion,
        "is_accretive": accretion > 0,
        "target_net_income": target_ni,
        "after_tax_synergies": after_tax_syn,
        "after_tax_financing_cost": after_tax_financing,
        "proforma_net_income": proforma_ni,
    }


def deal_npv(a: DealAssumptions) -> dict:
    """DCF of incremental after-tax cash flow (target + synergies) vs the purchase price."""
    cfs = []
    arr = a.target_arr
    rev_syn = a.revenue_synergy_arr
    for t in range(1, a.npv_years + 1):
        arr *= (1 + a.target_arr_growth * (0.8 ** (t - 1)))    # growth decays
        rev_syn *= (1 + a.target_arr_growth * (0.8 ** (t - 1)))
        # after-tax cash flow: target gross profit + cost synergy + revenue-synergy GP, taxed
        pretax = arr * a.gross_margin * 0.45 + a.cost_synergy + rev_syn * a.gross_margin
        cfs.append(pretax * (1 - a.tax_rate))
    pv = sum(cf / (1 + a.wacc) ** t for t, cf in enumerate(cfs, start=1))
    terminal = cfs[-1] * (1 + a.terminal_growth) / (a.wacc - a.terminal_growth)
    pv_terminal = terminal / (1 + a.wacc) ** a.npv_years
    ev = pv + pv_terminal
    npv = ev - a.deal_value
    # simple payback on undiscounted incremental cash flow
    cum, payback = 0.0, None
    for t, cf in enumerate(cfs, start=1):
        cum += cf
        if cum >= a.deal_value and payback is None:
            payback = t
    return {"pv_explicit": pv, "pv_terminal": pv_terminal, "enterprise_value_created": ev,
            "deal_value": a.deal_value, "npv": npv, "value_creation_multiple": ev / a.deal_value,
            "payback_years": payback, "implied_arr_multiple": a.deal_value / a.target_arr}


if __name__ == "__main__":
    print("=== Latest organic/inorganic split ===")
    for k, v in latest_split().items():
        print(f"  {k:16s}: {v}")
    print("\n=== CyberArk integration ramp (head) ===")
    print(integration_ramp("CyberArk").head(4).to_string(index=False))
    a = DealAssumptions()
    print("\n=== Hypothetical tuck-in: accretion/dilution ===")
    for k, v in accretion_dilution(a).items():
        print(f"  {k:28s}: {v}")
    print("\n=== Hypothetical tuck-in: NPV ===")
    for k, v in deal_npv(a).items():
        print(f"  {k:28s}: {v}")
