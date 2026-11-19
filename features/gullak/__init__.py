"""Galla Gullak (auto-savings for kirana merchants). Concept demo, mock data.

Public helpers for other features:
  gullak_summary_line(date) -> str   e.g. "Aaj Rs 80 gullak mein gaye. Diwali goal 62%."
  gullak_balance() -> int            e.g. a credit feature can show "gullak first"
"""


def gullak_summary_line(day=None):
    from features.gullak import ui
    return ui.summary_line(day)


def gullak_balance():
    from features.gullak import ui
    return ui.balance()
