import socket, paramiko
sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='8897870998s@SS', sock=sock)
_, stdout, _ = c.exec_command("grep -B2 -A15 'def list_candidates' /opt/telegramforward/features/candidate_store.py | head -30", timeout=30)
print("list_candidates function:")
print(stdout.read().decode())
c.close()
