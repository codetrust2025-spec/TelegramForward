import urllib.request

html = urllib.request.urlopen("https://teleautomation.online/").read().decode()
print("dashboard.bundle.js in HTML:", "dashboard.bundle.js" in html)
print("dashboard.bundle.css in HTML:", "dashboard.bundle.css" in html)
print("vite app-sjsEbgmN.js in HTML:", "app-sjsEbgmN.js" in html)

js = urllib.request.urlopen("https://teleautomation.online/assets/dashboard.bundle.js").read().decode("utf-8", "ignore")
for n in [
    "PendingWorksProvider",
    "Works pending",
    "Daily ops",
    "daily-ops",
    "cand-workspace",
    "data-room",
]:
    print(f"  {n}: {'OK' if n in js else 'missing'}")
