#!/usr/bin/env python3
"""Deploy All-accounts success rate = average of per-account rates."""
import os
import socket
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"
SRC = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\dashboard_vps_src")
LOCAL_BUNDLE = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js")

# Inject averageSuccessRate into aggregateFleetStats (BR) in the minified bundle.
BR_AVG_OLD = (
    'A=s==="forwarding"&&O>0?(c/O*100).toFixed(1):L>0?(c/L*100).toFixed(1):"0.0";f<=0'
)
BR_AVG_NEW = (
    'A=s==="forwarding"&&O>0?(c/O*100).toFixed(1):L>0?(c/L*100).toFixed(1):"0.0";'
    "let _avgSum=0;for(const _row of T){const _s=_row.success||0,_f=_row.failed||0,"
    "_sk=_row.skippedAlreadyPosted||0,_t=s===\"forwarding\"?_s+_f+_sk:_s+_f;"
    "_avgSum+=_t>0?_s/_t*100:0}const _avgRate=T.length>0?(_avgSum/T.length).toFixed(1):\"0.0\";f<=0"
)
BR_RETURN_OLD = "successRate:A,progressValue:"
BR_RETURN_NEW = "successRate:A,averageSuccessRate:_avgRate,progressValue:"

NF_FLEET_OLD = (
    'successRate:en.successRate,remaining:en.needResend,skipped:en.skippedAlreadyPosted}:'
    "{groups:sn||en.progressMax,sent:Vn,failed:Ue,successRate:Vs,remaining:vr,skipped:gn},"
    "[R,sn,en.progressMax,en.success,en.failed,en.successRate,en.needResend,"
    "en.skippedAlreadyPosted,Vn,Ue,Vs,vr,gn]);"
)
NF_FLEET_NEW = (
    "successRate:en.averageSuccessRate??en.successRate,remaining:en.needResend,"
    "skipped:en.skippedAlreadyPosted}:{groups:sn||en.progressMax,sent:Vn,failed:Ue,"
    "successRate:Vs,remaining:vr,skipped:gn},"
    "[R,sn,en.progressMax,en.success,en.failed,en.successRate,en.averageSuccessRate,"
    "en.needResend,en.skippedAlreadyPosted,Vn,Ue,Vs,vr,gn]);"
)


def patch_bundle(text: str) -> str:
    if BR_AVG_OLD in text and "averageSuccessRate:_avgRate" not in text:
        text = text.replace(BR_AVG_OLD, BR_AVG_NEW, 1)
        text = text.replace(BR_RETURN_OLD, BR_RETURN_NEW, 1)
        print("Patched BR (averageSuccessRate)")
    elif "averageSuccessRate:_avgRate" in text:
        print("BR already has averageSuccessRate")
    else:
        raise SystemExit("Could not find BR successRate block")

    if NF_FLEET_OLD in text:
        text = text.replace(NF_FLEET_OLD, NF_FLEET_NEW, 1)
        print("Patched nf useMemo (use averageSuccessRate)")
    elif "en.averageSuccessRate??en.successRate" in text:
        print("nf already uses averageSuccessRate")
    else:
        raise SystemExit("Could not find nf fleet block")

    return text


def main() -> None:
    bundle = patch_bundle(LOCAL_BUNDLE.read_text(encoding="utf-8", errors="replace"))
    LOCAL_BUNDLE.write_text(bundle, encoding="utf-8")
    print(f"Wrote bundle ({len(bundle)} chars)")

    sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
    sftp = client.open_sftp()

    for rel in ("App.jsx", "utils/globalStats.js"):
        local = SRC / rel
        remote = f"{ROOT}/dashboard/src/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        print(f"Uploaded {rel}")

    sftp.put(str(LOCAL_BUNDLE), f"{ROOT}/static/assets/app-BkUk1ts9.js")
    print("Uploaded app-BkUk1ts9.js")

    sftp.close()
    client.close()
    print("Done — hard-refresh https://teleautomation.online (Ctrl+Shift+R)")


if __name__ == "__main__":
    main()
