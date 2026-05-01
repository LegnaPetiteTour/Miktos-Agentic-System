"""
web/api/onboarding.py — Phase 12 operator onboarding wizard.

Routers exported:
    api_router   — mounted at /api/onboarding  (JSON endpoints)
    view_router  — mounted at /onboarding      (HTML views + YouTube OAuth)

Public helpers:
    write_env_key(key, value)  — atomic .env writer, never logs values
    read_env_keys()            — reads current .env state (values opaque)
    check_credentials()        — returns {key: bool} presence map
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import requests as _requests
import yaml
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from engine.paths import get_config_dir, get_env_path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENV_PATH = get_env_path()
_CONFIG_PATH = get_config_dir() / "session_config.yaml"
_BASE_DIR = Path(__file__).parent.parent
_templates = Jinja2Templates(directory=_BASE_DIR / "templates")

_YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
_YOUTUBE_REDIRECT_URI = "http://localhost:8000/onboarding/youtube/callback"

# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------


def write_env_key(key: str, value: str) -> None:
    """Atomically write or update a single key in .env.

    Safety rules (from spec):
    1. Read current .env into memory first.
    2. Parse line by line, preserving comments and blank lines.
    3. If key exists: replace that line only.
    4. If key does not exist: append at the end.
    5. Write atomically via temp file + rename.
    6. Never delete or modify keys that are not being updated.
    7. Never log or return the value.
    """
    lines: list[str] = []
    found = False

    if _ENV_PATH.exists():
        raw = _ENV_PATH.read_text(encoding="utf-8")
        for line in raw.splitlines(keepends=True):
            stripped = line.rstrip("\r\n")
            # Match lines of the form KEY=... or KEY= (even if value is empty)
            if stripped.startswith(f"{key}=") or stripped == key:
                lines.append(f"{key}={value}\n")
                found = True
            else:
                lines.append(line)

    if not found:
        # Ensure the file ends with a newline before appending
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"{key}={value}\n")

    # Atomic write: write to temp file in same dir, then rename
    tmp_fd, tmp_path = tempfile.mkstemp(dir=_ENV_PATH.parent, prefix=".env.tmp.")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.writelines(lines)
        os.replace(tmp_path, _ENV_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_env_keys() -> dict[str, str]:
    """Return a dict of key→value from .env. Values are not redacted here —
    callers must not log or expose them to clients."""
    if not _ENV_PATH.exists():
        return {}
    result: dict[str, str] = {}
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            k, _, v = stripped.partition("=")
            result[k.strip()] = v.strip()
    return result


def check_credentials() -> dict[str, Any]:
    """Return a presence map for all required credential keys.

    Returns:
        {
            youtube_client: bool,
            youtube_en: bool,
            youtube_fr: bool,
            translate: bool,
            elevenlabs: bool,
            hardware: str | None,   # "epiphan" | "obs" | None
        }
    """
    keys = read_env_keys()
    hardware: str | None = None
    if _CONFIG_PATH.exists():
        try:
            cfg = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
            hardware = cfg.get("hardware") or None
        except Exception:
            pass

    return {
        "youtube_client": bool(keys.get("YOUTUBE_CLIENT_ID"))
        and bool(keys.get("YOUTUBE_CLIENT_SECRET")),
        "youtube_en": bool(keys.get("YOUTUBE_REFRESH_TOKEN_EN")),
        "youtube_fr": bool(keys.get("YOUTUBE_REFRESH_TOKEN_FR")),
        "translate": bool(keys.get("GOOGLE_TRANSLATE_API_KEY")),
        "elevenlabs": bool(keys.get("ELEVENLABS_API_KEY")),
        "hardware": hardware,
    }


# ---------------------------------------------------------------------------
# session_config.yaml helper
# ---------------------------------------------------------------------------


def _read_config() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _write_config(data: dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _CONFIG_PATH.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True)


def _write_hardware_config(
    hardware_type: str,
    host: str,
    port: int,
    *,
    password: str = "",
) -> None:
    cfg = _read_config()
    cfg["hardware"] = hardware_type
    if hardware_type == "epiphan":
        cfg.setdefault("pearl", {})
        cfg["pearl"]["host"] = host
        cfg["pearl"]["port"] = port
    elif hardware_type == "obs":
        cfg.setdefault("obs", {})
        cfg["obs"]["host"] = host
        cfg["obs"]["port"] = port
        if password:
            cfg["obs"]["password"] = password
    _write_config(cfg)


# ---------------------------------------------------------------------------
# YouTube OAuth helpers
# ---------------------------------------------------------------------------


def _make_youtube_flow(client_id: str, client_secret: str) -> Any:
    """Build a google-auth-oauthlib web Flow for YouTube."""
    from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": [_YOUTUBE_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=_YOUTUBE_SCOPES,
        redirect_uri=_YOUTUBE_REDIRECT_URI,
    )


# ---------------------------------------------------------------------------
# Pydantic request bodies
# ---------------------------------------------------------------------------


class ApiKeyBody(BaseModel):
    api_key: str


class PearlBody(BaseModel):
    host: str
    port: int


class ObsBody(BaseModel):
    host: str
    port: int
    password: str = ""


class YoutubeClientBody(BaseModel):
    client_id: str
    client_secret: str


# ---------------------------------------------------------------------------
# API router — /api/onboarding/*
# ---------------------------------------------------------------------------

api_router = APIRouter()


@api_router.get("/status")
async def onboarding_status() -> JSONResponse:
    """Return credential presence map — no values exposed."""
    return JSONResponse(check_credentials())


@api_router.post("/youtube/client")
async def save_youtube_client(body: YoutubeClientBody) -> JSONResponse:
    """Save YouTube Client ID and Secret to .env."""
    if not body.client_id or not body.client_secret:
        return JSONResponse(
            {"success": False, "error": "client_id and client_secret are required"},
            status_code=400,
        )
    write_env_key("YOUTUBE_CLIENT_ID", body.client_id)
    write_env_key("YOUTUBE_CLIENT_SECRET", body.client_secret)
    return JSONResponse({"success": True, "error": None})


@api_router.post("/validate/translate")
async def validate_translate(body: ApiKeyBody) -> JSONResponse:
    """Validate a Google Translate API key; write to .env only on success."""
    try:
        resp = _requests.get(
            "https://translation.googleapis.com/language/translate/v2/languages",
            params={"key": body.api_key, "target": "en"},
            timeout=5,
        )
        resp.raise_for_status()
    except _requests.RequestException as exc:
        return JSONResponse({"success": False, "error": str(exc)})

    write_env_key("GOOGLE_TRANSLATE_API_KEY", body.api_key)
    return JSONResponse({"success": True, "error": None})


@api_router.post("/validate/elevenlabs")
async def validate_elevenlabs(body: ApiKeyBody) -> JSONResponse:
    """Validate an ElevenLabs API key; write to .env only on success."""
    try:
        resp = _requests.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": body.api_key},
            timeout=5,
        )
        resp.raise_for_status()
    except _requests.RequestException as exc:
        return JSONResponse({"success": False, "error": str(exc)})

    write_env_key("ELEVENLABS_API_KEY", body.api_key)
    return JSONResponse({"success": True, "error": None})


@api_router.post("/validate/pearl")
async def validate_pearl(body: PearlBody) -> JSONResponse:
    """Test Pearl connection; write hardware config only on success."""
    try:
        resp = _requests.get(
            f"http://{body.host}:{body.port}/api/channels",
            timeout=5,
        )
        resp.raise_for_status()
        firmware: str | None = resp.json().get("firmware") if resp.text else None
    except _requests.RequestException as exc:
        return JSONResponse({"success": False, "firmware": None, "error": str(exc)})
    except Exception:
        firmware = None

    _write_hardware_config("epiphan", body.host, body.port)
    return JSONResponse({"success": True, "firmware": firmware, "error": None})


@api_router.post("/validate/obs")
async def validate_obs(body: ObsBody) -> JSONResponse:
    """Test OBS WebSocket connection; write hardware config only on success."""
    try:
        import obsws_python as obs  # type: ignore[import-untyped]

        cl = obs.ReqClient(
            host=body.host,
            port=body.port,
            password=body.password,
            timeout=5,
        )
        version: str = cl.get_version().obs_version
        cl.disconnect()
    except Exception as exc:
        return JSONResponse({"success": False, "version": None, "error": str(exc)})

    _write_hardware_config("obs", body.host, body.port, password=body.password)
    return JSONResponse({"success": True, "version": version, "error": None})


# ---------------------------------------------------------------------------
# View router — /onboarding/*
# ---------------------------------------------------------------------------

view_router = APIRouter()


@view_router.get("", response_class=HTMLResponse)
@view_router.get("/", response_class=HTMLResponse)
async def onboarding_index(
    request: Request,
    step: str = "youtube",
    error: str = "",
    success: str = "",
) -> HTMLResponse:
    creds = check_credentials()
    return _templates.TemplateResponse(
        request=request,
        name="onboarding.html",
        context={
            "step": step,
            "creds": creds,
            "error": error,
            "success": success,
        },
    )


@view_router.get("/step/youtube", response_class=HTMLResponse)
async def step_youtube(request: Request, error: str = "", success: str = "") -> HTMLResponse:
    creds = check_credentials()
    return _templates.TemplateResponse(
        request=request,
        name="onboarding_youtube.html",
        context={"creds": creds, "error": error, "success": success},
    )


@view_router.get("/step/translate", response_class=HTMLResponse)
async def step_translate(request: Request, error: str = "", success: str = "") -> HTMLResponse:
    creds = check_credentials()
    return _templates.TemplateResponse(
        request=request,
        name="onboarding_translate.html",
        context={"creds": creds, "error": error, "success": success},
    )


@view_router.get("/step/elevenlabs", response_class=HTMLResponse)
async def step_elevenlabs(request: Request, error: str = "", success: str = "") -> HTMLResponse:
    creds = check_credentials()
    return _templates.TemplateResponse(
        request=request,
        name="onboarding_elevenlabs.html",
        context={"creds": creds, "error": error, "success": success},
    )


@view_router.get("/step/hardware", response_class=HTMLResponse)
async def step_hardware(request: Request, error: str = "", success: str = "") -> HTMLResponse:
    creds = check_credentials()
    return _templates.TemplateResponse(
        request=request,
        name="onboarding_hardware.html",
        context={"creds": creds, "error": error, "success": success},
    )


@view_router.get("/step/ready", response_class=HTMLResponse)
async def step_ready(request: Request) -> HTMLResponse:
    creds = check_credentials()
    all_done = (
        creds["youtube_client"]
        and creds["youtube_en"]
        and creds["youtube_fr"]
        and creds["translate"]
        and creds["elevenlabs"]
        and bool(creds["hardware"])
    )
    return _templates.TemplateResponse(
        request=request,
        name="onboarding_ready.html",
        context={"creds": creds, "all_done": all_done},
    )


@view_router.get("/youtube/authorize")
async def youtube_authorize(channel: str = "") -> RedirectResponse:
    """Redirect to Google OAuth consent screen for the given channel."""
    if channel not in ("en", "fr"):
        return RedirectResponse("/onboarding?error=invalid_channel")

    keys = read_env_keys()
    client_id = keys.get("YOUTUBE_CLIENT_ID", "")
    client_secret = keys.get("YOUTUBE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return RedirectResponse("/onboarding?error=missing_youtube_client")

    try:
        flow = _make_youtube_flow(client_id, client_secret)
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=channel,
            prompt="consent",
        )
    except Exception as exc:
        return RedirectResponse(f"/onboarding?error={exc!s:.80}")

    return RedirectResponse(auth_url)


@view_router.get("/youtube/callback")
async def youtube_callback(
    code: str = "",
    state: str = "",
    error: str = "",
) -> RedirectResponse:
    """Handle Google OAuth callback, exchange code for refresh token, write .env."""
    if error:
        return RedirectResponse(f"/onboarding?error=oauth_{error}")

    if state not in ("en", "fr"):
        return RedirectResponse("/onboarding?error=invalid_state")

    if not code:
        return RedirectResponse("/onboarding?error=missing_code")

    keys = read_env_keys()
    client_id = keys.get("YOUTUBE_CLIENT_ID", "")
    client_secret = keys.get("YOUTUBE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return RedirectResponse("/onboarding?error=missing_youtube_client")

    try:
        flow = _make_youtube_flow(client_id, client_secret)
        flow.fetch_token(code=code)
        refresh_token = flow.credentials.refresh_token
    except Exception as exc:
        return RedirectResponse(f"/onboarding?error=oauth_exchange_{exc!s:.60}")

    if not refresh_token:
        return RedirectResponse("/onboarding?error=no_refresh_token")

    env_key = f"YOUTUBE_REFRESH_TOKEN_{state.upper()}"
    write_env_key(env_key, refresh_token)

    return RedirectResponse(f"/onboarding?success={state}_authorized")
