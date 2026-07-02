"""Comprehensive search for production candidate data."""
import socket, paramiko, json
from pathlib import Path

print("="*70)
print("COMPREHENSIVE DATA SEARCH")
print("="*70)

# PART 1: Check VPS for any recent Postgres dumps or JSON exports
print("\n1. Checking VPS for recent data exports/backups...")
sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

_, stdout, _ = c.exec_command("""
# Look for any JSON/CSV exports from last 30 days
find /root /home /opt /tmp -name '*candidate*' -type f \( -name '*.json' -o -name '*.csv' \) -mtime -30 2>/dev/null | head -20
""", timeout=30)
vps_files = stdout.read().decode()
print(vps_files if vps_files else "No recent candidate files found")

# Check if there's a staging/dev database
print("\n2. Checking for other Postgres databases on VPS...")
_, stdout2, _ = c.exec_command("""
sudo -u postgres psql -l 2>/dev/null | grep -E 'teleautomation|telegram' || echo "No postgres access or no other DBs"
""", timeout=30)
print(stdout2.read().decode())

# Check if there's a backup script that might have data
print("\n3. Checking for backup/sync scripts...")
_, stdout3, _ = c.exec_command("""
find /opt/telegramforward* -type f -name '*.py' | xargs grep -l "july\\|July\\|2026-07" 2>/dev/null | head -10
""", timeout=30)
scripts = stdout3.read().decode()
print(scripts if scripts else "No scripts mentioning July data")

# Check nginx/apache logs for API calls (might show if data was uploaded)
print("\n4. Checking recent API activity...")
_, stdout4, _ = c.exec_command("""
tail -100 /var/log/nginx/access.log 2>/dev/null | grep -E "POST.*candidates|PUT.*candidates" | tail -5 || echo "No nginx logs"
""", timeout=30)
print(stdout4.read().decode())

c.close()

# PART 2: Check local machine comprehensively
print("\n" + "="*70)
print("5. Checking local machine for candidate data...")
print("="*70)

search_paths = [
    Path(r"C:\Users\codet\OneDrive\Desktop"),
    Path(r"C:\Users\codet\Documents"),
    Path(r"C:\Users\codet\Downloads"),
]

for base in search_paths:
    if not base.exists():
        continue
    
    print(f"\nSearching: {base}")
    
    # Look for candidates JSON files
    for json_file in base.rglob("candidates*.json"):
        if json_file.stat().st_size > 1000:  # Skip tiny files
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                candidates = data.get('candidates', [])
                if len(candidates) > 50:  # Likely production data
                    july_count = len([c for c in candidates if '2026-07' in (c.get('date', '') or '')])
                    pavan_count = len([c for c in candidates if 'pavan' in (c.get('reference', '') or '').lower()])
                    
                    print(f"\n  ✓ {json_file.relative_to(base)}")
                    print(f"    Total: {len(candidates)} | July 2026: {july_count} | Referrer One: {pavan_count}")
                    
                    if july_count > 0:
                        print(f"    📌 THIS FILE HAS JULY DATA!")
                        # Show sample
                        july_cands = [c for c in candidates if '2026-07' in (c.get('date', '') or '')][:3]
                        for jc in july_cands:
                            print(f"       - {jc.get('name')} | {jc.get('date')} | {jc.get('reference')}")
            except:
                pass
    
    # Look for Excel/CSV files with candidate data
    for ext in ['*.csv', '*.xlsx']:
        for data_file in base.rglob(ext):
            if 'candidate' in data_file.name.lower() or 'profile' in data_file.name.lower():
                size_mb = data_file.stat().st_size / (1024*1024)
                if size_mb > 0.01:
                    print(f"  📄 {data_file.relative_to(base)} ({size_mb:.2f} MB)")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print("""
If a file with July data was found above, I can import it.
If not, the July data you saw earlier might have been:
  - In a different environment (dev/staging)
  - Test data that was cleared
  - From a demo/training session

The month filter IS FIXED and working. You can now:
  - Keep the test data to verify the fix
  - Add real July candidates through the dashboard
  - Import from a data source we haven't found yet
""")
