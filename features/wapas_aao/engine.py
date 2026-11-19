"""Wapas Aao engine: win back lapsed regulars with consent-only, priced offers.

Everything numeric is computed here. Built-in fixes from the critique:
  * Reach   -- two consented channels: shop rewards (any UPI app) + Paytm-app opt-in.
  * Margin  -- offer cost per qualifying bill <= half the shop's gross margin; budget cap.
  * Noise   -- conservative "lapsed" rule + a holdout group from the reachable pool.
  * Consent -- only consented customers are ever targeted; merchant sees counts only.
  * Money   -- Paytm-app offers are instant discounts (no cashback payout).
  * Honesty -- result = extra profit AFTER offer cost, vs holdout; real end dates.
Mock data only. Concept demo.
"""
import csv
import json
import os
import random
from collections import defaultdict
from datetime import date, datetime, timedelta

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")
TODAY = "2026-11-19"
MARGIN = 0.11            # estimated kirana gross margin
MAX_COST_SHARE = 0.5     # offer cost per bill <= 50% of margin
LAPSE_DAYS = 21
REGULAR_MIN_DAYS = 4     # distinct visit days within a 30-day window
CAMPAIGN_DAYS = 14
DEFAULT_BUDGET = 600
MAX_NOTIFS_PER_WEEK = 1

OFFER_LIBRARY = {
    "flat_20_400": {"id": "flat_20_400", "kind": "flat", "value": 20, "min_bill": 400,
                    "title": "Rs 20 off on bills of Rs 400+"},
    "free_item_250": {"id": "free_item_250", "kind": "free_item", "value": 8, "min_bill": 250, "item": "biscuit packet",
                      "title": "Free biscuit packet on bills of Rs 250+"},
    "stamp_30_5": {"id": "stamp_30_5", "kind": "stamp", "value": 30, "visits": 5, "min_bill": 200,
                   "title": "Rs 30 back on every 5th visit (Rs 200+ bills)"},
    "pct_5_300": {"id": "pct_5_300", "kind": "percent", "value": 5, "min_bill": 300,
                  "title": "5% off on bills of Rs 300+"},
}
OFFER_KINDS = ("flat", "percent", "free_item", "stamp")
WINDOWS = {"evening": (18, 21), "allday": (8, 22)}  # "quiet" is computed from data
DEFAULT_OFFER = "flat_20_400"


# ---------------------------------------------------------------- loading
def load_payments(path=None):
    path = path or os.path.join(DATA, "payments.csv")
    out = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append({"ts": datetime.fromisoformat(r["ts"]), "amount": float(r["amount"]),
                        "payer": r["payer"], "app": r["app"]})
    return out


def load_consent(path=None):
    path = path or os.path.join(DATA, "consent.csv")
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["payer"]] = {"rewards_member": r["rewards_member"] == "1",
                               "paytm_offers_optin": r["paytm_offers_optin"] == "1"}
    return out


def load_outcome(path=None):
    with open(path or os.path.join(DATA, "outcome.json"), encoding="utf-8") as f:
        return json.load(f)


def _d(x):
    return x if isinstance(x, date) else date.fromisoformat(x)


# ---------------------------------------------------------------- detection
def find_regulars(payments, today=TODAY, lookback=90):
    """Payer with >= 4 distinct visit days inside some 30-day window in the last 90 days."""
    t = _d(today)
    days = defaultdict(set)
    for p in payments:
        d = p["ts"].date()
        if t - timedelta(days=lookback) <= d < t:
            days[p["payer"]].add(d)
    regs = set()
    for payer, ds in days.items():
        ds = sorted(ds)
        for i in range(len(ds)):
            j = i
            while j < len(ds) and (ds[j] - ds[i]).days < 30:
                j += 1
            if j - i >= REGULAR_MIN_DAYS:
                regs.add(payer)
                break
    return regs


def find_lapsed(payments, today=TODAY):
    t = _d(today)
    regs = find_regulars(payments, today)
    last = {}
    for p in payments:
        if p["payer"] in regs:
            last[p["payer"]] = max(last.get(p["payer"], p["ts"].date()), p["ts"].date())
    return sorted(p for p in regs if (t - last[p]).days > LAPSE_DAYS)


def quiet_hours(payments, today=TODAY, window_days=30, open_hours=range(8, 22), width=3):
    """Lowest-sales 3-hour window vs the average hour of the rest of the day."""
    t = _d(today)
    by_hour = defaultdict(float)
    for p in payments:
        d = p["ts"].date()
        if t - timedelta(days=window_days) <= d < t:
            by_hour[p["ts"].hour] += p["amount"]
    hours = list(open_hours)
    best = None
    for i in range(len(hours) - width + 1):
        win = hours[i:i + width]
        avg_in = sum(by_hour[h] for h in win) / width
        rest = [h for h in hours if h not in win]
        avg_out = sum(by_hour[h] for h in rest) / len(rest)
        drop = 1 - avg_in / avg_out if avg_out else 0
        if best is None or drop > best["drop"]:
            best = {"start": win[0], "end": win[-1] + 1, "drop": drop}
    best["drop_pct"] = int(round(100 * best["drop"]))
    return best


def reach_split(lapsed, consent):
    """Only consented customers are reachable. Rewards membership wins if both."""
    rewards, paytm, none = [], [], []
    for p in lapsed:
        c = consent.get(p, {})
        if c.get("rewards_member"):
            rewards.append(p)
        elif c.get("paytm_offers_optin"):
            paytm.append(p)
        else:
            none.append(p)
    return {"rewards": rewards, "paytm": paytm, "unreachable": none}


def holdout_size(n):
    return 0 if n < 5 else max(4, round(0.25 * n))


def assign_holdout(reachable, seed="campaign-1"):
    pool = sorted(reachable)
    k = holdout_size(len(pool))
    rnd = random.Random(seed)
    holdout = set(rnd.sample(pool, k)) if k else set()
    return [p for p in pool if p not in holdout], sorted(holdout)


# ---------------------------------------------------------------- offer pricing
def cost_share(offer):
    """Offer cost as a share of the qualifying spend (worst case: a bill right at the minimum)."""
    if offer["kind"] == "percent":
        return offer["value"] / 100.0
    if offer["kind"] == "stamp":
        return offer["value"] / (offer["min_bill"] * offer.get("visits", 5))
    return offer["value"] / offer["min_bill"]


def discount_for(bill, offer):
    """Rupees the shop gives on one qualifying bill."""
    if offer["kind"] == "percent":
        return int(round(bill * offer["value"] / 100.0))
    return int(offer["value"])


def make_custom_offer(kind, value, min_bill, visits=5):
    """A shopkeeper-built offer. Validated with cost_check() like any other."""
    kind = kind if kind in OFFER_KINDS else "flat"
    o = {"id": "custom", "kind": kind, "value": max(1, int(value or 0)), "min_bill": max(1, int(min_bill or 0)),
         "title": "custom"}
    if kind == "stamp":
        o["visits"] = visits
    if kind == "free_item":
        o["item"] = "item"
    return o


def cost_check(offer, margin=MARGIN):
    share = cost_share(offer)
    limit = MAX_COST_SHARE * margin
    return {"ok": share <= limit + 1e-9, "cost_pct": round(100 * share, 1), "limit_pct": round(100 * limit, 1),
            "margin_pct": round(100 * margin)}


def reprice(offer, margin=MARGIN):
    """Make an offer fit the cost cap: lower the % for percent offers, otherwise raise the
    minimum bill in Rs 50 steps."""
    o = dict(offer)
    if o["kind"] == "percent":
        o["value"] = min(o["value"], int(MAX_COST_SHARE * margin * 100))
        if o["value"] != offer["value"]:
            o["repriced_from"] = offer["min_bill"]
        return o
    for _ in range(400):
        if cost_check(o, margin)["ok"]:
            break
        o["min_bill"] += 50
    if o["min_bill"] != offer["min_bill"]:
        o["title"] = f"Rs {o['value']} off on bills of Rs {o['min_bill']}+" if o["kind"] == "flat" else o["title"]
        o["repriced_from"] = offer["min_bill"]
    return o


def max_redemptions(offer, budget):
    return int(budget // max(1, discount_for(offer["min_bill"], offer)))


def recommend_offers(margin=MARGIN):
    """Ranked offer ideas from the library, all within the cost cap. Code ranks; the LLM may
    re-order (validated) and only phrases the reason."""
    order = ["flat_20_400", "free_item_250", "stamp_30_5", "pct_5_300"]
    out = []
    for oid in order:
        o = OFFER_LIBRARY[oid]
        c = cost_check(o, margin)
        if c["ok"]:
            out.append({"offer": o, "cost_pct": c["cost_pct"], "why": o["kind"]})
    return out


def rank_with_llm(recs, llm_pick):
    """Move the LLM's pick to the top if it is one of the code-approved ideas."""
    ids = [r["offer"]["id"] for r in recs]
    if llm_pick in ids:
        i = ids.index(llm_pick)
        return [recs[i]] + recs[:i] + recs[i + 1:]
    return recs


# ---------------------------------------------------------------- proposal
def build_proposal(payments, consent, today=TODAY, offer_id=DEFAULT_OFFER, budget=DEFAULT_BUDGET, margin=MARGIN,
                   offer=None, window="quiet", days=CAMPAIGN_DAYS):
    lapsed = find_lapsed(payments, today)
    split = reach_split(lapsed, consent)
    reachable = split["rewards"] + split["paytm"]
    treatment, holdout = assign_holdout(reachable)
    q = quiet_hours(payments, today)
    offer = dict(offer) if offer else OFFER_LIBRARY.get(offer_id, OFFER_LIBRARY[DEFAULT_OFFER])
    check = cost_check(offer, margin)
    if not check["ok"]:
        offer = reprice(offer, margin)
        check = cost_check(offer, margin)
    start = _d(today)
    return {
        "lapsed": len(lapsed),
        "reach": {"rewards": len(split["rewards"]), "paytm": len(split["paytm"]),
                  "unreachable": len(split["unreachable"]), "reachable": len(reachable)},
        "treatment_n": len(treatment), "holdout_n": len(holdout),
        "quiet": {"start": q["start"], "end": q["end"], "drop_pct": q["drop_pct"]},
        "offer": offer, "cost": check, "budget": budget, "max_redemptions": max_redemptions(offer, budget),
        "window": {"key": window if window in WINDOWS else "quiet",
                   "start": WINDOWS.get(window, (q["start"], q["end"]))[0],
                   "end": WINDOWS.get(window, (q["start"], q["end"]))[1]},
        "start_date": start.isoformat(), "end_date": (start + timedelta(days=days)).isoformat(),
        "days": days,
        # private: never rendered for the merchant (see merchant_view)
        "_treatment": treatment, "_holdout": holdout,
    }


def merchant_view(proposal):
    """Counts and rupees only -- strips every customer identifier."""
    return {k: v for k, v in proposal.items() if not k.startswith("_")}


def notification_schedule(treatment, start, days=CAMPAIGN_DAYS):
    """One offer notification per treated Paytm-app customer per week, at the start of quiet hours."""
    s = _d(start)
    out = []
    for p in treatment:
        for week in range(0, (days + 6) // 7):
            out.append({"payer": p, "date": (s + timedelta(days=7 * week)).isoformat()})
    return out


def notifs_ok(schedule):
    per = defaultdict(list)
    for n in schedule:
        per[n["payer"]].append(_d(n["date"]))
    for ds in per.values():
        ds.sort()
        for a, b in zip(ds, ds[1:]):
            if (b - a).days < 7:
                return False
    return True


# ---------------------------------------------------------------- customer side
def apply_offer(bill, offer, consented, in_window=True, budget_left=None):
    """What the Paytm-app customer pays. Instant discount, no cashback."""
    if not consented or not in_window or offer["kind"] not in ("flat", "percent") or bill < offer["min_bill"]:
        return {"bill": bill, "discount": 0, "pay": bill, "applied": False}
    d = discount_for(bill, offer)
    if budget_left is not None and budget_left < d:
        return {"bill": bill, "discount": 0, "pay": bill, "applied": False, "budget_exhausted": True}
    return {"bill": bill, "discount": d, "pay": bill - d, "applied": True}


def soundbox_line(result):
    if result.get("applied"):
        return (f"Paytm par Rs {int(result['pay'])} prapt hue. Wapas Aao offer laga, Rs {int(result['discount'])}. "
                f"Bill Rs {int(result['bill'])}.")
    return f"Paytm par Rs {int(result['pay'])} prapt hue."


def stamp_progress(visits_so_far, offer=OFFER_LIBRARY["stamp_30_5"]):
    n = visits_so_far % offer["visits"]
    reward_now = n == 0 and visits_so_far > 0
    return {"stamps": offer["visits"] if reward_now else n, "of": offer["visits"], "reward_now": reward_now,
            "reward": offer["value"] if reward_now else 0}


def opt_out(consent, payer, history=None):
    """Leaving deletes the person's consent record and any offer history."""
    consent.pop(payer, None)
    if history is not None:
        history[:] = [h for h in history if h.get("payer") != payer]
    return consent


# ---------------------------------------------------------------- result
def run_redemptions(visits, offer, budget):
    """Apply budget cap: stop redeeming once the budget is used."""
    redeemed, spent = [], 0
    for bill in visits:
        d = discount_for(bill, offer)
        if bill >= offer["min_bill"] and spent + d <= budget:
            redeemed.append(bill)
            spent += d
    return redeemed, spent


def compute_result(outcome, proposal, margin=MARGIN):
    offer = proposal["offer"]
    n_t, n_h = proposal["treatment_n"], proposal["holdout_n"]
    redeemed, cost = run_redemptions(outcome["treated_visits"], offer, proposal["budget"])
    treated_spend = sum(outcome["treated_visits"])
    holdout_spend = outcome["holdout_spend_total"]
    per_t = treated_spend / n_t if n_t else 0
    per_h = holdout_spend / n_h if n_h else 0
    extra_sales = round((per_t - per_h) * n_t)
    extra_profit = round(extra_sales * margin)
    return {
        "returned": outcome["treated_returned"], "redemptions": len(redeemed), "offer_cost": cost,
        "extra_sales": extra_sales, "extra_profit": extra_profit, "net": extra_profit - cost,
        "margin_pct": round(100 * margin), "directional": True,
        "next_tip": outcome.get("best_days_note", ""),
    }


def net_profit(extra_sales, cost, margin=MARGIN):
    return round(extra_sales * margin) - cost


# ---------------------------------------------------------------- merchant commands
_CONTACT = ("sms", "whatsapp", "message bhej", "sabko bhej", "number do", "number dikhao", "naam dikhao", "list do",
            "phone number", "their numbers", "send everyone", "message everyone", "customer list",
            "मैसेज", "नंबर", "नाम दिखाओ", "सबको भेज", "लिस्ट")
_STOP = ("ruko", "rok", "band", "stop", "रोको", "रोक", "बंद")
_RESULT = ("nateeja", "result", "kitna fayda", "kaisa raha", "how did", "नतीजा", "कितना फ़ायदा", "कैसा रहा")
_WIN_BACK = ("khali", "dopahar", "kam log", "nahi aate", "nahi aa rahe", "grahak", "customer", "wapas", "quiet",
             "empty", "slow", "afternoon", "not coming", "come back", "regulars",
             "खाली", "दोपहर", "कम लोग", "नहीं आते", "नहीं आ रहे", "ग्राहक", "वापस")


def parse_ask(text):
    """Deterministic reading of what the merchant said (Hinglish, Hindi script or English)."""
    t = (text or "").lower()
    if any(k in t for k in _CONTACT):
        return {"intent": "refuse_contact", "question": None}
    if any(k in t for k in _STOP):
        return {"intent": "stop", "question": None}
    if any(k in t for k in _RESULT):
        return {"intent": "result", "question": None}
    if any(k in t for k in _WIN_BACK):
        return {"intent": "win_back", "question": None}
    return {"intent": "none", "question": None}


def validate_ask(llm_out, text):
    base = parse_ask(text)
    if base["intent"] in ("refuse_contact", "stop"):
        return base  # safety keywords always win
    if isinstance(llm_out, dict) and llm_out.get("intent") in {"win_back", "result", "stop", "none"}:
        if base["intent"] == "none":
            base["intent"] = llm_out["intent"]
        if llm_out.get("offer_id") in OFFER_LIBRARY:
            base["offer_id"] = llm_out["offer_id"]
    return base
