"""PyInstaller entry point for the Miktos server.

Electron spawns this binary and sets MIKTOS_DATA_DIR to:
    ~/Library/Application Support/Miktos/

This module bootstraps the data directory, loads .env, then hands off
to uvicorn which serves web.server:app on 127.0.0.1:8000.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure MIKTOS_DATA_DIR is set before any application module is imported.
# ---------------------------------------------------------------------------
_env_val = os.environ.get("MIKTOS_DATA_DIR", "")
if not _env_val:
    # Fallback for running the binary outside Electron during development.
    _default_data = Path.home() / "Library" / "Application Support" / "Miktos"
    os.environ["MIKTOS_DATA_DIR"] = str(_default_data)

# Now that MIKTOS_DATA_DIR is set, engine.paths will resolve to the right dir.
from engine.paths import get_data_dir, get_config_dir, get_env_path  # noqa: E402

# Create required directories so the app never crashes on first run.
get_data_dir().mkdir(parents=True, exist_ok=True)
(get_data_dir() / "sessions").mkdir(parents=True, exist_ok=True)
(get_data_dir() / "state").mkdir(parents=True, exist_ok=True)
(get_data_dir() / "logs").mkdir(parents=True, exist_ok=True)
(get_data_dir() / "messages" / "post_stream_processor" / "pending").mkdir(
    parents=True, exist_ok=True
)
get_config_dir().mkdir(parents=True, exist_ok=True)

# Load .env so API credentials are available as environment variables.
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=get_env_path(), override=False)
except ImportError:
    pass  # python-dotenv not available — env vars must be set externally

# ---------------------------------------------------------------------------
# Launch the web server.
# ---------------------------------------------------------------------------
import uvicorn  # noqa: E402
from web.server import app as _web_app  # noqa: E402 — static import so PyInstaller bundles it

uvicorn.run(
    _web_app,
    host="127.0.0.1",
    port=8000,
    reload=False,
    log_level="info",
)
