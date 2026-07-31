#!/usr/bin/env python3
"""Deterministic, release-based production deployment for TelegramForward.

This script is deliberately separate from ``deploy_prod.py``.  It never
commits, pushes, merges, or deploys by default.  A real deployment requires
``--apply`` and must originate from a clean local ``main`` that exactly equals
``origin/main``.

Release layout on the VPS::

    /opt/telegramforward/
      current -> releases/<commit>          # atomically switched symlink
      releases/<commit>/                    # immutable code + built static
      shared/.env                            # never part of a release
      shared/data/                           # runtime JSON/application state
      shared/uploads/                        # uploaded files
      shared/sessions/                       # Telegram session artefacts
      shared/logs/  shared/cache/  shared/config/
      shared/deployments/                    # deployment + rollback records

The v2 design refuses to use an unlocked Python or Node dependency graph.
Create and commit ``requirements.lock`` (with hashes) and
``dashboard/package-lock.json`` before the first real deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO = Path(__file__).resolve().parents[1]
BRANCH = "main"
REMOTE_ROOT = "/opt/telegramforward"
RELEASES = f"{REMOTE_ROOT}/releases"
SHARED = f"{REMOTE_ROOT}/shared"
PROCESS = "telegram-backend"
HEALTH_URL = "http://127.0.0.1:8000/health"
EXCLUDED_RELEASE_PREFIXES = ("data/", "logs/", "uploads/", "sessions/", "cache/")
EXCLUDED_RELEASE_NAMES = {".env", ".git", ".venv", "venv", "node_modules"}


class DeployError(RuntimeError):
    """A gate prevented a release from reaching Production."""


def run(command: list[str], *, cwd: Path | None = None, timeout: int = 900) -> str:
    """Run a local command, forwarding output and raising on failure."""
    print("+", " ".join(command))
    completed = subprocess.run(
        command,
        cwd=cwd or REPO,
        text=True,
        check=False,
        timeout=timeout,
    )
    if completed.returncode:
        raise DeployError(f"Command failed ({completed.returncode}): {' '.join(command)}")
    return ""


def capture(command: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd or REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise DeployError((completed.stderr or completed.stdout or "command failed").strip())
    return completed.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_clean_main() -> str:
    """Enforce the exact Git state from which production may be built."""
    run(["git", "fetch", "--prune", "origin", BRANCH], timeout=120)
    if capture(["git", "status", "--porcelain"]):
        raise DeployError("Deployment blocked: local Git working tree is not clean.")
    if capture(["git", "rev-parse", "--abbrev-ref", "HEAD"]) != BRANCH:
        raise DeployError("Deployment blocked: checkout main before deploying.")
    head = capture(["git", "rev-parse", "HEAD"])
    remote_head = capture(["git", "rev-parse", f"origin/{BRANCH}"])
    if head != remote_head:
        raise DeployError(
            "Deployment blocked: local main does not exactly equal origin/main. "
            "Pull or push through the reviewed workflow first."
        )
    return head


def require_reproducible_inputs() -> None:
    missing = []
    if not (REPO / "requirements.lock").is_file():
        missing.append("requirements.lock (hash-pinned Python dependencies)")
    if not (REPO / "dashboard" / "package-lock.json").is_file():
        missing.append("dashboard/package-lock.json (Node dependency lock)")
    if missing:
        raise DeployError("Deployment blocked: missing " + "; ".join(missing) + ".")


def clean_checkout(commit: str, workspace: Path) -> Path:
    """Create a disposable checkout containing only committed objects."""
    checkout = workspace / "source"
    run(["git", "clone", "--no-checkout", str(REPO), str(checkout)], cwd=workspace, timeout=180)
    run(["git", "checkout", "--detach", commit], cwd=checkout)
    if capture(["git", "rev-parse", "HEAD"], cwd=checkout) != commit:
        raise DeployError("Clean checkout does not match the requested commit.")
    if capture(["git", "status", "--porcelain"], cwd=checkout):
        raise DeployError("Fresh checkout unexpectedly contains local changes.")
    return checkout


def run_quality_gates(source: Path) -> None:
    """Install locked dependencies, test, build, and validate the generated manifest."""
    python = sys.executable
    venv = source / ".venv"
    run([python, "-m", "venv", str(venv)], cwd=source)
    python_bin = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pip_bin = venv / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
    run([str(pip_bin), "install", "--require-hashes", "-r", "requirements.lock"], cwd=source, timeout=1200)
    run([str(python_bin), "-m", "pytest", "-q"], cwd=source, timeout=1200)
    run([str(python_bin), "-m", "compileall", "-q", "api", "core", "features", "services", "workers", "server.py"], cwd=source)
    run([str(python_bin), "-c", "import server; from core.config import DATA_DIR; print(DATA_DIR)"], cwd=source)

    npm = "npm.cmd" if os.name == "nt" else "npm"
    dashboard = source / "dashboard"
    run([npm, "ci"], cwd=dashboard, timeout=1200)
    run([npm, "test"], cwd=dashboard, timeout=1200)
    run([npm, "run", "build"], cwd=dashboard, timeout=1200)
    run([str(python_bin), "scripts/write_production_manifest.py"], cwd=source)
    validate_manifest(source)


def validate_manifest(source: Path) -> dict:
    manifest_path = source / "static" / "production.manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeployError(f"Invalid production manifest: {exc}") from exc
    for name, hash_key in (("js", "js_sha256"), ("css", "css_sha256")):
        relative = str(manifest.get(name) or "")
        expected = str(manifest.get(hash_key) or "")
        asset = source / "static" / relative
        if not relative or not expected or not asset.is_file() or sha256(asset) != expected:
            raise DeployError(f"Manifest validation failed for {name} asset.")
    index = (source / "static" / "index.html").read_text(encoding="utf-8")
    if f"/{manifest['js']}" not in index or f"/{manifest['css']}" not in index:
        raise DeployError("index.html does not reference the manifest assets.")
    return manifest


def release_archive(source: Path, destination: Path) -> str:
    """Create a payload from the clean checkout and generated build only."""
    def include(path: Path) -> bool:
        relative = path.relative_to(source).as_posix()
        if relative == ".git" or relative.startswith(".git/"):
            return False
        if any(relative == name or relative.startswith(f"{name}/") for name in EXCLUDED_RELEASE_NAMES):
            return False
        return not relative.startswith(EXCLUDED_RELEASE_PREFIXES)

    with tarfile.open(destination, "w:gz") as archive:
        for path in sorted(source.rglob("*")):
            if include(path):
                archive.add(path, arcname=path.relative_to(source), recursive=False)
    return sha256(destination)


def connect(password: str):
    try:
        from scripts.prod_sync_common import ssh_connect
    except ImportError as exc:
        raise DeployError("Paramiko deployment support is unavailable.") from exc
    return ssh_connect(password)


def ssh(client, command: str, *, timeout: int = 900) -> str:
    from scripts.prod_sync_common import ssh_run

    status, output, error = ssh_run(client, command, timeout=timeout)
    if status:
        raise DeployError((error or output or f"remote command failed: {status}").strip())
    return output


def remote_script(release_id: str, archive_name: str, payload_hash: str, operator: str, commit: str) -> str:
    """Return a quoted Bash transaction.  It switches only after release validation."""
    values = {
        "ROOT": REMOTE_ROOT,
        "RELEASES": RELEASES,
        "SHARED": SHARED,
        "RELEASE": f"{RELEASES}/{release_id}",
        "RELEASE_ID": release_id,
        "STAGING": f"{RELEASES}/.staging-{release_id}",
        "ARCHIVE": f"{REMOTE_ROOT}/incoming/{archive_name}",
        "HASH": payload_hash,
        "OPERATOR": operator,
        "COMMIT": commit,
        "PROCESS": PROCESS,
        "PM2_CONFIG": f"{SHARED}/pm2/{PROCESS}.cjs",
        "HEALTH": HEALTH_URL,
    }
    exports = "\n".join(f"{key}={shlex.quote(value)}" for key, value in values.items())
    return f"""set -euo pipefail
{exports}
umask 027
mkdir -p "$RELEASES" "$SHARED" "$SHARED/data" "$SHARED/uploads" "$SHARED/sessions" "$SHARED/logs" "$SHARED/cache" "$SHARED/config" "$SHARED/deployments" "$SHARED/pm2" "$ROOT/incoming"
test -f "$SHARED/.env" || {{ echo 'Missing shared/.env'; exit 31; }}
test -r "$SHARED/.env" || {{ echo 'Shared .env is not readable by the deployment user'; exit 37; }}
test -w "$SHARED/data" -a -w "$SHARED/uploads" -a -w "$SHARED/logs" -a -w "$SHARED/cache" || {{ echo 'Shared runtime paths are not writable by the deployment user'; exit 38; }}
test -L "$ROOT/current" || {{ echo 'Migration incomplete: current must already be a release symlink'; exit 36; }}
test ! -e "$RELEASE" || {{ echo "Release already exists: $RELEASE"; exit 32; }}
test ! -e "$STAGING" || {{ echo "Staging path already exists: $STAGING"; exit 33; }}
test "$(sha256sum "$ARCHIVE" | awk '{{print $1}}')" = "$HASH" || {{ echo 'Payload hash mismatch'; exit 34; }}
mkdir "$STAGING"
cleanup() {{ rm -rf "$STAGING"; }}
trap cleanup ERR
tar -xzf "$ARCHIVE" -C "$STAGING"
mkdir -p "$STAGING/config"
rm -rf "$STAGING/data"
ln -s "$SHARED/.env" "$STAGING/.env"
ln -s "$SHARED/data" "$STAGING/data"
ln -s "$SHARED/uploads" "$STAGING/uploads"
ln -s "$SHARED/logs" "$STAGING/logs"
ln -s "$SHARED/cache" "$STAGING/cache"
if [ -d "$SHARED/config" ]; then
  find "$SHARED/config" -maxdepth 1 -type f -print0 | while IFS= read -r -d '' cfg; do
    name=$(basename "$cfg")
    test ! -e "$STAGING/config/$name" || {{ echo "Runtime config conflicts with committed config: $name"; exit 35; }}
    ln -s "$cfg" "$STAGING/config/$name"
  done
fi
find "$SHARED/sessions" -maxdepth 1 -type f -name '*.session*' -print0 | while IFS= read -r -d '' session; do
  ln -s "$session" "$STAGING/$(basename "$session")"
done
python3 -m venv "$STAGING/venv"
"$STAGING/venv/bin/pip" install --require-hashes -r "$STAGING/requirements.lock"
"$STAGING/venv/bin/python" -c 'import server; from core.config import DATA_DIR; assert DATA_DIR.endswith("/data")'
STAGING="$STAGING" "$STAGING/venv/bin/python" - <<'PY'
import hashlib, json, os, pathlib
root = pathlib.Path(os.environ["STAGING"])
m = json.loads((root / "static/production.manifest.json").read_text())
for field, digest in (("js", "js_sha256"), ("css", "css_sha256")):
    path = root / "static" / m[field]
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == m[digest]
html = (root / "static/index.html").read_text()
assert f"/{{m['js']}}" in html and f"/{{m['css']}}" in html
PY
timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{{"release_id":"%s","commit":"%s","payload_sha256":"%s","operator":"%s","prepared_at":"%s"}}\n' "$RELEASE_ID" "$COMMIT" "$HASH" "$OPERATOR" "$timestamp" > "$STAGING/RELEASE.json"
mv "$STAGING" "$RELEASE"
previous=""
if [ -L "$ROOT/current" ]; then previous=$(readlink -f "$ROOT/current"); fi
test -f "$previous/RELEASE.json" || {{ echo 'Rollback target is not a verified v2 release'; exit 39; }}
cat > "$PM2_CONFIG" <<PM2
module.exports = {{
  apps: [{{
    name: "$PROCESS",
    cwd: "$ROOT/current",
    script: "$ROOT/current/scripts/uvicorn_reload.py",
    interpreter: "$ROOT/current/venv/bin/python",
    autorestart: true,
    env: {{
      HOST: "0.0.0.0",
      PORT: "8000",
      NO_RELOAD: "1",
      PYTHONPATH: "$ROOT/current"
    }}
  }}]
}};
PM2
ln -s "$RELEASE" "$ROOT/.next"
mv -Tf "$ROOT/.next" "$ROOT/current"
rollback() {{
  reason="$1"
  if [ -n "$previous" ] && [ -d "$previous" ]; then
    ln -s "$previous" "$ROOT/.rollback-next"
    mv -Tf "$ROOT/.rollback-next" "$ROOT/current"
    pm2 startOrReload "$PM2_CONFIG" --only "$PROCESS" --update-env || true
  fi
  printf '{{"release_id":"%s","commit":"%s","previous_release":"%s","operator":"%s","rolled_back_at":"%s","reason":"%s"}}\n' "$RELEASE" "$COMMIT" "$previous" "$OPERATOR" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$reason" >> "$SHARED/deployments/rollback.log"
  exit 50
}}
pm2 startOrReload "$PM2_CONFIG" --only "$PROCESS" --update-env || rollback 'pm2_start_failed'
sleep 2
pm2 describe "$PROCESS" | grep -q 'online' || rollback 'pm2_not_online'
curl -fsS --max-time 10 "$HEALTH" | python3 -c 'import json,sys; assert json.load(sys.stdin).get("status") == "ok"' || rollback 'health_check_failed'
printf '{{"release_id":"%s","commit":"%s","previous_release":"%s","payload_sha256":"%s","operator":"%s","deployed_at":"%s"}}\n' "$RELEASE" "$COMMIT" "$previous" "$HASH" "$OPERATOR" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$SHARED/deployments/current.json"
cat "$SHARED/deployments/current.json" >> "$SHARED/deployments/deploy.log"
rm -f "$ARCHIVE"
trap - ERR
echo "RELEASE_OK=$RELEASE"
"""


def upload(client, archive: Path, remote_name: str) -> None:
    sftp = client.open_sftp()
    try:
        try:
            sftp.mkdir(f"{REMOTE_ROOT}/incoming")
        except OSError:
            pass
        sftp.put(str(archive), f"{REMOTE_ROOT}/incoming/{remote_name}")
    finally:
        sftp.close()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform the remote release transaction")
    parser.add_argument("--operator", default=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown")
    parser.add_argument("--keep-workspace", action="store_true", help="keep the disposable local build directory")
    args = parser.parse_args(argv)

    try:
        commit = require_clean_main()
        require_reproducible_inputs()
        release_id = commit
        print(f"Release candidate: {release_id}")
        print("Source: clean checkout of origin/main exact commit")
        print("Mode:", "APPLY" if args.apply else "DRY RUN (no VPS connection)")
        if not args.apply:
            return 0
        password = os.environ.get("VPS_PASSWORD", "")
        if not password:
            raise DeployError("Set VPS_PASSWORD only for an approved --apply run.")

        workspace_path = Path(tempfile.mkdtemp(prefix="telegramforward-release-"))
        try:
            source = clean_checkout(commit, workspace_path)
            run_quality_gates(source)
            payload = workspace_path / f"telegramforward-{commit}.tar.gz"
            payload_hash = release_archive(source, payload)
            manifest = validate_manifest(source)
            print(f"Build payload: {payload_hash} ({payload.stat().st_size} bytes)")
            print(f"Static assets: {manifest['js']} / {manifest['css']}")
            client = connect(password)
            try:
                remote_name = payload.name
                upload(client, payload, remote_name)
                print(ssh(client, remote_script(release_id, remote_name, payload_hash, args.operator, commit)))
            finally:
                client.close()
        finally:
            if args.keep_workspace:
                print(f"Retained workspace: {workspace_path}")
            else:
                shutil.rmtree(workspace_path, ignore_errors=True)
        return 0
    except (DeployError, subprocess.TimeoutExpired) as exc:
        print(f"DEPLOYMENT BLOCKED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
