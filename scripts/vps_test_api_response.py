#!/usr/bin/env python3
"""Test what the API returns for mail monitoring notifications."""
import paramiko
import json

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = 'REMOVED_VPS_PASSWORD'

def main():
    print("=== Testing API Response ===\n")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
    
    # Test the mail notifications API with authentication
    # Note: This endpoint requires auth, so we'll test from VPS localhost
    stdin, stdout, stderr = client.exec_command("""
curl -s 'http://localhost:8000/api/mail-monitoring/notifications?is_reviewed=false&limit=50' \\
  -H 'Cookie: session=test' \\
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
notifications = data.get('notifications', [])
print(f'Total notifications returned: {len(notifications)}')
print()
for i, notif in enumerate(notifications[:15], 1):
    status = notif.get('detected_status', 'Unknown')
    subject = notif.get('email_subject', '')[:60]
    confidence = notif.get('confidence', 0)
    print(f'{i}. [{status}] {confidence:.0%} - {subject}')
" 2>&1 || echo "API call failed"
""", timeout=60)
    
    stdout.channel.recv_exit_status()
    output = stdout.read().decode()
    print(output)
    
    client.close()
    
    print("\n=== Summary ===")
    print("If the API returns 3 items, the backend is correct.")
    print("If the dashboard shows more, it's a caching issue.")
    print("\nTo fix:")
    print("1. Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)")
    print("2. Clear browser cache for the site")
    print("3. Or add cache-busting param: ?v=" + str(__import__('time').time())[:10])

if __name__ == '__main__':
    main()
