#!/usr/bin/env python3
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js").read_text(encoding="utf-8", errors="ignore")
i = s.find("function Sl(")
print(s[i:i+600])
