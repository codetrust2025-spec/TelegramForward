"""One-off: replace en-IN date toLocale* with fmtIstDt/fmtIstD in bundled modules."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def patch(path: Path, import_line: str) -> None:
    text = path.read_text(encoding="utf-8")
    if "fmtIstDt" not in text and import_line not in text:
        text = import_line + text
    text2 = re.sub(
        r"new Date\(([^)]+)\)\.toLocaleString\(\"en-IN\",\s*\{[^}]*\}\)",
        r"fmtIstDt(\1)",
        text,
    )
    text2 = re.sub(
        r"new Date\(([^)]+)\)\.toLocaleDateString\(\"en-IN\",\s*\{[^}]*\}\)",
        r"fmtIstD(\1)",
        text2,
    )
    if text2 != text:
        path.write_text(text2, encoding="utf-8")
        print("patched", path.name)

patch(
    ROOT / "dashboard/src/candidates/candidatesModule.jsx",
    'import { formatIstDate as fmtIstD, formatIstDateTime as fmtIstDt } from "../utils/istTime.js"\n',
)
patch(
    ROOT / "dashboard/src/admin/adminModule.jsx",
    'import { formatIstDateTime as fmtIstDt } from "../utils/istTime.js"\n',
)
