import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

# Main app - find state fetch error
for needle in ["/state", "loadError", "setLoad", "app-load-error", "crm-error", "role:\"alert\""]:
    pass

idx = t.find("fetch(`${ve}/state")
print("state fetch", idx)
print(t[idx - 200 : idx + 600])

# search error displayed in inbox view area - near CRM Inbox title
idx2 = t.find("CRM Inbox")
print("CRM Inbox", idx2)
print(t[idx2 - 300 : idx2 + 1500])
