import glob
import os
import re

REMOTE = os.environ.get("TA_REMOTE", "/opt/telegramforward")
INJECT = r""";(function(){if(window.__TA_TAB_BADGE__)return;window.__TA_TAB_BADGE__=1;var baseTitle=(document.title||'TeleAutomation').replace(/^\(\d+\+?\)\s+/,'').trim();var baseIcon=document.querySelector('link[rel=icon]')||function(){var l=document.createElement('link');l.rel='icon';document.head.appendChild(l);return l;}();var baseHref=baseIcon.href||"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%235b21b6'/%3E%3Cpath fill='%23c4b5fd' d='M18 4 10 18h6l-4 10 12-16h-6z'/%3E%3C/svg%3E";baseIcon.href=baseHref;var img=new Image();var ready=false;function fmt(n){n=Math.max(0,Number(n)||0);if(!n)return'';return n>99?'99+':String(n);}function draw(n){if(n<=0){document.title=baseTitle;baseIcon.href=baseHref;return;}document.title='('+fmt(n)+') '+baseTitle;if(!ready||!img.naturalWidth)return;var c=document.createElement('canvas');c.width=32;c.height=32;var x=c.getContext('2d');if(!x)return;x.drawImage(img,0,0,32,32);var lab=fmt(n)||String(n),r=n>9?11:10,cx=32-r+1,cy=r-1;x.beginPath();x.arc(cx,cy,r,0,Math.PI*2);x.fillStyle='#25d366';x.fill();x.strokeStyle='#0f1117';x.lineWidth=1.5;x.stroke();x.fillStyle='#fff';x.font='bold '+(lab.length>2?8:11)+'px system-ui,sans-serif';x.textAlign='center';x.textBaseline='middle';x.fillText(lab,cx,cy+0.5);baseIcon.href=c.toDataURL('image/png');}img.crossOrigin='anonymous';img.onload=function(){ready=true;tick();};img.src=baseHref;function unreadFromDom(){var t=0;document.querySelectorAll('.inbox-unread-badge').forEach(function(b){t+=parseInt(b.textContent,10)||0;});return t;}function tick(){draw(unreadFromDom());}tick();setInterval(tick,4000);window.addEventListener('visibilitychange',tick);window.addEventListener('focus',tick);})();"""


def clean_app() -> None:
    app = f"{REMOTE}/dashboard/src/App.jsx"
    if not os.path.isfile(app):
        print("no App.jsx")
        return
    with open(app, encoding="utf-8") as f:
        lines = f.readlines()
    out = []
    skip = False
    for line in lines:
        if "CandidatesPanel" in line and "import" in line:
            continue
        if "<CandidatesPanel" in line:
            skip = True
            continue
        if skip:
            if "/>" in line or "</CandidatesPanel>" in line:
                skip = False
            continue
        out.append(line)
    with open(app, "w", encoding="utf-8") as f:
        f.writelines(out)
    print("app.jsx cleaned", len(out), "lines")


def patch_html() -> None:
    html = f"{REMOTE}/static/index.html"
    with open(html, encoding="utf-8") as f:
        t = f.read()
    if not re.search(r"<title>TeleAutomation</title>", t):
        t = re.sub(r"<title>[^<]+</title>", "<title>TeleAutomation</title>", t, count=1)
    icon = (
        '<link rel="icon" type="image/svg+xml" '
        "href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
        "viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%235b21b6'/%3E"
        "%3Cpath fill='%23c4b5fd' d='M18 4 10 18h6l-4 10 12-16h-6z'/%3E%3C/svg%3E\" />"
    )
    if 'rel="icon"' not in t and "rel='icon'" not in t:
        t = t.replace("</head>", icon + "</head>", 1)
    with open(html, "w", encoding="utf-8") as f:
        f.write(t)
    print("index.html ok")


def patch_bundles() -> int:
    n = 0
    static = f"{REMOTE}/static"
    for path in sorted(glob.glob(static + "/assets/app-*.js")):
        with open(path, encoding="utf-8", errors="replace") as f:
            body = f.read()
        if "__TA_TAB_BADGE__" in body:
            print("skip", os.path.basename(path))
            n += 1
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(body + INJECT)
        print("patched", os.path.basename(path))
        n += 1
    return n


if __name__ == "__main__":
    clean_app()
    patch_html()
    print("bundles", patch_bundles())
