"""Patch static bundle: phone-only mobile shell (767px), admin tab scroll."""
from pathlib import Path

BUNDLE = Path("static/assets/app-Dks3ojat.js")
CSS = Path("static/assets/index-X8Z7CYT5.css")
ADMIN_CSS = Path("dashboard/src/admin.css")

s = BUNDLE.read_text(encoding="utf-8")
old_hook = (
    'const fx="(max-width: 1023px)";function yc(){const[e,t]=b.useState(()=>typeof window>"u"?!1:'
    'window.matchMedia(fx).matches);return b.useEffect(()=>{const n=window.matchMedia(fx),'
    'r=()=>t(n.matches);return r(),n.addEventListener("change",r),()=>n.removeEventListener("change",r)},[]),e}'
)
new_hook = (
    'const fx="(max-width: 1023px)",mobMq="(max-width: 767px)";function yc(){const[e,t]=b.useState(()=>typeof window>"u"?!1:'
    'window.matchMedia(fx).matches);return b.useEffect(()=>{const n=window.matchMedia(fx),'
    'r=()=>t(n.matches);return r(),n.addEventListener("change",r),()=>n.removeEventListener("change",r)},[]),e}'
    'function mSh(){const[e,t]=b.useState(()=>typeof window>"u"?!1:window.matchMedia(mobMq).matches);'
    'return b.useEffect(()=>{const n=window.matchMedia(mobMq),r=()=>t(n.matches);return r(),'
    'n.addEventListener("change",r),()=>n.removeEventListener("change",r)},[]),e}'
)
if old_hook not in s:
    raise SystemExit("yc hook block not found in bundle")
s = s.replace(old_hook, new_hook, 1)
if "Lc=yc()" not in s:
    raise SystemExit("Lc=yc() not found")
s = s.replace("Lc=yc()", "Lc=mSh()", 1)
BUNDLE.write_text(s, encoding="utf-8")
print("patched mobile shell breakpoint in", BUNDLE)

# Admin tabs horizontal scroll in built CSS
for css_path in (ADMIN_CSS, CSS):
    if not css_path.exists():
        continue
    css = css_path.read_text(encoding="utf-8")
    css2 = css
    css2 = css2.replace(
        ".admin-tabs{display:flex;flex-wrap:wrap;gap:6px}",
        ".admin-tabs{display:flex;flex-wrap:nowrap;gap:6px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:thin;padding-bottom:2px}",
    )
    css2 = css2.replace(
        ".admin-tab{padding:8px 14px;border-radius:8px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.03);color:var(--text-dim,#94a3b8);font-size:13px;cursor:pointer;font-family:inherit}",
        ".admin-tab{padding:8px 14px;border-radius:8px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.03);color:var(--text-dim,#94a3b8);font-size:13px;cursor:pointer;font-family:inherit;flex:0 0 auto;white-space:nowrap}",
    )
    if css2 != css:
        css_path.write_text(css2, encoding="utf-8")
        print("patched admin tabs in", css_path)
