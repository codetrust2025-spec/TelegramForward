import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

i = t.find("async function f0(")
print(t[i : i + 400])
