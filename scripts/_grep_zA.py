import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

# zA next to OA stats bar
idx = t.find("function zA(")
print("zA", idx)
if idx >= 0:
    print(t[idx : idx + 2500])

# M6 demo tools
idx2 = t.find("function M6(")
print("M6", idx2)
if idx2 >= 0:
    print(t[idx2 : idx2 + 1500])
