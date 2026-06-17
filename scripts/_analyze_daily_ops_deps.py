"""Analyze undefined minified symbols in dailyOpsModule.core.js."""
from __future__ import annotations

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(REPO, "static", "assets", "dashboard.bundle.js")
CORE = os.path.join(REPO, "dashboard", "src", "dailyOps", "dailyOpsModule.core.js")

ENGLISH = {
    "Add", "All", "Any", "Apr", "Auto", "Avg", "Bug", "Call", "Cold", "Con", "Copy", "Core",
    "Data", "Date", "Do", "Drop", "Dup", "Each", "Edit", "End", "Fast", "File", "Food", "For",
    "From", "Get", "Go", "Has", "Hide", "High", "How", "If", "In", "Is", "It", "Jan", "Job",
    "Key", "Lab", "Lead", "Left", "Line", "List", "Load", "Log", "Low", "Map", "Max", "May",
    "Min", "Mon", "More", "Name", "New", "Next", "No", "Not", "Now", "Off", "Old", "On", "One",
    "Only", "Open", "Or", "Out", "Over", "PDF", "PM", "PT", "Put", "Raw", "Read", "Red", "Ref",
    "Remove", "Reply", "Reset", "Right", "Round", "Run", "SQL", "Sat", "Save", "See", "Select",
    "Send", "Set", "Show", "Slot", "Sort", "Star", "Start", "Stop", "Sun", "Tab", "Tag", "Team",
    "Test", "Text", "The", "This", "Thu", "Time", "To", "Top", "Total", "Try", "Tue", "Two",
    "Type", "URL", "Use", "User", "View", "Wed", "Win", "With", "Work", "Yes", "You", "ZIP",
    "AI", "AM", "AWS", "Asia", "BI", "CRM", "CSV", "CTA", "Ctrl", "DMs", "DOC", "DOCX", "ETL",
    "F1", "FILE", "FT", "HR", "ID", "IN", "IO", "IP", "IT", "IV", "JS", "KB", "MB", "OK", "QA",
    "UI", "UK", "US", "UTC", "VM", "VS", "XL", "XP", "LB", "We",
}


def strip_strings(s: str) -> str:
    s = re.sub(r"`(?:\\.|[^`\\])*`", '""', s)
    s = re.sub(r'"(?:\\.|[^"\\])*"', '""', s)
    s = re.sub(r"'(?:\\.|[^'\\])*'", "''", s)
    return s


def main() -> None:
    js = open(BUNDLE, encoding="utf-8", errors="replace").read()
    core = open(CORE, encoding="utf-8", errors="replace").read()
    core_clean = strip_strings(core)

    def_pattern = re.compile(r"(?:const|let|var|function)\s+([A-Za-z_$][A-Za-z0-9_$]*)")
    defined = set(def_pattern.findall(core_clean))
    defined |= set(re.findall(r"function\s+([A-Za-z_$][A-Za-z0-9_$]*)", core_clean))
    defined |= {
        "N", "o", "xc", "aY", "nY", "eY", "Xo", "Zx", "sn", "zce",
        "React", "jsx", "jsxs", "Fragment", "useAuth", "API", "_jsx", "_jsxs", "_Fragment",
    }

    use_pattern = re.compile(r"(?<![.\w$])([A-Za-z_$][A-Za-z0-9_$]{0,3})(?![.\w$])")
    uses: dict[str, int] = {}
    for m in use_pattern.finditer(core_clean):
        name = m.group(1)
        if len(name) <= 4 and (re.search(r"[0-9_]", name) or (len(name) <= 3 and name[0].isupper())):
            uses[name] = uses.get(name, 0) + 1

    missing = []
    for name, count in sorted(uses.items(), key=lambda x: -x[1]):
        if name in defined or name in ENGLISH:
            continue
        missing.append((name, count))

    print("Top missing minified symbols:")
    for name, count in missing[:60]:
        dm = re.search(r"(?:const|let|var|function)\s+" + re.escape(name) + r"\b", js)
        pos = dm.start() if dm else None
        print(f"  {name}: {count} uses, def@{pos}")

    for sym in ["LB", "O0", "Y5", "D_", "fP", "hee", "th", "vt", "cP", "uP", "qoe", "ke"]:
        u = len(re.findall(r"\b" + re.escape(sym) + r"\b", core_clean))
        d = len(re.findall(r"(?:const|let|var|function)\s+" + re.escape(sym) + r"\b", core_clean))
        print(f"CHECK {sym}: uses={u} defs={d}")


if __name__ == "__main__":
    main()
