import urllib.request

url = "https://teleautomation.online/assets/app-Dks3ojat.js"
req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
print("portal", "ops-row-menu__list--portal" in body)
print("update", "Update status & attendee" in body)
print("createPortal", "ops-row-menu__list--portal" in body and "is.createPortal" in body)
