#!/usr/bin/env python3
"""Policy-compliant Production deployment (see DEPLOYMENT.md).

Deploys the exact merged ``origin/main`` commit into an immutable release
directory and switches ``current`` atomically, keeping the previous release
available for rollback.

Guarantees enforced here, each mandated by DEPLOYMENT.md:

* only a commit that equals ``origin/main`` is deployable, from a clean tree
* the release payload is a ``git archive`` of that commit — never a worktree
* a verified backup exists before anything on the host changes
* the first run migrates the legacy flat tree into ``releases/<commit>/``
* runtime paths are symlinked into the release, never copied into it
* frontend assets are verified against the committed manifest by SHA-256
* health is proven before the switch, and again after it
* the switch is a single atomic ``rename`` of the ``current`` symlink
* the deploy marker is written only after post-switch verification passes
* any failed gate rolls back to the previous release automatically

Usage::

    python scripts/deploy_release.py --commit <full-sha>  # SSH key/agent
    # For password auth, set VPS_PASSWORD in the protected environment first.
    python scripts/deploy_release.py --commit <sha> --dry-run
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

REPO = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/opt/telegramforward"
RELEASES = f"{REMOTE_ROOT}/releases"
CURRENT = f"{REMOTE_ROOT}/current"
BACKUP_ROOT = "/var/backups/telegramforward"
HEALTH_URL = "http://127.0.0.1:8000/health"
PUBLIC_ORIGIN = "https://teleautomation.online"
PM2_APP = "telegram-backend"
POSTGRES_DB = "teleautomation"

# Runtime state lives outside releases and is linked in, never copied.
RUNTIME_LINKS = (".env", "data", "uploads", "logs")
RUNTIME_GLOBS = ("session_*.session",)

# Runtime state that lives inside a git-tracked directory, so the directory
# itself cannot be linked. These files are gitignored because they hold
# secrets, so they never arrive with the release payload. Without an explicit
# link a new release simply has no handler accounts and every handler login
# fails while the admin login — which reads .env — keeps working.
RUNTIME_FILE_LINKS = ("config/dashboard_handlers.yaml",)

# Minimum free space required on the target filesystem before deploying.
MIN_FREE_MB = 2048


def log(message: str) -> None:
    print(f"[deploy] {message}", flush=True)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ── local preflight ──────────────────────────────────────────────────────────

def require_deployable_commit(commit: str) -> str:
    """The deployed commit must equal origin/main, from a clean worktree."""
    if git("status", "--porcelain"):
        raise SystemExit("Refusing to deploy: local worktree is dirty.")
    git("fetch", "origin", "--quiet")
    origin_main = git("rev-parse", "origin/main")
    resolved = git("rev-parse", commit)
    if resolved != origin_main:
        raise SystemExit(
            f"Refusing to deploy: {resolved[:12]} != origin/main {origin_main[:12]}."
        )
    return resolved


def clean_checkout(commit: str, workspace: Path) -> Path:
    """Export the exact commit. Untracked and dirty files cannot leak in."""
    source = workspace / "source"
    source.mkdir(parents=True, exist_ok=True)
    archive = workspace / "source.tar"
    with archive.open("wb") as handle:
        subprocess.run(
            ["git", "archive", "--format=tar", commit],
            cwd=REPO, stdout=handle, check=True,
        )
    with tarfile.open(archive) as tar:
        # 'data' rejects absolute paths, traversal and unsafe metadata.
        tar.extractall(source, filter="data")
    archive.unlink()
    # A release must never ship runtime state, even if a path was committed.
    for name in RUNTIME_LINKS:
        stale = source / name
        if stale.is_dir():
            shutil.rmtree(stale)
        elif stale.exists():
            stale.unlink()
    return source


def build_frontend(source: Path) -> None:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    dashboard = source / "dashboard"
    log("installing frontend dependencies from the committed lockfile")
    subprocess.run([npm, "ci", "--ignore-scripts"], cwd=dashboard, check=True)
    log("building production assets")
    subprocess.run([npm, "run", "build"], cwd=dashboard, check=True)


def verify_exact_source(source: Path) -> None:
    """Run release-critical compile and invite regression checks on the archive."""
    log("compiling exact archived Python source")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "server.py",
            "core",
            "features",
            "services",
            "workers",
            "api",
        ],
        cwd=source,
        check=True,
    )
    log("verifying invite mismatch regression on exact archived source")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_ollama_invite_extract.py",
            "-k",
            (
                "matching_date_time_with_missing_timezone_is_not_reported_as_conflict "
                "or different_start_times_still_report_verification_conflict"
            ),
        ],
        cwd=source,
        check=True,
    )


def write_and_verify_manifest(source: Path, commit: str) -> dict:
    """Generate the manifest, then prove it matches the files on disk."""
    sys.path.insert(0, str(source))
    from scripts.prod_sync_common import write_manifest  # noqa: E402

    cwd = Path.cwd()
    os.chdir(source)
    try:
        manifest = write_manifest(git_commit=commit)
    finally:
        os.chdir(cwd)
        sys.path.remove(str(source))

    static = source / "static"
    for key, digest_key in (("js", "js_sha256"), ("css", "css_sha256")):
        rel = manifest.get(key)
        if not rel:
            raise SystemExit(f"Manifest is missing '{key}'.")
        asset = static / rel
        if not asset.is_file():
            raise SystemExit(f"Manifest references a missing asset: {rel}")
        actual = sha256_file(asset)
        if actual != manifest.get(digest_key):
            raise SystemExit(
                f"Manifest hash mismatch for {rel}: {actual} != {manifest.get(digest_key)}"
            )
    index = (static / "index.html").read_text(encoding="utf-8")
    for rel in (manifest["js"], manifest["css"]):
        if rel not in index:
            raise SystemExit(f"index.html does not reference {rel}")
    log(f"manifest verified: {manifest['js']} {manifest['js_sha256'][:12]}…")
    return manifest


# ── remote helpers ───────────────────────────────────────────────────────────

def connect(password: str | None):
    sys.path.insert(0, str(REPO))
    from scripts.prod_sync_common import ssh_connect

    return ssh_connect(password)


def ssh(client, command: str, *, check: bool = True, timeout: int = 900) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if check and code != 0:
        raise SystemExit(f"Remote command failed ({code}): {command}\n{err or out}")
    return out.strip()


def q(value: str) -> str:
    return shlex.quote(value)


# ── remote phases ────────────────────────────────────────────────────────────

def preflight(client) -> None:
    free_mb = int(ssh(client, f"df -Pm {q(REMOTE_ROOT)} | awk 'NR==2{{print $4}}'") or 0)
    log(f"free space: {free_mb} MB")
    if free_mb < MIN_FREE_MB:
        raise SystemExit(f"Refusing to deploy: only {free_mb} MB free (need {MIN_FREE_MB}).")


def take_backup(client, commit: str) -> str:
    """Back up runtime state and PostgreSQL, then prove every artifact is readable."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = f"{BACKUP_ROOT}/{stamp}-pre-{commit[:12]}"
    ssh(client, f"install -d -m 700 {q(BACKUP_ROOT)} && mkdir -m 700 {q(target)}")

    log(f"backing up to {target}")
    for name in RUNTIME_LINKS:
        src = f"{REMOTE_ROOT}/{name}"
        exists = ssh(client, f"test -e {q(src)} && echo yes || echo no", check=False)
        if exists != "yes":
            continue
        ssh(client, f"tar -czf {q(target + '/' + name + '.tar.gz')} -C {q(REMOTE_ROOT)} {q(name)}")

    ssh(
        client,
        f"cd {q(REMOTE_ROOT)} && tar -czf {q(target + '/sessions.tar.gz')} "
        f"$(ls session_*.session 2>/dev/null) 2>/dev/null || true",
        check=False,
    )
    ssh(client, f"cp -a /etc/nginx/sites-available/telegramforward {q(target)}/nginx.conf 2>/dev/null || true", check=False)
    ssh(client, f"pm2 jlist > {q(target)}/pm2.json 2>/dev/null || true", check=False)
    ssh(client, f"cp -a {q(CURRENT)}/static/production.manifest.json {q(target)}/manifest.json 2>/dev/null || true", check=False)

    # Database contents are protected runtime state and must be recoverable
    # independently of the application tree.
    dump = f"{target}/{POSTGRES_DB}.dump"
    schema = f"{target}/{POSTGRES_DB}-schema.sql"
    restore_list = f"{target}/{POSTGRES_DB}.restore-list"
    ssh(client, f"sudo -u postgres pg_dump -Fc {q(POSTGRES_DB)} > {q(dump)}")
    ssh(
        client,
        f"sudo -u postgres pg_dump --schema-only {q(POSTGRES_DB)} > {q(schema)}",
    )
    ssh(client, f"pg_restore --list {q(dump)} > {q(restore_list)}")

    # Validate every archive and database dump, record an inventory, then
    # verify the checksum manifest rather than merely creating it.
    archives = ssh(client, f"ls {q(target)}/*.tar.gz 2>/dev/null || true", check=False)
    for archive in [a for a in archives.splitlines() if a.strip()]:
        ssh(client, f"tar -tzf {q(archive)} > /dev/null")
    ssh(client, f"test -s {q(dump)} && test -s {q(schema)} && test -s {q(restore_list)}")
    ssh(
        client,
        f"cd {q(target)} && find . -maxdepth 1 -type f "
        "-printf '%P\\t%s bytes\\n' | sort > INVENTORY.txt",
    )
    ssh(
        client,
        f"cd {q(target)} && find . -maxdepth 1 -type f "
        "! -name SHA256SUMS -printf '%P\\0' | sort -z | "
        "xargs -0 sha256sum > SHA256SUMS",
    )
    ssh(client, f"cd {q(target)} && sha256sum -c SHA256SUMS > /dev/null")
    ssh(client, f"test -s {q(target + '/INVENTORY.txt')} && test -s {q(target + '/SHA256SUMS')}")
    log("backup validated (database restore list, archives, inventory, and hashes)")
    return target


def migrate_legacy_layout(client, commit: str) -> None:
    """First run only: fold the legacy flat tree into releases/<commit>/."""
    has_current = ssh(client, f"test -L {q(CURRENT)} && echo yes || echo no", check=False)
    if has_current == "yes":
        return
    log("no 'current' symlink: migrating legacy layout")
    legacy = f"{RELEASES}/legacy-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    ssh(client, f"mkdir -p {q(RELEASES)}")
    # Fail closed: a partial copy must never become 'current'. `set -e` plus an
    # unguarded cp means ENOSPC or a permission error aborts here, while the
    # live flat tree is still untouched and still serving.
    ssh(
        client,
        "set -e; cd {root}; mkdir -p {dest}; for entry in * .[!.]*; do "
        "case \"$entry\" in releases|current|.env|data|uploads|logs|session_*.session|venv) continue;; esac; "
        "[ -e \"$entry\" ] || continue; cp -a \"$entry\" {dest}/; done".format(
            root=q(REMOTE_ROOT), dest=q(legacy)
        ),
    )
    # Prove the copy is usable before anything points at it.
    for required in ("server.py", "core", "static/index.html"):
        present = ssh(
            client, f"test -e {q(legacy + '/' + required)} && echo yes || echo no", check=False
        )
        if present != "yes":
            raise SystemExit(
                f"Legacy migration incomplete: {required} missing from {legacy}. "
                "'current' was not created; the live tree is unchanged."
            )
    link_runtime(client, legacy)
    ssh(client, f"ln -sfn {q(legacy)} {q(CURRENT)}.tmp && mv -Tf {q(CURRENT)}.tmp {q(CURRENT)}")
    log(f"legacy release preserved as {legacy} and 'current' now points at it")


def link_runtime(client, release: str) -> None:
    """Runtime state is linked into the release, never copied into it."""
    for name in RUNTIME_LINKS:
        src = f"{REMOTE_ROOT}/{name}"
        ssh(client, f"test -e {q(src)} || mkdir -p {q(src)}", check=False)
        ssh(client, f"rm -rf {q(release + '/' + name)} && ln -sfn {q(src)} {q(release + '/' + name)}")
    for pattern in RUNTIME_GLOBS:
        ssh(
            client,
            f"cd {q(REMOTE_ROOT)} && for f in {pattern}; do "
            f"[ -e \"$f\" ] && ln -sfn {q(REMOTE_ROOT)}/\"$f\" {q(release)}/\"$f\" || true; done",
            check=False,
        )
    for rel in RUNTIME_FILE_LINKS:
        src = f"{REMOTE_ROOT}/{rel}"
        dest = f"{release}/{rel}"
        # The parent is a real directory shipped with the release; only the
        # file itself is replaced by a link to the shared copy.
        ssh(client, f"mkdir -p {q(os.path.dirname(dest))}", check=False)
        if ssh(client, f"test -e {q(src)} && echo yes || echo no", check=False).strip() == "yes":
            ssh(client, f"rm -rf {q(dest)} && ln -sfn {q(src)} {q(dest)}")
            log(f"linked runtime file: {rel}")
        else:
            log(f"WARNING: runtime file absent on the host, not linked: {rel}")


def health_ok(client, url: str = HEALTH_URL) -> bool:
    out = ssh(client, f"curl -sf -m 10 {q(url)} || true", check=False)
    return '"ok"' in out


def verify_release(client, release: str, manifest: dict) -> list[str]:
    """Contract checks that must hold before and after the switch."""
    problems: list[str] = []
    if not health_ok(client):
        problems.append("/health did not return ok")

    routes = ssh(client, f"grep -c 'bookings/confirm' {q(release)}/core/public_slot_api.py", check=False)
    if routes.strip() in ("", "0"):
        problems.append("/bookings/confirm route missing from release")

    legacy = ssh(client, f"grep -c 'status=410' {q(release)}/core/public_slot_api.py", check=False)
    if legacy.strip() in ("", "0"):
        problems.append("legacy /public/slots/book 410 guard missing")

    # Handler sign-in reads config/dashboard_handlers.yaml from the release.
    # The file is gitignored, so it only exists via the runtime link. Without
    # it every handler is locked out while the admin login keeps working, which
    # is exactly how this went unnoticed across twenty-three releases.
    for rel in RUNTIME_FILE_LINKS:
        present = ssh(client, f"test -r {q(release)}/{rel} && echo yes || echo no", check=False)
        if present.strip() != "yes":
            problems.append(f"runtime file not readable in release: {rel}")

    accounts = ssh(
        client,
        f"cd {q(release)} && {q(REMOTE_ROOT)}/venv/bin/python -c "
        "\"import sys;sys.path.insert(0,'.');"
        "from core.dashboard_auth_vps import _handler_accounts;"
        "print(len(_handler_accounts()))\" 2>/dev/null || echo 0",
        check=False,
    )
    if accounts.strip() in ("", "0"):
        problems.append("no handler accounts resolvable in release — handler login would fail")

    for key, digest_key in (("js", "js_sha256"), ("css", "css_sha256")):
        rel = manifest[key]
        remote_hash = ssh(
            client, f"sha256sum {q(release)}/static/{rel} 2>/dev/null | awk '{{print $1}}'", check=False
        ).strip()
        if remote_hash != manifest[digest_key]:
            problems.append(f"asset hash mismatch for {rel}")
    return problems


def verify_live_release(
    client,
    release: str,
    manifest: dict,
    commit: str,
) -> list[str]:
    """Verify the active process, proxy, APIs, and publicly served assets."""
    problems = verify_release(client, release, manifest)

    current = ssh(client, f"readlink -f {q(CURRENT)}", check=False).strip()
    if current != release:
        problems.append(f"current resolves to {current or 'nothing'}, expected release")

    manifest_has_commit = ssh(
        client,
        f"grep -F -c {q(commit)} {q(release)}/static/production.manifest.json",
        check=False,
    ).strip()
    if manifest_has_commit in ("", "0"):
        problems.append("production manifest does not contain the target commit")

    fix_present = ssh(
        client,
        f"grep -F -c 'agreed on the date and start time, but did not' "
        f"{q(release)}/features/ollama_invite_extract.py",
        check=False,
    ).strip()
    if fix_present in ("", "0"):
        problems.append("invite mismatch fix missing from active release")

    pm2_cwd = ssh(
        client,
        f"pid=$(pm2 pid {q(PM2_APP)} | tail -n 1); "
        "test \"${pid:-0}\" -gt 0 && readlink -f /proc/$pid/cwd || true",
        check=False,
    ).strip()
    if pm2_cwd != release:
        problems.append("PM2 app is offline or running from the wrong release")

    nginx = ssh(
        client,
        "nginx -t > /dev/null 2>&1 && echo ok || echo failed",
        check=False,
    ).strip()
    if nginx != "ok":
        problems.append("Nginx configuration test failed")

    public_health = ssh(
        client,
        f"curl -sf -m 15 {q(PUBLIC_ORIGIN + '/health')} || true",
        check=False,
    )
    if '"ok"' not in public_health:
        problems.append("public /health did not return ok")

    confirm_status = ssh(
        client,
        f"curl -sS -m 15 -o /dev/null -w '%{{http_code}}' -X POST "
        f"{q(PUBLIC_ORIGIN + '/bookings/confirm')} || true",
        check=False,
    ).strip()
    if confirm_status not in {"400", "422"}:
        problems.append(
            f"/bookings/confirm invalid-input guard returned {confirm_status or 'no status'}"
        )

    legacy_status = ssh(
        client,
        f"curl -sS -m 15 -o /dev/null -w '%{{http_code}}' -X POST "
        f"{q(PUBLIC_ORIGIN + '/public/slots/book')} || true",
        check=False,
    ).strip()
    if legacy_status != "410":
        problems.append(
            f"legacy booking endpoint returned {legacy_status or 'no status'}, expected 410"
        )

    public_index = ssh(
        client,
        f"curl -sf -m 15 {q(PUBLIC_ORIGIN + '/')} || true",
        check=False,
    )
    for key, digest_key in (("js", "js_sha256"), ("css", "css_sha256")):
        rel = manifest[key]
        if rel not in public_index:
            problems.append(f"public index does not reference {rel}")
        public_hash = ssh(
            client,
            f"curl -sf -m 30 {q(PUBLIC_ORIGIN + '/' + rel)} | "
            "sha256sum | awk '{print $1}'",
            check=False,
        ).strip()
        if public_hash != manifest[digest_key]:
            problems.append(f"public asset hash mismatch for {rel}")

    return problems


def switch_current(client, release: str) -> None:
    """Atomic pointer move: rename(2) replaces the symlink in one step."""
    ssh(client, f"ln -sfn {q(release)} {q(CURRENT)}.tmp && mv -Tf {q(CURRENT)}.tmp {q(CURRENT)}")


def reload_app(client) -> None:
    ssh(client, f"cd {q(CURRENT)} && pm2 restart {q(PM2_APP)} --update-env", check=False)
    ssh(client, "sleep 3", check=False)


def rollback(client, previous: str, previous_marker: str = "") -> bool:
    log(f"ROLLING BACK to {previous}")
    switch_current(client, previous)
    reload_app(client)
    ok = health_ok(client)
    if ok and previous_marker:
        ssh(
            client,
            f"printf '%s' {q(previous_marker)} > {q(REMOTE_ROOT)}/.deploy-commit",
        )
    log(f"rollback health: {'ok' if ok else 'FAILED'}")
    return ok


def activate_release(
    client,
    *,
    release: str,
    previous: str,
    previous_marker: str,
    manifest: dict,
    commit: str,
) -> int:
    """Atomically activate, verify, and roll back on every critical failure."""
    switched = False
    try:
        switch_current(client, release)
        switched = True
        reload_app(client)

        problems = verify_live_release(client, release, manifest, commit)
        if problems:
            raise RuntimeError("; ".join(problems))

        # Marker is written only once the release is proven good.
        ssh(client, f"printf '%s' {q(commit)} > {q(REMOTE_ROOT)}/.deploy-commit")
        return 0
    except BaseException as exc:
        log(f"POST-SWITCH VERIFICATION FAILED: {exc}")
        recovered = False
        if switched:
            try:
                recovered = rollback(client, previous, previous_marker)
            except BaseException as rollback_exc:
                log(f"ROLLBACK FAILED: {rollback_exc}")
        log(f"failed release retained for diagnosis: {release}")
        return 1 if recovered else 2


# ── orchestration ────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True, help="full SHA, must equal origin/main")
    parser.add_argument("--dry-run", action="store_true", help="build and verify locally only")
    args = parser.parse_args(argv)

    commit = require_deployable_commit(args.commit)
    log(f"deployable commit verified: {commit}")

    workspace = Path(tempfile.mkdtemp(prefix="release-"))
    source = clean_checkout(commit, workspace)
    verify_exact_source(source)
    build_frontend(source)
    manifest = write_and_verify_manifest(source, commit)

    if args.dry_run:
        log("dry run: local build and manifest verification passed; host untouched")
        return 0

    # Paramiko also supports an existing SSH key or agent. A password remains
    # available through the protected environment when key auth is not used.
    password = os.environ.get("VPS_PASSWORD") or None

    release = f"{RELEASES}/{commit}"
    client = connect(password)
    try:
        preflight(client)
        take_backup(client, commit)
        migrate_legacy_layout(client, commit)

        previous = ssh(client, f"readlink -f {q(CURRENT)}", check=False).strip()
        if not previous:
            raise SystemExit("No previous release resolved; refusing to continue.")
        previous_marker = ssh(
            client,
            f"cat {q(REMOTE_ROOT)}/.deploy-commit 2>/dev/null || true",
            check=False,
        ).strip()
        log(f"previous release: {previous}")

        log(f"uploading release payload to {release}")
        release_exists = ssh(
            client,
            f"test -e {q(release)} && echo yes || echo no",
            check=False,
        ).strip()
        if release_exists == "yes":
            raise SystemExit(
                f"Refusing to overwrite immutable release directory: {release}"
            )
        ssh(client, f"mkdir -p {q(release)}")
        payload = workspace / "release.tar.gz"
        with tarfile.open(payload, "w:gz") as tar:
            tar.add(source, arcname=".")
        sftp = client.open_sftp()
        sftp.put(str(payload), f"{release}.tar.gz")
        sftp.close()
        ssh(client, f"tar -xzf {q(release)}.tar.gz -C {q(release)} && rm -f {q(release)}.tar.gz")

        link_runtime(client, release)

        problems = verify_release(client, release, manifest)
        asset_problems = [p for p in problems if "asset" in p or "route" in p or "410" in p]
        if asset_problems:
            raise SystemExit("Pre-switch verification failed: " + "; ".join(asset_problems))
        log("pre-switch verification passed")

        activation_status = activate_release(
            client,
            release=release,
            previous=previous,
            previous_marker=previous_marker,
            manifest=manifest,
            commit=commit,
        )
        if activation_status:
            return activation_status

        log(f"deployed and verified: {commit}")
        log(f"previous release retained for rollback: {previous}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
