import re
import urllib.request

t = urllib.request.urlopen("https://teleautomation.online/assets/app-sPW-AjZE.js").read().decode("utf-8", "replace")
# context around admin/dashboard fetch
i = t.find("/admin/dashboard?window_hours")
print(t[i : i + 800])
# search for fields used from dashboard data
for field in [
    "window_hours",
    "handlers",
    "leads",
    "hot_leads",
    "accounts",
    "issues",
    "summary",
    "kpis",
    "live_chats",
]:
    if field in t[i : i + 5000]:
        print("field near admin:", field)
