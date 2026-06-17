#!/usr/bin/env python3
"""Remove stale Vite bundle backups — keep only active assets from index.html."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
STATIC = REPO / "static"
ASSETS = STATIC / "assets"
INDEX = STATIC / "index.html"
MANIFEST = STATIC / "production.manifest.json"

# Root-level static files always kept (not in assets/)
ROOT_KEEP = frozenset({
    "index.html",
    "favicon.svg",
    "icons.svg",
    "sw.js",
    "production.manifest.json",
})

# Filename patterns that are always safe to delete when not in keep set
STALE_PATTERNS = (
    re.compile(r"^app-[A-Za-z0-9_-]+\.js"),
    re.compile(r"^app-[A-Za-z0-9_.-]+\.js\.bak"),
    re.compile(r"^index-[A-Za-z0-9_-]+\.(js|css)$"),
    re.compile(r"^InterviewAdminMonitor-[A-Za-z0-9_-]+\.js$"),
    re.compile(r"^dashboard\.bundle\.(js|css)"),
    re.compile(r"^pdf\.worker\.min-[A-Za-z0-9_-]+\.(js|mjs)$"),
    re.compile(r"\.bak"),
    re.compile(r"^index-[A-Za-z0-9_-]+\.js\.bak"),
)


def _read_keep_from_index() -> set[str]:
    keep: set[str] = set()
    if not INDEX.is_file():
        return keep
    text = INDEX.read_text(encoding="utf-8")
    for m in re.finditer(r"/assets/([A-Za-z0-9_.-]+)", text):
        keep.add(m.group(1))
    return keep


def _read_keep_from_manifest() -> set[str]:
    keep: set[str] = set()
    if not MANIFEST.is_file():
        return keep
    try:
        import json

        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for key in ("js", "css"):
            val = str(data.get(key) or "")
            if val.startswith("assets/"):
                keep.add(val.split("/", 1)[1])
    except Exception:
        pass
    return keep


def build_keep_set() -> set[str]:
    keep = _read_keep_from_index() | _read_keep_from_manifest()
    if not keep:
        raise SystemExit("Could not determine active assets — check static/index.html")
    return keep


def is_removable_asset(name: str, keep: set[str]) -> bool:
    if name in keep:
        return False
    if name.startswith("_"):
        return True
    return any(pat.search(name) for pat in STALE_PATTERNS)


def cleanup_local(*, execute: bool) -> tuple[int, int]:
    keep = build_keep_set()
    print(f"Keeping assets: {', '.join(sorted(keep))}")

    removed = 0
    kept = 0
    if not ASSETS.is_dir():
        print("No static/assets directory")
        return 0, 0

    for path in sorted(ASSETS.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if is_removable_asset(name, keep):
            removed += 1
            size_kb = path.stat().st_size // 1024
            action = "DELETE" if execute else "would delete"
            print(f"  {action}: assets/{name} ({size_kb} KB)")
            if execute:
                path.unlink()
        else:
            kept += 1

    # Remove empty stray files at static root not in ROOT_KEEP
    for path in STATIC.iterdir():
        if path.is_file() and path.name not in ROOT_KEEP:
            if path.name.endswith((".bak", ".tmp")):
                removed += 1
                print(f"  {'DELETE' if execute else 'would delete'}: {path.name}")
                if execute:
                    path.unlink()

    return removed, kept


def cleanup_vps(*, execute: bool) -> tuple[int, int]:
    from scripts.prod_sync_common import REMOTE, ssh_connect, ssh_run, vps_real_root

    password = os.environ.get("VPS_PASSWORD", "")
    if not password:
        raise SystemExit("Set VPS_PASSWORD for VPS cleanup")

    keep = build_keep_set()
    keep_csv = " ".join(sorted(keep))
    root = vps_real_root(ssh_connect(password))

    # Bash: delete stale bundle patterns except keep list
    mode = "" if execute else "echo DRY-RUN:"
    script = f"""
set -euo pipefail
ASSETS="{root}/static/assets"
KEEP=({keep_csv})
keep_file() {{
  local f="$1"
  for k in "${{KEEP[@]}}"; do
    [ "$f" = "$k" ] && return 0
  done
  return 1
}}
removed=0
kept=0
if [ ! -d "$ASSETS" ]; then echo "No assets dir"; exit 0; fi
for f in "$ASSETS"/*; do
  [ -f "$f" ] || continue
  base=$(basename "$f")
  if keep_file "$base"; then
    kept=$((kept+1))
    continue
  fi
  case "$base" in
    app-*.js|index-*.js|index-*.css|InterviewAdminMonitor-*.js|dashboard.bundle.*|pdf.worker.min-*|*.bak*|_*)
      {mode} rm -f "$f"
      removed=$((removed+1))
      ;;
  esac
done
echo "VPS assets kept=$kept removed=$removed"
"""
    client = ssh_connect(password)
    try:
        code, out, err = ssh_run(client, f"bash -s <<'EOS'\n{script}\nEOS", timeout=300)
        print(out)
        if err.strip():
            print(err, file=sys.stderr)
        if code != 0:
            raise SystemExit(code)
        m = re.search(r"removed=(\d+)", out)
        r = int(m.group(1)) if m else 0
        m2 = re.search(r"kept=(\d+)", out)
        k = int(m2.group(1)) if m2 else 0
        return r, k
    finally:
        client.close()


def git_remove_stale_tracked() -> list[str]:
    """Return git-tracked static/assets files that are not in keep set."""
    import subprocess

    keep = build_keep_set()
    out = subprocess.check_output(["git", "ls-files", "static/assets"], cwd=REPO, text=True)
    stale = []
    for line in out.splitlines():
        name = Path(line).name
        if name and is_removable_asset(name, keep):
            stale.append(line)
    return stale


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Clean stale static/assets bundle backups")
    ap.add_argument("--local", action="store_true", help="Clean local static/assets")
    ap.add_argument("--vps", action="store_true", help="Clean VPS static/assets")
    ap.add_argument("--git", action="store_true", help="git rm stale tracked assets in repo")
    ap.add_argument("--execute", action="store_true", help="Actually delete (default is dry-run)")
    ap.add_argument("--all", action="store_true", help="local + vps + git")
    args = ap.parse_args()

    if args.all:
        args.local = args.vps = args.git = True
    if not (args.local or args.vps or args.git):
        args.local = args.vps = args.git = True

    if not args.execute:
        print("DRY RUN — pass --execute to delete\n")

    total_removed = 0

    if args.local:
        print("=== Local static/assets ===")
        r, k = cleanup_local(execute=args.execute)
        print(f"Summary: {r} removable, {k} kept\n")
        total_removed += r

    if args.git:
        print("=== Git tracked stale assets ===")
        stale = git_remove_stale_tracked()
        for rel in stale:
            print(f"  {'git rm' if args.execute else 'would git rm'}: {rel}")
        if args.execute and stale:
            import subprocess

            subprocess.run(["git", "rm", "-f", *stale], cwd=REPO, check=True)
        print(f"Summary: {len(stale)} tracked stale files\n")
        total_removed += len(stale)

    if args.vps:
        print("=== VPS static/assets ===")
        r, k = cleanup_vps(execute=args.execute)
        print(f"Summary: {r} removed, {k} kept\n")
        total_removed += r

    print(f"Done. {'Removed' if args.execute else 'Would remove'} ~{total_removed} files total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
