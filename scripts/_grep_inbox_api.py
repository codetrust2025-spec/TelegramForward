import re
import urllib.request

t = urllib.request.urlopen("https://teleautomation.online/assets/app-sPW-AjZE.js").read().decode("utf-8", "replace")
# inbox-related paths
paths = set()
for m in re.finditer(r"\$\{[a-zA-Z0-9_]{1,6}\}/(inbox[a-zA-Z0-9_/-]*)", t):
    paths.add("/" + m.group(1))
for m in re.finditer(r'"(/inbox[^"]+)"', t):
    paths.add(m.group(1))
print("inbox paths:")
for p in sorted(paths):
    print(" ", p)

# find fetch near "CRM Inbox" or inbox fast
for needle in ["inbox/fast", "inbox/leads", "inbox/threads", "crm/inbox", "/inbox?"]:
    i = t.find(needle)
    if i >= 0:
        print(f"\n--- {needle} ---")
        print(t[i - 80 : i + 120])
