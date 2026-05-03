"""web/api/auth.py — Single-password JWT auth for the cockpit.

Guards the entire cockpit when AUTH_ENABLED=true.
When AUTH_ENABLED=false (default) every check is a no-op, so existing
behaviour is **identical** and no existing tests are affected.

Env vars (read once at import time, not inside functions):
  AUTH_ENABLED         — "true"/"false"  (default: "false")
  AUTH_PASSWORD        — shared cockpit password
  JWT_SECRET           — signing key  (auto-generated in-process if missing)
  JWT_EXPIRE_MINUTES   — token lifetime in minutes  (default: 480 = 8 h)

Public API consumed by web/server.py:
  router               — FastAPI router with /login and /logout
  auth_check(request)  — returns True when request is allowed through
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import jwt  # PyJWT >= 2.8
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

if TYPE_CHECKING:
    pass

# ── Configuration ──────────────────────────────────────────────────────────
AUTH_ENABLED: bool = os.environ.get("AUTH_ENABLED", "false").strip().lower() == "true"

_AUTH_PASSWORD: str = os.environ.get("AUTH_PASSWORD", "")

# Generate a per-process secret when JWT_SECRET is not set.
# This means sessions are invalidated on restart — acceptable for local use.
# Production deployments should set JWT_SECRET in .env.
_JWT_SECRET: str = os.environ.get("JWT_SECRET", "") or secrets.token_hex(32)

_ALGORITHM = "HS256"
_COOKIE = "miktos_token"
_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))

# ── Helpers ────────────────────────────────────────────────────────────────

def _make_token() -> str:
    """Create a signed JWT valid for _EXPIRE_MINUTES."""
    exp = datetime.now(tz=timezone.utc) + timedelta(minutes=_EXPIRE_MINUTES)
    return jwt.encode({"sub": "cockpit", "exp": exp}, _JWT_SECRET, algorithm=_ALGORITHM)


def _verify_token(token: str) -> bool:
    """Return True if token is a valid, unexpired cockpit JWT."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])
        return payload.get("sub") == "cockpit"
    except jwt.PyJWTError:
        return False


# ── Public auth check (used by server middleware) ──────────────────────────

# Paths that are always public regardless of AUTH_ENABLED
_PUBLIC_PATHS: tuple[str, ...] = (
    "/login",
    "/logout",
    # Static assets — needed so the login page can load CSS/JS
    "/static/",
    # Rehearsal always bypasses auth (as per spec)
    "/api/rehearsal",
    # Health-check endpoint used by Docker HEALTHCHECK
    "/health-check",
)


def auth_check(request: Request) -> bool:  # noqa: D401
    """Return True when the request is permitted.

    When AUTH_ENABLED is False, always returns True.
    When AUTH_ENABLED is True, checks the JWT cookie.
    Requests whose path starts with a public prefix are always permitted.
    """
    if not AUTH_ENABLED:
        return True

    path = request.url.path
    for prefix in _PUBLIC_PATHS:
        if path.startswith(prefix):
            return True

    token = request.cookies.get(_COOKIE, "")
    return _verify_token(token)


# ── Router ─────────────────────────────────────────────────────────────────

router = APIRouter(tags=["auth"])


def _get_templates():  # noqa: ANN201
    """Return the server's Jinja2Templates instance (lazy import to avoid circular)."""
    from web.server import templates  # noqa: PLC0415

    return templates


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Serve the login form.  Redirect to / if already authenticated."""
    if not AUTH_ENABLED:
        return RedirectResponse("/")  # type: ignore[return-value]
    # Check cookie directly (not auth_check, which marks /login as public)
    token = request.cookies.get(_COOKIE, "")
    if _verify_token(token):
        return RedirectResponse("/")  # type: ignore[return-value]
    return _get_templates().TemplateResponse(
        request=request, name="login.html", context={"error": None}
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    password: str = Form(...),
) -> Response:
    """Validate the shared password and set the JWT cookie on success."""
    if not AUTH_ENABLED:
        return RedirectResponse("/", status_code=303)

    if not _AUTH_PASSWORD:
        # Misconfiguration: AUTH_ENABLED=true but no password set
        return _get_templates().TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Server misconfiguration: AUTH_PASSWORD not set."},
            status_code=500,
        )

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(password, _AUTH_PASSWORD):
        return _get_templates().TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid password."},
            status_code=401,
        )

    token = _make_token()
    response: Response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        key=_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=_EXPIRE_MINUTES * 60,
        # secure=True should be set in production behind TLS
    )
    return response


@router.post("/logout")
async def logout() -> Response:
    """Clear the auth cookie and redirect to /login."""
    response: Response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(_COOKIE, httponly=True, samesite="lax")
    return response
