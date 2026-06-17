#!/usr/bin/env python3
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js").read_text(encoding="utf-8", errors="ignore")

terms = [
    "Default t.me post link",
    "All → Forwarding",
    "Message to send",
    'value:"setup"',
    'value:"bulk"',
    "setup-column-panel",
    "BulkDefaults",
    "defaultMessage",
]
for term in terms:
    i = s.find(term)
    if i >= 0:
        print(f"\n=== {term} @ {i} ===")
        print(s[max(0,i-150):i+350])
