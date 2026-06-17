#!/usr/bin/env python3
"""Configure campaign vs forwarding from output-based logic + clear shutdown + restart workers."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

from core.account_info_store import load_account_info
from core.account_shutdown import clear_all_shutdowns
from core.message_store import save_message_for_account
from core.posting_mode import set_forwarding_source, set_posting_mode

PHONE = "9000000001"
WA = "https://wa.me/919000000001"
FOOTER = f"""
⚠️ Serious only

📞 {PHONE}
💬 {WA}
"""

MSG_POWER_BI = f"""🔥 Power BI Developer | Data Analyst
💼 Interview Support — Calls to Offer

Still waiting for interview calls? 👇

✅ ATS Resume + Naukri (Power BI · Analyst roles)
✅ Power BI · SQL · DAX · Dashboard prep
✅ Technical + client rounds — cleared with you
✅ Non-IT · Gap · Bench · Fresher — supported
✅ 3 months help after you join
✅ BGV + counter-offer tips

🏆 100+ placed | 💯 No result → No pay
{FOOTER}"""

MSG_REACT = f"""🔥 React JS Developer | Frontend Engineer
💼 Interview Support — Calls to Offer

Still waiting for interview calls? 👇

✅ ATS Resume + Naukri (React JS · Frontend roles)
✅ React · JavaScript · TypeScript · Redux · Next.js prep
✅ Technical + client rounds — cleared with you
✅ Non-IT · Gap · Bench · Fresher — supported
✅ 3 months help after you join
✅ BGV + counter-offer tips

🏆 100+ placed | 💯 No result → No pay
{FOOTER}"""

MSG_MERN = f"""🔥 MERN Stack Developer | Full Stack Engineer
💼 Interview Support — Calls to Offer

Still waiting for interview calls? 👇

✅ ATS Resume + Naukri (MERN stack · Full Stack roles)
✅ MERN stack · MongoDB · Express · React · Node.js · REST APIs prep
✅ Technical + client rounds — cleared with you
✅ Non-IT · Gap · Bench · Fresher — supported
✅ 3 months help after you join
✅ BGV + counter-offer tips

🏆 100+ placed | 💯 No result → No pay
{FOOTER}"""

MSG_COMBINED = f"""🔥 Power BI | React JS | Data Analyst | MERN Stack
💼 Interview Support — Calls to Offer

Still waiting for interview calls? 👇

✅ ATS Resume + Naukri (Power BI · Analyst · React JS · MERN stack · Full Stack)
✅ Power BI · SQL · DAX · Dashboard prep
✅ React · JavaScript · TypeScript · Redux · Next.js prep
✅ MERN stack · MongoDB · Express · React · Node.js · REST APIs prep
✅ Technical + client rounds — cleared with you
✅ Non-IT · Gap · Bench · Fresher — supported
✅ 3 months help after you join
✅ BGV + counter-offer tips

🏆 100+ placed | 💯 No result → No pay
{FOOTER}"""

MSG_RESUME_OFFER = f"""🔥 Live Interview Support — Resume to Offer
💼 End-to-end Interview Support (till placement)

Not getting interview calls? We fix that.

✅ ATS Resume + Naukri Profile Optimization
✅ Interview, Coding & Client Round Clearance
✅ Non-IT · Gap · Bench · Fresher — supported
✅ 3 months help after you join
✅ BGV + counter-offer tips

🏆 100+ placed | 💯 No result → No pay
{FOOTER}"""

MESSAGES = {
    "power_bi": MSG_POWER_BI,
    "react": MSG_REACT,
    "mern": MSG_MERN,
    "combined": MSG_COMBINED,
    "resume_offer": MSG_RESUME_OFFER,
}

# Output-based routing (send history + last cycle + group health — not profile names)
# Forwarding: account9 recent posts | account6 campaign 19/19 fail | account1,2,4 blocked but forward history
# Campaign: account7 only 8 successes | account3,5 skip+cooling | account8 forward 19/19 fail | account10 has message
ACCOUNT_PLANS = {
    "account1": {"mode": "forwarding", "reason": "500 send history; groups blocked; forwarding built history"},
    "account2": {"mode": "forwarding", "reason": "500 send history; groups blocked; forwarding mode in use"},
    "account3": {"mode": "campaign", "message": "react", "reason": "0 fail 13 skip; 23 cooling groups"},
    "account4": {"mode": "forwarding", "reason": "500 send history; groups blocked; forwarding mode in use"},
    "account5": {"mode": "campaign", "message": "mern", "reason": "0 fail 7 skip; 28 cooling groups"},
    "account6": {"mode": "forwarding", "reason": "campaign last cycle 19/19 failed — switch"},
    "account7": {"mode": "campaign", "message": "combined", "reason": "only account with last_cycle success=8"},
    "account8": {"mode": "campaign", "message": "combined", "reason": "forwarding 19/19 failed; needs message"},
    "account9": {"mode": "forwarding", "reason": "only active poster Jun 6; 500 events"},
    "account10": {"mode": "campaign", "message": "resume_offer", "reason": "500 sends + message.txt + Jun 5 last post"},
}

FORWARD_PEER = "@jobsupport0"
FORWARD_MSG_ID = 161879
API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")


def configure_accounts() -> list[str]:
    configured: list[str] = []
    for slot, plan in ACCOUNT_PLANS.items():
        info = load_account_info(slot)
        if not info or not info.get("phone"):
            print(f"SKIP {slot}: not logged in")
            continue
        mode = plan["mode"]
        set_posting_mode(slot, mode)
        if mode == "campaign":
            key = plan.get("message") or "combined"
            save_message_for_account(slot, MESSAGES[key])
            print(f"CONFIG {slot}: campaign ({key}) — {plan.get('reason', '')}")
        else:
            set_forwarding_source(
                slot,
                source_peer=FORWARD_PEER,
                source_message_id=FORWARD_MSG_ID,
            )
            print(f"CONFIG {slot}: forwarding ({FORWARD_PEER}/{FORWARD_MSG_ID}) — {plan.get('reason', '')}")
        configured.append(slot)
    cleared = clear_all_shutdowns()
    print(f"Cleared shutdown entries: {cleared}")
    return configured


class ApiClient:
    def __init__(self) -> None:
        self.cookie: str | None = None

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None
        headers = {"Content-Type": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        if self.cookie:
            headers["Cookie"] = self.cookie
        req = urllib.request.Request(
            f"{API_BASE}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                set_cookie = resp.headers.get("Set-Cookie")
                if set_cookie and "ta_session=" in set_cookie:
                    self.cookie = set_cookie.split(";")[0]
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw.strip() else {"detail": str(e)}
            except json.JSONDecodeError:
                payload = {"detail": raw or str(e)}
            payload["http_status"] = e.code
            return payload

    def login(self) -> bool:
        user = os.environ.get("DASHBOARD_USERNAME", "admin")
        password = os.environ.get("DASHBOARD_PASSWORD", "")
        if not password:
            print("WARN: DASHBOARD_PASSWORD not set — skip API start")
            return False
        out = self._request(
            "POST",
            "/auth/login",
            {"username": user, "password": password},
        )
        ok = out.get("status") == "ok" or out.get("username")
        print("LOGIN:", "ok" if ok else out)
        return bool(ok)

    def stop(self, slot: str) -> dict:
        return self._request("POST", f"/account/{slot}/stop")

    def start(self, slot: str, feature: str) -> dict:
        return self._request("POST", f"/account/{slot}/start?feature={feature}")


def start_accounts(slots: list[str]) -> None:
    api = ApiClient()
    if not api.login():
        return
    for slot in slots:
        plan = ACCOUNT_PLANS[slot]
        feature = plan["mode"]
        stop_out = api.stop(slot)
        print(f"STOP {slot}:", json.dumps(stop_out, ensure_ascii=False))
        time.sleep(2)
        out = api.start(slot, feature)
        print(f"START {slot} ({feature}):", json.dumps(out, ensure_ascii=False))
        time.sleep(4)


def verify() -> None:
    from core.posting_mode import load_posting_mode

    for slot in ACCOUNT_PLANS:
        info = load_account_info(slot)
        if not info:
            continue
        pm = load_posting_mode(slot)
        print(
            f"{slot}: mode={pm.mode} campaign={pm.campaign_enabled} "
            f"forwarding={pm.forwarding_enabled} "
            f"display={info.get('display_name')}"
        )


def main() -> None:
    slots = configure_accounts()
    if not slots:
        print("No accounts configured")
        sys.exit(1)
    start_accounts(slots)
    print("\n=== VERIFY ===")
    verify()


if __name__ == "__main__":
    main()
