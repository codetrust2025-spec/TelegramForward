#!/usr/bin/env python3
"""Final functional testing — verify all endpoints and flows work."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

def run(cmd, label=""):
    if label:
        print(f"\n{'─'*50}\n  {label}\n{'─'*50}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    result = out or err or "(no output)"
    print(result[:500])
    return out

# 1. Site loads
run("curl -s -o /dev/null -w '%{http_code}' https://teleautomation.online", "1. Site loads (HTTPS)")
run("curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/public/slots/candidates", "2. /submit-slot candidates API")
run("curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/public/slots/booked", "3. Booked slots API")

# 4. AI endpoint responds (without file = 422, which is correct)
run("curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/public/slots/extract-invite-ai", "4. AI endpoint registered (422=correct)")

# 5. Test AI extraction with a dummy image (should fall back to OCR since Ollama not installed)
run("""curl -s -X POST http://localhost:8000/public/slots/extract-invite-ai \
  -F 'file=@/opt/telegramforward.old/static/favicon.svg' \
  2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('Status:', data.get('status'))
print('Success:', data.get('success'))
print('Source:', data.get('extraction_source') or data.get('data',{}).get('extraction_source',''))
warnings = data.get('data',{}).get('warnings',[])
if warnings:
    print('Warnings:', warnings[0][:80])
print('Manual required:', data.get('data',{}).get('manual_fields_required'))
" """, "5. AI fallback test (Ollama not running)")

# 6. Existing book endpoint still works
run("curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/public/slots/book", "6. Book endpoint (422=needs fields)")

# 7. Payment proof endpoint still works
run("curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/public/slots/payment-proof", "7. Payment proof endpoint (422=needs fields)")

# 8. Parse screenshot endpoint still works
run("curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/public/slots/parse-screenshot", "8. Parse screenshot endpoint (422=needs file)")

# 9. Check PM2 logs for any errors in last minute
run("pm2 logs telegram-backend --lines 10 --nostream 2>&1 | grep -i 'error\\|traceback\\|exception' | head -5 || echo 'No errors in recent logs'", "9. Recent error logs")

# 10. Check confirmed slots exist
run("""curl -s http://localhost:8000/public/slots/booked | python3 -c "
import sys, json
data = json.load(sys.stdin)
slots = data.get('slots', [])
print(f'Confirmed slots: {len(slots)}')
if slots:
    s = slots[0]
    print(f'  Latest: {s.get(\"name\")} on {s.get(\"date\")} at {s.get(\"time\")}')
" """, "10. Confirmed slots data")

# 11. Nginx serving static files
run("curl -s -o /dev/null -w '%{http_code}' https://teleautomation.online/assets/", "11. Static assets accessible")

# 12. Check time format in booked slots (should be HH:MM 24h internally, displayed as 12h on frontend)
run("""curl -s http://localhost:8000/public/slots/booked | python3 -c "
import sys, json
data = json.load(sys.stdin)
slots = data.get('slots', [])[:3]
for s in slots:
    print(f'  {s.get(\"name\")}: time={s.get(\"time\")} time_end={s.get(\"time_end\")}')
" """, "12. Time format in API response (backend stores HH:MM)")

ssh.close()
print("\n\n" + "="*50)
print("  FINAL TEST SUMMARY")
print("="*50)
print("""
✓ Tests complete. Results above.

Key expectations:
- HTTP 200 = endpoint works
- HTTP 422 = endpoint registered, needs required fields
- AI fallback = extraction_source should be 'ocr_fallback' or 'failed'
- No errors in logs = backend stable
- Confirmed slots exist = booking flow works
- Times stored as HH:MM = frontend converts to 12h display
""")
