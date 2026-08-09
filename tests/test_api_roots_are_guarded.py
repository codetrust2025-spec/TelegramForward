"""Every mounted API root must be known to the auth middleware.

`is_spa_shell_request` treats any path whose first segment is not in
`_API_ROOTS` as a client-side route and lets the request through unauthenticated.
The real API route then answers it. So an API root that nobody remembers to add
to that set silently serves data without a session — which is how
/payments/reconciliation and /bgv/dashboard came to return full financial JSON
to an anonymous caller.
"""

import pytest

from core.dashboard_auth_vps import _API_ROOTS, is_spa_shell_request

# Public by design: legal pages, the OAuth landing page, and call-join links
# reached by people who have no dashboard account.
INTENTIONALLY_PUBLIC = {"privacy", "terms", "oauth-home", "call"}

# Pre-existing debt, recorded so it stays visible and cannot grow. These are NOT
# approved as public — each answers without a session today. Two of them are also
# proxied by nginx, which makes them reachable from the internet:
#
#   company-expenses   5 routes, proxied  -> publicly readable
#   forward-message    2 routes, proxied  -> publicly readable
#
# The rest are not in the nginx proxy list, so they are only reachable on the
# host itself. Guarding them is a separate change: adding a root here without
# checking its callers can log people out of a working screen.
KNOWN_UNGUARDED = {
    "company-expenses",
    "forward-message",
    "referrers",
    "referrer-payment-accounts",
    "shutdown",
    "start-test",
}


def _api_roots_from_app():
    import server
    from fastapi.routing import APIRoute

    roots = set()
    for route in server.app.routes:
        if not isinstance(route, APIRoute):
            continue
        stripped = route.path.strip("/")
        if not stripped:
            continue
        first = stripped.split("/")[0]
        if first.startswith("{"):
            continue
        roots.add(first)
    return roots


def test_payments_and_bgv_require_a_session():
    for path in (
        "/payments/reconciliation",
        "/payments/reconciliation.csv",
        "/bgv/dashboard",
        "/bgv/cases",
    ):
        assert is_spa_shell_request("GET", path) is False, (
            f"{path} is treated as an SPA route, so the auth middleware waves it "
            "through and the API answers anonymously"
        )


def test_a_real_client_side_route_is_still_served_without_a_session():
    # The SPA shell must keep working for anonymous visitors, or the login page
    # itself cannot load.
    assert is_spa_shell_request("GET", "/") is True
    assert is_spa_shell_request("GET", "/submit-slot") is True


def test_no_new_api_root_becomes_accidentally_public():
    unguarded = (
        _api_roots_from_app() - set(_API_ROOTS) - INTENTIONALLY_PUBLIC - KNOWN_UNGUARDED
    )
    assert sorted(unguarded) == [], (
        "These API roots bypass the auth middleware entirely, so they answer "
        "without a session. Add each to _API_ROOTS, or to INTENTIONALLY_PUBLIC "
        f"with a reason: {sorted(unguarded)}"
    )


def test_the_known_unguarded_list_does_not_go_stale():
    """If a root here gets guarded, drop it from the list rather than leaving a
    fixed problem recorded as outstanding."""
    still_unguarded = KNOWN_UNGUARDED & (_api_roots_from_app() - set(_API_ROOTS))
    assert still_unguarded == KNOWN_UNGUARDED, (
        "Now guarded, so remove from KNOWN_UNGUARDED: "
        f"{sorted(KNOWN_UNGUARDED - still_unguarded)}"
    )
