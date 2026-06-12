#!/usr/bin/env python3
"""Block production deploys unless git is committed and pushed (git first, prod second)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRANCH = "main"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "git failed").strip())
    return (result.stdout or "").strip()


def git_deploy_status(branch: str = DEFAULT_BRANCH) -> dict[str, str | bool | int]:
    dirty = bool(_git("status", "--porcelain"))
    head = _git("rev-parse", "--short", "HEAD")
    try:
        upstream = _git("rev-parse", "--abbrev-ref", f"@{branch}")
    except RuntimeError:
        upstream = branch
    try:
        ahead = int(_git("rev-list", "--count", f"origin/{branch}..HEAD") or "0")
    except RuntimeError:
        ahead = -1
    behind = 0
    try:
        behind = int(_git("rev-list", "--count", f"HEAD..origin/{branch}") or "0")
    except RuntimeError:
        pass
    return {
        "dirty": dirty,
        "head": head,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "ok": not dirty and ahead == 0,
    }


def require_git_pushed(branch: str = DEFAULT_BRANCH) -> str:
    """Exit 1 unless working tree clean and HEAD is pushed to origin/<branch>."""
    status = git_deploy_status(branch)
    problems: list[str] = []

    if status["dirty"]:
        problems.append("Uncommitted changes — commit everything before deploy.")
    ahead = status["ahead"]
    if isinstance(ahead, int) and ahead > 0:
        problems.append(f"{ahead} commit(s) not pushed to origin/{branch} — push first.")
    if isinstance(ahead, int) and ahead < 0:
        problems.append(f"Could not compare with origin/{branch}. Run: git fetch origin")

    behind = status["behind"]
    if isinstance(behind, int) and behind > 0:
        problems.append(
            f"Local branch is {behind} commit(s) behind origin/{branch} — pull before deploy."
        )

    if problems:
        print("Deploy blocked — git first, prod second.", file=sys.stderr)
        print(f"Repo: {REPO_ROOT}", file=sys.stderr)
        print(f"Branch: {status['branch']} @ {status['head']}", file=sys.stderr)
        for item in problems:
            print(f"  • {item}", file=sys.stderr)
        print(
            "\nWorkflow: edit → commit → push origin main → deploy\n"
            "After dashboard build, commit static/ too before deploy.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    head = str(status["head"])
    print(f"Git OK @ {head} (clean, pushed to origin/{branch})")
    return head


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Enforce git-first deploy policy")
    parser.add_argument("--require", action="store_true", help="Exit 1 unless deploy-safe")
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--status", action="store_true", help="Print status JSON-ish lines")
    args = parser.parse_args()

    if args.require:
        require_git_pushed(args.branch)
        return

    status = git_deploy_status(args.branch)
    if args.status:
        for key, value in status.items():
            print(f"{key}={value}")
        return

    if status["ok"]:
        print(f"OK: {status['head']} on {status['branch']}")
    else:
        print(f"NOT READY: {status['head']} on {status['branch']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
