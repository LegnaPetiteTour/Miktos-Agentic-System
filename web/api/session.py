"""
web/api/session.py — /api/session/* endpoints + /api/sessions/* endpoints.

GET  /api/session/config            → returns session_config.yaml as JSON
POST /api/session/config            → validates required fields, writes yaml
GET  /api/sessions                  → named sessions, most recent 20
GET  /api/sessions/{name}/report    → inline _report.html content
"""

import re
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

router = APIRouter()

_CONFIG_PATH = Path("domains/streamlab_post/config/session_config.yaml")
_SESSIONS_DIR = Path("data/sessions")

_REQUIRED_FIELDS = {"event_name", "hardware"}
_UUID_RE = re.compile(r"^[0-9a-f]{12}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_config() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return {}
    with _CONFIG_PATH.open("r") as fh:
        return yaml.safe_load(fh) or {}


def _write_config(data: dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _CONFIG_PATH.open("w") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_config() -> JSONResponse:
    return JSONResponse(_read_config())


class ConfigUpdate(BaseModel):
    model_config = {"extra": "allow"}

    event_name: str | None = None
    hardware: str | None = None


@router.post("/config")
async def post_config(body: dict[str, Any]) -> JSONResponse:
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if not body.get(field):
            errors.append(f"'{field}' is required")

    if errors:
        return JSONResponse({"success": False, "errors": errors}, status_code=422)

    existing = _read_config()
    existing.update(body)
    _write_config(existing)
    return JSONResponse({"success": True, "errors": []})


# ---------------------------------------------------------------------------
# Session history endpoints  (also mounted under /api/sessions by server.py
# because the router is included with prefix /api/session — so we use a
# separate path prefix trick via a second include_router call in server.py
# or register these directly here.  server.py includes this router at
# /api/session, but we need /api/sessions.  We register an additional
# router below that server.py also includes.)
# ---------------------------------------------------------------------------

sessions_router = APIRouter()


def _list_named_sessions(limit: int = 20) -> list[dict]:
    if not _SESSIONS_DIR.exists():
        return []
    dirs = sorted(
        (
            d for d in _SESSIONS_DIR.iterdir()
            if d.is_dir() and not _UUID_RE.match(d.name)
        ),
        key=lambda d: d.name,
        reverse=True,
    )[:limit]

    hardware = _read_config().get("hardware")
    results = []
    for d in dirs:
        report_files = list(d.glob("*_report.html"))
        results.append({
            "name": d.name,
            "hardware": hardware,
            "has_report": bool(report_files),
        })
    return results


@sessions_router.get("")
async def list_sessions(limit: int = 20) -> JSONResponse:
    return JSONResponse(_list_named_sessions(limit))


@sessions_router.get("/{session_name}/report")
async def session_report(session_name: str) -> HTMLResponse:
    session_dir = _SESSIONS_DIR / session_name
    reports = list(session_dir.glob("*_report.html")) if session_dir.is_dir() else []
    if not reports:
        return HTMLResponse("<p>No report found for this session.</p>", status_code=404)
    return HTMLResponse(reports[0].read_text(encoding="utf-8"))
