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


def _fetch_origin(branch: str) -> None:
    _git("fetch", "--quiet", "origin", branch)


def git_deploy_status(branch: str = DEFAULT_BRANCH) -> dict[str, str | bool | int]:
    dirty = bool(_git("status", "--porcelain"))
    head = _git("rev-parse", "HEAD")
    current_branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    try:
        upstream = _git("rev-parse", "--abbrev-ref", "@{upstream}")
    except RuntimeError:
        upstream = ""
    try:
        origin_head = _git("rev-parse", f"origin/{branch}")
    except RuntimeError:
        origin_head = ""
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
        "branch": current_branch,
        "upstream": upstream,
        "origin_head": origin_head,
        "ahead": ahead,
        "behind": behind,
        "ok": (
            not dirty
            and current_branch == branch
            and bool(origin_head)
            and head == origin_head
            and ahead == 0
            and behind == 0
        ),
    }


def require_git_pushed(branch: str = DEFAULT_BRANCH) -> str:
    """Exit unless clean local branch exactly matches the merged origin branch."""
    try:
        _fetch_origin(branch)
    except RuntimeError as exc:
        print(f"Deploy blocked — could not refresh origin/{branch}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    status = git_deploy_status(branch)
    problems: list[str] = []

    if status["branch"] != branch:
        problems.append(
            f"Deploys must run from {branch}; current branch is {status['branch']}."
        )
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
    if not status["origin_head"]:
        problems.append(f"Could not resolve origin/{branch}. Run: git fetch origin {branch}")
    elif status["head"] != status["origin_head"]:
        problems.append(
            f"HEAD does not equal origin/{branch}; deploy only the merged remote commit."
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
    print(f"Git OK @ {head[:12]} (clean {branch} exactly matches origin/{branch})")
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
