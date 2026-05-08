"""
web/server.py — FastAPI entry point for the Miktos web cockpit.

Usage (separate terminal, before or after run_session.py):
    cd "/Users/atorrella/Desktop/Miktos Agentic System"
    .venv/bin/python -m web.server
        -- OR --
    .venv/bin/python web/server.py

Then open: http://localhost:8000
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path when this file is run directly
# (i.e. `python web/server.py`).  Has no effect when run as a module.
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")  # must run before any PearlClient instantiation

import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import HTMLResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402

from fastapi.responses import RedirectResponse  # noqa: E402

from web.api import (  # noqa: E402
    action_log,
    adapters,
    audio_control,
    auth as auth_api,
    captions,
    graphics,
    health,
    onboarding,
    pearl,
    preview,
    rehearsal,
    runner,
    runofshow,
    safe_mode,
    session,
    status,
    switcher,
    templates as templates_api,
)

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Miktos Web Cockpit", version="0.1.0")

# Static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

import hashlib as _hashlib

# Templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")
# Expose AUTH_ENABLED to every template as a global so base.html can render
# the logout button without repeating the env-var lookup in every view.
templates.env.globals["auth_enabled"] = auth_api.AUTH_ENABLED

# Cache-busting version string for style.css — derived from the file's
# content hash so the browser fetches a fresh copy whenever CSS changes.
_css_path = BASE_DIR / "static" / "style.css"
_css_hash = _hashlib.md5(_css_path.read_bytes()).hexdigest()[:8]
templates.env.globals["css_version"] = _css_hash

# API routers
app.include_router(session.router, prefix="/api/session")
app.include_router(session.sessions_router, prefix="/api/sessions")
app.include_router(runner.router, prefix="/api/session")
app.include_router(status.router, prefix="/api/status")
app.include_router(pearl.router, prefix="/api/pearl")
app.include_router(onboarding.api_router, prefix="/api/onboarding")
app.include_router(onboarding.view_router, prefix="/onboarding")
app.include_router(switcher.router, prefix="/api/switcher")
app.include_router(health.router, prefix="/api/health")
app.include_router(audio_control.router, prefix="/api/audio")
app.include_router(captions.router, prefix="/api/captions")
app.include_router(preview.router, prefix="/api/preview")
app.include_router(graphics.router, prefix="/api/graphics")
app.include_router(adapters.router, prefix="/api/adapters")
app.include_router(action_log.router, prefix="/api/action_log")
app.include_router(safe_mode.router, prefix="/api/safe_mode")
app.include_router(runofshow.router, prefix="/api/runofshow")
app.include_router(rehearsal.router, prefix="/api/rehearsal")
app.include_router(templates_api.router, prefix="/api/templates")
app.include_router(auth_api.router)  # /login, /logout at root


# ---------------------------------------------------------------------------
# Auth middleware — runs before every request when AUTH_ENABLED=true.
# When AUTH_ENABLED=false this is a sub-millisecond no-op.
# ---------------------------------------------------------------------------


@app.middleware("http")
async def require_auth(request: Request, call_next):  # type: ignore[no-untyped-def]
    if not auth_api.auth_check(request):
        return RedirectResponse("/login")
    return await call_next(request)


# ---------------------------------------------------------------------------
# Docker health-check endpoint (always public)
# ---------------------------------------------------------------------------


@app.get("/health-check")
async def health_check() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@app.get("/", response_class=RedirectResponse)
async def root_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(url="/home", status_code=302)


@app.get("/home", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="home.html")


@app.get("/produce", response_class=HTMLResponse)
async def produce(request: Request) -> HTMLResponse:
    creds = onboarding.check_credentials()
    missing_credentials = not all([
        creds["youtube_client"],
        creds["youtube_en"],
        creds["youtube_fr"],
        creds["translate"],
        creds["elevenlabs"],
        creds["hardware"],
    ])
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"missing_credentials": missing_credentials},
    )


@app.get("/diagnostics", response_class=HTMLResponse)
async def diagnostics(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="diagnostics.html")


@app.get("/index", response_class=RedirectResponse)
async def index_legacy(request: Request) -> RedirectResponse:
    """Legacy /index alias — redirects to /produce."""
    return RedirectResponse(url="/produce", status_code=302)


@app.get("/setup", response_class=HTMLResponse)
async def setup(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="setup.html")


@app.get("/sessions", response_class=HTMLResponse)
async def sessions_view(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="sessions.html")


@app.get("/sessions/{name}", response_class=HTMLResponse)
async def session_report(request: Request, name: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="report.html", context={"session_name": name}
    )


# ---------------------------------------------------------------------------
# HTMX panel partials (Phase 14)
# ---------------------------------------------------------------------------


@app.get("/panels/switcher", response_class=HTMLResponse)
async def panel_switcher(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_switcher.html")


@app.get("/panels/health", response_class=HTMLResponse)
async def panel_health(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_health.html")


@app.get("/panels/audio", response_class=HTMLResponse)
async def panel_audio(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_audio.html")


@app.get("/panels/captions", response_class=HTMLResponse)
async def panel_captions(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_captions.html")


@app.get("/panels/preview", response_class=HTMLResponse)
async def panel_preview(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_preview.html")


@app.get("/panels/graphics", response_class=HTMLResponse)
async def panel_graphics(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_graphics.html")


@app.get("/panels/action_log", response_class=HTMLResponse)
async def panel_action_log(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_action_log.html")


@app.get("/panels/safe_mode", response_class=HTMLResponse)
async def panel_safe_mode(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_safe_mode.html")


@app.get("/panels/runofshow", response_class=HTMLResponse)
async def panel_runofshow(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_runofshow.html")


@app.get("/panels/rehearsal", response_class=HTMLResponse)
async def panel_rehearsal(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_rehearsal.html")


@app.get("/panels/channels", response_class=HTMLResponse)
async def panel_channels(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="panel_channels.html")



if __name__ == "__main__":
    uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=True)
