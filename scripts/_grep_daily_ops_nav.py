import pathlib
import re

js = pathlib.Path(__file__).resolve().parents[1] / "static/assets/dashboard.bundle.js"
js = js.read_text(encoding="utf-8", errors="replace")

# AppViewNav / sidebar daily ops
for pat in [
    "daily-ops",
    "Daily ops",
    "dailyOps",
    "mainViewOptions",
    "APP_VIEWS",
    "HANDLER_VIEWS",
]:
    print(pat, js.count(pat))

# context around daily-ops-page
i = js.find("daily-ops-page")
print("\ndaily-ops-page context:")
print(js[max(0, i - 500) : i + 200][:700])

# nav with daily
for m in re.finditer(r".{0,30}daily-ops.{0,120}", js):
    s = m.group()
    if "label" in s or "value" in s or "nav" in s.lower():
        print("NAV:", s[:200])
