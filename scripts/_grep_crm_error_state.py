import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

needle = "Leads today"
idx = t.find(needle)
# walk backward for useState error
chunk = t[max(0, idx - 8000) : idx + 3000]

for kw in ["error", "Error", "crm-", "inbox-", "Re(", "setErr", "message"]:
    pass

# find red error display pattern
for s in ['className:"crm', 'className:"inbox', "crm-stats", "crm-inbox"]:
    i = t.find(s)
    if i >= 0:
        print(s, "at", i)

# broader: inbox page component with stats
i = t.find("Blocked:")
if i < 0:
    i = t.find("Replied:")
print("stats area", i)
print(t[i - 1500 : i + 800])
