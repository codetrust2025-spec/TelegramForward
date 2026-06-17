import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

i = t.find("inbox-error")
print(t[max(0, i - 500) : i + 800])
