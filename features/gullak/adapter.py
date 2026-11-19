"""Read-only data loading for Gullak.

EMI and cash come from data/cash.json; Gullak
reads them from there. Settlements are kept in
its own mock settlements.csv. Nothing in this
module writes to data files.
"""
import csv
import json
import os

HERE = os.path.dirname(__file__)
GULLAK_DATA = os.path.join(HERE, "data")
SHARED_DATA = GULLAK_DATA  # EMI + cash now live in features/gullak/data/cash.json


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_settlements(path=None):
    """{iso_date: settlement_amount}"""
    path = path or os.path.join(GULLAK_DATA, "settlements.csv")
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out[r["date"]] = float(r["settlement_amount"])
    except OSError:
        pass
    return out


def load_obligations():
    """Merge the shared EMI/cash (data/cash.json) with Gullak-only extras."""
    shared = _read_json(os.path.join(SHARED_DATA, "cash.json"), {})
    extra = _read_json(os.path.join(GULLAK_DATA, "obligations.json"), {})
    emi_dates = list(extra.get("past_emi_due_dates", []))
    if shared.get("emi_due_date"):
        emi_dates.append(shared["emi_due_date"])
    return {
        "emi_amount": float(shared.get("emi_due_amount", 0) or 0),
        "emi_due_dates": sorted(set(emi_dates)),
        "default_cash": float(shared.get("available_cash", 0) or 0),
        "cash_by_date": {k: float(v) for k, v in extra.get("cash_by_date", {}).items()},
        "default_stock_spend": float(extra.get("default_stock_spend_next_3_days", 0) or 0),
        "stock_spend_by_date": {k: float(v) for k, v in extra.get("stock_spend_next_3_days", {}).items()},
    }


def load_seed_state():
    return _read_json(os.path.join(GULLAK_DATA, "gullak.json"), {})
