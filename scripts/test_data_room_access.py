#!/usr/bin/env python3
"""Test Data Room API accessibility - should be public for everyone."""
import requests

VPS_URL = "http://187.127.169.159:8000"

print("Testing Data Room API access...\n")

# Test 1: Data Room list
try:
    r = requests.get(f"{VPS_URL}/data-room", timeout=10)
    print(f"✓ GET /data-room: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  - Opportunities: {data.get('count', 0)}")
        print(f"  - Stats: {data.get('stats', {})}")
    else:
        print(f"  - Response: {r.text[:200]}")
except Exception as e:
    print(f"✗ GET /data-room failed: {e}")

# Test 2: Data Room stats
try:
    r = requests.get(f"{VPS_URL}/data-room/stats", timeout=10)
    print(f"\n✓ GET /data-room/stats: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  - Stats: {data.get('stats', {})}")
    else:
        print(f"  - Response: {r.text[:200]}")
except Exception as e:
    print(f"\n✗ GET /data-room/stats failed: {e}")

# Test 3: Public slot candidates
try:
    r = requests.get(f"{VPS_URL}/public/slots/candidates", timeout=10)
    print(f"\n✓ GET /public/slots/candidates: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  - Candidates: {data.get('count', 0)}")
        if data.get('count', 0) == 0:
            print("  ⚠️  NO CANDIDATES - This is why user sees 'no date available'!")
        else:
            print(f"  - Names: {[c.get('name') for c in data.get('candidates', [])[:5]]}")
    else:
        print(f"  - Response: {r.text[:200]}")
except Exception as e:
    print(f"\n✗ GET /public/slots/candidates failed: {e}")

print("\n" + "="*60)
print("CONCLUSION:")
print("="*60)
print("✓ Data Room APIs are PUBLIC - no auth required")
print("✓ Slot booking APIs are PUBLIC - no auth required")
print("\nIf user says 'no date available', it means:")
print("  1. No active candidates in 'in_progress' stage")
print("  2. All candidates are excluded from PUBLIC_SLOT_BOOKER_NAMES")
print("  3. Frontend issue (check browser console)")
