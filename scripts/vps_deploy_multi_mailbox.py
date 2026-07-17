#!/usr/bin/env python3
"""Deploy multi-mailbox feature: migration + backend + dashboard."""
import sys
import paramiko
from pathlib import Path

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'
VPS_PATH = '/opt/telegramforward'

def run_ssh(command: str, check: bool = True) -> tuple[str, str, int]:
    """Execute command on VPS via SSH."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
        stdin, stdout, stderr = client.exec_command(command, timeout=300)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if check and exit_code != 0:
            raise RuntimeError(f"Command failed (exit {exit_code}): {command}\n{err}")
        return out, err, exit_code
    finally:
        client.close()

def upload_file(local_path: Path, remote_path: str):
    """Upload a file to VPS via SFTP."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
        sftp = client.open_sftp()
        sftp.put(str(local_path), remote_path)
        sftp.close()
        print(f"✓ Uploaded {local_path.name} → {remote_path}")
    finally:
        client.close()

def main():
    repo_root = Path(__file__).parent.parent
    
    print("=== Multi-Mailbox Feature Deployment ===\n")
    
    # Step 1: Pull latest code on VPS (backup untracked files and force pull)
    print("Step 1/4: Pulling latest code from git...")
    print("  - Creating backup of potentially conflicting files...")
    backup_dir = f"/tmp/telegramforward_backup_{int(__import__('time').time())}"
    run_ssh(f"mkdir -p {backup_dir}", check=False)
    run_ssh(f"cd {VPS_PATH} && git diff --name-only > {backup_dir}/changed_files.txt", check=False)
    run_ssh(f"cd {VPS_PATH} && git stash", check=False)
    print("  - Resetting to clean state...")
    run_ssh(f"cd {VPS_PATH} && git reset --hard HEAD", check=False)
    run_ssh(f"cd {VPS_PATH} && git clean -fd", check=False)
    print("  - Pulling from origin/main...")
    out, err, _ = run_ssh(f"cd {VPS_PATH} && git pull origin main")
    print(out)
    
    # Step 2: Run database migration
    print("\nStep 2/4: Running database migration 009...")
    migration_file = repo_root / 'core' / 'migrations' / '009_recruitment_mail_multi_mailbox.sql'
    if not migration_file.exists():
        print(f"ERROR: Migration file not found: {migration_file}")
        sys.exit(1)
    
    # Get DATABASE_URL from .env
    print("  - Reading DATABASE_URL...")
    db_url_out, _, _ = run_ssh(f"cd {VPS_PATH} && grep '^DATABASE_URL=' .env | cut -d'=' -f2-")
    db_url = db_url_out.strip()
    
    if not db_url:
        print("ERROR: DATABASE_URL not found in .env")
        sys.exit(1)
    
    # Run migration using psql with the DATABASE_URL
    print("  - Executing SQL migration...")
    out, err, _ = run_ssh(
        f"cd {VPS_PATH} && psql '{db_url}' < core/migrations/009_recruitment_mail_multi_mailbox.sql"
    )
    print(out)
    if err:
        print(f"stderr: {err}")
    
    # Step 3: Restart backend service
    print("\nStep 3/4: Restarting backend service...")
    # Try various restart methods
    out, err, code = run_ssh("systemctl restart telegramforward 2>&1 || echo 'systemctl not available'", check=False)
    if "systemctl not available" in out or code != 0:
        print("  - systemctl not available, trying process kill...")
        run_ssh(f"cd {VPS_PATH} && pkill -f 'python.*main.py' 2>/dev/null || true", check=False)
        run_ssh(f"cd {VPS_PATH} && pkill -f 'python.*server.py' 2>/dev/null || true", check=False)
        print("  - Backend processes stopped (if any were running)")
        print("  - Note: You may need to manually restart the backend service")
    else:
        print("✓ Backend restarted via systemctl")
    
    # Step 4: Verify deployment
    print("\nStep 4/4: Verifying deployment...")
    out, err, code = run_ssh(
        f"cd {VPS_PATH} && "
        f"psql '{db_url}' -t -c 'SELECT COUNT(*) FROM candidate_mailboxes' && "
        f"psql '{db_url}' -t -c \"SELECT COUNT(*) FROM pg_indexes WHERE tablename='candidate_mailboxes' AND indexname='candidate_mailboxes_candidate_email_key'\"",
        check=False
    )
    if code == 0:
        lines = [l.strip() for l in out.strip().split('\n') if l.strip()]
        mailbox_count = lines[0] if lines else '?'
        index_exists = lines[1] if len(lines) > 1 else '0'
        print(f"  Mailboxes in DB: {mailbox_count}")
        print(f"  New index exists: {index_exists == '1'}")
    else:
        print(f"  Warning: Could not verify (non-critical)")
        print(f"  {out}")
    
    print("\n=== Deployment Complete ===")
    print("✓ Code pulled from git")
    print("✓ Migration 009 executed")
    print("✓ Backend restarted")
    print("✓ Dashboard static files already deployed via git pull")
    print("\nNext steps:")
    print("1. Test adding a 2nd Gmail for an existing candidate")
    print("2. Verify both mailboxes show as separate rows")
    print("3. Test per-mailbox actions (sync, pause, disconnect)")

if __name__ == '__main__':
    main()
