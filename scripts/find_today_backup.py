"""Find today's automated backup - cron runs at 2:15 AM daily."""
import socket, paramiko

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='8897870998s@SS', sock=sock)

print("="*70)
print("Looking for today's automated backup (2:15 AM daily)")
print("="*70)

# Check backup directory for .sql.gz files
print("\n1. Checking /opt/telegramforward/backups for .sql.gz files...")
_, stdout, _ = c.exec_command("ls -lth /opt/telegramforward/backups/teleautomation_*.sql.gz 2>/dev/null | head -10", timeout=30)
gz_files = stdout.read().decode()
print(gz_files if gz_files else "No .sql.gz files found")

# Also check logs
print("\n2. Checking backup log...")
_, stdout2, _ = c.exec_command("tail -20 /opt/telegramforward/logs/pg_backup.log 2>/dev/null || tail -20 /var/log/teleautomation-backup.log 2>/dev/null || echo 'No backup log found'", timeout=30)
print(stdout2.read().decode())

# Check if backup ran today
print("\n3. Finding ALL backup files from today or yesterday...")
_, stdout3, _ = c.exec_command("""
find /opt/telegramforward/backups -type f -mtime -1 -ls 2>/dev/null
find /opt/telegramforward/backups -name '*20260702*' -o -name '*20260701*' 2>/dev/null
""", timeout=30)
print(stdout3.read().decode())

# Try to decompress and restore the latest backup
print("\n4. Trying to find and decompress latest backup...")
_, stdout4, _ = c.exec_command("""
LATEST=$(ls -t /opt/telegramforward/backups/teleautomation_*.sql.gz 2>/dev/null | head -1)
if [ -n "$LATEST" ]; then
    echo "Latest backup: $LATEST"
    ls -lh "$LATEST"
    
    # Decompress to temp
    gunzip -c "$LATEST" > /tmp/latest_backup.sql
    
    echo ""
    echo "Checking for candidates data in backup..."
    grep -c "candidates_store" /tmp/latest_backup.sql || echo "No candidates_store found"
    
    echo ""
    echo "Looking for July 2026 data..."
    grep "2026-07" /tmp/latest_backup.sql | head -3
    
    echo ""
    echo "Looking for Vamini..."
    grep -i "vamini" /tmp/latest_backup.sql | head -3
    
    echo ""
    echo "Looking for Ravi Tumu / Ravi Pavan..."
    grep -i "ravi" /tmp/latest_backup.sql | grep -i "tumu\|pavan" | head -3
else
    echo "No .sql.gz backups found!"
fi
""", timeout=60)
print(stdout4.read().decode())

c.close()
