"""Emergency: Find any Postgres backups."""
import socket, paramiko

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='8897870998s@SS', sock=sock)

print("🚨 EMERGENCY DATA RECOVERY ATTEMPT")
print("="*70)

print("\n1. Searching for Postgres backup dumps...")
_, stdout, _ = c.exec_command("""
find / -name '*.sql' -o -name '*.dump' -o -name '*postgres*.backup' 2>/dev/null | grep -v '/proc\\|/sys' | head -30
""", timeout=60)
print(stdout.read().decode() or "No SQL dumps found")

print("\n2. Checking if Postgres has WAL archives...")
_, stdout2, _ = c.exec_command("""
sudo -u postgres psql -c "SHOW archive_command;" 2>/dev/null || echo "No archive command"
sudo -u postgres psql -c "SHOW wal_level;" 2>/dev/null || echo "No WAL info"
""", timeout=30)
print(stdout2.read().decode())

print("\n3. Checking for automated backup scripts/cron jobs...")
_, stdout3, _ = c.exec_command("""
crontab -l 2>/dev/null | grep -i backup
find /etc/cron* -type f -exec grep -l 'pg_dump\\|backup' {} \\; 2>/dev/null
""", timeout=30)
cron_result = stdout3.read().decode()
print(cron_result if cron_result.strip() else "No automated backups found")

print("\n4. Check for Point-in-Time Recovery (PITR) possibility...")
_, stdout4, _ = c.exec_command("""
sudo -u postgres psql teleautomation -c "SELECT pg_current_wal_lsn();" 2>/dev/null || echo "No PITR"
""", timeout=30)
print(stdout4.read().decode())

print("\n5. Check systemd journal for recent database operations...")
_, stdout5, _ = c.exec_command("""
journalctl -u postgresql --since "2 hours ago" --no-pager 2>/dev/null | tail -20 || echo "No journal"
""", timeout=30)
journal = stdout5.read().decode()
if journal and 'No journal' not in journal:
    print(journal)
else:
    print("No recent Postgres logs")

c.close()

print("\n" + "="*70)
print("RECOVERY OPTIONS:")
print("="*70)
print("""
If no backups found above:
  ❌ The evening interview slots data is permanently lost
  ❌ I apologize - this was my mistake syncing wrong data
  
To prevent this in future:
  ✅ Set up automated Postgres backups (pg_dump daily)
  ✅ Keep backups before any data migration
  ✅ Test on staging environment first

You'll need to re-enter the lost interview slots manually.
""")
