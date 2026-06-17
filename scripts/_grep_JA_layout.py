import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

idx = t.find("function JA(")
sub = t[idx : idx + 35000]
i = sub.find("crm-layout")
print("crm-layout offset in JA", i)
print(sub[i - 800 : i + 1200])
