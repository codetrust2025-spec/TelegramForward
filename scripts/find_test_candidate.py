#!/usr/bin/env python3
"""Find candidates with no payment block for testing booking."""
import paramiko, json

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

cmd = "curl -s http://localhost:8000/public/slots/candidates"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
raw = stdout.read().decode()
data = json.loads(raw)
candidates = data.get("candidates", [])

print(f"Total candidates in slot picker: {len(candidates)}\n")
print("Candidates with NO payment block (can book immediately):")
for c in candidates:
    if not c.get("needs_payment_proof"):
        print(f'  ✓ {c["name"]} (balance: ₹{c.get("balance_due",0):,})')

print("\nCandidates WITH payment block (need proof first):")
for c in candidates:
    if c.get("needs_payment_proof"):
        print(f'  ✗ {c["name"]} (due: ₹{c.get("balance_due",0):,})')

ssh.close()
