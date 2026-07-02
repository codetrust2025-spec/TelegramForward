"""Find where Vamini Akhil exists on the VPS."""
import socket, paramiko, json

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

print("=== Searching for all candidates.json files ===")
_, stdout, _ = c.exec_command("find /opt/telegramforward* -name 'candidates.json' -type f 2>/dev/null", timeout=30)
files = stdout.read().decode().strip().split('\n')
for f in files:
    if f:
        print(f"  {f}")

print("\n=== Checking main candidates.json for Vamini Akhil ===")
_, stdout2, _ = c.exec_command("""python3 << 'EOF'
import json
data = json.load(open('/opt/telegramforward/data/candidates.json'))
candidates = data.get('candidates', [])

vamini = [c for c in candidates if 'vamini' in (c.get('name', '') or '').lower()]
ravi = [c for c in candidates if 'ravi' in (c.get('name', '') or '').lower() and 'tumu' in (c.get('name', '') or '').lower()]

print(f"Vamini Akhil entries: {len(vamini)}")
for c in vamini:
    print(f"  {c.get('name')} | date={c.get('date')} | id={c.get('id')} | ref={c.get('reference')}")

print(f"\\nRavi Tumu entries: {len(ravi)}")
for c in ravi:
    print(f"  {c.get('name')} | date={c.get('date')} | id={c.get('id')} | ref={c.get('reference')}")

# Check all July 2026 Referrer One entries
july_pavan = [c for c in candidates 
              if 'pavan' in (c.get('reference', '') or '').lower() 
              and c.get('date', '').startswith('2026-07')]

print(f"\\nJuly 2026 + Referrer One entries: {len(july_pavan)}")
for c in july_pavan:
    print(f"  {c.get('name')} | date={c.get('date')} | id={c.get('id')}")
EOF
""", timeout=30)
print(stdout2.read().decode())

print("\n=== Checking when file was last modified ===")
_, stdout3, _ = c.exec_command("ls -lh /opt/telegramforward/data/candidates.json", timeout=30)
print(stdout3.read().decode())

print("\n=== Checking if backend is using a different path ===")
_, stdout4, _ = c.exec_command("grep 'DATA_DIR\\|candidates.json' /opt/telegramforward/core/config.py | head -10", timeout=30)
config_data = stdout4.read().decode()
if config_data:
    print(config_data)
else:
    print("No DATA_DIR config found")

c.close()
