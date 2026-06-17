import urllib.request

t = urllib.request.urlopen("https://teleautomation.online/assets/app-sPW-AjZE.js").read().decode("utf-8", "replace")
for needle in ["/alerts", "alerts/", "vapid", "push/", "Unexpected", "CRM Inbox", "dm_inbox"]:
    idx = 0
    n = 0
    while n < 6:
        i = t.find(needle, idx)
        if i < 0:
            break
        print(f"\n--- {needle} @ {i} ---")
        print(t[i - 60 : i + 140])
        idx = i + 1
        n += 1
