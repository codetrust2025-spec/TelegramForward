import socket, paramiko
sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)
_, stdout, stderr = c.exec_command("""
sudo -u postgres psql teleautomation -t -c "
SELECT payload->>'name', payload->>'date', payload->>'logged_date', payload->>'updated_at'
FROM candidates_store
WHERE payload->>'name' ILIKE '%gangadhar%'
ORDER BY payload->>'date';
"
""", timeout=30)
print("Gangadhar rows:")
print(stdout.read().decode())
_, stdout2, _ = c.exec_command("""
sudo -u postgres psql teleautomation -t -c "
SELECT payload->>'name', payload->>'date', payload->>'logged_date', payload->>'updated_at'
FROM candidates_store
WHERE payload->>'name' ILIKE '%kaleshwar%'
ORDER BY payload->>'date';
"
""", timeout=30)
print("KALESHWAR rows:")
print(stdout2.read().decode())
c.close()
