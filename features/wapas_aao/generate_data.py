"""Regenerate Wapas Aao mock data (deterministic). Run: python -m features.wapas_aao.generate_data

payments.csv  90 days of Soundbox UPI payments ending the day before the demo
              "today" (2026-11-19): ts, amount, payer (hashed id), app (paytm|other).
              ~160 regulars (41 of whom stopped coming 3+ weeks ago) + occasional payers.
              Afternoon (2-5 pm) is clearly quieter than the rest of the day.
consent.csv   payer, rewards_member, paytm_offers_optin. Among the 41 lapsed regulars:
              12 joined shop rewards, 5 turned on Paytm-app offers, 24 gave no consent.
outcome.json  scripted 14-day campaign outcome (MOCK) used by the "14 din baad" demo step.
All values are MOCK. Payer ids are random hashes, not real people.
"""
import csv
import hashlib
import json
import os
import random
from datetime import date, datetime, timedelta

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")
TODAY = date(2026, 11, 19)
START = TODAY - timedelta(days=90)
# hourly weights 7am..9pm; 2-5 pm deliberately low
HOUR_W = {7: 4, 8: 8, 9: 9, 10: 8, 11: 7, 12: 6, 13: 6.2, 14: 4.4, 15: 3.9, 16: 4.7, 17: 7, 18: 10, 19: 11, 20: 9, 21: 5}


def pid(rnd):
    return hashlib.sha1(str(rnd.random()).encode()).hexdigest()[:10]


def pick_hour(rnd):
    hours, weights = zip(*HOUR_W.items())
    return rnd.choices(hours, weights=weights)[0]


def build():
    rnd = random.Random(7)
    rows = []
    regulars, lapsed = [], []
    for i in range(160):
        p = pid(rnd)
        app = "paytm" if rnd.random() < 0.08 else "other"
        stop_day = None
        if i < 41:  # will lapse: last visit 22-45 days before today
            stop_day = TODAY - timedelta(days=rnd.randint(22, 45))
            lapsed.append(p)
        regulars.append((p, app, stop_day))
    for p, app, stop_day in regulars:
        d = START
        while d < TODAY:
            if stop_day and d > stop_day:
                break
            if rnd.random() < 0.22:  # ~1.5 visits a week
                h = pick_hour(rnd)
                ts = datetime(d.year, d.month, d.day, h, rnd.randint(0, 59))
                rows.append({"ts": ts.isoformat(), "amount": int(rnd.lognormvariate(5.1, 0.55)), "payer": p, "app": app})
            d += timedelta(days=1)
    for _ in range(240):  # occasional payers
        p = pid(rnd)
        app = "paytm" if rnd.random() < 0.08 else "other"
        for _ in range(rnd.randint(1, 3)):
            d = START + timedelta(days=rnd.randint(0, 89))
            h = pick_hour(rnd)
            ts = datetime(d.year, d.month, d.day, h, rnd.randint(0, 59))
            rows.append({"ts": ts.isoformat(), "amount": int(rnd.lognormvariate(5.0, 0.6)), "payer": p, "app": app})
    rows.sort(key=lambda r: r["ts"])
    with open(os.path.join(DATA, "payments.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "amount", "payer", "app"])
        w.writeheader()
        w.writerows(rows)

    # consent among lapsed: 12 rewards, 5 paytm opt-in (force their app to paytm), 24 none
    consent = []
    for i, p in enumerate(lapsed):
        consent.append({"payer": p, "rewards_member": int(i < 12), "paytm_offers_optin": int(12 <= i < 17)})
    paytm_optin = {p for p in lapsed[12:17]}
    for r in rows:
        if r["payer"] in paytm_optin:
            r["app"] = "paytm"
    with open(os.path.join(DATA, "payments.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "amount", "payer", "app"])
        w.writeheader()
        w.writerows(rows)
    # some active regulars are rewards members too (not targeted: they still come)
    for p, app, stop in regulars[41:61]:
        consent.append({"payer": p, "rewards_member": 1, "paytm_offers_optin": 0})
    with open(os.path.join(DATA, "consent.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["payer", "rewards_member", "paytm_offers_optin"])
        w.writeheader()
        w.writerows(consent)

    # scripted outcome: 9 of the treated come back for 20 offer visits worth Rs 8,100;
    # 1 holdout customer comes once for Rs 400. Engine computes the rest.
    outcome = {
        "mock": True,
        "days": 14,
        "treated_returned": 9,
        "treated_visits": [405, 410, 400, 402, 415, 400, 400, 418, 405, 403, 410, 400, 404, 406, 412, 400, 401, 409, 400, 400],
        "holdout_spend_total": 400,
        "day1_redemptions": 3,
        "new_rewards_members_day1": 2,
        "best_days_note": "Mangal-Budh ko asar lagbhag dugna tha",
    }
    with open(os.path.join(DATA, "outcome.json"), "w") as f:
        json.dump(outcome, f, indent=2)
    print(len(rows), "payments;", len(lapsed), "lapsed regulars")


if __name__ == "__main__":
    build()
