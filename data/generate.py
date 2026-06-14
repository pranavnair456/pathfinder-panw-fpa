"""
Pathfinder — synthetic data generator (seeded, reproducible).

Builds a customer-level SaaS ledger for a fictional PANW FP&A team and the surrounding GL,
plan, M&A, and threat-signal tables. AGGREGATES are calibrated to PANW's public disclosures
(see data/calibration.py and docs/assumptions.md). ALL DATA IS SYNTHETIC.

Design choice — "reconcile by construction":
    The subscription-event ledger is the source of truth for ARR. For each platform/month we know
    the target ending ARR (from the calibrated curve). We emit realistic new / expansion /
    contraction / churn / platformization events, then add ONE small balancing event so the
    platform's ending ARR equals the target EXACTLY. This makes the SQL ARR roll-forward tie to
    the penny and gives the governance/reconciliation layer something real to verify.

Run:  python data/generate.py     ->  writes data/raw/*.csv
"""
from __future__ import annotations

import os
from datetime import date

import numpy as np
import pandas as pd

import calibration as C  # noqa: E402  (run from data/ or via -m; see __main__)

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ORGANIC_PLATFORMS = ["Strata", "Prisma Cloud", "Cortex"]

# Modules under each platform (for product/module-level grain).
PLATFORM_MODULES = {
    "Strata": ["NGFW Software", "SASE / Prisma Access", "Cloud-Delivered Security Services"],
    "Prisma Cloud": ["CSPM", "CWP (Workload)", "Code Security", "AI Security (Prisma AIRS)"],
    "Cortex": ["XSIAM", "XDR", "XSOAR", "AgentiX"],
    "Identity": ["Privileged Access (PAM)", "Secrets Management", "Identity Security Platform"],
    "Observability": ["Metrics", "Logs", "Tracing"],
}


# ---------------------------------------------------------------------------
# Fiscal-calendar helpers (PANW FY ends July 31)
# ---------------------------------------------------------------------------
def fiscal_year(d: pd.Timestamp) -> int:
    return d.year + 1 if d.month >= 8 else d.year


def fiscal_quarter(d: pd.Timestamp) -> int:
    m = d.month
    if m in (8, 9, 10):
        return 1
    if m in (11, 12, 1):
        return 2
    if m in (2, 3, 4):
        return 3
    return 4  # 5,6,7


def month_spine(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq="MS")


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------
def build_dim_date(end: str = C.SPINE_END) -> pd.DataFrame:
    idx = month_spine(C.HISTORY_START, end)
    df = pd.DataFrame({"month": idx})
    df["fiscal_year"] = df["month"].apply(fiscal_year)
    df["fiscal_quarter"] = df["month"].apply(fiscal_quarter)
    df["fy_label"] = "FY" + df["fiscal_year"].astype(str)
    df["fq_label"] = df["fy_label"] + "-Q" + df["fiscal_quarter"].astype(str)
    df["calendar_year"] = df["month"].dt.year
    df["calendar_month"] = df["month"].dt.month
    # Fiscal quarter-end months for PANW are Oct (Q1), Jan (Q2), Apr (Q3), Jul (Q4).
    df["is_quarter_end_month"] = df["calendar_month"].isin([10, 1, 4, 7])
    df["is_history"] = df["month"] <= pd.Timestamp(C.HISTORY_END)
    df["date_id"] = df["month"].dt.strftime("%Y-%m")
    return df


def build_dim_platform() -> pd.DataFrame:
    rows = []
    parent = {
        "Strata": "Network Security", "Prisma Cloud": "Cloud Security",
        "Cortex": "Security Operations", "Identity": "Identity Security (CyberArk)",
        "Observability": "Observability (Chronosphere)",
    }
    source = {"Strata": "organic", "Prisma Cloud": "organic", "Cortex": "organic",
              "Identity": "CyberArk", "Observability": "Chronosphere"}
    pid = 1
    for plat, modules in PLATFORM_MODULES.items():
        for mod in modules:
            rows.append({
                "platform_id": pid, "platform": plat, "segment_group": parent[plat],
                "module": mod, "source": source[plat],
                "is_organic": source[plat] == "organic",
            })
            pid += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Calibrated monthly ARR curves
# ---------------------------------------------------------------------------
def _quarterly_to_monthly(qvals: dict, spine: pd.DatetimeIndex) -> pd.Series:
    """Convert {(fy,fq): value} quarter-END levels to a monthly END-of-month level series.

    Within a quarter the increment is back-loaded ([0.2, 0.3, 0.5]) to mimic enterprise deals
    closing late in the quarter. The PRE-history starting point is extrapolated from the first
    quarter's implied growth so month 1 isn't a cliff.
    """
    weights = [0.2, 0.3, 0.5]
    # ordered list of quarter levels aligned to the spine
    months = list(spine)
    # build quarter-end level lookup
    out = pd.Series(index=spine, dtype=float)
    # group months by (fy, fq)
    by_q: dict[tuple, list] = {}
    for m in months:
        by_q.setdefault((fiscal_year(m), fiscal_quarter(m)), []).append(m)
    prev_level = None
    ordered_q = sorted(by_q.keys())
    for i, q in enumerate(ordered_q):
        level = qvals.get(q)
        if level is None:
            continue
        if prev_level is None:
            # extrapolate a start point one quarter back using next growth
            nxt = qvals.get(ordered_q[i + 1]) if i + 1 < len(ordered_q) else level
            g = (level / nxt) if nxt else 0.9
            prev_level = level * g  # slightly below first level
        inc = level - prev_level
        qm = by_q[q]
        cum = 0.0
        for j, m in enumerate(qm):
            w = weights[j] if j < len(weights) else weights[-1]
            cum += w
            out[m] = prev_level + inc * cum
        prev_level = level
    return out.ffill()


def organic_monthly_by_platform(spine: pd.DatetimeIndex) -> dict[str, pd.Series]:
    """Monthly END-of-month ORGANIC NGS ARR ($) per organic platform, summing to the total curve."""
    # total organic quarterly -> {(fy,fq): $}
    qtotal = {}
    for fy, qs in C.NGS_ARR_ORGANIC_B.items():
        for qi, v in enumerate(qs, start=1):
            qtotal[(fy, qi)] = v * 1e9
    total_m = _quarterly_to_monthly(qtotal, spine)
    out = {p: pd.Series(0.0, index=spine) for p in ORGANIC_PLATFORMS}
    for m in spine:
        fy = fiscal_year(m)
        fr = C.PLATFORM_FRACTIONS.get(fy, C.PLATFORM_FRACTIONS[2026])
        out["Strata"][m] = total_m[m] * fr[0]
        out["Prisma Cloud"][m] = total_m[m] * fr[1]
        out["Cortex"][m] = total_m[m] * fr[2]
    return out


def inorganic_monthly_by_platform(spine: pd.DatetimeIndex) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for deal, cfg in C.INORGANIC_DEALS.items():
        plat = cfg["platform"]
        s = pd.Series(0.0, index=spine)
        close = pd.Timestamp(cfg["close_month"])
        arr = cfg["arr_at_close_b"] * 1e9
        for m in spine:
            if m < close:
                s[m] = 0.0
            else:
                k = (m.year - close.year) * 12 + (m.month - close.month)
                s[m] = arr * (1 + cfg["monthly_growth"]) ** k
        out[plat] = s
    return out


# ---------------------------------------------------------------------------
# Ledger simulation
# ---------------------------------------------------------------------------
def _distribute(total: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """n positive amounts summing EXACTLY to `total` (Dirichlet weights)."""
    if n <= 0 or total <= 0:
        return np.array([])
    w = rng.dirichlet(np.ones(n) * 3.0)
    amts = w * total
    amts[-1] = total - amts[:-1].sum()  # absorb fp error
    return amts


class CustomerPool:
    """Holds customer attributes and a name generator."""

    def __init__(self, rng):
        self.rng = rng
        self.next_id = 1
        self.customers: dict[int, dict] = {}
        seg_names, seg_p = zip(*[(k, v[0]) for k, v in C.SEGMENTS.items()])
        self.seg_names, self.seg_p = list(seg_names), np.array(seg_p) / sum(seg_p)
        self.reg_names, self.reg_p = list(C.REGIONS), np.array(list(C.REGIONS.values()))
        self.ind_names, self.ind_p = list(C.INDUSTRIES), np.array(list(C.INDUSTRIES.values()))

    def new_customer(self, month, source="organic", inorganic_segment=None):
        cid = self.next_id
        self.next_id += 1
        seg = inorganic_segment or self.rng.choice(self.seg_names, p=self.seg_p)
        self.customers[cid] = {
            "customer_id": cid,
            "customer_name": f"{source[:3].upper()}-{cid:06d}",
            "segment": seg,
            "region": self.rng.choice(self.reg_names, p=self.reg_p),
            "industry": self.rng.choice(self.ind_names, p=self.ind_p),
            "acquisition_cohort_month": month.strftime("%Y-%m"),
            "platformized_flag": False,
            "platformization_date": None,
            "source": source,
            "organic_inorganic": "organic" if source == "organic" else "inorganic",
        }
        return cid


def simulate(spine_hist: pd.DatetimeIndex, rng: np.random.Generator):
    """Return (events_df, dim_customer_df, platform_arr_history_df)."""
    organic = organic_monthly_by_platform(spine_hist)
    inorganic = inorganic_monthly_by_platform(spine_hist)
    pool = CustomerPool(rng)

    subs: dict[tuple, float] = {}          # (cust_id, platform) -> arr
    cust_platforms: dict[int, set] = {}    # cust_id -> set(platform)
    events = []
    eid = 0
    arr_history = []  # monthly platform ARR snapshots

    def add_event(month, cid, platform, etype, delta, acv=0.0, term=12):
        nonlocal eid
        eid += 1
        events.append({
            "event_id": eid, "month": month.strftime("%Y-%m"), "customer_id": cid,
            "platform": platform, "module": rng.choice(PLATFORM_MODULES[platform]),
            "event_type": etype, "arr_delta": round(float(delta), 2),
            "acv": round(float(acv), 2), "term_months": int(term),
        })

    def platform_base(platform):
        return sum(v for (c, p), v in subs.items() if p == platform)

    # platformization schedule: target cumulative count per quarter-end month
    plat_targets = {(fy, q): n for (fy, q), n in C.PLATFORMIZED_COUNT.items()}

    for m in spine_hist:
        fy, fq = fiscal_year(m), fiscal_quarter(m)
        seasonal = 1.0 + (0.25 if fq == 4 else (-0.1 if fq == 1 else 0.0))  # Q4-heavy bookings

        # ---- ORGANIC platforms: realize the calibrated ending ARR exactly ----
        for plat in ORGANIC_PLATFORMS:
            base = platform_base(plat)
            target_end = organic[plat][m]
            realized = 0.0
            active = [(c, p) for (c, p) in subs if p == plat]

            # churn: terminate whole subs (prefer non-platformized, smaller)
            if active and base > 0:
                churn_amt = base * (
                    C.CHURN_MONTHLY_NONPLATFORM * 0.7 + C.CHURN_MONTHLY_PLATFORM * 0.3)
                cand = sorted(
                    active,
                    key=lambda cp: (pool.customers[cp[0]]["platformized_flag"], subs[cp]))
                acc = 0.0
                for cp in cand:
                    if acc >= churn_amt:
                        break
                    amt = subs[cp]
                    add_event(m, cp[0], plat, "churn", -amt, term=0)
                    realized -= amt
                    acc += amt
                    del subs[cp]
                    cust_platforms[cp[0]].discard(plat)

            # contraction on a few surviving subs
            active = [(c, p) for (c, p) in subs if p == plat]
            if active:
                contraction_amt = base * C.CONTRACTION_MONTHLY
                k = min(len(active), max(1, len(active) // 25))
                picks = [active[i] for i in rng.choice(len(active), size=k, replace=False)]
                for cp, amt in zip(picks, _distribute(contraction_amt, len(picks), rng)):
                    amt = min(amt, subs[cp] * 0.5)
                    subs[cp] -= amt
                    realized -= amt
                    add_event(m, cp[0], plat, "contraction", -amt)

            # expansion (weighted to platformized) — drives NRR
            active = [(c, p) for (c, p) in subs if p == plat]
            if active:
                exp_rate = 0.018 * seasonal
                expansion_amt = base * exp_rate
                k = min(len(active), max(1, len(active) // 8))
                # Concentrate expansion on platformized accounts (they land-and-expand); single-
                # product accounts rarely expand. This is what drives the NRR gap that Option B
                # monetizes. Weight ~3:1 selection toward platformized (yields ~128% vs ~104%).
                wts = np.array([
                    (3.0 if pool.customers[c]["platformized_flag"] else 1.0)
                    for (c, p) in active])
                wts = wts / wts.sum()
                idx = rng.choice(len(active), size=k, replace=False, p=wts)
                picks = [active[i] for i in idx]
                for cp, amt in zip(picks, _distribute(expansion_amt, len(picks), rng)):
                    subs[cp] += amt
                    realized += amt
                    add_event(m, cp[0], plat, "expansion", amt)

            # new business: target so ending ~ target_end (balanced exactly after)
            net = target_end - base
            new_amt = max(0.0, net - realized)
            if new_amt > 0:
                seg_mean = {k: v[1] for k, v in C.SEGMENTS.items()}
                avg_acv = sum(C.SEGMENTS[s][0] * C.SEGMENTS[s][1] for s in C.SEGMENTS)
                n_deals = max(1, int(new_amt / (avg_acv * 1.2)))
                n_deals = min(n_deals, 1500)
                for amt in _distribute(new_amt, n_deals, rng):
                    if rng.random() < 0.5 or not cust_platforms:  # new logo
                        cid = pool.new_customer(m)
                        cust_platforms[cid] = set()
                    else:  # cross-sell to an existing customer
                        cid = int(rng.choice(list(cust_platforms.keys())))
                    subs[(cid, plat)] = subs.get((cid, plat), 0.0) + amt
                    cust_platforms[cid].add(plat)
                    term = int(rng.choice([12, 24, 36], p=[0.5, 0.3, 0.2]))
                    add_event(m, cid, plat, "new", amt, acv=amt, term=term)
                    realized += amt

            # renewals (zero-delta, for realism) on a sample of subs at anniversary
            active = [(c, p) for (c, p) in subs if p == plat]
            if active and m.month in (1, 4, 7, 10):
                k = min(len(active), max(1, len(active) // 12))
                for i in rng.choice(len(active), size=k, replace=False):
                    cp = active[i]
                    add_event(m, cp[0], plat, "renewal", 0.0, term=12)

            # exact balancing event so platform_base == target_end
            adjust = target_end - platform_base(plat)
            if abs(adjust) > 1.0:
                if adjust > 0:
                    cid = pool.new_customer(m)
                    cust_platforms[cid] = {plat}
                    subs[(cid, plat)] = adjust
                    add_event(m, cid, plat, "new", adjust, acv=adjust, term=12)
                else:
                    # trim from the largest sub
                    cp = max((cp for cp in subs if cp[1] == plat), key=lambda x: subs[x])
                    subs[cp] += adjust
                    add_event(m, cp[0], plat, "contraction", adjust)

        # ---- platformization conversions at quarter-end ----
        if (fy, fq) in plat_targets:
            current = sum(1 for c in pool.customers.values() if c["platformized_flag"])
            want = plat_targets[(fy, fq)]
            need = max(0, want - current)
            # Prefer genuine multi-platform customers; fall back to the largest single-platform
            # accounts (a big customer signing a platform agreement) so we hit the disclosed count.
            multi = [cid for cid, plats in cust_platforms.items()
                     if len(plats) >= 2 and not pool.customers[cid]["platformized_flag"]]
            rng.shuffle(multi)
            chosen = multi[:need]
            if len(chosen) < need:
                single = [cid for cid, plats in cust_platforms.items()
                          if len(plats) == 1 and not pool.customers[cid]["platformized_flag"]]
                single.sort(key=lambda c: -sum(subs.get((c, p), 0) for p in cust_platforms[c]))
                chosen += single[:need - len(chosen)]
            for cid in chosen:
                pool.customers[cid]["platformized_flag"] = True
                pool.customers[cid]["platformization_date"] = m.strftime("%Y-%m")
                # platformization bump on the customer's largest sub (counts as expansion)
                cps = [(cid, p) for p in cust_platforms[cid] if (cid, p) in subs]
                if cps:
                    cp = max(cps, key=lambda x: subs[x])
                    bump = subs[cp] * 0.06
                    subs[cp] += bump
                    add_event(m, cid, cp[1], "platformization", bump)

        # ---- inorganic platforms: onboard at close, then grow ----
        for plat in ["Observability", "Identity"]:
            if plat not in inorganic:
                continue
            target = inorganic[plat][m]
            base = platform_base(plat)
            if base == 0 and target > 0:  # close month: onboard a book of customers
                deal = "Chronosphere" if plat == "Observability" else "CyberArk"
                n = 60 if plat == "Observability" else 220
                for amt in _distribute(target, n, rng):
                    cid = pool.new_customer(m, source=deal,
                                            inorganic_segment="Enterprise")
                    subs[(cid, plat)] = amt
                    cust_platforms[cid] = {plat}
                    add_event(m, cid, plat, "inorganic_onboarding", amt, acv=amt, term=12)
            elif target > base > 0:  # subsequent growth via expansion
                grow = target - base
                active = [(c, p) for (c, p) in subs if p == plat]
                for cp, amt in zip(active, _distribute(grow, len(active), rng)):
                    subs[cp] += amt
                    add_event(m, cp[0], plat, "expansion", amt)
                # balance
                adj = target - platform_base(plat)
                if abs(adj) > 1.0 and active:
                    subs[active[0]] += adj
                    add_event(m, active[0][0], plat, "expansion", adj)

        # snapshot
        for plat in ORGANIC_PLATFORMS + ["Identity", "Observability"]:
            arr_history.append({
                "month": m.strftime("%Y-%m"), "platform": plat,
                "ending_arr": round(platform_base(plat), 2),
                "is_organic": plat in ORGANIC_PLATFORMS,
            })

    events_df = pd.DataFrame(events)
    dim_customer = pd.DataFrame(list(pool.customers.values()))
    arr_hist_df = pd.DataFrame(arr_history)
    return events_df, dim_customer, arr_hist_df


# ---------------------------------------------------------------------------
# Financials (GL) — calibrated to the SEC GAAP backbone
# ---------------------------------------------------------------------------
def build_fact_financials(dim_date, arr_hist_df, rng) -> pd.DataFrame:
    backbone = pd.read_csv(os.path.join(HERE, os.pardir, "docs", "panw_real_gaap_backbone.csv"))
    backbone["fy"] = backbone["fiscal_year"].str.replace("FY", "").astype(int)
    backbone["q"] = backbone["fiscal_quarter"].str.replace("Q", "").astype(int)
    rev_q = {(r.fy, r.q): r.revenue_usd for r in backbone.itertuples() if not pd.isna(r.revenue_usd)}
    rpo_q = {(r.fy, r.q): r.rpo_usd for r in backbone.itertuples() if not pd.isna(r.rpo_usd)}
    dc_q = {(r.fy, r.q): r.deferred_rev_current_usd for r in backbone.itertuples()
            if not pd.isna(r.deferred_rev_current_usd)}
    dl_q = {(r.fy, r.q): r.deferred_rev_noncurrent_usd for r in backbone.itertuples()
            if not pd.isna(r.deferred_rev_noncurrent_usd)}

    hist = dim_date[dim_date["is_history"]].copy()
    spine = pd.DatetimeIndex(hist["month"])

    # Quarterly revenue: fill missing Q4 with seasonal uplift over Q3, then monthly interpolate.
    def fill_q4(qmap):
        out = dict(qmap)
        for fy in range(2021, 2027):
            if (fy, 4) not in out and (fy, 3) in out:
                out[(fy, 4)] = out[(fy, 3)] * 1.08
        return out
    rev_q = fill_q4(rev_q)

    # monthly revenue from quarterly totals -> monthly (each month ~ 1/3 of its quarter, seasonal)
    rev_m = pd.Series(index=spine, dtype=float)
    rpo_m = _quarterly_to_monthly({(fy, q): v for (fy, q), v in rpo_q.items()}, spine)
    dc_m = _quarterly_to_monthly({(fy, q): v for (fy, q), v in dc_q.items()}, spine)
    dl_m = _quarterly_to_monthly({(fy, q): v for (fy, q), v in dl_q.items()}, spine)
    for m in spine:
        fy, fq = fiscal_year(m), fiscal_quarter(m)
        qtot = rev_q.get((fy, fq))
        if qtot is None:
            qtot = rev_q.get((fy, 3), 1e9) * 1.05
        w = {1: 0.31, 2: 0.33, 3: 0.36}  # within-quarter month shares (back-loaded)
        pos = [mm for mm in spine if fiscal_year(mm) == fy and fiscal_quarter(mm) == fq]
        j = pos.index(m)
        rev_m[m] = qtot * (w[1] if j == 0 else w[2] if j == 1 else w[3])

    ngs = arr_hist_df.groupby("month")["ending_arr"].sum()
    rows = []
    for m in spine:
        key = m.strftime("%Y-%m")
        fy = fiscal_year(m)
        total_rev = rev_m[m]
        prod_share = C.PRODUCT_REV_SHARE.get(fy, 0.20)
        product = total_rev * prod_share
        subscription = total_rev - product
        gp = total_rev * C.NONGAAP_GROSS_MARGIN
        cogs = total_rev - gp
        opm = C.NONGAAP_OPMARGIN_PATH.get(fy, 0.29)
        op_income = total_rev * opm
        opex = gp - op_income
        # split opex S&M / R&D / G&A ~ 0.52 / 0.33 / 0.15
        sm, rd, ga = opex * 0.52, opex * 0.33, opex * 0.15
        fcf_margin = C.ADJ_FCF_MARGIN_PATH.get(fy, 0.37)
        rows.append({
            "month": key, "fiscal_year": f"FY{fy}", "fiscal_quarter": f"Q{fiscal_quarter(m)}",
            "total_revenue": round(total_rev, 2), "product_revenue": round(product, 2),
            "subscription_revenue": round(subscription, 2), "cogs": round(cogs, 2),
            "gross_profit": round(gp, 2), "sales_marketing": round(sm, 2),
            "research_development": round(rd, 2), "general_admin": round(ga, 2),
            "operating_income": round(op_income, 2), "operating_margin": round(opm, 4),
            "ngs_arr_total": round(float(ngs.get(key, np.nan)), 2),
            "rpo": round(float(rpo_m[m]), 2),
            "deferred_revenue_current": round(float(dc_m[m]), 2),
            "deferred_revenue_noncurrent": round(float(dl_m[m]), 2),
            "adjusted_free_cash_flow": round(total_rev * fcf_margin, 2),
            "fcf_margin": round(fcf_margin, 4),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Plan / budget
# ---------------------------------------------------------------------------
def build_fact_plan(fin_df, dim_date, rng) -> pd.DataFrame:
    """Budget version per period: plan set at FY start, slightly off actuals, plus forward plan
    FY27-FY30 ramping NGS ARR toward the $20B FY2030 target."""
    rows = []
    # historical plan = actual * (1 +/- small FY bias)
    fy_bias = {f"FY{y}": b for y, b in
               {2021: 0.02, 2022: -0.03, 2023: 0.01, 2024: -0.02, 2025: 0.03, 2026: -0.04}.items()}
    for r in fin_df.itertuples():
        bias = fy_bias.get(r.fiscal_year, 0.0)
        for metric, val in [("ngs_arr_total", r.ngs_arr_total),
                            ("total_revenue", r.total_revenue),
                            ("operating_margin", r.operating_margin)]:
            plan = val * (1 + bias) if metric != "operating_margin" else val + bias * 0.1
            rows.append({"month": r.month, "metric": metric,
                        "plan_value": round(plan, 4), "plan_version": "Board-Approved Plan"})
    # forward plan FY27-FY30 (NGS ARR + revenue) ramping to $20B
    fwd = dim_date[~dim_date["is_history"]].copy()
    last_ngs = fin_df["ngs_arr_total"].iloc[-1]
    last_rev = fin_df["total_revenue"].iloc[-1]
    target = C.TARGET_NGS_ARR_FY2030_B * 1e9
    n = len(fwd)
    g = (target / last_ngs) ** (1 / n) - 1  # CAGR(monthly) to hit $20B at FY2030 end
    for i, r in enumerate(fwd.itertuples(), start=1):
        plan_ngs = last_ngs * (1 + g) ** i
        plan_rev = last_rev * (1 + g * 0.75) ** i
        rows.append({"month": r.date_id, "metric": "ngs_arr_total",
                    "plan_value": round(plan_ngs, 2), "plan_version": "FY30 Strategic Plan"})
        rows.append({"month": r.date_id, "metric": "total_revenue",
                    "plan_value": round(plan_rev, 2), "plan_version": "FY30 Strategic Plan"})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# M&A deals
# ---------------------------------------------------------------------------
def build_fact_ma_deals() -> pd.DataFrame:
    return pd.DataFrame([
        {"deal_name": "CyberArk", "platform": "Identity", "deal_value_usd": 25_000_000_000,
         "cash_pct": 0.40, "equity_pct": 0.60, "target_arr_usd": 1_400_000_000,
         "target_arr_growth": 0.30, "close_date": "2026-02-11",
         "integration_ramp_months": 24, "cost_synergy_pct": 0.08, "revenue_synergy_pct": 0.12,
         "is_hypothetical": False},
        {"deal_name": "Chronosphere", "platform": "Observability", "deal_value_usd": 3_350_000_000,
         "cash_pct": 0.85, "equity_pct": 0.15, "target_arr_usd": 175_000_000,
         "target_arr_growth": 1.00, "close_date": "2026-01-15",
         "integration_ramp_months": 18, "cost_synergy_pct": 0.06, "revenue_synergy_pct": 0.20,
         "is_hypothetical": False},
        {"deal_name": "Hypothetical Tuck-In (NHI Security)", "platform": "Identity",
         "deal_value_usd": 2_000_000_000, "cash_pct": 0.60, "equity_pct": 0.40,
         "target_arr_usd": 120_000_000, "target_arr_growth": 0.70, "close_date": "2027-02-01",
         "integration_ramp_months": 18, "cost_synergy_pct": 0.07, "revenue_synergy_pct": 0.18,
         "is_hypothetical": True},
    ])


# ---------------------------------------------------------------------------
# Threat signals (Option D) — built with a real-but-noisy LEAD over bookings
# ---------------------------------------------------------------------------
def build_fact_threat_signals(fin_df, events_df, rng) -> pd.DataFrame:
    months = fin_df["month"].tolist()
    # net-new organic bookings per month (drives the "true" demand signal)
    bookings = (events_df[events_df["event_type"].isin(["new", "expansion"])]
                .groupby("month")["arr_delta"].sum().reindex(months).fillna(0.0))
    z = (bookings - bookings.mean()) / (bookings.std() + 1e-9)
    n = len(months)
    rows = []
    for i, mk in enumerate(months):
        # AI-threat index LEADS bookings by ~2 months: index[i] correlates with bookings[i+2]
        lead = z.iloc[min(i + 2, n - 1)]
        trend = i / n  # secular rise in threat activity
        ai_index = 100 + 35 * trend + 18 * lead + rng.normal(0, 9)
        cve = int(2200 + 1400 * trend + 220 * lead + rng.normal(0, 180))
        breaches = int(95 + 70 * trend + 12 * max(lead, 0) + rng.normal(0, 14))
        rows.append({"month": mk, "cve_count": max(cve, 0),
                    "disclosed_breach_count": max(breaches, 0),
                    "ai_threat_index": round(ai_index, 2)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.makedirs(RAW, exist_ok=True)
    rng = np.random.default_rng(C.RANDOM_SEED)
    print("Building dimensions ...")
    dim_date = build_dim_date()
    dim_platform = build_dim_platform()
    spine_hist = month_spine(C.HISTORY_START, C.HISTORY_END)

    print(f"Simulating customer ledger over {len(spine_hist)} months ...")
    events_df, dim_customer, arr_hist = simulate(spine_hist, rng)

    print("Building financials (calibrated to SEC GAAP backbone) ...")
    fin_df = build_fact_financials(dim_date, arr_hist, rng)
    plan_df = build_fact_plan(fin_df, dim_date, rng)
    ma_df = build_fact_ma_deals()
    threat_df = build_fact_threat_signals(fin_df, events_df, rng)

    out = {
        "dim_date": dim_date.assign(month=dim_date["month"].dt.strftime("%Y-%m-%d")),
        "dim_platform": dim_platform,
        "dim_customer": dim_customer,
        "fact_subscription_events": events_df,
        "fact_financials": fin_df,
        "fact_plan": plan_df,
        "fact_ma_deals": ma_df,
        "fact_threat_signals": threat_df,
        "_arr_history": arr_hist,  # helper, also useful for validation
    }
    for name, df in out.items():
        path = os.path.join(RAW, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"  wrote {name:28s} {len(df):>7,} rows -> {path}")

    # ---- calibration summary ----
    print("\n=== Calibration check (synthetic vs real anchors) ===")
    ngs_by_m = arr_hist.groupby("month")["ending_arr"].sum() / 1e9
    for mk, label, real in [("2025-07", "FY25Q4 NGS ARR", 5.60),
                            ("2026-01", "FY26Q2 NGS ARR", 6.30),
                            ("2026-04", "FY26Q3 NGS ARR", 8.10),
                            ("2026-07", "FY26Q4 NGS ARR", 8.90)]:
        syn = ngs_by_m.get(mk, float("nan"))
        print(f"  {label:18s}: synthetic ${syn:5.2f}B  vs real ~${real:.2f}B")
    plat3 = arr_hist[arr_hist["month"] == "2026-04"].groupby("platform")["ending_arr"].sum() / 1e9
    print("  Q3FY26 by platform ($B):", {k: round(v, 2) for k, v in plat3.items()})
    print(f"  customers: {len(dim_customer):,}  | events: {len(events_df):,}  |"
          f" platformized: {dim_customer['platformized_flag'].sum():,}")
    print("Done.")


if __name__ == "__main__":
    main()
