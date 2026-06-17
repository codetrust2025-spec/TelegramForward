import re
import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

print("paths containing analytics:")
for m in re.finditer(r"[`\"](/[^`\"]*analytics[^`\"]*)[`\"]", t):
    print(" ", m.group(1))

print("\nfetch(...analytics...")
for m in re.finditer(r"fetch\([^)]{0,120}analytics[^)]{0,80}\)", t):
    print(" ", m.group(0)[:180])

print("\ninbox init snippets with .json():")
for m in re.finditer(r"fetch\(`\$\{[^}]+\}/inbox[^`]+`[^;]{0,200}\.json\(\)", t):
    print(" ", m.group(0)[:200])
