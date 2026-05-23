#!/usr/bin/env python3
"""Apply groups_list_suggested_keep.txt as the new master groups_list.json."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.groups_store import GROUPS_FILE, load_master_groups, save_master_groups

KEEP_FILE = os.path.join(ROOT, "data", "groups_list_suggested_keep.txt")
UPLOAD_TXT = os.path.join(ROOT, "data", "groups_list_clean_upload.txt")


def parse_keep_file(path: str) -> list[str]:
    groups: list[str] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("=") or "Suggested" in line:
                continue
            m = re.match(r"^\d+\.\s+(@?)([a-zA-Z0-9_]+)", line)
            if m:
                name = m.group(2)
            else:
                m2 = re.match(r"^@?([a-zA-Z0-9_]{3,})$", line)
                if not m2:
                    continue
                name = m2.group(1)
            key = name.lower()
            if key not in seen:
                seen.add(key)
                groups.append(name)
    return groups


def main() -> int:
    if not os.path.exists(KEEP_FILE):
        print(f"Missing {KEEP_FILE} — run: python scripts/suggest_clean_groups.py")
        return 1

    keep = parse_keep_file(KEEP_FILE)
    if not keep:
        print("No groups parsed from keep file.")
        return 1

    old = load_master_groups()
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    backup = os.path.join(ROOT, "data", f"groups_list_backup_{len(old)}_{ts}.json")
    if old and os.path.exists(GROUPS_FILE):
        shutil.copy2(GROUPS_FILE, backup)
        print(f"Backup: {backup} ({len(old)} groups)")

    save_master_groups(keep)
    print(f"Updated: {GROUPS_FILE} ({len(keep)} groups)")

    with open(UPLOAD_TXT, "w", encoding="utf-8") as f:
        f.write(f"Telegram Groups List — cleaned ({len(keep)} total)\n")
        f.write("=" * 40 + "\n\n")
        for i, g in enumerate(keep, 1):
            f.write(f"{i}. {g}\n")
    print(f"Upload copy: {UPLOAD_TXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
