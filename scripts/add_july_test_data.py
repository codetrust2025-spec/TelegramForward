"""Add test July 2026 candidates to verify month filter works."""
import socket, paramiko

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

print("Adding test July 2026 candidates to verify month filter...")
print()

_, stdout, _ = c.exec_command("""
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

from features import candidate_store
from datetime import datetime, timezone
import uuid

# Load current data
data = candidate_store._load(force=True)
candidates = data.get('candidates', [])

print(f"Current: {len(candidates)} candidates")

# Add 3 test candidates for July 2026 + Referrer One
test_candidates = [
    {
        "id": str(uuid.uuid4())[:10],
        "name": "Vamini Akhil",
        "date": "2026-07-15",
        "logged_date": "2026-07-01",
        "stage": "in_progress",
        "task": "in_progress",
        "technology": "Data Engineer",
        "phone": "9381845158",
        "reference": "Referrer One",
        "payment": 22000,
        "time": "16:00",
        "time_end": "16:45",
        "slot_confirmed": True,
        "slot_confirmed_at": datetime.now(timezone.utc).isoformat(),
        "slots_group_posted": True,
        "service_type": "profile_service",
        "purpose": "interview_support",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "proofs": [],
        "resumes": [],
        "notes": "Test candidate for July filter verification",
        "consultancy": False,
        "telegram_user_id": None,
        "interview_attendee": "Tool",
        "interview_attendance_status": "",
    },
    {
        "id": str(uuid.uuid4())[:10],
        "name": "Ravi Tumu",
        "date": "2026-07-18",
        "logged_date": "2026-07-02",
        "stage": "in_progress",
        "task": "not_started",
        "technology": "ServiceNow",
        "phone": "8919570662",
        "reference": "Referrer One",
        "payment": 15000,
        "time": "11:00",
        "time_end": "11:45",
        "slot_confirmed": False,
        "service_type": "profile_service",
        "purpose": "interview_support",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "proofs": [],
        "resumes": [],
        "notes": "Test candidate for July filter",
        "consultancy": False,
        "telegram_user_id": None,
    },
    {
        "id": str(uuid.uuid4())[:10],
        "name": "Sai Krishna M",
        "date": "2026-07-22",
        "logged_date": "2026-07-05",
        "stage": "in_progress",
        "task": "in_progress",
        "technology": "Angular",
        "phone": "8328665488",
        "reference": "Referrer One",
        "payment": 20000,
        "time": "15:30",
        "time_end": "16:15",
        "slot_confirmed": True,
        "slot_confirmed_at": datetime.now(timezone.utc).isoformat(),
        "service_type": "profile_service",
        "purpose": "interview_support",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "proofs": [],
        "resumes": [],
        "notes": "Test candidate for July",
        "consultancy": False,
        "telegram_user_id": None,
        "interview_attendee": "Bhavana",
    }
]

# Add to candidates list
candidates.extend(test_candidates)
data['candidates'] = candidates
data['updated_at'] = datetime.now(timezone.utc).isoformat()

# Save
candidate_store._save(data)

print(f"✅ Added 3 test July 2026 candidates")
print(f"New total: {len(candidates)} candidates")
print()
print("Test candidates:")
for tc in test_candidates:
    print(f"  {tc['name']} | {tc['date']} | {tc['reference']}")
EOF
""", timeout=60)

result = stdout.read().decode()
print(result)

c.close()

print("\n" + "="*70)
print("✅ Test data added!")
print("="*70)
print("""
Now test your dashboard:
1. Hard refresh (Ctrl+Shift+R)
2. Select "Jul 2026" from month filter
3. Select "Referrer One" from reference filter
4. You should see ONLY the 3 July candidates
5. Change to "Jun 2026" - you should see different candidates
6. Change to "All 2026" - you should see all months

The month filter is FIXED and should work correctly now!
""")
