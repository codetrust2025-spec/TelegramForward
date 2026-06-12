#!/usr/bin/env python3
"""Pin all candidate filters to sticky top bar on Candidates page."""
import os
import re
import socket
import sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"
BUNDLE = f"{ROOT}/static/assets/app-D89Ign3q.js"
STYLES = f"{ROOT}/static/assets/index-CYOx-Gpf.css"
APP_CSS = f"{ROOT}/dashboard/src/teleautomation.css"
APP_JSX = f"{ROOT}/dashboard/src/teleautomation-app.jsx"

CSS_RULE = (
    ".cand-page-topbar{position:sticky;top:0;z-index:20;display:flex;flex-wrap:wrap;align-items:center;"
    "gap:10px;padding:10px 0 14px;margin-bottom:4px;background:#0f1117;border-bottom:1px solid #1e293b}"
    ".cand-page-topbar .cand-top-perf-earn-btn{margin-right:4px}"
    ".cand-page-topbar .cand-input{min-width:148px;flex:0 1 auto}"
    ".cand-page-topbar .cand-toggle{flex-shrink:0}"
)

# --- bundle: expand existing topbar (month only) to full filter row ---
BUNDLE_OLD_TOPBAR = (
    'cand-page-topbar",role:"region","aria-label":"Earnings and month filter",children:['
    'a&&!r&&s.jsxs("button",{type:"button",className:"cand-btn cand-btn--primary cand-top-perf-earn-btn",'
    'onClick:fe,title:"Open a full board with every handler\'s salary, commission, paid out and net owed — with chart view",'
    'children:[s.jsx("span",{"aria-hidden":!0,style:{marginRight:6},children:"\U0001f4ca"}),"Total earnings"]}),'
    's.jsxs("div",{className:"cand-top-perf-control",children:['
    's.jsx("label",{className:"cand-top-perf-sort-label",children:"Month"}),'
    's.jsx("select",{className:"cand-input cand-input--compact",value:m||"all",'
    'onChange:he=>y(he.target.value),"aria-label":"Filter by month",'
    'children:ze.map(he=>s.jsx("option",{value:he.value,children:he.label},he.value))})]})]}),'
)

BUNDLE_NEW_TOPBAR = (
    'cand-page-topbar",role:"region","aria-label":"Candidate filters",children:['
    'a&&!r&&s.jsxs("button",{type:"button",className:"cand-btn cand-btn--primary cand-top-perf-earn-btn",'
    'onClick:fe,title:"Open a full board with every handler\'s salary, commission, paid out and net owed — with chart view",'
    'children:[s.jsx("span",{"aria-hidden":!0,style:{marginRight:6},children:"\U0001f4ca"}),"Total earnings"]}),'
    's.jsx("select",{className:"cand-input",value:m,onChange:he=>y(he.target.value),"aria-label":"Filter by month",'
    'children:ze.map(he=>s.jsx("option",{value:he.value,children:he.label},he.value))}),'
    's.jsx("select",{className:"cand-input",value:x,onChange:he=>_(he.target.value),'
    'children:JO.map(he=>s.jsx("option",{value:he.value,children:he.label},he.value))}),'
    'a&&s.jsx("select",{className:`cand-input${N!=="all"?" cand-input--active":""}`,value:N,'
    'onChange:he=>k(he.target.value),"aria-label":"Filter by handler / reference",'
    'title:"Show only candidates referred by this handler",'
    'children:ct.map(he=>s.jsx("option",{value:he.value,children:he.label},he.value))}),'
    's.jsxs("label",{className:`cand-toggle${v?" cand-toggle--on":""}${(c==null?void 0:c.pending_count)>0?" cand-toggle--has-pending":""}`,'
    'title:"Show only candidates with a pending balance",children:['
    's.jsx("input",{type:"checkbox",checked:v,onChange:he=>w(he.target.checked)}),'
    's.jsx("span",{children:"Pending only"}),'
    '(c==null?void 0:c.pending_count)>0&&s.jsx("span",{className:"cand-toggle-badge",children:c.pending_count})]})]}),'
)

# --- bundle: toolbar keeps search + count only ---
BUNDLE_OLD_TOOLBAR_FILTERS = (
    's.jsx("input",{className:"cand-input cand-input--search",placeholder:"Search name, tech, reference, phone, notes\u2026",value:b,onChange:he=>E(he.target.value)}),'
    's.jsx("select",{className:"cand-input",value:m,onChange:he=>y(he.target.value),"aria-label":"Filter by month",'
    'children:ze.map(he=>s.jsx("option",{value:he.value,children:he.label},he.value))}),'
    's.jsx("select",{className:"cand-input",value:x,onChange:he=>_(he.target.value),'
    'children:JO.map(he=>s.jsx("option",{value:he.value,children:he.label},he.value))}),'
    'a&&s.jsx("select",{className:`cand-input${N!=="all"?" cand-input--active":""}`,value:N,'
    'onChange:he=>k(he.target.value),"aria-label":"Filter by handler / reference",'
    'title:"Show only candidates referred by this handler",'
    'children:ct.map(he=>s.jsx("option",{value:he.value,children:he.label},he.value))}),'
    's.jsxs("label",{className:`cand-toggle${v?" cand-toggle--on":""}${(c==null?void 0:c.pending_count)>0?" cand-toggle--has-pending":""}`,'
    'title:"Show only candidates with a pending balance",children:['
    's.jsx("input",{type:"checkbox",checked:v,onChange:he=>w(he.target.checked)}),'
    's.jsx("span",{children:"Pending only"}),'
    '(c==null?void 0:c.pending_count)>0&&s.jsx("span",{className:"cand-toggle-badge",children:c.pending_count})]}),'
)

BUNDLE_NEW_TOOLBAR_FILTERS = (
    's.jsx("input",{className:"cand-input cand-input--search",placeholder:"Search name, tech, reference, phone, notes\u2026",value:b,onChange:he=>E(he.target.value)}),'
)

# --- source jsx patches ---
JSX_OLD_TOPBAR = (
    '<div className="cand-page-topbar" role="region" aria-label="Earnings and month filter">'
    '{a && !n && <button type="button" className="cand-btn cand-btn--primary cand-top-perf-earn-btn" onClick={pe} '
    'title="Open a full board with every handler\'s salary, commission, paid out and net owed'
)
# partial match - use two-step for jsx

JSX_TOOLBAR_FILTERS = (
    '<input className="cand-input cand-input--search" placeholder="Search name, tech, reference, phone, notes'
)


def sftp_read(path: str) -> str:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
    sftp = c.open_sftp()
    with sftp.open(path, "r") as f:
        data = f.read().decode("utf-8", errors="replace")
    sftp.close()
    c.close()
    return data


def sftp_write(path: str, data: str) -> None:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
    sftp = c.open_sftp()
    with sftp.open(path, "w") as f:
        f.write(data.encode("utf-8"))
    sftp.close()
    c.close()


def patch_css(src: str) -> tuple[str, str]:
    if ".cand-page-topbar .cand-input{" in src:
        return src, "already updated"
    # replace old shorter rule if present
    old = (
        ".cand-page-topbar{position:sticky;top:0;z-index:20;display:flex;flex-wrap:wrap;align-items:center;"
        "gap:12px;padding:10px 0 14px;margin-bottom:4px;background:#0f1117;border-bottom:1px solid #1e293b}"
        ".cand-page-topbar .cand-top-perf-earn-btn{margin-right:auto}"
    )
    if old in src:
        return src.replace(old, CSS_RULE, 1), "replaced rule"
    if "cand-page-topbar" in src:
        return src + CSS_RULE, "appended extras"
    return src + CSS_RULE, "appended full"


def patch_jsx(jsx: str) -> tuple[str, list[str]]:
    logs = []
    new_topbar = (
        '<div className="cand-page-topbar" role="region" aria-label="Candidate filters">'
        '{a && !n && <button type="button" className="cand-btn cand-btn--primary cand-top-perf-earn-btn" onClick={pe} '
        'title="Open a full board with every handler\'s salary, commission, paid out and net owed — with chart view">'
        '<span aria-hidden={true} style={{marginRight: 6}}>📊</span>Total earnings</button>}'
        '<select className="cand-input" value={m} onChange={ge => _(ge.target.value)} aria-label="Filter by month">'
        '{Le.map(ge => <option value={ge.value} key={ge.value}>{ge.label}</option>)}</select>'
        '<select className="cand-input" value={g} onChange={ge => p(ge.target.value)}>'
        '{dR.map(ge => <option value={ge.value} key={ge.value}>{ge.label}</option>)}</select>'
        '{a && <select className={`cand-input${T !== "all" ? " cand-input--active" : ""}`} value={T} '
        'onChange={ge => S(ge.target.value)} aria-label="Filter by handler / reference" '
        'title="Show only candidates referred by this handler">'
        '{st.map(ge => <option value={ge.value} key={ge.value}>{ge.label}</option>)}</select>}'
        '<label className={`cand-toggle${y ? " cand-toggle--on" : ""}${(c == null ? undefined : c.pending_count) > 0 ? " cand-toggle--has-pending" : ""}`} '
        'title="Show only candidates with a pending balance">'
        '<input type="checkbox" checked={y} onChange={ge => k(ge.target.checked)} />'
        '<span>Pending only</span>'
        '{(c == null ? undefined : c.pending_count) > 0 && <span className="cand-toggle-badge">{c.pending_count}</span>}'
        '</label></div>'
    )
    patched, n = re.subn(
        r'<div className="cand-page-topbar"[^>]*>.*?</div>\s*</div>',
        new_topbar,
        jsx,
        count=1,
        flags=re.DOTALL,
    )
    if n:
        jsx = patched
        logs.append("jsx: expanded topbar (nested div)")
    else:
        patched, n = re.subn(
            r'<div className="cand-page-topbar"[^>]*>.*?</div>',
            new_topbar,
            jsx,
            count=1,
            flags=re.DOTALL,
        )
        if n:
            jsx = patched
            logs.append("jsx: expanded topbar")
        else:
            logs.append("jsx: topbar block not found")

    tb = jsx.find('<div className="cand-toolbar"')
    sp = jsx.find('<div className="cand-toolbar-spacer"', tb)
    if tb < 0 or sp < 0:
        logs.append("jsx: toolbar not found")
        return jsx, logs
    for needle in ['onChange={ge => b(ge.target.value)} />', 'onChange={ge=>b(ge.target.value)} />']:
        search_end = jsx.find(needle, tb)
        if search_end >= 0:
            search_end += len(needle)
            jsx = jsx[:search_end] + jsx[sp:]
            logs.append("jsx: trimmed toolbar filters")
            break
    else:
        logs.append("jsx: search input not found")
    return jsx, logs


def patch_bundle(bundle: str) -> tuple[str, list[str]]:
    logs = []
    if 'cand-page-topbar",role:"region","aria-label":"Candidate filters",children:' in bundle:
        logs.append("bundle: topbar already expanded")
    elif BUNDLE_OLD_TOPBAR in bundle:
        bundle = bundle.replace(BUNDLE_OLD_TOPBAR, BUNDLE_NEW_TOPBAR, 1)
        logs.append("bundle: expanded topbar")
    elif BUNDLE_NEW_TOPBAR.split("children:[")[0] in bundle:
        logs.append("bundle: topbar already expanded")
    else:
        logs.append("bundle: ERROR topbar anchor not found")
        return bundle, logs

    if BUNDLE_OLD_TOOLBAR_FILTERS in bundle:
        bundle = bundle.replace(BUNDLE_OLD_TOOLBAR_FILTERS, BUNDLE_NEW_TOOLBAR_FILTERS, 1)
        logs.append("bundle: trimmed toolbar")
    else:
        logs.append("bundle: WARN toolbar anchor not found")

    return bundle, logs


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    bundle = sftp_read(BUNDLE)
    bundle, blogs = patch_bundle(bundle)
    for line in blogs:
        print(line)
    sftp_write(BUNDLE, bundle)

    jsx = sftp_read(APP_JSX)
    jsx, jlogs = patch_jsx(jsx)
    for line in jlogs:
        print(line)
    sftp_write(APP_JSX, jsx)

    for path, label in [(STYLES, "live-css"), (APP_CSS, "src-css")]:
        css, status = patch_css(sftp_read(path))
        sftp_write(path, css)
        print(f"{label}: {status}")

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
