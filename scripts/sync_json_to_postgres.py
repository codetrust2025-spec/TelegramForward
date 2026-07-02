"""Sync local candidates.json to VPS Postgres database."""
import socket, paramiko, json
from pathlib import Path

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = 'REMOVED_VPS_PASSWORD'

local_json = Path(__file__).resolve().parents[1] / "data" / "candidates.json"

print(f"📁 Loading local: {local_json}")
with open(local_json, 'r', encoding='utf-8') as f:
    data = json.load(f)

candidates = data.get('candidates', [])
print(f"📊 Candidates in local JSON: {len(candidates)}")

# Show sample
print("\nSample candidates:")
for c in candidates[:3]:
    print(f"  {c.get('name')} | date={c.get('date')} | ref={c.get('reference')}")

print(f"\n🔌 Connecting to VPS...")
sock = socket.create_connection((VPS_HOST, 22), timeout=30)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, sock=sock)

print("📤 Uploading JSON temporarily...")
# Upload to temp location
sftp = client.open_sftp()
temp_json = '/tmp/candidates_sync.json'
sftp.put(str(local_json), temp_json)
sftp.close()
print(f"✅ Uploaded to {temp_json}")

print("\n💾 Saving to Postgres...")
_, stdout, stderr = client.exec_command(f"""cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 << 'EOF'
import sys
import json
sys.path.insert(0, '/opt/telegramforward')

# Load env
import os
from pathlib import Path
env_file = Path('/opt/telegramforward/.env')
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

from core.db.candidates_pg import pg_save
from features import candidate_store

# Load the JSON
with open('{temp_json}', 'r') as f:
    data = json.load(f)

print(f"Loaded {{len(data.get('candidates', []))}} candidates from JSON")

# Save to Postgres
pg_save(data)
print("✅ Saved to Postgres")

# Force reload to clear cache
candidate_store._load_cache = None
candidate_store._load_cache_at = 0.0

# Verify
fresh_data = candidate_store._load(force=True)
fresh_count = len(fresh_data.get('candidates', []))
print(f"✅ Verified: {{fresh_count}} candidates in Postgres")

# Check for our test candidates
vamini = [c for c in fresh_data.get('candidates', []) if 'vamini' in (c.get('name', '') or '').lower()]
ravi = [c for c in fresh_data.get('candidates', []) if 'ravi' in (c.get('name', '') or '').lower() and 'tumu' in (c.get('name', '') or '').lower()]
print(f"Vamini Akhil: {{len(vamini)}} entries")
print(f"Ravi Tumu: {{len(ravi)}} entries")
EOF
""", timeout=60)

output = stdout.read().decode()
errors = stderr.read().decode()

print(output)
if errors:
    print("\nSTDERR:")
    print(errors)

print("\n🧹 Cleaning up...")
_, stdout2, _ = client.exec_command(f"rm {temp_json}", timeout=30)
stdout2.read()

print("\n✅ Sync complete!")
print("\n💡 Now test your dashboard:")
print("   1. Hard refresh (Ctrl+Shift+R)")
print("   2. Select July 2026 month filter")
print("   3. Should now show correct data!")

client.close()
