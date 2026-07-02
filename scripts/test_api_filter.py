"""Test the API filtering directly."""
import socket, paramiko, json, urllib.parse

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

# Get auth token first
print("=== Getting auth token ===")
_, stdout, _ = c.exec_command("""curl -s -X POST http://127.0.0.1:8000/login \
-H 'Content-Type: application/json' \
-d '{"username":"codetrust2025@gmail.com","password":"8897870998"}' """, timeout=30)

login_data = stdout.read().decode()
try:
    token_json = json.loads(login_data)
    token = token_json.get('token')
    if not token:
        print(f"❌ No token: {login_data[:200]}")
        c.close()
        exit(1)
    print(f"✅ Got token")
except:
    print(f"❌ Login failed: {login_data[:200]}")
    c.close()
    exit(1)

# Test 1: All Referrer One
print("\n=== Test 1: All Referrer One (no month filter) ===")
_, stdout2, _ = c.exec_command(f"""curl -s -H 'Authorization: Bearer {token}' \
'http://127.0.0.1:8000/candidates?reference=Pavan+Kalyan' """, timeout=30)
data1 = json.loads(stdout2.read().decode())
print(f"Count: {data1.get('count', 0)}")
for r in data1.get('candidates', [])[:5]:
    print(f"  {r.get('name'):25} | date={r.get('date'):12}")

# Test 2: July + Referrer One
print("\n=== Test 2: July 2026 + Referrer One ===")
_, stdout3, _ = c.exec_command(f"""curl -s -H 'Authorization: Bearer {token}' \
'http://127.0.0.1:8000/candidates?month=2026-07&reference=Pavan+Kalyan' """, timeout=30)
data2 = json.loads(stdout3.read().decode())
print(f"Count: {data2.get('count', 0)}")

if data2.get('count', 0) > 0:
    print("Returned candidates:")
    for r in data2.get('candidates', []):
        date = r.get('date', '')
        month_match = '✅' if '2026-07' in date else '❌'
        print(f"  {month_match} {r.get('name'):25} | date={date:12}")
else:
    print("❌ NO CANDIDATES RETURNED!")
    print("\nThis means there are NO July 2026 entries for Referrer One in the backend data.")

# Test 3: Just July (all references)
print("\n=== Test 3: July 2026 (all references) ===")
_, stdout4, _ = c.exec_command(f"""curl -s -H 'Authorization: Bearer {token}' \
'http://127.0.0.1:8000/candidates?month=2026-07' """, timeout=30)
data3 = json.loads(stdout4.read().decode())
print(f"Count: {data3.get('count', 0)}")
print("First 10:")
for r in data3.get('candidates', [])[:10]:
    print(f"  {r.get('name'):25} | date={r.get('date'):12} | ref={r.get('reference', '')}")

c.close()

print("\n" + "="*70)
print("CONCLUSION:")
print("If Test 2 returns 0 candidates, your backend JSON has NO July Referrer One entries.")
print("The dashboard is probably showing CACHED data from your browser.")
print("="*70)
