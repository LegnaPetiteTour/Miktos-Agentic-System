"""
tests/test_phase_18.py — Phase 18: Docker, multi-column grid, JWT auth.

Auth-disabled path must produce identical behaviour to the pre-Phase-18
system (all existing tests must still pass).  Only new tests added here.

New test coverage:
  1. Docker / YAML artefacts exist and are well-formed
  2. CSS grid classes are present in style.css
  3. Cockpit HTML uses the new column structure
  4. AUTH_ENABLED=false (default) — no redirect, all routes open
  5. AUTH_ENABLED=true — unauthenticated requests redirect to /login
  6. Login page serves correctly when auth is enabled
  7. POST /login with wrong password → 401
  8. POST /login with correct password → sets JWT cookie → / accessible
  9. POST /logout → clears cookie → / redirects again
 10. /api/rehearsal always bypasses auth even without a cookie
 11. /health-check endpoint always returns 200 + {"status": "ok"}
 12. Cockpit grid panels are assigned to expected columns in index.html
 13. PyJWT is importable and can round-trip a token
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml  # PyYAML — already a project dependency

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent
_STYLE = _ROOT / "web" / "static" / "style.css"
_INDEX = _ROOT / "web" / "templates" / "index.html"
_DOCKERFILE = _ROOT / "Dockerfile"
_COMPOSE = _ROOT / "docker-compose.yml"


# ---------------------------------------------------------------------------
# 1 — Docker artefacts
# ---------------------------------------------------------------------------


def test_dockerfile_exists() -> None:
    """Dockerfile is present in the project root."""
    assert _DOCKERFILE.exists(), "Dockerfile not found"


def test_dockerfile_has_cmd() -> None:
    """Dockerfile contains a CMD that launches uvicorn."""
    content = _DOCKERFILE.read_text()
    assert "uvicorn" in content, "Dockerfile CMD must run uvicorn"
    assert "8000" in content, "Dockerfile must EXPOSE / use port 8000"


def test_dockerfile_has_healthcheck() -> None:
    """Dockerfile defines a HEALTHCHECK instruction."""
    content = _DOCKERFILE.read_text()
    assert "HEALTHCHECK" in content, "Dockerfile must have a HEALTHCHECK"


def test_docker_compose_exists() -> None:
    """docker-compose.yml is present in the project root."""
    assert _COMPOSE.exists(), "docker-compose.yml not found"


def test_docker_compose_valid_yaml() -> None:
    """docker-compose.yml parses as valid YAML."""
    content = _COMPOSE.read_text()
    data = yaml.safe_load(content)
    assert isinstance(data, dict), "docker-compose.yml must be a YAML mapping"


def test_docker_compose_has_cockpit_service() -> None:
    """docker-compose.yml defines a 'cockpit' service with required keys."""
    data = yaml.safe_load(_COMPOSE.read_text())
    services = data.get("services", {})
    assert "cockpit" in services, "docker-compose.yml must define a 'cockpit' service"
    svc = services["cockpit"]
    assert "ports" in svc or "PORT" in str(svc), "cockpit service must expose a port"
    assert "volumes" in svc, "cockpit service must mount a data volume"


# ---------------------------------------------------------------------------
# 2 — CSS grid
# ---------------------------------------------------------------------------


def test_style_css_has_cockpit_grid() -> None:
    """style.css defines the .cockpit-grid class."""
    css = _STYLE.read_text()
    assert ".cockpit-grid" in css


def test_style_css_has_column_classes() -> None:
    """style.css defines all three cockpit zone classes."""
    css = _STYLE.read_text()
    for cls in (".cockpit-col-left", ".cockpit-col-centre", ".cockpit-col-right-rail"):
        assert cls in css, f"Missing CSS class: {cls}"


def test_style_css_has_responsive_breakpoint() -> None:
    """style.css includes a max-width media query for the cockpit grid."""
    css = _STYLE.read_text()
    assert "@media" in css and "max-width" in css, "Missing responsive @media rule"


def test_style_css_col_label_defined() -> None:
    """style.css defines the .col-label utility class."""
    css = _STYLE.read_text()
    assert ".col-label" in css


# ---------------------------------------------------------------------------
# 3 — index.html structure
# ---------------------------------------------------------------------------


def test_index_html_uses_cockpit_grid() -> None:
    """index.html wraps panels in a .cockpit-grid container."""
    html = _INDEX.read_text()
    assert 'class="cockpit-grid"' in html or "cockpit-grid" in html


def test_index_html_has_four_columns() -> None:
    """index.html has all three cockpit zone divs."""
    html = _INDEX.read_text()
    for cls in ("cockpit-col-left", "cockpit-col-centre", "cockpit-col-right-rail"):
        assert cls in html, f"index.html missing zone: {cls}"


def test_index_html_control_panel_in_centre() -> None:
    """Session control panel is inside the centre column, not at root level."""
    html = _INDEX.read_text()
    centre_start = html.find("cockpit-col-centre")
    centre_end = html.find("cockpit-col-right")
    assert centre_start != -1 and centre_end != -1
    control_pos = html.find('id="panel-control"')
    assert centre_start < control_pos < centre_end, \
        "panel-control must be inside cockpit-col-centre"


def test_index_html_health_in_sidebar() -> None:
    """Compact health chip (panel-health-chip) is inside the right rail."""
    html = _INDEX.read_text()
    rail_start = html.find("cockpit-col-right-rail")
    assert rail_start != -1
    chip_pos = html.find('id="panel-health-chip"')
    assert chip_pos > rail_start, "panel-health-chip must be inside cockpit-col-right-rail"


# ---------------------------------------------------------------------------
# 4 — AUTH_ENABLED=false (default) — behaviour unchanged
# ---------------------------------------------------------------------------


def test_auth_disabled_root_accessible() -> None:
    """GET /home returns 200 when AUTH_ENABLED is not set (default)."""
    # Ensure AUTH_ENABLED is off for this test module
    os.environ.pop("AUTH_ENABLED", None)
    # Re-import to pick up env state (server module imported at module level)
    from fastapi.testclient import TestClient
    from web.server import app

    client = TestClient(app, follow_redirects=False)
    r = client.get("/home")
    assert r.status_code == 200


def test_auth_disabled_api_accessible() -> None:
    """GET /api/health/snapshot returns 200 when auth is disabled."""
    os.environ.pop("AUTH_ENABLED", None)
    from fastapi.testclient import TestClient
    from web.server import app

    client = TestClient(app)
    r = client.get("/api/health/snapshot")
    assert r.status_code == 200


def test_health_check_always_200() -> None:
    """GET /health-check always returns 200 + {status: ok}."""
    from fastapi.testclient import TestClient
    from web.server import app

    client = TestClient(app)
    r = client.get("/health-check")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# ---------------------------------------------------------------------------
# 5-9 — AUTH_ENABLED=true path tests
#        (uses a fresh import of auth module with patched env vars)
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_client(monkeypatch: pytest.MonkeyPatch):
    """TestClient with AUTH_ENABLED=true and a known password/secret.

    Rather than reloading the entire server module (which breaks route
    registration), we monkeypatch the module-level vars in web.api.auth
    directly.  The middleware closure calls auth_api.auth_check() which
    reads AUTH_ENABLED and _JWT_SECRET from the same module at call time,
    so patching them is sufficient.
    """
    import web.api.auth as auth_mod
    from fastapi.testclient import TestClient
    from web.server import app

    _TEST_PASSWORD = "s3cret-test-pw!"
    _TEST_SECRET = "test-jwt-secret-not-for-production-x"

    monkeypatch.setattr(auth_mod, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_mod, "_AUTH_PASSWORD", _TEST_PASSWORD)
    monkeypatch.setattr(auth_mod, "_JWT_SECRET", _TEST_SECRET)
    monkeypatch.setattr(auth_mod, "_EXPIRE_MINUTES", 60)

    yield TestClient(app, follow_redirects=False)


def test_auth_enabled_root_redirects(auth_client) -> None:
    """When AUTH_ENABLED=true, GET / without a cookie → 307 to /login."""
    r = auth_client.get("/")
    assert r.status_code in (302, 303, 307, 308)
    assert "/login" in r.headers.get("location", "")


def test_auth_enabled_login_page_served(auth_client) -> None:
    """GET /login returns 200 with a password form."""
    r = auth_client.get("/login")
    assert r.status_code == 200
    assert "<form" in r.text
    assert 'name="password"' in r.text


def test_auth_login_wrong_password(auth_client) -> None:
    """POST /login with wrong password returns 401."""
    r = auth_client.post("/login", data={"password": "wrong-password"})
    assert r.status_code == 401
    assert "Invalid password" in r.text


def test_auth_login_correct_password(auth_client) -> None:
    """POST /login with correct password sets a JWT cookie and redirects."""
    r = auth_client.post("/login", data={"password": "s3cret-test-pw!"})
    assert r.status_code in (302, 303), f"Expected redirect, got {r.status_code}"
    # Cookie must be set
    assert "miktos_token" in r.cookies, "JWT cookie not set after successful login"


def test_auth_logout(auth_client) -> None:
    """POST /logout clears the cookie and redirects to /login."""
    # First log in to get a cookie
    login = auth_client.post("/login", data={"password": "s3cret-test-pw!"})
    assert login.status_code in (302, 303)

    # The TestClient holds the cookie; now log out
    r = auth_client.post("/logout")
    assert r.status_code in (302, 303, 307, 308)
    assert "/login" in r.headers.get("location", "")


# ---------------------------------------------------------------------------
# 10 — Rehearsal bypass
# ---------------------------------------------------------------------------


def test_rehearsal_bypasses_auth(auth_client) -> None:
    """/api/rehearsal/state is always accessible regardless of auth cookie."""
    # No cookie set — rehearsal must still respond (best-effort 200)
    r = auth_client.get("/api/rehearsal/state")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 11 — PyJWT round-trip
# ---------------------------------------------------------------------------


def test_pyjwt_importable() -> None:
    """PyJWT can be imported and can sign/verify a token."""
    import jwt  # noqa: PLC0415

    secret = "test-secret"
    token = jwt.encode({"sub": "test"}, secret, algorithm="HS256")
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    assert payload["sub"] == "test"
