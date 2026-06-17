import re
import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

# tw() call at inbox mount
idx = t.find("tw().then(ee=>Re(ee))")
print("tw call idx", idx)
print(t[max(0, idx - 400) : idx + 200])

# find function tw = or async function tw
for pat in [
    r"async function tw\(",
    r"function tw\(",
    r"tw=async",
    r",tw=async",
    r"const tw=",
]:
    ms = list(re.finditer(pat, t))
    print(pat, len(ms))
    for m in ms[:3]:
        print(" ", t[m.start() : m.start() + 200])

# search valid JSON error string
for s in ["is not valid JSON", "Unexpected token", "Could not load"]:
    print(s, t.find(s))
