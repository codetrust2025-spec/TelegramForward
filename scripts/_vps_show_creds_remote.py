import os
import yaml

BASE = "/opt/telegramforward"

print("=== ADMIN (dashboard header login) ===")
for path in [os.path.join(BASE, ".env"), os.path.join(BASE, "data", ".env")]:
    if not os.path.isfile(path):
        continue
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("DASHBOARD_USERNAME="):
                print("username:", s.split("=", 1)[1].strip().strip('"').strip("'"))
            if s.startswith("DASHBOARD_PASSWORD="):
                print("password:", s.split("=", 1)[1].strip().strip('"').strip("'"))

hp = os.path.join(BASE, "config", "dashboard_handlers.yaml")
print()
print("=== HANDLERS ===")
if os.path.isfile(hp):
    with open(hp, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    for row in raw.get("handlers") or []:
        if isinstance(row, dict) and row.get("username"):
            print("---")
            print("username:", row.get("username"))
            print("password:", row.get("password", ""))
            print("reference:", row.get("reference", ""))
else:
    print("(no dashboard_handlers.yaml)")
