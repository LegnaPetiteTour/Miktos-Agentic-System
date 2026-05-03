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

import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402

from web.api import (  # noqa: E402
    action_log,
    adapters,
    audio_control,
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

# Templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")

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


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=True)
