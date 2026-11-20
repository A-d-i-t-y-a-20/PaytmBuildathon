"""Platform Console engine: all numbers in code, reusing gullak/wapas_aao engines.

Nothing here invents new savings/offer maths -- it calls features/gullak/engine.py
(backtest, avg_daily, buffer_days, week_drop, rs) and features/wapas_aao/engine.py
(net_profit, discount_for, cost_check, OFFER_LIBRARY, MARGIN) on the mock merchant
population from generate_data.py. Every figure shown is labelled "mock pilot".
Concept demo, mock data only.
"""
from datetime import date, timedelta

from features.gullak import engine as GE
from features.wapas_aao import engine as WE

TODAY = "2026-11-19"
CHURN_OFFER = WE.OFFER_LIBRARY[WE.DEFAULT_OFFER]
DEFAULT_FEE_PCT = 8.0

# Safe credit timing (concept only -- lending partner decides eligibility/rates)
CREDIT_MONTHS = 6
CREDIT_SHARE_RANGE = (0.3, 0.9)        # the "existing offer" size varies per merchant, as a share of one month's sales
SAFE_INSTALMENT_PCT = 30.0            # <30% of a slow day's sales is tagged "safe"


# ---------------------------------------------------------------- per-merchant (reuses gullak engine)
def gullak_outcome(m):
    """Balance/buffer this merchant would have if Galla Gullak ran on their real settlements."""
    if not m.get("gullak_opted_in"):
        return {"opted_in": False, "balance": 0, "buffer_days": 0.0, "avg_daily": GE.avg_daily(m["settlements"], TODAY)}
    bt = GE.backtest(m["settlements"], m["obligations"], 3.0, TODAY, days=30)
    avg = GE.avg_daily(m["settlements"], TODAY)
    return {"opted_in": True, "balance": bt["total"], "buffer_days": GE.buffer_days(bt["total"], avg), "avg_daily": avg}


def churn_score(m, gullak_out):
    """Risk score 0-100, code rules only: falling UPI days, falling sales, no approvals in 14 days."""
    drop = GE.week_drop(m["settlements"], TODAY)  # positive = sales down this week
    score = 0
    flags = []
    if not m.get("weekly_active"):
        score += 40
        flags.append("falling_upi_days")
    if drop >= 15:
        score += min(40, round(drop))
        flags.append("falling_sales")
    if m.get("group") == "pilot" and m.get("approvals_last_14d", 0) == 0:
        score += 20
        flags.append("no_approvals_14d")
    score = min(100, score)
    save_pct = 1.0 if score >= 70 else (2.0 if score >= 40 else 3.0)
    suggested_amount = GE.compute_amount(gullak_out["avg_daily"] or 0, save_pct)
    return {"score": score, "flags": flags, "suggested_save_pct": save_pct, "suggested_save_amount": suggested_amount}


def instalment_safety(m):
    """Daily instalment of a mock credit offer as % of the merchant's slow-day sales. The offer
    size varies per merchant (seeded on id) so some come out safe and some too heavy."""
    rng = __import__("random").Random(f"credit-{m['id']}")
    offer_share = rng.uniform(*CREDIT_SHARE_RANGE)
    monthly_sales = (m["base_sales"] or 0) * 30
    offer_amount = monthly_sales * offer_share
    daily_instalment = offer_amount / (CREDIT_MONTHS * 30)
    slow_day_sales = (m["base_sales"] or 0) * 0.3  # matches the "slow day" multiplier used in generate_data
    pct = round(100 * daily_instalment / slow_day_sales, 1) if slow_day_sales else 999.0
    safe = pct < SAFE_INSTALMENT_PCT
    suggested_amount = offer_amount
    if not safe and slow_day_sales:
        suggested_amount = (SAFE_INSTALMENT_PCT / 100) * slow_day_sales * CREDIT_MONTHS * 30
    return {"offer_amount": round(offer_amount), "daily_instalment": round(daily_instalment),
            "pct_of_slow_day": pct, "safe": safe, "suggested_amount": round(suggested_amount)}


def winback_profit(m):
    """Extra profit from a Wapas Aao-style win-back campaign, reusing wapas_aao's own cost/profit
    maths (net_profit, discount_for, OFFER_LIBRARY, MARGIN) instead of inventing new formulas."""
    if m.get("group") != "pilot" or not m.get("lapsed_customers"):
        return {"returned": 0, "extra_sales": 0, "cost": 0, "profit": 0}
    offer = CHURN_OFFER
    rng = __import__("random").Random(f"winback-{m['id']}")
    reachable = round(m["lapsed_customers"] * 0.6)
    returned = round(reachable * rng.uniform(0.25, 0.45))
    avg_bill = max(offer["min_bill"], round((m["base_sales"] or 0) * 0.15))
    extra_sales = returned * avg_bill
    cost = returned * WE.discount_for(avg_bill, offer)
    profit = WE.net_profit(extra_sales, cost, WE.MARGIN)
    return {"returned": returned, "extra_sales": extra_sales, "cost": cost, "profit": profit}


def value_this_month(m, gullak_out, winback):
    """Rs this merchant gained this month (estimate): gullak saved + win-back profit."""
    gullak_gain = gullak_out["balance"] if gullak_out["opted_in"] else 0
    return gullak_gain + winback["profit"]


def merchant_row(m):
    g = gullak_outcome(m)
    w = winback_profit(m)
    c = churn_score(m, g)
    return {"merchant": m, "gullak": g, "winback": w, "churn": c, "value": value_this_month(m, g, w)}


# ---------------------------------------------------------------- pilot vs holdout aggregates
def _rate(xs):
    return round(100 * sum(1 for x in xs if x) / len(xs)) if xs else 0


def _avg(xs):
    return round(sum(xs) / len(xs)) if xs else 0


def pilot_summary(pilot_rows, holdout_rows):
    """Pilot vs holdout KPIs. Every figure here is from the mock population; label it 'mock pilot'."""
    def group_kpis(rows):
        merchants = [r["merchant"] for r in rows]
        gullak = [r["gullak"] for r in rows]
        return {
            "n": len(rows),
            "weekly_active_pct": _rate([m["weekly_active"] for m in merchants]),
            "gullak_optin_pct": _rate([m.get("gullak_opted_in", False) for m in merchants]),
            "avg_gullak_balance": _avg([g["balance"] for g in gullak if g["opted_in"]]),
            "avg_buffer_days": round(_avg([g["buffer_days"] for g in gullak if g["opted_in"]]), 1),
            "avg_winback_profit": _avg([r["winback"]["profit"] for r in rows]),
            "churn_rate_pct": _rate([r["churn"]["score"] >= 70 for r in rows]),
        }
    pilot, holdout = group_kpis(pilot_rows), group_kpis(holdout_rows)
    diff = {k: (pilot[k] - holdout[k]) for k in pilot if k != "n"}
    return {"pilot": pilot, "holdout": holdout, "diff": diff}


def churn_radar(pilot_rows, top_n=30):
    ranked = sorted(pilot_rows, key=lambda r: r["churn"]["score"], reverse=True)
    return [r for r in ranked if r["churn"]["score"] > 0][:top_n]


def outcome_fee(rows, fee_pct):
    """Platform extra revenue vs holdout x fee%, counted ONLY for merchants with positive net gain."""
    positive = [r for r in rows if r["value"] > 0]
    platform_revenue = sum(r["value"] for r in positive) * (fee_pct / 100)
    return {"eligible_merchants": len(positive), "total_merchants": len(rows),
            "total_positive_value": sum(r["value"] for r in positive),
            "platform_revenue": round(platform_revenue), "fee_pct": fee_pct}


def numbers_ok(text, facts):
    """Every number in the model's answer must come from the filtered facts (same rule wapas_aao
    applies to its own AI text -- see features/wapas_aao/ai.py:numbers_ok)."""
    import re
    allowed = set()
    for v in facts.values():
        allowed |= {int(n) for n in re.findall(r"\d+", str(v))}
    used = {int(n) for n in re.findall(r"\d+", (text or "").replace(",", ""))}
    return used <= allowed
