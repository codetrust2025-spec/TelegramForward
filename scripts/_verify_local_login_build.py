import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
html = (root / "static" / "index.html").read_text(encoding="utf-8")
m = re.search(r"/assets/(app-[^\"']+\.js)", html)
js = root / "static" / "assets" / (m.group(1) if m else "")
print("local bundle:", m.group(1) if m else "MISSING")
if js.is_file():
    t = js.read_text(encoding="utf-8", errors="replace")
    for s in ["TeleAutomation", "Sign in", "auth-password-toggle", "Show password", "Operator access"]:
        print(f"  {s}:", s in t)
css = list((root / "static" / "assets").glob("index-*.css"))
if css:
    c = css[0].read_text(encoding="utf-8", errors="replace")
    print("  auth-password-wrap in css:", "auth-password-wrap" in c)
