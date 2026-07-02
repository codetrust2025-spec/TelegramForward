"""Try to recover data from WAL files using pg_waldump."""
import socket, paramiko

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

print("="*70)
print("WAL RECOVERY ATTEMPT")
print("="*70)

# Try pg_waldump to extract records
print("\n1. Using pg_waldump to check WAL contents...")
_, stdout, _ = c.exec_command("""
# Find pg_waldump
which pg_waldump 2>/dev/null || find /usr -name 'pg_waldump' 2>/dev/null

# Get the OID of candidates_store table
sudo -u postgres psql teleautomation -c "SELECT oid FROM pg_class WHERE relname = 'candidates_store';" 2>/dev/null
""", timeout=30)
print(stdout.read().decode())

# Try the older WAL file (7B from 06:27 - before my changes)
print("\n2. Checking older WAL file (7B from 06:27 today - BEFORE my changes)...")
_, stdout2, _ = c.exec_command("""
WAL_DIR=/var/lib/postgresql/16/main/pg_wal

# Try pg_waldump on the older WAL file
sudo -u postgres /usr/lib/postgresql/16/bin/pg_waldump $WAL_DIR/00000001000000000000007B 2>/dev/null | head -20 || echo "pg_waldump failed"
""", timeout=30)
wal_output = stdout2.read().decode()
print(wal_output[:500] if wal_output else "No output")

# Alternative: try to read the WAL file directly for JSON strings
print("\n3. Searching WAL files for candidate JSON data...")
_, stdout3, _ = c.exec_command("""
WAL_DIR=/var/lib/postgresql/16/main/pg_wal

# Search the WAL binary files for JSON candidate data
# The older file (7B) should have data from before the overwrite
echo "Searching WAL file 7B (from 06:27 - should have morning data)..."
strings $WAL_DIR/00000001000000000000007B | grep -o '"name": "[^"]*"' | sort -u | head -20

echo ""
echo "Looking for Vamini..."
strings $WAL_DIR/00000001000000000000007B | grep -i "vamini" | head -5

echo ""
echo "Looking for Ravi Pavan / Ravi Tumu..."
strings $WAL_DIR/00000001000000000000007B | grep -i "ravi" | grep -iv "ravinder" | head -5

echo ""
echo "Looking for July 2026 dates..."
strings $WAL_DIR/00000001000000000000007B | grep "2026-07-0" | head -5

echo ""
echo "=== Now checking WAL file 7A (current, from 14:33) ==="
strings $WAL_DIR/00000001000000000000007A | grep -o '"name": "[^"]*"' | sort -u | head -30

echo ""
echo "Looking for Vamini in 7A..."
strings $WAL_DIR/00000001000000000000007A | grep -i "vamini" | head -5

echo ""
echo "Looking for Ravi in 7A..."
strings $WAL_DIR/00000001000000000000007A | grep -i "ravi" | grep -iv "ravinder" | head -5
""", timeout=60)
print(stdout3.read().decode())

c.close()
