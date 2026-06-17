"""Log out one account slot on the VPS (keeps session cleanup server-side)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = os.environ.get("VPS_HOST", "127.0.0.1")
PORT = int(os.environ.get("VPS_API_PORT", "8000"))
SLOT = (sys.argv[1] if len(sys.argv) > 1 else "account11").strip()


def main() -> int:
    url = f"http://{HOST}:{PORT}/login/logout"
    body = json.dumps({"slot": SLOT}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            data = json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        data = json.loads(e.read().decode() or "{}")
        print(json.dumps(data, indent=2))
        return 1
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 1
    print(json.dumps(data, indent=2))
    return 0 if data.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
