"""Debug why April entries appear in June filter."""
import socket, paramiko, json

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

print("="*70)
print("DEBUG: Why April data appears in June filter")
print("="*70)

_, stdout, _ = c.exec_command("""
cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 << 'EOF'
import sys, os, json
sys.path.insert(0, '/opt/telegramforward')
from pathlib import Path
env_file = Path('.env')
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

from features import candidate_store

# Clear cache
candidate_store._load_cache = None
candidate_store._load_cache_at = 0.0

# Call the API function with June filter + Thrilok reference
results = candidate_store.list_candidates(month='2026-06', reference='Thrilok')

print(f"Results for month=2026-06, reference=Thrilok: {len(results)} entries")
print()

for r in results:
    name = r.get('name', '')
    date = r.get('date', '')
    logged = r.get('logged_date', '')
    is_june = date.startswith('2026-06') if date else False
    marker = '✅' if is_june else '❌ NOT JUNE'
    print(f"  {marker} {name:25} | date={date:12} | logged_date={logged:12} | id={r.get('id','')[:8]}")

# Check specifically Gangadhar and KALESHWAR
print("\n\nAll Gangadhar entries in raw data:")
data = candidate_store._load(force=True)
all_cands = data.get('candidates', [])
for c2 in all_cands:
    if 'gangadhar' in (c2.get('name', '') or '').lower():
        print(f"  {c2.get('name'):20} | date={c2.get('date'):12} | logged={c2.get('logged_date'):12} | id={c2.get('id')}")

print("\nAll KALESHWAR entries in raw data:")
for c2 in all_cands:
    if 'kaleshwar' in (c2.get('name', '') or '').lower():
        print(f"  {c2.get('name'):20} | date={c2.get('date'):12} | logged={c2.get('logged_date'):12} | id={c2.get('id')}")
EOF
""", timeout=60)
print(stdout.read().decode())

c.close()
