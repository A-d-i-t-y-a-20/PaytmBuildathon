"""Mock merchant population for the Platform Console.

500 merchants, deterministic (seeded per merchant id so reruns are stable),
split 250 PILOT (Galla AI active) / 250 HOLDOUT (baseline, no Galla AI).
Settlements/obligations are generated in the same shape gullak's own
adapter.py produces, so features/gullak/engine.py runs on them unchanged.
Concept demo, mock data only.
"""
import random
from datetime import date, timedelta

TODAY = date(2026, 11, 19)  # same "today" the rest of the mock data uses
HISTORY_DAYS = 100           # enough for a 30-day backtest + 5 weeks of weekday lookback

TOWNS = ["Kanpur", "Indore", "Surat", "Nagpur", "Patna", "Jaipur", "Lucknow", "Coimbatore", "Nashik", "Ranchi"]
CATEGORIES = ["Kirana", "Electronics", "Pharmacy", "Stationery", "Mobile Recharge", "Bakery", "Hardware", "Garments"]
NAME_PREFIXES = ["Sharma", "Gupta", "Patel", "Singh", "Reddy", "Khan", "Iyer", "Das", "Mehta", "Yadav",
                  "Verma", "Nair", "Joshi", "Rao", "Ahmed", "Kaur"]
NAME_SUFFIXES = ["General Store", "Kirana", "Mart", "Traders", "Provision Store", "Stores", "Supermart"]

N_MERCHANTS = 500


def _rng(merchant_id):
    return random.Random(f"galla-merchant-{merchant_id}")


def _settlements_for(rng, base, days=HISTORY_DAYS):
    """Same shape as features/gullak/adapter.load_settlements(): {iso_date: float}."""
    out = {}
    for k in range(days):
        day = TODAY - timedelta(days=k)
        weekday_mult = 1.15 if day.weekday() in (4, 5) else (0.85 if day.weekday() == 0 else 1.0)
        noise = rng.uniform(0.75, 1.25)
        slow = rng.random() < 0.08
        amt = base * weekday_mult * noise * (0.3 if slow else 1.0)
        out[day.isoformat()] = round(amt, 2)
    return out


def _obligations_for(rng, base):
    """Same shape as features/gullak/adapter.load_obligations()."""
    emi_amount = round(base * rng.uniform(1.5, 4.0))
    due = TODAY + timedelta(days=rng.randint(1, 20))
    return {
        "emi_amount": emi_amount,
        "emi_due_dates": [due.isoformat()],
        "default_cash": round(base * rng.uniform(2, 6)),
        "cash_by_date": {},
        "default_stock_spend": round(base * rng.uniform(0.5, 2)),
        "stock_spend_by_date": {},
    }


def _one(i):
    mid = f"M{i + 1:04d}"
    rng = _rng(mid)
    name = f"{rng.choice(NAME_PREFIXES)} {rng.choice(NAME_SUFFIXES)}"
    town = rng.choice(TOWNS)
    category = rng.choice(CATEGORIES)
    base = rng.uniform(1200, 6000)
    group = "pilot" if i % 2 == 0 else "holdout"
    gullak_opted_in = group == "pilot" and rng.random() < 0.72
    approvals_last_14d = rng.randint(1, 10) if (group == "pilot" and rng.random() < 0.75) else 0
    weekly_active = rng.random() < (0.82 if group == "pilot" else 0.68)
    return {
        "id": mid, "name": name, "town": town, "category": category, "group": group,
        "base_sales": round(base),
        "settlements": _settlements_for(rng, base),
        "obligations": _obligations_for(rng, base),
        "lapsed_customers": rng.randint(0, 24),
        "gullak_opted_in": gullak_opted_in,
        "approvals_last_14d": approvals_last_14d,
        "weekly_active": weekly_active,
    }


def generate_merchants(n=N_MERCHANTS):
    return [_one(i) for i in range(n)]


def pilot_holdout_split(merchants):
    return [m for m in merchants if m["group"] == "pilot"], [m for m in merchants if m["group"] == "holdout"]
