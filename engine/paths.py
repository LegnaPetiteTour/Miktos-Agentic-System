"""
engine/paths.py — Portable path resolution for dev and packaged app.

In development (MIKTOS_DATA_DIR not set):
    get_data_dir()   → <project_root>/data/
    get_config_dir() → <project_root>/domains/streamlab_post/config/
    get_env_path()   → <project_root>/.env

In the packaged Electron app (MIKTOS_DATA_DIR set by Electron main process):
    get_data_dir()   → $MIKTOS_DATA_DIR/data/
    get_config_dir() → $MIKTOS_DATA_DIR/config/
    get_env_path()   → $MIKTOS_DATA_DIR/.env

This module has zero imports beyond stdlib so it can be imported early
in miktos_entry.py before any other application code.
"""

from __future__ import annotations

import os
from pathlib import Path

# Project root — two levels up from engine/paths.py
_PROJECT_ROOT = Path(__file__).parent.parent


def _miktos_data_dir() -> Path | None:
    """Return the value of MIKTOS_DATA_DIR env var, or None if not set."""
    val = os.environ.get("MIKTOS_DATA_DIR", "")
    return Path(val) if val else None


def get_data_dir() -> Path:
    """Return the user data directory.

    Development: <project_root>/data/
    Packaged:    $MIKTOS_DATA_DIR/data/
    """
    base = _miktos_data_dir()
    if base:
        return base / "data"
    return _PROJECT_ROOT / "data"


def get_config_dir() -> Path:
    """Return the session config directory.

    Development: <project_root>/domains/streamlab_post/config/
    Packaged:    $MIKTOS_DATA_DIR/config/
    """
    base = _miktos_data_dir()
    if base:
        return base / "config"
    return _PROJECT_ROOT / "domains" / "streamlab_post" / "config"


def get_env_path() -> Path:
    """Return the path to the .env credentials file.

    Development: <project_root>/.env
    Packaged:    $MIKTOS_DATA_DIR/.env
    """
    base = _miktos_data_dir()
    if base:
        return base / ".env"
    return _PROJECT_ROOT / ".env"
