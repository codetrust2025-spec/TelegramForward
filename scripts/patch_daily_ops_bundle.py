"""Patch static daily-ops bundle for roster reload + upcoming date range."""
from pathlib import Path

BUNDLE = Path("static/assets/app-Dks3ojat.js")
CSS = Path("static/assets/index-X8Z7CYT5.css")
DAILY_CSS = Path("dashboard/src/dailyOps.css")

s = BUNDLE.read_text(encoding="utf-8")
orig = s

# 1) Upcoming preset: today through +14 days (not past week).
old_upcoming = 'case"upcoming":return{from:t,to:Fd(t,14)}'
new_upcoming = 'case"upcoming":return{from:t,to:Fd(t,14)}'
if old_upcoming not in s:
    print("upcoming preset already correct or not found — skip")
else:
    pass  # no-op; kept for documentation

# 2) Default tab: upcoming interviews (today through +14 days).
old_default = 'f=Wh("last7"),[h,m]=b.useState(f.from),[g,p]=b.useState(f.to),[w,x]=b.useState("last7")'
new_default = 'f=Wh("upcoming"),[h,m]=b.useState(f.from),[g,p]=b.useState(f.to),[w,x]=b.useState("upcoming")'
if old_default not in s:
    if new_default.split(",[h,m]")[0] in s:
        print("default already upcoming — skip")
    else:
        raise SystemExit("default preset init not found")
else:
    s = s.replace(old_default, new_default, 1)

# 3) Roster refetches via useEffect when dashboardFromDate/To change — no remount key needed.

if s == orig:
    print("no bundle changes needed")
else:
    BUNDLE.write_text(s, encoding="utf-8")
    print("patched", BUNDLE)

# 4) CSS scroll trap — source + built bundle.
for css_path in (DAILY_CSS, CSS):
    if not css_path.exists():
        continue
    css = css_path.read_text(encoding="utf-8")
    css2 = css
    css2 = css2.replace(
        ".desktop-body--daily-ops{padding:6px 10px 10px;overflow:hidden;display:flex;flex-direction:column}",
        ".desktop-body--daily-ops{padding:6px 10px 10px;overflow-y:auto;overflow-x:hidden;display:flex;flex-direction:column}",
    )
    css2 = css2.replace(
        ".desktop-body--daily-ops .ops-dash-roster,.app-shell--view-daily-ops .ops-dash-roster{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;overflow:hidden}",
        ".desktop-body--daily-ops .ops-dash-roster,.app-shell--view-daily-ops .ops-dash-roster{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;overflow:visible}",
    )
    if css2 != css:
        css_path.write_text(css2, encoding="utf-8")
        print("patched", css_path)
