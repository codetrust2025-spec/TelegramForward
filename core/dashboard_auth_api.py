"""Dashboard auth HTTP routes + middleware (TeleAutomation login & admin gate)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core import dashboard_auth as auth


def _json(payload: dict[str, Any], status: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status)


def _set_session_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key=auth.SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=auth.SESSION_TTL_SEC,
        path="/",
    )


def install_dashboard_auth(app: FastAPI) -> None:
    """Register /auth/* routes and optional session middleware."""

    @app.get("/auth/status")
    async def auth_status(request: Request):
        if not auth.auth_enabled():
            return {
                "enabled": False,
                "authenticated": True,
                "username": "dev",
                "role": "admin",
                "reference": None,
            }
        profile = auth.operator_profile_from_cookies(dict(request.cookies))
        username = profile.get("username")
        return {
            "enabled": True,
            "authenticated": bool(username),
            "username": username,
            "role": profile.get("role") or "admin",
            "reference": profile.get("reference"),
        }

    @app.post("/auth/login")
    async def auth_login(request: Request, body: dict | None = None):
        payload = body or {}
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        if not auth.auth_enabled():
            return {"username": "dev", "role": "admin", "reference": None}

        profile = auth.resolve_operator_login(username, password)
        if not profile:
            return _json({"detail": "Invalid username or password"}, status=401)

        token = auth.create_session_token(
            profile["username"],
            role=profile.get("role") or "admin",
            reference=profile.get("reference"),
        )
        resp = _json(
            {
                "status": "ok",
                "username": profile["username"],
                "role": profile.get("role") or "admin",
                "reference": profile.get("reference"),
            }
        )
        _set_session_cookie(resp, token)
        return resp

    @app.post("/auth/logout")
    async def auth_logout():
        resp = _json({"status": "ok"})
        resp.delete_cookie(auth.SESSION_COOKIE, path="/")
        return resp

    @app.post("/auth/verify-admin")
    async def auth_verify_admin(body: dict | None = None):
        """Re-check admin password for sensitive UI (handler payouts, etc.)."""
        payload = body or {}
        password = str(payload.get("password") or "")
        if not auth.auth_enabled():
            return {"status": "ok", "verified": True}

        expected_user, expected_pass = auth.get_credentials()
        if not expected_pass:
            return {"status": "ok", "verified": True}
        if not password:
            return _json({"detail": "Password required"}, status=400)
        import secrets

        if secrets.compare_digest(password, expected_pass):
            return {"status": "ok", "verified": True}
        return _json({"detail": "Incorrect password"}, status=401)

    @app.post("/auth/change-password")
    async def auth_change_password(request: Request, body: dict | None = None):
        """Logged-in handlers can update their dashboard password."""
        if not auth.auth_enabled():
            return {"status": "ok", "message": "Auth disabled — no password to change"}

        profile = auth.operator_profile_from_cookies(dict(request.cookies))
        if not profile.get("username"):
            return _json({"detail": "Authentication required"}, status=401)
        if profile.get("role") != "handler":
            return _json({"detail": "Only referrer/handler logins can change password here"}, status=403)

        payload = body or {}
        err = auth.change_handler_password(
            profile["username"],
            str(payload.get("current_password") or ""),
            str(payload.get("new_password") or ""),
        )
        if err:
            return _json({"detail": err}, status=400)
        return {"status": "ok", "message": "Password updated"}

    @app.post("/auth/reset-password")
    async def auth_reset_password(body: dict | None = None):
        """Forgot password — reset with username + reference (referrer name)."""
        if not auth.auth_enabled():
            return _json({"detail": "Auth is disabled on this server"}, status=400)

        payload = body or {}
        err = auth.reset_handler_password_forgot(
            str(payload.get("username") or ""),
            str(payload.get("reference") or ""),
            str(payload.get("new_password") or ""),
        )
        if err:
            return _json({"detail": err}, status=400)
        return {"status": "ok", "message": "Password reset — you can sign in now"}

    class DashboardAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            from core.dashboard_access import is_ops_request_authorized

            path = request.url.path
            if not auth.auth_enabled():
                return await call_next(request)
            if auth.is_public_path(path):
                return await call_next(request)
            if is_ops_request_authorized(request) and path.startswith("/ai/smart-reply/"):
                return await call_next(request)
            if (
                is_ops_request_authorized(request)
                and request.method.upper() == "POST"
                and path.startswith("/inbox/")
                and "/sync/" in path
            ):
                return await call_next(request)
            if auth.is_spa_shell_request(request.method, path):
                return await call_next(request)
            if auth.username_from_request_cookies(dict(request.cookies)):
                return await call_next(request)
            return _json({"detail": "Authentication required"}, status=401)

    app.add_middleware(DashboardAuthMiddleware)
