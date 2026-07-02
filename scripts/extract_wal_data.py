"""Extract ALL candidate data from WAL file 7B (contains production data)."""
import socket, paramiko, json

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='8897870998s@SS', sock=sock)

print("="*70)
print("EXTRACTING CANDIDATE DATA FROM WAL FILE 7B")
print("="*70)

# Extract all JSON-like candidate data from WAL
_, stdout, _ = c.exec_command("""
WAL_DIR=/var/lib/postgresql/16/main/pg_wal

cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 << 'PYEOF'
import re, json, os, sys

WAL_FILE = '/var/lib/postgresql/16/main/pg_wal/00000001000000000000007B'

print(f"Reading WAL file: {WAL_FILE}")
print(f"Size: {os.path.getsize(WAL_FILE) / 1024 / 1024:.1f} MB")

# Read as binary and extract strings
with open(WAL_FILE, 'rb') as f:
    raw = f.read()

# Convert to string (lossy) to find JSON patterns
text = raw.decode('utf-8', errors='replace')

# Find all JSON objects that look like candidate records
# They have "id" and "name" and "date" fields
pattern = r'\{"id":\s*"[^"]+",\s*"date":\s*"[^"]*",\s*"name":\s*"[^"]*"[^}]*\}'
matches = re.findall(pattern, text)

print(f"Found {len(matches)} JSON candidate patterns")

# Parse and deduplicate
candidates = {}
for match in matches:
    try:
        # Try to fix incomplete JSON
        candidate = json.loads(match)
        cid = candidate.get('id')
        if cid and candidate.get('name'):
            # Keep the longest/most complete version
            if cid not in candidates or len(match) > len(json.dumps(candidates[cid])):
                candidates[cid] = candidate
    except json.JSONDecodeError:
        pass

print(f"Unique candidates parsed: {len(candidates)}")

if candidates:
    # Save to file
    output = {"candidates": list(candidates.values()), "source": "WAL_recovery_7B"}
    with open('/tmp/wal_recovered_candidates.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nRecovered candidates:")
    for cand in sorted(candidates.values(), key=lambda c: c.get('date', ''), reverse=True)[:20]:
        print(f"  {cand.get('name', 'N/A'):25} | date={cand.get('date', ''):12} | ref={cand.get('reference', '')}")
    
    # Check for July data
    july = [c for c in candidates.values() if '2026-07' in (c.get('date', '') or '')]
    print(f"\nJuly 2026 entries: {len(july)}")
    for c in july:
        print(f"  {c.get('name')} | {c.get('date')} | {c.get('reference')}")

print("\\nSaved to /tmp/wal_recovered_candidates.json")
PYEOF
""", timeout=120)

result = stdout.read().decode()
print(result)

# Also try WAL file 7A
print("\n" + "="*70)
print("Also checking WAL file 7A for more data...")
print("="*70)

_, stdout2, _ = c.exec_command("""
cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 << 'PYEOF'
import re, json, os

WAL_FILE = '/var/lib/postgresql/16/main/pg_wal/00000001000000000000007A'

print(f"Reading WAL file: {WAL_FILE}")
print(f"Size: {os.path.getsize(WAL_FILE) / 1024 / 1024:.1f} MB")

with open(WAL_FILE, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

pattern = r'\{"id":\s*"[^"]+",\s*"date":\s*"[^"]*",\s*"name":\s*"[^"]*"[^}]*\}'
matches = re.findall(pattern, text)

print(f"Found {len(matches)} JSON candidate patterns")

candidates = {}
for match in matches:
    try:
        candidate = json.loads(match)
        cid = candidate.get('id')
        if cid and candidate.get('name'):
            if cid not in candidates or len(match) > len(json.dumps(candidates[cid])):
                candidates[cid] = candidate
    except json.JSONDecodeError:
        pass

print(f"Unique candidates parsed: {len(candidates)}")

if candidates:
    output = {"candidates": list(candidates.values()), "source": "WAL_recovery_7A"}
    with open('/tmp/wal_recovered_7a.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    july = [c for c in candidates.values() if '2026-07' in (c.get('date', '') or '')]
    print(f"July 2026 entries: {len(july)}")
    for c in july[:10]:
        print(f"  {c.get('name')} | {c.get('date')} | {c.get('reference')}")
PYEOF
""", timeout=120)
print(stdout2.read().decode())

c.close()
