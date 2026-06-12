#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
# extract try/except structure with python
script = '''
import ast, pathlib
src = pathlib.Path("/opt/telegramforward.old/workers/account_worker.py").read_text(encoding="utf-8")
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.AsyncFunctionDef) and node.name == "_execute_cycle":
        # print line range
        print(f"_execute_cycle lines {node.lineno}-{node.end_lineno}")
        for child in ast.walk(node):
            if isinstance(child, (ast.Try, ast.ExceptHandler)):
                print(f"  Try at {getattr(child, 'lineno', '?')}: {type(child).__name__}")
        break
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{script}\nPY", timeout=30)
print(stdout.read().decode())
_, stdout, _ = c.exec_command("sed -n '2045,2075p' /opt/telegramforward.old/workers/account_worker.py | cat -A", timeout=30)
print("=== raw lines 2045-2075 ===")
print(stdout.read().decode())
c.close()
