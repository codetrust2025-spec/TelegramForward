"""No backend route may answer anonymously by accident.

`is_spa_shell_request` used to decide "is this the SPA or the API?" from a
hand-maintained `_API_ROOTS` set, and it failed *open*: a first path segment
nobody had listed was taken for a client-side route, so the auth middleware
waved the GET through and the real API route answered it without a session.
That is how /payments, /bgv, /company-expenses and /forward-message all became
anonymously readable.

API roots are now derived from the routes the app actually registers, so the
default is closed. These tests hold that line.
"""

import pytest
from fastapi.routing import APIRoute

from core.dashboard_auth_vps import (
    _API_ROOTS,
    api_roots,
    is_public_path,
    is_spa_shell_request,
    register_api_roots,
)

# Anonymous on purpose: the login screen, health checks, the public booking
# boundary, call-join links and static assets. Each is listed in _PUBLIC_EXACT
# or _PUBLIC_PREFIXES, which is_public_path consults before anything else.
PUBLIC_BY_DESIGN = {
    "/auth/login",
    "/auth/status",
    "/health",
    "/bookings/confirm",
    "/public/anything",
    "/call/join/abc123",
    "/assets/app.js",
}

# Roots whose whole purpose is anonymous access; they must stay reachable.
PUBLIC_ROOT_PATHS = {"privacy", "terms", "oauth-home"}


@pytest.fixture(scope="module")
def app():
    import server

    return server.app


def _api_routes(app):
    for route in app.routes:
        if isinstance(route, APIRoute):
            yield route


def _route_guards(route):
    names = []
    for dep in route.dependant.dependencies:
        fn = getattr(dep, "call", None)
        name = getattr(fn, "__name__", "") if fn else ""
        if any(token in name for token in ("require", "admin", "auth")):
            names.append(name)
    return names


# ── the specific holes that were found in production ────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/payments/reconciliation",
        "/payments/reconciliation.csv",
        "/bgv/dashboard",
        "/bgv/cases",
        "/company-expenses",
        "/company-expenses/total",
        "/forward-message/settings",
        "/referrers",
        "/shutdown/clear-all",
        "/start-test",
    ],
)
def test_sensitive_paths_are_not_mistaken_for_spa_routes(app, path):
    register_api_roots(app)
    assert is_spa_shell_request("GET", path) is False, (
        f"{path} is treated as a client-side route, so the auth middleware "
        "lets an anonymous GET through and the API answers it"
    )


def test_financial_read_routes_carry_their_own_guard(app):
    """Defence in depth: these must not depend on the middleware alone, so that
    they stay protected even if the SPA/API split is ever got wrong again."""
    register_api_roots(app)
    required = {
        "/company-expenses",
        "/company-expenses/total",
        "/forward-message/settings",
    }
    unguarded = []
    for route in _api_routes(app):
        if route.path in required and not _route_guards(route):
            unguarded.append(f"{sorted(route.methods - {'HEAD', 'OPTIONS'})} {route.path}")
    assert unguarded == [], f"no route-level authorization: {unguarded}"


# ── the invariant that keeps it from happening again ────────────────────────


def test_a_new_api_root_is_protected_without_anyone_listing_it(app):
    """The point of the refactor. A router mounted under a brand-new root must
    be closed by default, not open until someone remembers the allowlist."""
    from fastapi import APIRouter, FastAPI

    probe = FastAPI()
    router = APIRouter()

    @router.get("/totally-new-root/secrets")
    async def _secrets():  # pragma: no cover - never called
        return {"secret": True}

    probe.include_router(router)

    assert "totally-new-root" not in _API_ROOTS
    register_api_roots(probe)
    assert is_spa_shell_request("GET", "/totally-new-root/secrets") is False


def test_every_registered_api_root_is_known(app):
    register_api_roots(app)
    known = api_roots()
    missing = sorted(
        {
            route.path.strip("/").split("/")[0]
            for route in _api_routes(app)
            if route.path.strip("/") and not route.path.strip("/").startswith("{")
        }
        - known
    )
    assert missing == [], f"registered but unknown to the auth layer: {missing}"


# ── the SPA and the genuinely public surface must still work ────────────────


def test_the_spa_shell_still_loads_for_anonymous_visitors(app):
    register_api_roots(app)
    # Without these the login page itself cannot be fetched.
    assert is_spa_shell_request("GET", "/") is True
    for client_route in ("/submit-slot", "/dashboard", "/candidates-ui"):
        assert is_spa_shell_request("GET", client_route) is True, client_route


@pytest.mark.parametrize("path", sorted(PUBLIC_BY_DESIGN))
def test_public_paths_stay_public(app, path):
    register_api_roots(app)
    assert is_public_path(path) is True
    assert is_spa_shell_request("GET", path) is True


@pytest.mark.parametrize("root", sorted(PUBLIC_ROOT_PATHS))
def test_public_pages_stay_reachable(app, root):
    register_api_roots(app)
    # These are real routes, so registration now classifies them as API roots.
    # They must still be served anonymously, which is_public_path decides.
    assert is_spa_shell_request("GET", f"/{root}") or is_public_path(f"/{root}"), (
        f"/{root} is meant to be readable without an account"
    )


def test_write_methods_are_never_treated_as_spa_navigation(app):
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert is_spa_shell_request(method, "/anything-at-all") is False
