#!/usr/bin/env python3
"""Copy VPS helper scripts from Desktop\\Automation and strip hardcoded password defaults."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

SRC = Path.home() / "OneDrive" / "Desktop" / "Automation" / "scripts"
DST = Path(__file__).resolve().parents[1] / "scripts"

PAT = re.compile(r'os\.environ\.get\("VPS_PASSWORD",\s*"[^"]*"\)')


def main() -> None:
    if not SRC.is_dir():
        raise SystemExit(f"Source missing: {SRC}")
    DST.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in sorted(SRC.glob("*.py")):
        text = src.read_text(encoding="utf-8", errors="replace")
        text = PAT.sub('os.environ.get("VPS_PASSWORD", "")', text)
        (DST / src.name).write_text(text, encoding="utf-8")
        copied += 1
    print(f"Copied {copied} scripts -> {DST}")


if __name__ == "__main__":
    main()
