"""Deploy only tab unread badge — patch built bundle on VPS without full App.jsx rebuild."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PATCH_JS = r"""
import { formatUnreadBadgeCount } from './inboxUnread.js';

let baseTitle = '';
let baseFaviconUrl = '';
let faviconLink = null;
let faviconImage = null;
let faviconReady = false;
let lastUnreadCount = 0;

function readBaseTitle() {
  if (baseTitle) return baseTitle;
  const raw = (document.title || 'TeleAutomation').trim();
  baseTitle = raw.replace(/^\(\d+\+?\)\s+/, '');
  return baseTitle;
}

function defaultFaviconSvg() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#5b21b6"/><path fill="#c4b5fd" d="M18 4 10 18h6l-4 10 12-16h-6z"/></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

function ensureFaviconLink() {
  if (faviconLink) return faviconLink;
  faviconLink = document.querySelector('link[rel="icon"]') || document.querySelector('link[rel="shortcut icon"]');
  if (!faviconLink) {
    faviconLink = document.createElement('link');
    faviconLink.rel = 'icon';
    document.head.appendChild(faviconLink);
  }
  if (!faviconLink.href) faviconLink.href = defaultFaviconSvg();
  return faviconLink;
}

function loadBaseFavicon() {
  if (faviconReady) return;
  const link = ensureFaviconLink();
  baseFaviconUrl = link.href || defaultFaviconSvg();
  if (!faviconImage) {
    faviconImage = new Image();
    faviconImage.crossOrigin = 'anonymous';
    faviconImage.onload = () => { faviconReady = true; syncTabUnreadBadge(lastUnreadCount); };
    faviconImage.onerror = () => { baseFaviconUrl = defaultFaviconSvg(); faviconImage.src = baseFaviconUrl; };
  }
  faviconImage.src = baseFaviconUrl;
}

function drawFaviconBadge(count) {
  const link = ensureFaviconLink();
  const n = Math.max(0, Number(count) || 0);
  if (n <= 0) { link.href = baseFaviconUrl || defaultFaviconSvg(); return; }
  if (!faviconReady || !faviconImage?.naturalWidth) { link.href = baseFaviconUrl || defaultFaviconSvg(); return; }
  const size = 32;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.drawImage(faviconImage, 0, 0, size, size);
  const label = formatUnreadBadgeCount(n) || String(n);
  const r = n > 9 ? 11 : 10;
  const cx = size - r + 1;
  const cy = r - 1;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fillStyle = '#25d366';
  ctx.fill();
  ctx.strokeStyle = '#0f1117';
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.fillStyle = '#fff';
  ctx.font = `bold ${label.length > 2 ? 8 : 11}px system-ui,sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(label, cx, cy + 0.5);
  link.href = canvas.toDataURL('image/png');
}

export function syncTabUnreadBadge(unreadCount) {
  lastUnreadCount = Math.max(0, Number(unreadCount) || 0);
  readBaseTitle();
  loadBaseFavicon();
  if (lastUnreadCount > 0) {
    const badge = formatUnreadBadgeCount(lastUnreadCount);
    document.title = `(${badge}) ${baseTitle}`;
  } else {
    document.title = baseTitle;
  }
  drawFaviconBadge(lastUnreadCount);
}

export function resetTabUnreadBadge() {
  lastUnreadCount = 0;
  readBaseTitle();
  document.title = baseTitle;
  ensureFaviconLink().href = baseFaviconUrl || defaultFaviconSvg();
}

export function installTabUnreadBadge(getUnread) {
  const tick = () => {
    try {
      const n = typeof getUnread === 'function' ? getUnread() : 0;
      syncTabUnreadBadge(n);
    } catch (_) {}
  };
  tick();
  const id = window.setInterval(tick, 4000);
  window.addEventListener('visibilitychange', tick);
  window.addEventListener('focus', tick);
  return () => window.clearInterval(id);
}
"""

INJECT_SNIPPET = """
;(function(){
  if(window.__TA_TAB_BADGE__)return;
  window.__TA_TAB_BADGE__=1;
  var baseTitle=(document.title||'TeleAutomation').replace(/^\\(\\d+\\+?\\)\\s+/,'').trim();
  var baseIcon=document.querySelector('link[rel=icon]');
  var baseHref=baseIcon&&baseIcon.href?baseIcon.href:'';
  var img=new Image();
  var ready=false;
  function fmt(n){n=Math.max(0,Number(n)||0);if(!n)return'';return n>99?'99+':String(n);}
  function draw(n){
    if(!baseIcon)return;
    if(n<=0){document.title=baseTitle;baseIcon.href=baseHref;return;}
    document.title='('+fmt(n)+') '+baseTitle;
    if(!ready||!img.naturalWidth){return;}
    var c=document.createElement('canvas');c.width=32;c.height=32;
    var x=c.getContext('2d');if(!x)return;
    x.drawImage(img,0,0,32,32);
    var lab=fmt(n)||String(n),r=n>9?11:10,cx=32-r+1,cy=r-1;
    x.beginPath();x.arc(cx,cy,r,0,Math.PI*2);x.fillStyle='#25d366';x.fill();
    x.strokeStyle='#0f1117';x.lineWidth=1.5;x.stroke();
    x.fillStyle='#fff';x.font='bold '+(lab.length>2?8:11)+'px system-ui,sans-serif';
    x.textAlign='center';x.textBaseline='middle';x.fillText(lab,cx,cy+0.5);
    baseIcon.href=c.toDataURL('image/png');
  }
  img.crossOrigin='anonymous';
  img.onload=function(){ready=true;tick();};
  if(baseHref)img.src=baseHref;
  function unreadFromDom(){
    var badges=document.querySelectorAll('.inbox-unread-badge');
    var t=0;badges.forEach(function(b){t+=parseInt(b.textContent,10)||0;});
    return t;
  }
  function tick(){draw(unreadFromDom());}
  tick();setInterval(tick,4000);
  window.addEventListener('visibilitychange',tick);
  window.addEventListener('focus',tick);
})();
"""

REMOTE_PY = f"""
import glob, re, os
static = '{REMOTE}/static'
html = static + '/index.html'
if not os.path.isfile(html):
    print('no index.html'); raise SystemExit(1)
with open(html, encoding='utf-8') as f:
    t = f.read()
if 'TeleAutomation' not in t and 'Telegram' in t:
    t = re.sub(r'<title>[^<]+</title>', '<title>TeleAutomation</title>', t, count=1)
if 'rel=\"icon\"' not in t:
    t = t.replace('</head>',
        \"<link rel=\\\"icon\\\" type=\\\"image/svg+xml\\\" href=\\\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%235b21b6'/%3E%3Cpath fill='%23c4b5fd' d='M18 4 10 18h6l-4 10 12-16h-6z'/%3E%3C/svg%3E\\\" /></head>\", 1)
inject = {repr(INJECT_SNIPPET.strip())}
patched = 0
for path in glob.glob(static + '/assets/app-*.js') + glob.glob(static + '/assets/index-*.js'):
    with open(path, encoding='utf-8', errors='replace') as f:
        body = f.read()
    if '__TA_TAB_BADGE__' in body:
        print('already', os.path.basename(path))
        patched += 1
        continue
    with open(path, 'w', encoding='utf-8') as f:
        f.write(body + inject)
    print('patched', os.path.basename(path))
    patched += 1
with open(html, 'w', encoding='utf-8') as f:
    f.write(t)
print('html ok, files', patched)
"""

def main() -> int:
    if not PWD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1
    import paramiko

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    # Restore VPS App.jsx from last good build if broken — skip upload App.jsx
    print(">>> patch static bundles")
    _, o, e = c.exec_command(f"python3 -c {repr(REMOTE_PY)}", timeout=120)
    print(o.read().decode())
    err = e.read().decode()
    if err:
        print(err, file=sys.stderr)
    code = o.channel.recv_exit_status()
    c.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
