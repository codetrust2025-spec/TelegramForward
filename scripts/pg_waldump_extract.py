"""Use pg_waldump + strings to extract candidate data from WAL."""
import socket, paramiko, json, re

sock = socket.create_connection(('187.127.169.159', 22), timeout=60)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

print("="*70)
print("EXTRACTING CANDIDATE DATA USING strings + PATTERN MATCHING")
print("="*70)

# From the earlier strings output, we saw data in this format:
# <column_names_header>  <id>  <date>  <name>  <task>  <time> ...
# The columns appear as: id date name task time notes phone stage ...
# followed by the actual values

# Let's extract ALL rows from both WAL files
_, stdout, _ = c.exec_command("""
WAL_DIR=/var/lib/postgresql/16/main/pg_wal

# Extract all strings that contain candidate-like patterns from BOTH WAL files
# Focus on strings that have a 10-char hex ID followed by a date
{
    strings $WAL_DIR/00000001000000000000007B
    strings $WAL_DIR/00000001000000000000007A
} | grep -E '^[0-9a-f]{10}2026-' > /tmp/wal_candidate_rows.txt

echo "Lines extracted:"
wc -l /tmp/wal_candidate_rows.txt

echo ""
echo "Unique candidate IDs:"
cat /tmp/wal_candidate_rows.txt | grep -oP '^[0-9a-f]{10}' | sort -u | wc -l

echo ""
echo "Sample rows:"
head -5 /tmp/wal_candidate_rows.txt | cut -c1-200
""", timeout=120)
print(stdout.read().decode())

# Now parse the extracted data
print("\n" + "="*70)
print("Parsing extracted rows...")
print("="*70)

_, stdout2, _ = c.exec_command("""
cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 << 'PYEOF'
import re, json
from collections import defaultdict

# Read extracted rows
with open('/tmp/wal_candidate_rows.txt', 'r', errors='replace') as f:
    lines = f.readlines()

print(f"Total lines to parse: {len(lines)}")

# The WAL stores rows in a specific format for the candidates_store table
# Based on what we saw, the format seems to be all column values concatenated:
# <id><date><name><task><time><notes><phone><stage>...
# But they're not tab-separated in the strings output - they're concatenated

# Let's try a different approach: look for known patterns
# ID is always 10 hex chars, date is YYYY-MM-DD

candidates = {}

for line in lines:
    line = line.strip()
    if not line:
        continue
    
    # Try to extract: first 10 chars = id, next 10 chars = date (YYYY-MM-DD)
    if len(line) < 20:
        continue
    
    cid = line[:10]
    # Check if it starts with a valid hex ID
    if not re.match(r'^[0-9a-f]{10}$', cid):
        continue
    
    date_part = line[10:20]
    # Check if date is valid YYYY-MM-DD
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_part):
        continue
    
    # The rest contains name and other fields concatenated
    rest = line[20:]
    
    # Try to extract name - it's the first text after the date
    # followed by task status (in_progress, completed, not_started, etc.)
    name_match = re.match(r'^([A-Za-z][A-Za-z .]+?)(?:in_progress|completed|not_started|decision_need|fail|dropped)', rest)
    if name_match:
        name = name_match.group(1).strip()
    else:
        # Try less strict: get text up to first known field value
        name_match2 = re.match(r'^([^\d]{2,40})', rest)
        name = name_match2.group(1).strip() if name_match2 else ''
    
    if not name or len(name) < 2:
        continue
    
    # Extract phone (10 digits)
    phone_match = re.search(r'(\d{10})', rest)
    phone = phone_match.group(1) if phone_match else ''
    
    # Extract reference - look for known handler names
    reference = ''
    for ref_name in ['Referrer One', 'PAVAN KALYAN', 'Thrilok', 'Venugopal', 'Ravinder', 'Charan']:
        if ref_name in rest:
            reference = ref_name
            break
    
    # Extract technology
    tech = ''
    for tech_name in ['Data Engineer', 'ServiceNow', 'Angular', 'React JS', 'SAP BASIS', 
                       'Power BI', 'Data Analyst', 'AWS', 'Python', 'Java', 'DevOps',
                       'Salesforce', '.NET', 'Tableau', 'SQL']:
        if tech_name in rest:
            tech = tech_name
            break
    
    # Extract payment amount (5-6 digit number)
    payment_match = re.search(r'(\d{5,6})', rest)
    payment = int(payment_match.group(1)) if payment_match else 0
    
    # Build candidate record
    candidate = {
        "id": cid,
        "date": date_part,
        "name": name,
        "phone": phone,
        "reference": reference,
        "technology": tech,
        "payment": payment,
        "stage": "in_progress",
        "task": "in_progress",
        "service_type": "profile_service",
        "purpose": "interview_support",
    }
    
    # Keep longest/most complete version per ID
    if cid not in candidates or len(rest) > len(json.dumps(candidates[cid])):
        candidates[cid] = candidate

print(f"\\nParsed {len(candidates)} unique candidates")

# Show all
july = [c for c in candidates.values() if '2026-07' in c.get('date', '')]
june_after_17 = [c for c in candidates.values() if c.get('date', '') > '2026-06-17']
pavan = [c for c in candidates.values() if 'pavan' in (c.get('reference', '') or '').lower()]

print(f"  July 2026: {len(july)}")
print(f"  After June 17: {len(june_after_17)}")
print(f"  Referrer One: {len(pavan)}")

print(f"\\nAll candidates found (sorted by date):")
for cand in sorted(candidates.values(), key=lambda c: c.get('date', ''), reverse=True):
    print(f"  {cand['id']} | {cand.get('date'):12} | {cand.get('name'):25} | {cand.get('reference'):15} | {cand.get('phone')}")

# Save
with open('/tmp/wal_parsed_candidates.json', 'w') as f:
    json.dump({"candidates": list(candidates.values())}, f, indent=2)

print(f"\\n✅ Saved to /tmp/wal_parsed_candidates.json")
PYEOF
""", timeout=120)
print(stdout2.read().decode())

c.close()
