"""Shared helpers for git ↔ production sync (deploy + verify)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
GITHUB_REPO = "https://github.com/codetrust2025-spec/TelegramForward.git"
LIVE_ORIGIN = "https://teleautomation.online"
MANIFEST_PATH = REPO / "static" / "production.manifest.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_cmd(*args: str, cwd: Path | None = None) -> str:
    out = subprocess.check_output(
        ["git", *args],
        cwd=cwd or REPO,
        text=True,
        stderr=subprocess.STDOUT,
    )
    return out.strip()


def git_head(*, short: bool = True) -> str:
    if short:
        return git_cmd("rev-parse", "--short", "HEAD")
    return git_cmd("rev-parse", "HEAD")


def parse_index_assets(index_html: str) -> tuple[str | None, str | None]:
    js = re.search(r"/assets/(app-[A-Za-z0-9_-]+\.js)", index_html)
    css = re.search(r"/assets/(index-[A-Za-z0-9_-]+\.css)", index_html)
    return (js.group(1) if js else None, css.group(1) if css else None)


def read_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_manifest(*, git_commit: str | None = None) -> dict:
    index_path = REPO / "static" / "index.html"
    if not index_path.is_file():
        raise FileNotFoundError("static/index.html missing — run: cd dashboard && npm run build")

    index_html = index_path.read_text(encoding="utf-8")
    js_name, css_name = parse_index_assets(index_html)
    if not js_name or not css_name:
        raise ValueError("Could not parse JS/CSS from static/index.html")

    js_path = REPO / "static" / "assets" / js_name
    css_path = REPO / "static" / "assets" / css_name
    server_path = REPO / "server.py"
    commit = git_commit or git_cmd("rev-parse", "HEAD")

    manifest = {
        "version": 2,
        "description": "Pinned production assets — live site must match these hashes.",
        "git_commit": commit,
        "git_commit_short": commit[:7],
        "deployed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "js": f"assets/{js_name}",
        "css": f"assets/{css_name}",
        "js_sha256": sha256_file(js_path),
        "css_sha256": sha256_file(css_path),
        "js_bytes": js_path.stat().st_size if js_path.is_file() else 0,
        "css_bytes": css_path.stat().st_size if css_path.is_file() else 0,
        "server_py_sha256": sha256_file(server_path),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def fetch_live_bundle_hash(js_asset: str) -> str | None:
    url = f"{LIVE_ORIGIN}/{js_asset.lstrip('/')}"
    req = urllib.request.Request(url, headers={"User-Agent": "TelegramForward-prod-sync"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return _sha256_bytes(resp.read())


def ssh_connect(password: str):
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username="root", password=password, timeout=30)
    return client


def ssh_run(client, cmd: str, *, timeout: int = 120) -> tuple[int, str, str]:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def vps_real_root(client) -> str:
    code, out, _ = ssh_run(client, f"readlink -f {REMOTE}")
    return out.strip() or REMOTE


def vps_file_hash(client, rel_path: str) -> str | None:
    root = vps_real_root(client)
    code, out, _ = ssh_run(client, f"sha256sum {root}/{rel_path} 2>/dev/null | awk '{{print $1}}'")
    if code != 0:
        return None
    val = out.strip()
    return val or None


def vps_has_git(client) -> bool:
    code, _, _ = ssh_run(
        client,
        f"REAL=$(readlink -f {REMOTE}) && test -d \"$REAL/.git\"",
    )
    return code == 0


def git_ls_files() -> list[str]:
    return [line for line in git_cmd("ls-files").splitlines() if line.strip()]


def upload_tracked_tree(sftp, client) -> int:
    """Upload all git-tracked files to VPS (works for private repos without VPS git credentials)."""
    root = vps_real_root(client)
    count = 0
    skip_prefixes = ("data/",)
    for rel in git_ls_files():
        if rel.startswith(skip_prefixes) or rel == ".env":
            continue
        local = REPO / rel.replace("/", os.sep)
        if not local.is_file():
            continue
        remote = f"{root}/{rel.replace(chr(92), '/')}"
        remote_dir = os.path.dirname(remote).replace("\\", "/")
        parts = remote_dir.split("/")
        path = ""
        for p in parts:
            if not p:
                continue
            path += f"/{p}"
            try:
                sftp.stat(path)
            except OSError:
                try:
                    sftp.mkdir(path)
                except OSError:
                    pass
        sftp.put(str(local), remote)
        count += 1
    return count


def write_vps_deploy_marker(client, commit: str) -> None:
    root = vps_real_root(client)
    ssh_run(client, f"printf '%s' '{commit}' > {root}/.deploy-commit")


def read_vps_deploy_commit(client) -> str:
    root = vps_real_root(client)
    code, out, _ = ssh_run(client, f"cat {root}/.deploy-commit 2>/dev/null")
    if code != 0:
        return ""
    return out.strip()


def bump_build_stamp() -> bool:
    """Bump dashboard BUILD_STAMP so Vite emits a new hashed bundle."""
    config = REPO / "dashboard" / "src" / "config.js"
    if not config.is_file():
        return False
    text = config.read_text(encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    new_text, n = re.subn(
        r"export const BUILD_STAMP = '[^']*'",
        f"export const BUILD_STAMP = '{stamp}'",
        text,
        count=1,
    )
    if n:
        config.write_text(new_text, encoding="utf-8")
    return bool(n)
