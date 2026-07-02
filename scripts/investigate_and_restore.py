"""Investigate data sources and restore production data."""
import socket, paramiko, json
from pathlib import Path

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='8897870998s@SS', sock=sock)

print("="*70)
print("STEP 1: Check if there's a Postgres backup from today")
print("="*70)

_, stdout, _ = c.exec_command("""
cd /opt/telegramforward
# Check for automatic Postgres dumps
ls -lth /tmp/*.json /opt/telegramforward*/backups/*.sql 2>/dev/null | head -20
""", timeout=30)
print(stdout.read().decode())

print("\n" + "="*70)
print("STEP 2: Check old Postgres data in .old folder")
print("="*70)

_, stdout2, _ = c.exec_command("""
# The old telegramforward folder might have the production DB
if [ -d /opt/telegramforward.old ]; then
    echo "Found /opt/telegramforward.old"
    ls -lh /opt/telegramforward.old/data/candidates.json 2>/dev/null || echo "No JSON in .old"
    
    # Check if there's a different Postgres DB URL in .old
    grep DATABASE_URL /opt/telegramforward.old/.env 2>/dev/null || echo "No .env in .old"
fi
""", timeout=30)
print(stdout2.read().decode())

print("\n" + "="*70)
print("STEP 3: Dump current Postgres and check what we have NOW")
print("="*70)

_, stdout3, _ = c.exec_command("""
cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 << 'EOF'
import sys, os, json
sys.path.insert(0, '/opt/telegramforward')

# Load env
from pathlib import Path
env_file = Path('.env')
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

from core.db.candidates_pg import pg_load

# Get current data
data = pg_load()
candidates = data.get('candidates', [])

print(f"\\n📊 Current Postgres: {len(candidates)} candidates")

# Analyze by reference
from collections import Counter
refs = Counter(c.get('reference', 'Unknown') for c in candidates)
print(f"\\nTop 10 references:")
for ref, count in refs.most_common(10):
    print(f"  {ref}: {count}")

# Analyze by month
months = Counter((c.get('date', '') or '')[:7] for c in candidates if c.get('date'))
print(f"\\nCandidates by month:")
for month in sorted(months.keys(), reverse=True)[:6]:
    print(f"  {month}: {months[month]}")

# Check for the specific people we saw in screenshots
names_to_find = ['Vamini', 'Ravi Tumu', 'Ram Charan']
print(f"\\nSearching for screenshot candidates:")
for name_part in names_to_find:
    matches = [c for c in candidates if name_part.lower() in (c.get('name', '') or '').lower()]
    if matches:
        for m in matches[:2]:
            print(f"  ✓ {m.get('name')} | date={m.get('date')} | ref={m.get('reference')}")
    else:
        print(f"  ✗ No '{name_part}' found")

# Save current state as backup
with open('/tmp/current_postgres_state.json', 'w') as f:
    json.dump(data, f, indent=2)
print(f"\\n💾 Saved to /tmp/current_postgres_state.json")
EOF
""", timeout=60)
print(stdout3.read().decode())

print("\n" + "="*70)
print("STEP 4: Check SQL backup from June 5th")
print("="*70)

_, stdout4, _ = c.exec_command("""
# Try to extract info from SQL backup
if [ -f /opt/telegramforward.old/backups/pre_keerthana_delete_20260605_095113/candidates_store.sql ]; then
    echo "Found SQL backup"
    # Count candidates in SQL
    grep -c "INSERT INTO candidates_store" /opt/telegramforward.old/backups/pre_keerthana_delete_20260605_095113/candidates_store.sql 2>/dev/null || echo "Can't count INSERTs"
    
    # Check if it has recent dates
    grep "2026-07\\|2026-06" /opt/telegramforward.old/backups/pre_keerthana_delete_20260605_095113/candidates_store.sql 2>/dev/null | head -5 || echo "No June/July dates"
fi
""", timeout=30)
print(stdout4.read().decode())

print("\n" + "="*70)
print("STEP 5: Check if there's a production sync script")
print("="*70)

_, stdout5, _ = c.exec_command("""
find /opt/telegramforward* -name '*sync*' -type f | grep -E '\\.py$|\\.sh$' | head -10
""", timeout=30)
sync_scripts = stdout5.read().decode()
print(sync_scripts if sync_scripts else "No sync scripts found")

print("\n" + "="*70)
print("DECISION POINT")
print("="*70)
print("""
The current Postgres now has 103 candidates from your local JSON.
We need to determine the SOURCE OF TRUTH for production data.

Options:
1. Restore from SQL backup (June 5th - might be outdated)
2. Keep current data (103 from local JSON - missing July/Pavan data)
3. Find another data source

The month filter code IS fixed, but we need the right data.
""")

c.close()
