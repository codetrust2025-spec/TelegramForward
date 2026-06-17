#!/usr/bin/env python3
"""Keep only .txt export in chat overflow menu."""
import os
import socket
import sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
BUNDLE = "/opt/telegramforward.old/static/assets/app-D89Ign3q.js"

OLD = (
    'typeof p=="function"&&s.jsxs(s.Fragment,{children:['
    's.jsx("button",{type:"button",role:"menuitem",onClick:()=>{N(!1),p("txt")},disabled:x||_,'
    'children:x?"Exporting…":"Export chat (.txt)"}),'
    's.jsx("button",{type:"button",role:"menuitem",onClick:()=>{N(!1),p("csv")},disabled:x||_,children:"Export chat (.csv)"}),'
    's.jsx("button",{type:"button",role:"menuitem",onClick:()=>{N(!1),p("json")},disabled:x||_,children:"Export chat (.json)"})]})'
)

NEW = (
    'typeof p=="function"&&s.jsx("button",{type:"button",role:"menuitem",onClick:()=>{N(!1),p("txt")},disabled:x||_,'
    'children:x?"Exporting…":"Export chat"})'
)


def sftp_rw(path: str, data: str | None = None) -> str:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
    sftp = c.open_sftp()
    if data is None:
        with sftp.open(path, "r") as f:
            out = f.read().decode("utf-8", errors="replace")
    else:
        with sftp.open(path, "w") as f:
            f.write(data.encode("utf-8"))
        out = ""
    sftp.close()
    c.close()
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bundle = sftp_rw(BUNDLE)
    if "Export chat (.csv)" not in bundle:
        if 'children:x?"Exporting' in bundle and 'p("txt")' in bundle and "Export chat (.csv)" not in bundle:
            print("already patched")
            return 0
        print("ERROR: anchor not found")
        return 1
    bundle = bundle.replace(OLD, NEW, 1)
    if "Export chat (.csv)" in bundle:
        print("ERROR: replace failed")
        return 1
    sftp_rw(BUNDLE, bundle)
    print("removed csv/json export options; kept txt as Export chat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
