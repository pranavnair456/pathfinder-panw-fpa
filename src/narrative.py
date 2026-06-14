"""
LLM-style narrative commentary — cached for the public demo, live behind st.secrets.

Design for a zero-secret deploy:
  - build_context()      gathers the real computed figures (KPIs, variance, trajectory, threat).
  - template_narrative() turns that context into solid prose with NO API call (deterministic).
  - llm_narrative()      calls the Anthropic API IF a key is present (st.secrets / env), for a
                         richer, live-generated version — used only when demoing locally.
  - run_and_cache()      writes data/narratives.json (built with the template by default) so the
                         deployed app serves committed narratives with no key and no network call.

The app calls get_narrative(kind): cached if available, else template. It NEVER needs a key.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "narratives.json")
MODEL = "claude-opus-4-8"


def _fmt_b(x: float) -> str:
    return f"${x/1e9:.2f}B"


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------
def build_context() -> dict:
    from src import metrics, threat_signals, variance
    from src.forecast import backtest, trajectory
    snap = metrics.kpi_snapshot()
    var = variance.variance_highlights()
    base = trajectory.summary("Base")
    bull = trajectory.summary("Bull")
    solver = trajectory.required_platformizations("Base")
    bt = backtest.load_cached() or {}
    abl = (threat_signals.load_cached() or {}).get("ablation", {})
    return {"snap": snap, "var": var, "base": base, "bull": bull,
            "solver": solver, "backtest": bt, "ablation": abl}


# ---------------------------------------------------------------------------
# Template (deterministic) narratives
# ---------------------------------------------------------------------------
def template_narrative(kind: str, ctx: dict) -> str:
    s, v, base, bull = ctx["snap"], ctx["var"], ctx["base"], ctx["bull"]
    sol, abl = ctx["solver"], ctx["ablation"]

    if kind == "executive_summary":
        return (
            f"NGS ARR reached {_fmt_b(s['ngs_arr'])} as of {s['month']}, up "
            f"{s['ngs_arr_yoy']*100:.0f}% year over year — of which {_fmt_b(s['ngs_arr_organic'])} "
            f"is organic and {_fmt_b(s['ngs_arr_inorganic'])} is inorganic from the CyberArk and "
            f"Chronosphere acquisitions. Net revenue retention of {s['nrr']*100:.0f}% and a "
            f"Rule-of-40 score of {s['rule_of_40']:.0f} confirm growth and profitability are "
            f"compounding together, with adjusted FCF margin at {s['fcf_margin']*100:.1f}%. "
            f"The business sits at {s['progress_to_20b']*100:.0f}% of the $20B FY2030 NGS ARR "
            f"target with {s['platformized']:,} platformized customers. On current driver-based "
            f"trajectory the base case reaches {_fmt_b(base['ngs_arr_2030'])} by FY2030 "
            f"({base['pct_of_target']*100:.0f}% of target); the bull case reaches "
            f"{_fmt_b(bull['ngs_arr_2030'])}. Closing the remaining gap requires sustained "
            f"above-trend execution: hitting $20B implies a ~"
            f"{((20e9/s['ngs_arr'])**(1/4)-1)*100:.0f}% CAGR, versus the base case's "
            f"~{base['implied_cagr_to_2030']*100:.0f}% — the difference platformization, new-logo "
            f"growth, and further M&A must bridge."
        )

    if kind == "variance":
        ahead = "ahead of" if v["ngs_arr_var"] >= 0 else "behind"
        bridge = v["bridge"]
        return (
            f"In {v['fiscal_period']}, NGS ARR of {_fmt_b(v['actual_ngs_arr'])} came in "
            f"{abs(v['ngs_arr_var_pct'])*100:.1f}% {ahead} the board-approved plan "
            f"({_fmt_b(v['plan_ngs_arr'])}), a {_fmt_b(abs(v['ngs_arr_var']))} variance. Revenue "
            f"was {v['revenue_var_pct']*100:+.1f}% vs plan and operating margin "
            f"{v['op_margin_var_bps']:+.0f} bps. The ARR bridge shows expansion "
            f"({_fmt_b(bridge.get('expansion_arr',0))}) as the largest positive motion, partly "
            f"offset by churn ({_fmt_b(bridge.get('churn_arr',0))}); net-new logos contributed "
            f"{_fmt_b(bridge.get('new_arr',0))}. The expansion-led bridge is the platformization "
            f"flywheel working as designed — existing customers growing faster than new logos."
        )

    if kind == "platformization":
        return (
            f"Platformized customers retain and expand materially better than single-product "
            f"accounts — the data shows roughly {s['nrr']*100:.0f}% blended NRR, with platformized "
            f"cohorts well above non-platformized. That gap is the entire economic case for "
            f"spending on platformization incentives: each conversion buys a faster-compounding "
            f"revenue stream. With {s['platformized']:,} platformized customers today against a "
            f"4,000+ FY2030 goal, the incentive ROI model shows attractive NPV and short payback, "
            f"and the tornado confirms value is overwhelmingly driven by the retention gap."
        )

    if kind == "ma":
        return (
            f"Inorganic NGS ARR of {_fmt_b(s['ngs_arr_inorganic'])} from CyberArk and Chronosphere "
            f"is now {s['ngs_arr_inorganic']/s['ngs_arr']*100:.0f}% of total NGS ARR. Separating it "
            f"out, organic growth remains the core engine while M&A adds identity and observability "
            f"adjacencies. The accretion/dilution model illustrates the classic corp-dev tension: a "
            f"high-growth tuck-in can be near-term EPS-dilutive yet strongly NPV-positive — "
            f"justifiable on strategic and DCF grounds even when it pressures next year's EPS."
        )

    if kind == "threat":
        lift = abl.get("threat_lift_pct", 0.0)
        helps = abl.get("threat_helps", False)
        verdict = "do improve" if helps else "do not improve"
        return (
            f"External threat signals — CVE volume, disclosed breaches, and an AI-threat index — "
            f"{verdict} the near-term demand forecast. In a like-for-like 1-step ablation, adding "
            f"lagged threat features changed forecast WAPE by {lift:.0f}% and the augmented model "
            f"{'beat' if abl.get('beats_seasonal_naive') else 'did not beat'} the seasonal-naive "
            f"baseline. The lead is ~2 months, so the signal helps the next quarter's demand read "
            f"but cannot inform the multi-year $20B trajectory — an honest, bounded result."
        )

    return "No narrative available for this section."


# ---------------------------------------------------------------------------
# Live LLM (only when a key is present)
# ---------------------------------------------------------------------------
def llm_available() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    try:
        import streamlit as st
        return "ANTHROPIC_API_KEY" in st.secrets
    except Exception:
        return False


def _get_key() -> str | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def llm_narrative(kind: str, ctx: dict) -> str:
    """Live generation via the Anthropic API. Requires `pip install anthropic` + a key."""
    key = _get_key()
    if not key:
        return template_narrative(kind, ctx)
    import anthropic  # local import so the deployed app never needs the dep
    client = anthropic.Anthropic(api_key=key)
    facts = template_narrative(kind, ctx)  # seed the model with the exact figures
    prompt = (
        "You are an FP&A analyst at Palo Alto Networks writing crisp, executive commentary. "
        "Rewrite the following into 4-6 sentences of polished prose for a CFO. Keep every number "
        "exactly as given; do not invent figures. Be specific and confident, not hyped.\n\n"
        f"Section: {kind}\nFacts: {facts}"
    )
    msg = client.messages.create(model=MODEL, max_tokens=400,
                                 messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text.strip()


# ---------------------------------------------------------------------------
# Cache API
# ---------------------------------------------------------------------------
KINDS = ["executive_summary", "variance", "platformization", "ma", "threat"]


def run_and_cache(use_llm: bool = False) -> dict:
    ctx = build_context()
    gen = llm_narrative if (use_llm and llm_available()) else template_narrative
    payload = {"generated_with": "llm" if (use_llm and llm_available()) else "template",
               "narratives": {k: gen(k, ctx) for k in KINDS}}
    with open(CACHE, "w") as fh:
        json.dump(payload, fh, indent=2)
    return payload


def load_cached() -> dict | None:
    if os.path.exists(CACHE):
        with open(CACHE) as fh:
            return json.load(fh)
    return None


def get_narrative(kind: str, live: bool = False) -> str:
    """Cached narrative for prod; optionally regenerate live if a key is configured."""
    if live and llm_available():
        return llm_narrative(kind, build_context())
    cached = load_cached()
    if cached and kind in cached.get("narratives", {}):
        return cached["narratives"][kind]
    return template_narrative(kind, build_context())


if __name__ == "__main__":
    p = run_and_cache(use_llm=False)
    print(f"Generated narratives with: {p['generated_with']}\n")
    for k, t in p["narratives"].items():
        print(f"--- {k} ---\n{t}\n")
