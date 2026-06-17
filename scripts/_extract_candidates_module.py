"""Extract candidates UI from teleautomation-app.jsx into dashboard module."""
from __future__ import annotations

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "scripts", "_vps_extract", "teleautomation-app.jsx")
OUT = os.path.join(REPO, "dashboard", "src", "candidates", "candidatesModule.jsx")

START_LINE = 36244  # kx()
END_LINE = 38056  # end of _Component35

HEADER = '''/**
 * Candidates tracker UI — extracted from production teleautomation-app.jsx.
 * CSS: index.css (.cand-*). API: /candidates, /handler-expenses.
 */
import React from 'react'
import { useConfirm } from '../context/ConfirmContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const w = React
const s = { Fragment: React.Fragment }

const K1 = typeof window !== 'undefined' && window.location.port === '3000'
const ve = K1 ? '' : (typeof window !== 'undefined'
  ? `${window.location.protocol}//${window.location.host}`
  : '')
const Y8 = ''

function nc() {
  return useConfirm()
}

function wu() {
  return useAuth()
}

function cR() {
  const [gate, setGate] = w.useState(null)
  const closeGate = w.useCallback(() => setGate(null), [])
  const runProtected = w.useCallback((action, opts = {}) => {
    if (typeof action === 'function') {
      setGate({
        title: opts.title || 'Admin password required',
        message: opts.message || 'Enter the main dashboard admin password to continue.',
        onVerified: () => {
          setGate(null)
          action()
        },
      })
    }
  }, [])
  return { gate, closeGate, runProtected }
}

'''


def main() -> None:
    lines = open(SRC, encoding="utf-8", errors="replace").read().splitlines()
    chunk = "\n".join(lines[START_LINE - 1 : END_LINE])
    chunk = re.sub(r"function _Component35\(\)", "export function CandidatesPanel()", chunk, count=1)
    chunk = re.sub(r'\nconst Y8 = "";?\n', "\n", chunk, count=1)
    # Header already defines cR(); drop duplicate from bundle slice.
    chunk = re.sub(
        r"\nfunction cR\(\) \{\n  const \[e, t\] = w\.useState\(null\);.*?\n  return \{\n    gate: e,\n    closeGate: r,\n    runProtected: n\n  \};\n\}\n",
        "\n",
        chunk,
        count=1,
        flags=re.DOTALL,
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEADER)
        f.write(chunk)
        f.write("\n")
    print("Wrote", OUT, "lines", END_LINE - START_LINE + 1)


if __name__ == "__main__":
    main()
