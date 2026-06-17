import urllib.request

t = urllib.request.urlopen("https://teleautomation.online/assets/app-sPW-AjZE.js").read().decode("utf-8", "replace")
needle = "/admin/dashboard"
idx = 0
n = 0
while n < 8:
    i = t.find(needle, idx)
    if i < 0:
        break
    print(f"\n--- hit {n} at {i} ---")
    print(t[i - 120 : i + 200])
    idx = i + 1
    n += 1
