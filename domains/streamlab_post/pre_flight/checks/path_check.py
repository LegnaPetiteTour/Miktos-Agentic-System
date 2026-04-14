"""
path_check — Pre-flight Check 3 (hard failure).

Verifies that the recording path (from session_config.yaml or the
~/Movies default) exists on disk and is writable. If OBS cannot write
the recording to that path the entire pipeline fails.
"""

import os
from pathlib import Path

import yaml


_CONFIG_PATH = (
    Path(__file__).parent.parent.parent / "config" / "session_config.yaml"
)

_DEFAULT_RECORDING_PATH = Path.home() / "Movies"


def _load_recording_path(config_path: Path) -> Path:
    """Return the recording path from config, or ~/Movies as fallback."""
    try:
        with config_path.open() as fh:
            cfg = yaml.safe_load(fh) or {}
        local_path = cfg.get("recording", {}).get("local_path", "")
        if local_path and str(local_path).strip():
            return Path(str(local_path).strip())
    except Exception:
        pass
    return _DEFAULT_RECORDING_PATH


def run(dry_run: bool = False, config_path: str | Path | None = None) -> dict:
    """
    Check that the recording path exists and is writable.

    Args:
        dry_run:     If True return ok without touching the filesystem.
        config_path: Override config path (used in tests).

    Returns:
        {"name": "recording_path", "status": "ok"|"fail", "message": str}
    """
    if dry_run:
        return {
            "name": "recording_path",
            "status": "ok",
            "message": "Recording path — writable (dry-run)",
        }

    cfg_path = Path(config_path) if config_path else _CONFIG_PATH
    recording_path = _load_recording_path(cfg_path)

    if not recording_path.exists():
        return {
            "name": "recording_path",
            "status": "fail",
            "message": f"Recording path — does not exist: {recording_path}",
        }

    if not os.access(recording_path, os.W_OK):
        return {
            "name": "recording_path",
            "status": "fail",
            "message": f"Recording path — not writable: {recording_path}",
        }

    return {
        "name": "recording_path",
        "status": "ok",
        "message": f"Recording path — exists and writable: {recording_path}",
    }
