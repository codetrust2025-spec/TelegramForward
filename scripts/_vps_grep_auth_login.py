import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -rn 'auth/login\\|auth/status\\|verify.admin' /opt/telegramforward.old --include='*.py' 2>/dev/null | grep -v venv"
)
print(o.read().decode() or "(none)")
# Try curl on server
_, o, _ = c.exec_command(
    'curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/auth/verify-admin -H "Content-Type: application/json" -d \'{"password":"734720077743"}\''
)
print("POST verify-admin:", o.read().decode())
_, o, _ = c.exec_command(
    'curl -s -o /dev/null -w "%{http_code}" -X GET http://127.0.0.1:8000/auth/verify-admin'
)
print("GET verify-admin:", o.read().decode())
_, o, _ = c.exec_command(
    'curl -s -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" -d \'{"username":"admin","password":"734720077743"}\''
)
print("POST login:", o.read().decode()[:500])
c.close()
