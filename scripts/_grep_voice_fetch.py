import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

for needle in [
    "voice/calls/start",
    "voice/analytics",
    "voice/calls/",
]:
    i = t.find(needle)
    print(needle, i)
    if i >= 0:
        print(t[i - 100 : i + 350])
        print("---")
