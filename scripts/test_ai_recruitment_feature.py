"""Run the AI recruitment feature verification suite without interactive input."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
PYTHON = sys.executable
NPM = "npm.cmd" if os.name == "nt" else "npm"

BACKEND_TESTS = [
    "tests/test_gmail_provider.py", "tests/test_recruitment_api.py",
    "tests/test_recruitment_attachment.py", "tests/test_recruitment_evaluation.py",
    "tests/test_recruitment_mail_agent.py", "tests/test_recruitment_parsing.py",
    "tests/test_recruitment_pipeline.py", "tests/test_recruitment_worker.py",
]


def run(label: str, command: list[str], cwd: Path = ROOT, *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print(f"\n[RUN] {label}", flush=True)
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=capture, check=False)
    if capture:
        if result.stdout: print(result.stdout.rstrip())
        if result.stderr and result.returncode: print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")
    print(f"[PASS] {label}")
    return result


def security_scan() -> None:
    paths = [
        ROOT / ".env.example", ROOT / "core" / "ai_gateway.py",
        ROOT / "core" / "recruitment_mail_api.py", ROOT / "core" / "recruitment_mail_store.py",
        ROOT / "services" / "gmail_mailbox_provider.py", ROOT / "services" / "recruitment_mail_agent.py",
        ROOT / "services" / "mail_attachment_processor.py", ROOT / "workers" / "recruitment_mail_worker.py",
        DASHBOARD / "src" / "components" / "RecruitmentMailPanel.jsx",
    ]
    findings=[]
    email_pattern=re.compile(r"[A-Za-z0-9._%+-]+@(?!test\.invalid)[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    secret_pattern=re.compile(r"(?i)(?:password|client_secret|refresh_token)\s*=\s*['\"][^'\"]{4,}['\"]")
    for path in paths:
        text=path.read_text("utf-8")
        for line_number,line in enumerate(text.splitlines(),1):
            if email_pattern.search(line) or secret_pattern.search(line):
                findings.append(f"{path.relative_to(ROOT)}:{line_number}")
    if findings:
        raise RuntimeError("possible hardcoded credential or mailbox: " + ", ".join(findings))
    print("[PASS] credential and mailbox source scan")


def production_audit() -> None:
    result=subprocess.run([NPM, "audit", "--omit=dev", "--json"], cwd=DASHBOARD, text=True, capture_output=True, check=False)
    report=json.loads(result.stdout or "{}")
    vulnerabilities=report.get("vulnerabilities") or {}
    unexpected=[name for name,value in vulnerabilities.items() if name != "xlsx" or value.get("severity") == "critical"]
    if unexpected:
        raise RuntimeError("unexpected production dependency vulnerabilities: " + ", ".join(unexpected))
    if "xlsx" in vulnerabilities:
        print("[WARN] pre-existing xlsx advisory has no registry fix; replace before untrusted spreadsheet uploads")
    else:
        print("[PASS] production dependency audit")


def main() -> int:
    checks = [
        ("backend and evaluation tests", [PYTHON, "-m", "pytest", "-q", *BACKEND_TESTS], ROOT),
        ("Python compile", [PYTHON, "-m", "compileall", "-q", "core", "services", "workers", "tests"], ROOT),
        ("server import", [PYTHON, "-c", "import server; print('server import ok')"], ROOT),
        ("frontend formatting", [NPM, "run", "format:check:recruitment"], DASHBOARD),
        ("frontend tests", [NPM, "test", "--", "--run"], DASHBOARD),
        ("frontend lint", [NPM, "run", "lint:recruitment"], DASHBOARD),
        ("frontend type-check", [NPM, "run", "typecheck:recruitment"], DASHBOARD),
        ("production build", [NPM, "run", "build"], DASHBOARD),
    ]
    try:
        security_scan()
        for label,command,cwd in checks:run(label,command,cwd)
        production_audit()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    print("\nAUTOMATED FEATURE VERIFICATION PASSED")
    print("External activation still requires PostgreSQL configuration and one-time Google OAuth consent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
