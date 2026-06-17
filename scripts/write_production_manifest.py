#!/usr/bin/env python3
"""Write static/production.manifest.json from current build + git HEAD."""
from __future__ import annotations

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from scripts.prod_sync_common import write_manifest  # noqa: E402

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    m = write_manifest()
    print(f"Wrote production.manifest.json")
    print(f"  commit: {m.get('git_commit_short')}")
    print(f"  js:     {m.get('js')} ({m.get('js_sha256', '')[:12]}…)")
    print(f"  css:    {m.get('css')}")
