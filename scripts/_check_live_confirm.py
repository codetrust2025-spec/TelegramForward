import urllib.request

html = urllib.request.urlopen("https://teleautomation.online/", timeout=20).read().decode()
import re

m = re.search(r"/assets/(app-[^\"]+\.js)", html)
print("index bundle:", m.group(1) if m else "?")
if m:
    url = "https://teleautomation.online/assets/" + m.group(1)
    t = urllib.request.urlopen(url, timeout=30).read().decode("utf-8", errors="replace")
    i = t.find("function eo()")
    hook = t[i : i + 220] if i >= 0 else "eo not found"
    print("hook:", hook)
    print("patched:", "__TA_CONFIRM_VALUE__" in hook and "||" in hook)
