#!/usr/bin/env python3
"""
Suggest a cleaned master list: keep groups not blocked on any account.

Usage (from project root):
  python scripts/suggest_clean_groups.py

Outputs:
  data/groups_list_suggested_keep.txt   — upload candidate
  data/groups_list_suggested_remove.txt — names to drop
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.config import STATE_DIR, ACCOUNTS
from core.groups_store import load_master_groups


def _load_json_set(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {str(x).strip() for x in data if x}
    except Exception:
        pass
    return set()


def main() -> int:
    master = load_master_groups()
    if not master:
        print("No master list in data/groups_list.json")
        return 1

    blocked_any: set[str] = set()
    for slot in ACCOUNTS:
        base = os.path.join(STATE_DIR, slot)
        blocked_any |= _load_json_set(os.path.join(base, "blocked_groups.json"))
        blocked_any |= _load_json_set(os.path.join(base, "invalid_groups.json"))

    master_set = set(master)
    remove = sorted(master_set & blocked_any)
    keep = sorted(master_set - blocked_any)

    out_dir = os.path.join(ROOT, "data")
    keep_path = os.path.join(out_dir, "groups_list_suggested_keep.txt")
    remove_path = os.path.join(out_dir, "groups_list_suggested_remove.txt")

    with open(keep_path, "w", encoding="utf-8") as f:
        f.write(f"Suggested keep list ({len(keep)} groups)\n")
        f.write("=" * 40 + "\n\n")
        for i, g in enumerate(keep, 1):
            f.write(f"{i}. {g}\n")

    with open(remove_path, "w", encoding="utf-8") as f:
        f.write(f"Suggested remove ({len(remove)} groups — blocked on >=1 account)\n")
        f.write("=" * 40 + "\n\n")
        for i, g in enumerate(remove, 1):
            f.write(f"{i}. {g}\n")

    print(f"Master: {len(master)}")
    print(f"Blocked on any account: {len(blocked_any)}")
    print(f"Suggest KEEP: {len(keep)} -> {keep_path}")
    print(f"Suggest REMOVE: {len(remove)} -> {remove_path}")
    print("Review keep list, then upload via dashboard Groups upload.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
