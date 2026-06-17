import re
import urllib.request

h = urllib.request.urlopen("https://teleautomation.online/").read().decode()
m = re.search(r"/assets/(app-[^\"']+\.js)", h)
print("html bundle:", m.group(1) if m else "MISSING")
if m:
    t = urllib.request.urlopen("https://teleautomation.online" + m.group(0)).read().decode("utf-8", "replace")
    for s in ["TeleAutomation", "Sign in", "auth-password", "Operator access", "Dashboard password"]:
        print(f"  {s}:", s in t)
