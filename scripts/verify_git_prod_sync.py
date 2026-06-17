#!/usr/bin/env python3
"""Verify GitHub/local repo matches live production (exit 0 = in sync)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.prod_sync_common import (  # noqa: E402
    HOST,
    LIVE_ORIGIN,
    MANIFEST_PATH,
    REMOTE,
    fetch_live_bundle_hash,
    git_cmd,
    parse_index_assets,
    read_manifest,
    read_vps_deploy_commit,
    sha256_file,
    ssh_connect,
    vps_file_hash,
)


def _git_show_bytes(path: str) -> bytes | None:
    try:
        return subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=REPO)
    except subprocess.CalledProcessError:
        return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Check git vs production alignment")
    ap.add_argument("--skip-vps", action="store_true", help="Only compare git vs live site")
    args = ap.parse_args()

    password = __import__("os").environ.get("VPS_PASSWORD", "")
    issues: list[str] = []

    print("=== Git ↔ Production sync check ===\n")

    # Git state
    try:
        head = git_cmd("rev-parse", "HEAD")
        short = head[:7]
        branch = git_cmd("rev-parse", "--abbrev-ref", "HEAD")
        dirty = bool(git_cmd("status", "--porcelain"))
        origin = git_cmd("rev-parse", "origin/main")
    except subprocess.CalledProcessError as exc:
        print(f"Git error: {exc}")
        return 2

    print(f"Branch:      {branch}")
    print(f"HEAD:        {short}")
    print(f"origin/main: {origin[:7]}")
    print(f"Working tree dirty: {dirty}")
    if dirty:
        issues.append("Local git has uncommitted changes — commit or stash before deploy")

    if head != origin:
        issues.append("HEAD != origin/main — push or pull before deploy")

    manifest = read_manifest()
    index_local = (REPO / "static" / "index.html").read_text(encoding="utf-8") if (REPO / "static" / "index.html").is_file() else ""
    js_name, css_name = parse_index_assets(index_local)
    js_asset = f"assets/{js_name}" if js_name else manifest.get("js", "")
    expected_js_hash = manifest.get("js_sha256") or (sha256_file(REPO / "static" / js_asset) if js_asset else None)
    expected_server_hash = manifest.get("server_py_sha256") or sha256_file(REPO / "server.py")

    if manifest.get("git_commit") and not manifest["git_commit"].startswith(head[: len(manifest["git_commit"])]):
        issues.append(
            f"production.manifest.json commit ({manifest.get('git_commit_short')}) "
            f"does not match HEAD ({short})"
        )

    print(f"\nManifest js: {manifest.get('js') or js_asset or '—'}")

    # Live site
    if js_asset:
        try:
            live_hash = fetch_live_bundle_hash(js_asset)
            print(f"Live bundle:  {live_hash[:16]}…")
            print(f"Git/manifest: {(expected_js_hash or '')[:16]}…")
            if expected_js_hash and live_hash != expected_js_hash:
                issues.append("Live site JS bundle hash != git manifest")
            elif expected_js_hash and live_hash == expected_js_hash:
                print("Live site: OK")
        except Exception as exc:
            issues.append(f"Could not fetch live bundle: {exc}")
    else:
        issues.append("No JS bundle found in static/index.html")

    if not args.skip_vps:
        if not password:
            issues.append("VPS_PASSWORD not set — cannot check VPS")
        else:
            client = ssh_connect(password)
            try:
                deployed = read_vps_deploy_commit(client)
                print(f"\nVPS .deploy-commit: {deployed[:7] if deployed else '— (run deploy_prod.py)'}")
                if deployed and deployed != head:
                    issues.append(f"VPS deploy marker ({deployed[:7]}) != git HEAD ({short})")
                elif deployed and deployed == head:
                    print("VPS commit marker: OK")

                if js_asset:
                    vps_js = vps_file_hash(client, f"static/{js_asset}")
                    if vps_js and expected_js_hash and vps_js != expected_js_hash:
                        issues.append("VPS static JS hash != git manifest")
                    elif vps_js and expected_js_hash and vps_js == expected_js_hash:
                        print("VPS static:   OK")

                vps_srv = vps_file_hash(client, "server.py")
                if vps_srv and expected_server_hash and vps_srv != expected_server_hash:
                    issues.append("VPS server.py hash != git")
                elif vps_srv and expected_server_hash and vps_srv == expected_server_hash:
                    print("VPS server.py: OK")
            finally:
                client.close()

    print("\n=== Result ===")
    if issues:
        for item in issues:
            print(f"  ✗ {item}")
        print(f"\nFix: python scripts/deploy_prod.py")
        print(f"Docs: docs/GIT_PROD_SYNC.md")
        return 1

    print("  ✓ Git, live site, and VPS are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
