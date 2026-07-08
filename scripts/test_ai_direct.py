#!/usr/bin/env python3
"""Test AI extraction endpoint directly with a real proof image."""
import paramiko, json

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

# Find a real image to test with
cmd = """
# First check tunnel is alive
echo "Tunnel check:"
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:11434/api/tags

echo ""
echo "---"

# Find a proof image to test
TESTIMG=$(find /opt/telegramforward.old/data/candidates_proofs -name "*.jpg" -o -name "*.png" | head -1)
echo "Test image: $TESTIMG"

if [ -n "$TESTIMG" ]; then
    echo "Calling AI endpoint..."
    RESULT=$(curl -s --max-time 120 -X POST http://localhost:8000/public/slots/extract-invite-ai -F "file=@$TESTIMG")
    echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('Status:', data.get('status'))
print('Success:', data.get('success'))
print('Source:', data.get('extraction_source', data.get('data',{}).get('extraction_source','')))
d = data.get('data', {})
print('Model:', d.get('primary_model',''))
print('Confidence:', d.get('confidence_score',''))
print('Date:', d.get('interview_date',''))
print('Time:', d.get('start_time',''))
warnings = d.get('warnings',[])
if warnings:
    print('Warnings:', warnings[:2])
"
fi
"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=180)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err[:300])

ssh.close()
