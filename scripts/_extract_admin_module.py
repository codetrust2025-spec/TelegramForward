"""Extract Admin dashboard + AI settings modal from teleautomation-app.jsx."""
from __future__ import annotations

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "scripts", "_vps_extract", "teleautomation-app.jsx")
OUT = os.path.join(REPO, "dashboard", "src", "admin", "adminModule.jsx")

SLICES = [
    (373, 380, None),  # ct
    (34442, 34475, ("function P8(", "function KarthikAssessmentScorecard(")),
    (34476, 34757, ("function __(", "function AiSmartReplySettingsModal(")),
    (38057, 38086, None),
    (38087, 38156, ("function _Component36()", "export function AdminPanel()")),
]

HEADER = '''/**
 * Karthik admin dashboard — extracted from production teleautomation-app.jsx.
 */
import React from 'react'
import { Spinner } from '../Loader.jsx'

const w = React
const s = { Fragment: React.Fragment }

const K1 = typeof window !== 'undefined' && window.location.port === '3000'
const ve = K1 ? '' : (typeof window !== 'undefined'
  ? `${window.location.protocol}//${window.location.host}`
  : '')

function ButtonSpinner({ loading, loadingLabel, children }) {
  if (loading) {
    return (
      <s.Fragment>
        <Spinner size={14} className="ui-spinner--on-dark" />
        <span>{loadingLabel || 'Loading…'}</span>
      </s.Fragment>
    )
  }
  return children
}

'''


def main() -> None:
    lines = open(SRC, encoding="utf-8", errors="replace").read().splitlines()
    parts = [HEADER]
    for start, end, rename in SLICES:
        chunk = "\n".join(lines[start - 1 : end])
        if rename:
            old, new = rename
            chunk = chunk.replace(old, new, 1)
        # AI modal uses _Component2 and P8
        chunk = chunk.replace("_Component2", "ButtonSpinner")
        chunk = chunk.replace("<__ ", "<AiSmartReplySettingsModal ")
        chunk = chunk.replace("<P8 ", "<KarthikAssessmentScorecard ")
        parts.append(chunk)
        parts.append("\n")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    text = "\n".join(parts)
    text = re.sub(r"\b__\b", "AiSmartReplySettingsModal", text)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
