import re
import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

# Find CRM / Inbox component area
idx = t.find("CRM Inbox")
if idx < 0:
    idx = t.find("Leads today")
print("anchor idx", idx)

chunk = t[idx : idx + 12000] if idx >= 0 else t[:12000]

fetches = re.findall(r"fetch\([^)]{10,200}\)", chunk)
print(f"fetches near inbox header: {len(fetches)}")
for f in fetches[:25]:
    print(" ", f[:160])

# Global: fetch then .json() without ok check near inbox?sync
for m in re.finditer(r"fetch\(`\$\{ve\}/[^`]+`[^;]{0,300}", t):
    s = m.group(0)
    if "inbox" in s or "crm" in s or "alerts" in s or "assessment" in s:
        if ".json()" in s or "json()" in s:
            print("\n---")
            print(s[:350])
