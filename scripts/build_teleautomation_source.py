#!/usr/bin/env python3
"""Rebuild dashboard source from recovered production bundle."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEOB = ROOT / "recovered_ui" / "deobfuscated.js"
OUT_APP = ROOT / "dashboard" / "src" / "teleautomation-app.jsx"
OUT_CSS = ROOT / "dashboard" / "src" / "teleautomation.css"
PROD_CSS = ROOT / "prod_styles.css"
MAIN = ROOT / "dashboard" / "src" / "main.jsx"
INDEX = ROOT / "dashboard" / "index.html"

HEADER = """/* AUTO-GENERATED from production bundle — run scripts/build_teleautomation_source.py to refresh */
import React from 'react'
import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from 'react/jsx-runtime'

const w = React
const s = { jsx: _jsx, jsxs: _jsxs, Fragment: _Fragment }
const An = React

"""

FOOTER = """
export default function TeleAutomationApp() {
  if (U0) {
    return <_Component44 joinToken={U0} />;
  }
  return <_Component46><_Component45><SR /></_Component45></_Component46>;
}
"""

MAIN_CONTENT = """import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './teleautomation.css'
import TeleAutomationApp from './teleautomation-app.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <TeleAutomationApp />
  </StrictMode>,
)
"""

INDEX_CONTENT = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <meta name="theme-color" content="#0f1117" />
    <meta name="description" content="TeleAutomation — Telegram CRM, AI sales inbox, and multi-account fleet operations." />
    <meta name="mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-title" content="TeleAutomation" />
    <title>TeleAutomation</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <style>
      html, body { margin: 0; background: #0f1117; color: #e2e8f0; min-height: 100%; width: 100%; overflow-x: hidden; }
      #root { min-height: 100%; width: 100%; }
    </style>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""


def main() -> None:
    if not DEOB.exists():
        raise SystemExit(f"Missing {DEOB}")

    lines = DEOB.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("const Bl = {"))
    mount = next(i for i, ln in enumerate(lines) if ln.startswith("const Lx = Cd.createRoot"))
    body = lines[start:mount]
    text = "\n".join(body)
    # webcrack occasionally splits unicode literals inside bundled xlsx
    text = text.replace('"…": "\n",', '"…": "\\u2026",')

    OUT_APP.write_text(HEADER + text + FOOTER, encoding="utf-8", newline="\n")
    print(f"Wrote {OUT_APP.name}: {(OUT_APP.stat().st_size // 1024)} KB, {len(body)} lines")

    if PROD_CSS.exists():
        OUT_CSS.write_text(PROD_CSS.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Wrote {OUT_CSS.name}: {(OUT_CSS.stat().st_size // 1024)} KB")

    MAIN.write_text(MAIN_CONTENT, encoding="utf-8", newline="\n")
    INDEX.write_text(INDEX_CONTENT, encoding="utf-8", newline="\n")
    print("Updated main.jsx + index.html")


if __name__ == "__main__":
    main()
