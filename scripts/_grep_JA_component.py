import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

# JA is InboxPanel - find function JA(
idx = t.find("function JA(")
if idx < 0:
    idx = t.find("function JA({")
print("JA at", idx)
print(t[idx : idx + 4000])
