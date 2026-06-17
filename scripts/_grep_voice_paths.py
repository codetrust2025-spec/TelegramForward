import re
import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

paths = sorted(set(re.findall(r"`\$\{ve\}/voice/[^`]+`", t)))
for p in paths:
    print(p)
