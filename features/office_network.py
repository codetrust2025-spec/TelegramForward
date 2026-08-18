"""Is this request coming from the office network?

A browser cannot read the Wi-Fi SSID — there is no web API for it on any
browser — so "connected to office Wi-Fi" is only checkable as "arriving from an
approved public IP". That check has to happen on the server: anything the page
reports about itself is writable by whoever is sitting at the page.

The subtlety is ``X-Forwarded-For``. A client can send that header itself, so
trusting the leftmost entry would let anybody claim an office IP with one curl
flag. Only the hops appended by our own proxy are trustworthy, so we count in
from the right by the number of proxies actually in front of the app.
"""
from __future__ import annotations

import ipaddress

from features.attendance_config import load_config

VERIFIED = "verified"
NOT_ALLOWLISTED = "ip_not_allowlisted"
NO_ALLOWLIST = "allowlist_not_configured"
NO_CLIENT_IP = "client_ip_unavailable"


def peer_is_trusted_proxy(peer: object, trusted: list[str]) -> bool:
    """Whether the machine that opened this connection is one of our proxies."""
    address = _parse(peer)
    if address is None:
        return False
    return any(_matches(address, rule) for rule in trusted)


def client_ip(request, *, config: dict | None = None) -> str | None:
    """The caller's real IP.

    Two conditions before ``X-Forwarded-For`` is believed at all:

    1. The connection has to come *from* a proxy we trust. The app binds
       0.0.0.0:8000 on this host with no firewall, so it is reachable directly
       as well as through nginx. A request that skipped nginx carries whatever
       forwarding header its sender typed, and honouring that would let anyone
       claim an office IP with one curl flag — defeating the whole check.
    2. Then the entry is counted in from the *right* by the number of proxies
       actually in front, because nginx appends the peer it saw. Entries further
       left are client-supplied and are ignored.
    """
    cfg = config or load_config()
    hops = cfg["trusted_proxy_hops"]
    peer = getattr(getattr(request, "client", None), "host", None)
    peer_text = str(peer) if peer else None

    if hops > 0 and peer_is_trusted_proxy(peer_text, cfg["trusted_proxy_ips"]):
        forwarded = (request.headers.get("x-forwarded-for") or "").strip()
        if forwarded:
            chain = [part.strip() for part in forwarded.split(",") if part.strip()]
            if chain:
                index = max(0, len(chain) - hops)
                candidate = chain[index]
                if _parse(candidate) is not None:
                    return candidate

    return peer_text


def _parse(value: object):
    try:
        return ipaddress.ip_address(str(value).strip())
    except ValueError:
        return None


def _matches(address, rule: str) -> bool:
    rule = rule.strip()
    if not rule:
        return False
    try:
        if "/" in rule:
            return address in ipaddress.ip_network(rule, strict=False)
        return address == ipaddress.ip_address(rule)
    except ValueError:
        return False


def verify(request, *, config: dict | None = None) -> dict:
    """Decide whether this request is on the office network.

    Fails closed on every ambiguity: an unparseable IP, no allowlist configured,
    or no client address at all all come back unverified. An attendance record
    that cannot prove where it came from is worth less than no record.
    """
    cfg = config or load_config()
    allowlist = cfg["office_ip_allowlist"]
    ip_text = client_ip(request, config=cfg)

    if not ip_text:
        return {"verified": False, "ip": None, "reason": NO_CLIENT_IP, "matched_rule": None}

    address = _parse(ip_text)
    if address is None:
        return {"verified": False, "ip": ip_text, "reason": NO_CLIENT_IP, "matched_rule": None}

    if not allowlist:
        # No allowlist is not "everywhere is the office" — it is "we cannot tell".
        return {"verified": False, "ip": ip_text, "reason": NO_ALLOWLIST, "matched_rule": None}

    for rule in allowlist:
        if _matches(address, rule):
            return {"verified": True, "ip": ip_text, "reason": VERIFIED, "matched_rule": rule}

    return {"verified": False, "ip": ip_text, "reason": NOT_ALLOWLISTED, "matched_rule": None}


def failure_message(result: dict) -> str:
    """Wording shown to the employee when Start Work is blocked."""
    reason = (result or {}).get("reason")
    if reason == NO_ALLOWLIST:
        return (
            "Attendance cannot be recorded yet: the office network has not been "
            "configured. Ask an administrator to add the office public IP."
        )
    return "You must be connected to the office network to start your workday."
