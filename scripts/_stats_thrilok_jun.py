import json
import os
import sys

sys.path.insert(0, "/opt/telegramforward.old")
from features import candidate_store as cs

s = cs.stats(month="2026-06", reference="thrilok")
keys = [
    "handler_auto_earnings_total",
    "handler_commission_total",
    "handler_salary_total",
    "handler_paid_out_total",
    "handler_deductions_total",
    "revenue_total",
    "pending_total",
    "commission_pct",
]
print("AGGREGATE:")
for k in keys:
    print(f"  {k}: {s.get(k)}")
tp = (s.get("top_performers") or [])
if tp:
    p = tp[0]
    print("PERFORMER:")
    for k in [
        "name", "revenue_total", "commission_total", "salary_total",
        "auto_earnings_total", "paid_out_total", "net_payable",
    ]:
        print(f"  {k}: {p.get(k)}")
paid = int(s.get("handler_paid_out_total") or s.get("handler_deductions_total") or 0)
owed = int(s.get("handler_auto_earnings_total") or s.get("handler_earnings_total") or 0)
print(f"PENDING (owed - paid): {owed - paid}")
