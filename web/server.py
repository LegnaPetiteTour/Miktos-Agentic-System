"""
web/server.py — FastAPI entry point for the Miktos web cockpit.

Usage (separate terminal, before or after run_session.py):
    cd "/Users/atorrella/Desktop/Miktos Agentic System"
    .venv/bin/python web/server.py

Then open: http://localhost:8000
"""

from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.api import pearl, session, status

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Miktos Web Cockpit", version="0.1.0")

# Static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# API routers
app.include_router(session.router, prefix="/api/session")
app.include_router(session.sessions_router, prefix="/api/sessions")
app.include_router(status.router, prefix="/api/status")
app.include_router(pearl.router, prefix="/api/pearl")


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=True)
