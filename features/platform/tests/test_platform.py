"""Platform Console tests. No API key needed.

pytest:      .venv/bin/python -m pytest features/platform/tests -q
table:       .venv/bin/python -m features.platform.tests.test_platform
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from features.platform import engine as PE
from features.platform import generate_data as GD

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    assert cond, f"{name}: {detail}"


def _merchant(**kw):
    m = dict(GD.generate_merchants(n=1)[0])
    m.update(kw)
    return m


def test_split_sizes():
    merchants = GD.generate_merchants(n=500)
    pilot, holdout = GD.pilot_holdout_split(merchants)
    check("500 merchants split 250/250 pilot/holdout",
          len(pilot) == 250 and len(holdout) == 250 and len(pilot) + len(holdout) == 500,
          (len(pilot), len(holdout)))


def test_pilot_summary_consistent():
    merchants = GD.generate_merchants(n=40)
    pilot, holdout = GD.pilot_holdout_split(merchants)
    pilot_rows = [PE.merchant_row(m) for m in pilot]
    holdout_rows = [PE.merchant_row(m) for m in holdout]
    s = PE.pilot_summary(pilot_rows, holdout_rows)
    diff_matches = all(abs(s["diff"][k] - (s["pilot"][k] - s["holdout"][k])) < 1e-6 for k in s["diff"])
    check("pilot vs holdout: diff column = pilot - holdout for every KPI",
          diff_matches and s["pilot"]["n"] == len(pilot) and s["holdout"]["n"] == len(holdout), s)


def test_holdout_never_opts_into_gullak():
    merchants = GD.generate_merchants(n=60)
    _, holdout = GD.pilot_holdout_split(merchants)
    check("holdout group never has gullak_opted_in (baseline, no Galla AI)",
          all(not m["gullak_opted_in"] for m in holdout), [m["gullak_opted_in"] for m in holdout])


def test_churn_score_high_for_inactive_no_approvals():
    m = _merchant(group="pilot", weekly_active=False, approvals_last_14d=0)
    g = PE.gullak_outcome(m)
    c = PE.churn_score(m, g)
    check("inactive + no approvals in 14 days -> churn score at least 60, both flags set",
          c["score"] >= 60 and "falling_upi_days" in c["flags"] and "no_approvals_14d" in c["flags"], c)


def test_churn_score_low_for_healthy_merchant():
    m = _merchant(group="pilot", weekly_active=True, approvals_last_14d=5)
    g = PE.gullak_outcome(m)
    c = PE.churn_score(m, g)
    check("active, recent approvals -> no 'falling_upi_days' / 'no_approvals_14d' flags",
          "falling_upi_days" not in c["flags"] and "no_approvals_14d" not in c["flags"], c)


def test_churn_score_bounded_and_scores_rise_with_more_flags():
    healthy = _merchant(group="pilot", weekly_active=True, approvals_last_14d=5)
    worst = _merchant(group="pilot", weekly_active=False, approvals_last_14d=0)
    sc_healthy = PE.churn_score(healthy, PE.gullak_outcome(healthy))["score"]
    sc_worst = PE.churn_score(worst, PE.gullak_outcome(worst))["score"]
    check("churn score stays within 0-100 and a merchant with more risk flags scores higher",
          0 <= sc_healthy <= 100 and 0 <= sc_worst <= 100 and sc_worst > sc_healthy, (sc_healthy, sc_worst))


def test_instalment_safety_percent_and_tag():
    m = _merchant(base_sales=4000)
    r = PE.instalment_safety(m)
    slow_day = 4000 * 0.3
    expected_pct = round(100 * r["daily_instalment"] / slow_day, 1)
    check("instalment % of slow-day sales matches daily_instalment/slow_day_sales, tagged consistently",
          r["pct_of_slow_day"] == expected_pct and r["safe"] == (expected_pct < PE.SAFE_INSTALMENT_PCT), r)


def test_instalment_safety_varies_and_heavy_gets_smaller_suggestion():
    # the offer size is seeded per merchant id, so some come out safe and some too heavy
    results = [PE.instalment_safety(_merchant(base_sales=4000, id=f"M-credit-{i}")) for i in range(30)]
    safe = [r for r in results if r["safe"]]
    heavy = [r for r in results if not r["safe"]]
    check("instalment safety varies across merchants, and every unsafe one gets a smaller suggested amount",
          len(safe) > 0 and len(heavy) > 0 and all(r["suggested_amount"] < r["offer_amount"] for r in heavy),
          {"safe": len(safe), "heavy": len(heavy)})


def test_winback_profit_only_for_pilot_with_lapsed_customers():
    holdout_m = _merchant(group="holdout", lapsed_customers=10)
    pilot_no_lapsed = _merchant(group="pilot", lapsed_customers=0)
    pilot_m = _merchant(group="pilot", lapsed_customers=10, id="M-wb-test")
    check("holdout / no-lapsed-customers merchants get zero win-back profit; a real pilot case doesn't error",
          PE.winback_profit(holdout_m)["profit"] == 0 and PE.winback_profit(pilot_no_lapsed)["profit"] == 0
          and PE.winback_profit(pilot_m)["returned"] >= 0,
          (PE.winback_profit(holdout_m), PE.winback_profit(pilot_m)))


def test_outcome_fee_counts_only_positive_gain():
    rows = [{"value": 500}, {"value": -200}, {"value": 0}, {"value": 1000}]
    fee = PE.outcome_fee(rows, fee_pct=10.0)
    check("outcome fee ignores non-positive-gain merchants",
          fee["eligible_merchants"] == 2 and fee["total_positive_value"] == 1500
          and fee["platform_revenue"] == 150, fee)


def test_outcome_fee_zero_when_nobody_gains():
    rows = [{"value": -10}, {"value": 0}]
    fee = PE.outcome_fee(rows, fee_pct=10.0)
    check("outcome fee is 0 when no merchant has positive net gain",
          fee["eligible_merchants"] == 0 and fee["platform_revenue"] == 0, fee)


def test_numbers_ok_rejects_invented_numbers():
    facts = {"drop_pct": 12, "lapsed": 5}
    ok_text = "Sales are down 12% and 5 regulars lapsed."
    bad_text = "Sales are down 99% and 500 regulars lapsed."
    check("numbers_ok accepts numbers drawn from the facts, rejects invented ones",
          PE.numbers_ok(ok_text, facts) and not PE.numbers_ok(bad_text, facts), (ok_text, bad_text))


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def run_table():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    order = [test_split_sizes, test_pilot_summary_consistent, test_holdout_never_opts_into_gullak,
             test_churn_score_high_for_inactive_no_approvals, test_churn_score_low_for_healthy_merchant,
             test_churn_score_bounded_and_scores_rise_with_more_flags, test_instalment_safety_percent_and_tag,
             test_instalment_safety_varies_and_heavy_gets_smaller_suggestion, test_winback_profit_only_for_pilot_with_lapsed_customers,
             test_outcome_fee_counts_only_positive_gain, test_outcome_fee_zero_when_nobody_gains,
             test_numbers_ok_rejects_invented_numbers]
    for t in order:
        try:
            t()
        except AssertionError:
            pass
        except Exception as exc:
            RESULTS.append((t.__name__, False, f"EXCEPTION {exc!r}"))
    w = max(len(n) for n, _, _ in RESULTS)
    print(f"{'PLATFORM TEST':<{w}} | RESULT")
    print("-" * (w + 10))
    for n, ok, d in RESULTS:
        print(f"{n:<{w}} | {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"{'':<{w}} |   {d}")
    p = sum(ok for _, ok, _ in RESULTS)
    print("-" * (w + 10))
    print(f"{p}/{len(RESULTS)} passed ({100 * p // len(RESULTS)}%)")
    return p == len(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if run_table() else 1)
