import re
import urllib.request

t = urllib.request.urlopen("https://teleautomation.online/assets/app-sPW-AjZE.js").read().decode("utf-8", "replace")
for pat in ["HTTP ${", "HTTP 404", "status===404", "status==404", "Not Found"]:
    print(pat, t.count(pat))
for m in re.finditer(r"HTTP.{0,40}status", t):
    s = m.group()
    if "404" in s or "${" in s:
        print(s[:100])
# admin-related fetch template strings
for m in re.finditer(r"\$\{[a-zA-Z0-9_]+\}/[a-zA-Z0-9_/-]+", t):
    s = m.group()
    if "admin" in s or "metric" in s or "workspace" in s or "ai" in s:
        if s not in getattr(main, "seen", set()):
            print(s)
