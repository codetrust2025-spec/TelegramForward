"""Extract candidate data from WAL using strings + pattern matching."""
import socket, paramiko, json

sock = socket.create_connection(('187.127.169.159', 22), timeout=60)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

print("="*70)
print("EXTRACTING ALL CANDIDATE DATA FROM WAL")
print("="*70)

# The WAL stores candidates as individual columns in the candidates_store table
# Format we saw: id | date | name | task | time | notes | phone | stage | ...
# Extract full JSON blobs from the WAL
_, stdout, _ = c.exec_command("""
cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 << 'PYEOF'
import os, json, re

WAL_7B = '/var/lib/postgresql/16/main/pg_wal/00000001000000000000007B'

print(f"Reading {WAL_7B}...")

with open(WAL_7B, 'rb') as f:
    raw = f.read()

# The candidates_store table stores JSON in a jsonb column
# In WAL, jsonb is stored as binary. But we can find the text representation
# by looking for patterns

# Look for complete candidate JSON objects - the key insight is that
# pg stores the entire JSONB value which starts with { and contains "id":
# Let's find all occurrences of candidate ID patterns followed by data

text = raw.decode('latin-1')  # Use latin-1 to preserve all bytes

# Find candidate IDs (10 char hex strings) followed by data
# The format in WAL binary is: id_column \\t json_column
# But for jsonb, it might be stored differently

# Let's search for the actual JSON strings stored in the JSONB column
# These will contain "id": "xxx", "date": "xxx", "name": "xxx"
# They start with a length prefix in binary, then the JSON text

# Method: find all substrings that look like candidate JSON
found_candidates = {}

# Search for name patterns we know exist
# From earlier strings output we saw: c36c0f1cc0 2026-07-01 Yamini Akhil
# This suggests the data is stored in a columnar/row format, not JSON in WAL

# Let's try to find the JSONB blobs by searching for the pattern
# "id": " which starts every candidate JSON
idx = 0
json_starts = []
marker = b'"id": "'
while True:
    pos = raw.find(marker, idx)
    if pos == -1:
        break
    # Try to find the start of the JSON object (look backwards for {)
    start = raw.rfind(b'{', max(0, pos-50), pos)
    if start != -1:
        # Try to find the matching closing brace
        # Simple approach: look for next } that's followed by non-JSON content
        depth = 0
        end = start
        for i in range(start, min(start + 10000, len(raw))):
            if raw[i:i+1] == b'{':
                depth += 1
            elif raw[i:i+1] == b'}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        if end > start + 50:  # minimum viable JSON size
            try:
                json_str = raw[start:end].decode('utf-8', errors='replace')
                obj = json.loads(json_str)
                if isinstance(obj, dict) and obj.get('id') and obj.get('name'):
                    cid = obj['id']
                    if cid not in found_candidates or len(json_str) > len(json.dumps(found_candidates[cid])):
                        found_candidates[cid] = obj
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
    
    idx = pos + 1

print(f"Found {len(found_candidates)} unique candidates in WAL 7B")

# Also check WAL 7A
WAL_7A = '/var/lib/postgresql/16/main/pg_wal/00000001000000000000007A'
print(f"\\nReading {WAL_7A}...")

with open(WAL_7A, 'rb') as f:
    raw2 = f.read()

idx = 0
while True:
    pos = raw2.find(marker, idx)
    if pos == -1:
        break
    start = raw2.rfind(b'{', max(0, pos-50), pos)
    if start != -1:
        depth = 0
        end = start
        for i in range(start, min(start + 10000, len(raw2))):
            if raw2[i:i+1] == b'{':
                depth += 1
            elif raw2[i:i+1] == b'}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        if end > start + 50:
            try:
                json_str = raw2[start:end].decode('utf-8', errors='replace')
                obj = json.loads(json_str)
                if isinstance(obj, dict) and obj.get('id') and obj.get('name'):
                    cid = obj['id']
                    if cid not in found_candidates or len(json_str) > len(json.dumps(found_candidates[cid])):
                        found_candidates[cid] = obj
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
    
    idx = pos + 1

print(f"Total unique candidates from both WALs: {len(found_candidates)}")

if found_candidates:
    # Save
    data = {"candidates": list(found_candidates.values()), "source": "WAL_recovery"}
    with open('/tmp/wal_recovered_all.json', 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Summary
    july = [c for c in found_candidates.values() if '2026-07' in (c.get('date', '') or '')]
    pavan = [c for c in found_candidates.values() if 'pavan' in (c.get('reference', '') or '').lower()]
    
    print(f"\\n📊 Summary:")
    print(f"  Total recovered: {len(found_candidates)}")
    print(f"  July 2026: {len(july)}")
    print(f"  Referrer One: {len(pavan)}")
    
    print(f"\\nAll recovered candidates:")
    for cand in sorted(found_candidates.values(), key=lambda c: c.get('date', ''), reverse=True)[:30]:
        print(f"  {cand.get('name', 'N/A'):25} | date={cand.get('date', ''):12} | ref={cand.get('reference', '')}")
    
    print(f"\\n✅ Saved to /tmp/wal_recovered_all.json")
else:
    print("\\n❌ No candidates found in WAL files")
PYEOF
""", timeout=180)

result = stdout.read().decode()
print(result)

# If we found data, restore it
if 'wal_recovered_all.json' in result and 'Total recovered: 0' not in result:
    print("\n" + "="*70)
    print("RESTORING RECOVERED DATA TO POSTGRES")
    print("="*70)
    
    _, stdout3, _ = c.exec_command("""
cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 << 'PYEOF'
import sys, os, json
sys.path.insert(0, '/opt/telegramforward')
from pathlib import Path
env_file = Path('.env')
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

# Load recovered data
with open('/tmp/wal_recovered_all.json', 'r') as f:
    recovered = json.load(f)

recovered_cands = recovered.get('candidates', [])
print(f"Recovered candidates: {len(recovered_cands)}")

# Load current Postgres data
from features import candidate_store
candidate_store._load_cache = None
current = candidate_store._load(force=True)
current_cands = current.get('candidates', [])
current_ids = {c.get('id') for c in current_cands}

print(f"Current in Postgres: {len(current_cands)}")

# Merge: add recovered candidates that aren't already in Postgres
new_cands = [c for c in recovered_cands if c.get('id') not in current_ids]
print(f"New candidates to add: {len(new_cands)}")

if new_cands:
    merged = current_cands + new_cands
    current['candidates'] = merged
    
    from core.db.candidates_pg import pg_save
    pg_save(current)
    
    # Clear cache
    candidate_store._load_cache = None
    candidate_store._load_cache_at = 0.0
    
    # Verify
    fresh = candidate_store._load(force=True)
    print(f"\\n✅ After merge: {len(fresh.get('candidates', []))} total candidates")
else:
    print("No new candidates to add (all already in DB)")
PYEOF
""", timeout=60)
    print(stdout3.read().decode())

c.close()
