import re
import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

idx = t.find("Select a lead to view")
print("select lead idx", idx)
print(t[idx - 2500 : idx + 500][:3000])

# smart-reply parallel load
idx2 = t.find("ai/smart-reply/assessment")
print("\nassessment idx", idx2)
print(t[idx2 - 200 : idx2 + 400])
