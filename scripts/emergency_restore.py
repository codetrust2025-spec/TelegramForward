"""EMERGENCY: Try every possible method to recover the lost data."""
import socket, paramiko, json

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='8897870998s@SS', sock=sock)

print("="*70)
print("🚨 EMERGENCY DATA RECOVERY - TRYING ALL METHODS")
print("="*70)

# Method 1: Check if Postgres has transaction logs (WAL) we can replay
print("\n" + "="*70)
print("METHOD 1: Check Postgres WAL for recent data")
print("="*70)
_, stdout, _ = c.exec_command("""
sudo -u postgres psql teleautomation << 'SQL'
-- Check if we can see recent transactions
SELECT pg_current_wal_lsn();

-- Check for any dead tuples (recently deleted/updated rows)
SELECT n_dead_tup, n_live_tup, last_vacuum, last_autovacuum 
FROM pg_stat_user_tables 
WHERE relname = 'candidates_store';

-- Check if VACUUM hasn't run yet (dead tuples still exist)
SELECT relname, n_dead_tup FROM pg_stat_user_tables WHERE n_dead_tup > 0;
SQL
""", timeout=30)
print(stdout.read().decode())

# Method 2: Check if the candidates.json.backup files have the data
print("\n" + "="*70)
print("METHOD 2: Check backup JSON files created by my sync script")
print("="*70)
_, stdout2, _ = c.exec_command("""
ls -lth /opt/telegramforward/data/candidates.json.backup_* 2>/dev/null | head -5
""", timeout=30)
backup_files = stdout2.read().decode()
print(backup_files)

if 'backup_' in backup_files:
    # Get the first backup file (created before my sync)
    _, stdout3, _ = c.exec_command("""
    FIRST_BACKUP=$(ls -t /opt/telegramforward/data/candidates.json.backup_* 2>/dev/null | tail -1)
    echo "Earliest backup: $FIRST_BACKUP"
    python3 << EOF
import json
import glob
backups = sorted(glob.glob('/opt/telegramforward/data/candidates.json.backup_*'))
for bf in backups:
    with open(bf, 'r') as f:
        data = json.load(f)
    cands = data.get('candidates', [])
    july = [c for c in cands if '2026-07' in (c.get('date', '') or '')]
    vamini = [c for c in cands if 'vamini' in (c.get('name', '') or '').lower()]
    print(f"{bf}: {len(cands)} candidates, {len(july)} July, {len(vamini)} Vamini")
    if july or vamini:
        print("  *** THIS FILE HAS THE DATA! ***")
        for c in july[:5]:
            print(f"    {c.get('name')} | {c.get('date')} | {c.get('reference')}")
EOF
    """, timeout=30)
    print(stdout3.read().decode())

# Method 3: Check /tmp for any data files we created
print("\n" + "="*70)
print("METHOD 3: Check /tmp for cached data files")
print("="*70)
_, stdout4, _ = c.exec_command("""
ls -lth /tmp/*candidate* /tmp/*postgres* /tmp/*sync* 2>/dev/null | head -10
""", timeout=30)
tmp_files = stdout4.read().decode()
print(tmp_files if tmp_files else "No temp files found")

if tmp_files:
    _, stdout5, _ = c.exec_command("""
python3 << 'EOF'
import json, glob
for pattern in ['/tmp/*candidate*', '/tmp/*postgres*', '/tmp/*sync*']:
    for f in glob.glob(pattern):
        try:
            with open(f, 'r') as fh:
                data = json.load(fh)
            cands = data.get('candidates', [])
            if cands:
                july = [c for c in cands if '2026-07' in (c.get('date', '') or '')]
                print(f"{f}: {len(cands)} candidates, {len(july)} July")
                if july:
                    print("  *** FOUND JULY DATA! ***")
                    for c in july[:3]:
                        print(f"    {c.get('name')} | {c.get('date')}")
        except:
            pass
EOF
""", timeout=30)
    print(stdout5.read().decode())

# Method 4: Try pg_dirtyread extension to read dead tuples
print("\n" + "="*70)
print("METHOD 4: Try reading dead tuples from Postgres")
print("="*70)
_, stdout6, _ = c.exec_command("""
sudo -u postgres psql teleautomation << 'SQL'
-- Try to find if pg_dirtyread is available
SELECT * FROM pg_available_extensions WHERE name = 'pg_dirtyread';

-- Check if there are dead tuples we could recover
SELECT n_dead_tup, n_live_tup FROM pg_stat_user_tables WHERE relname = 'candidates_store';

-- Try to get ALL rows including dead ones using ctid trick
-- This won't work for truly deleted rows but might catch UPDATE ghosts
SELECT count(*) FROM candidates_store;
SQL
""", timeout=30)
print(stdout6.read().decode())

# Method 5: Check if there's a pg_dump from the cron backup_postgres_once.py
# that might have captured data after June 17
print("\n" + "="*70)
print("METHOD 5: Check for any other backups/dumps")  
print("="*70)
_, stdout7, _ = c.exec_command("""
# Check ALL .sql, .sql.gz, .dump files anywhere
find / -maxdepth 4 -type f \\( -name '*.sql.gz' -o -name '*.dump' \\) -newer /root/teleautomation_migration/teleautomation_pg.sql 2>/dev/null | head -10

# Check if there's a pg_basebackup
ls -lth /var/lib/postgresql/*/main/pg_wal/ 2>/dev/null | head -5

# Check systemd timer for backups
systemctl list-timers 2>/dev/null | grep -i backup
""", timeout=30)
print(stdout7.read().decode())

c.close()

print("\n" + "="*70)
print("RECOVERY SUMMARY")
print("="*70)
