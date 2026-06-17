import re
import urllib.request

h = urllib.request.urlopen("https://teleautomation.online/").read().decode()
m = re.search(r"/assets/app-[^\"]+\.js", h)
print("html script:", m.group() if m else "MISSING")
if not m:
    raise SystemExit(1)
t = urllib.request.urlopen("https://teleautomation.online" + m.group()).read().decode()
hook = re.search(r"function to\(\)\{[^}]+\}", t)
print("to():", hook.group() if hook else "missing")
print("sync global set:", "GLOBAL_VALUE_KEY" in t or "__TA_CONFIRM_VALUE__" in t and "children:[e" in t)
print("render tail:", t[-380:])
