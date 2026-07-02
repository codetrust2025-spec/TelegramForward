import socket, paramiko, time
from pathlib import Path

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='8897870998s@SS', sock=sock)

# Upload the fixed file
local_file = Path(__file__).resolve().parents[1] / "features" / "candidate_store.py"
sftp = c.open_sftp()
sftp.put(str(local_file), '/opt/telegramforward/features/candidate_store.py')
sftp.close()
print("Uploaded fixed candidate_store.py")

# Restart backend
_, stdout, _ = c.exec_command("pkill -9 -f uvicorn", timeout=30)
stdout.read()
time.sleep(5)
_, stdout2, _ = c.exec_command("ps aux | grep uvicorn | grep -v grep", timeout=30)
ps = stdout2.read().decode()
print(f"Backend: {'running' if 'uvicorn' in ps else 'NOT running'}")

c.close()
print("Done. Hard refresh browser.")
