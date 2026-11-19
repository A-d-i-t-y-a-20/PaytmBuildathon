"""Regenerate Gullak mock data (deterministic). Run: python -m features.gullak.generate_data

settlements.csv: 2026-09-21 .. 2026-11-26 (67 days). The demo "today" starts on
2026-11-19 and the "Agla din (demo)" button walks forward through a scripted
week (good day, normal, EMI-crunch skip, Sunday good day, slow-day skip,
normal, stock-spend skip, normal). Weekday variation, 2 festival spikes
(Dussehra 20 Oct, Diwali 8 Nov) and 3 very slow days in the history.
All values are MOCK.
"""
import csv
import json
import os
import random
from datetime import date, timedelta

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")

START, END = date(2026, 9, 21), date(2026, 11, 26)
BASE = 3300
WEEKDAY = {0: 0.90, 1: 0.88, 2: 0.95, 3: 0.97, 4: 1.00, 5: 1.12, 6: 1.30}  # Mon..Sun
FESTIVAL = {"2026-10-20": 2.2, "2026-11-08": 2.4}
SLOW = {"2026-10-05": 0.30, "2026-10-29": 0.35, "2026-11-11": 0.32}
# scripted demo week (absolute rupees), chosen so each day shows a different rule
SCRIPT = {
    "2026-11-19": 4000,   # Thu: good day (>120% of usual)
    "2026-11-20": 3350,   # Fri: normal day
    "2026-11-21": 3650,   # Sat: normal sales, but EMI due in 1 day and cash short -> skip
    "2026-11-22": 7100,   # Sun: good day
    "2026-11-23": 1200,   # Mon: very slow -> skip
    "2026-11-24": 2950,   # Tue: normal
    "2026-11-25": 3150,   # Wed: big stock purchase planned -> skip
    "2026-11-26": 3300,   # Thu: normal
}


def build():
    rnd = random.Random(42)
    rows = []
    d = START
    while d <= END:
        key = d.isoformat()
        if key in SCRIPT:
            amt = SCRIPT[key]
        else:
            amt = BASE * WEEKDAY[d.weekday()] * (1 + rnd.uniform(-0.08, 0.08))
            amt *= FESTIVAL.get(key, 1.0) * SLOW.get(key, 1.0)
            amt = int(round(amt / 10.0) * 10)
        rows.append({"date": key, "settlement_amount": amt})
        d += timedelta(days=1)

    with open(os.path.join(DATA, "settlements.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "settlement_amount"])
        w.writeheader()
        w.writerows(rows)

    obligations = {
        "mock": True,
        "note": "EMI amount/next due date are read from data/cash.json via adapter.py; "
                "this file only adds what that file does not have.",
        "past_emi_due_dates": ["2026-09-22", "2026-10-22"],
        "default_stock_spend_next_3_days": 1200,
        "stock_spend_next_3_days": {"2026-11-05": 2600, "2026-11-25": 2600},
        "cash_by_date": {"2026-10-21": 900, "2026-11-21": 950},
    }
    with open(os.path.join(DATA, "obligations.json"), "w") as f:
        json.dump(obligations, f, indent=2)

    state = {
        "mock": True,
        "opted_in": False,
        "mode": "suggest",
        "cap_pct": 3.0,
        "goal": {"name": "Diwali", "target": 10000},
        "balance": 0,
        "yes_count": 0,
        "suggest_days_left": 7,
        "auto_offer_pending": False,
        "today": "2026-11-19",
        "history": [],
    }
    with open(os.path.join(DATA, "gullak.json"), "w") as f:
        json.dump(state, f, indent=2)
    print(f"wrote {len(rows)} settlement rows")


if __name__ == "__main__":
    build()
