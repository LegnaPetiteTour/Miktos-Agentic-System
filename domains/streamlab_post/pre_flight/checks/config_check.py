"""
config_check — Pre-flight Check 2 (hard failure).

Loads domains/streamlab_post/config/session_config.yaml and verifies
that the required fields are present and non-empty:
  - event_name
  - youtube.en.channel_id
  - youtube.fr.channel_id

A missing file, a YAML parse error, or any empty required field → fail.
"""

from pathlib import Path

import yaml


_CONFIG_PATH = (
    Path(__file__).parent.parent.parent / "config" / "session_config.yaml"
)

_REQUIRED = [
    ("event_name", lambda cfg: cfg.get("event_name", "")),
    ("youtube.en.channel_id", lambda cfg: cfg.get("youtube", {}).get("en", {}).get("channel_id", "")),
    ("youtube.fr.channel_id", lambda cfg: cfg.get("youtube", {}).get("fr", {}).get("channel_id", "")),
]


def run(dry_run: bool = False, config_path: str | Path | None = None) -> dict:
    """
    Validate session_config.yaml.

    Args:
        dry_run:     If True return ok without loading the file.
        config_path: Override config path (used in tests).

    Returns:
        {"name": "session_config", "status": "ok"|"fail", "message": str}
    """
    if dry_run:
        return {
            "name": "session_config",
            "status": "ok",
            "message": "session_config.yaml — valid (dry-run)",
        }

    path = Path(config_path) if config_path else _CONFIG_PATH

    if not path.exists():
        return {
            "name": "session_config",
            "status": "fail",
            "message": f"session_config.yaml — not found at {path}",
        }

    try:
        with path.open() as fh:
            cfg = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        return {
            "name": "session_config",
            "status": "fail",
            "message": f"session_config.yaml — parse error: {exc}",
        }

    for field_name, getter in _REQUIRED:
        value = getter(cfg)
        if not value or not str(value).strip():
            return {
                "name": "session_config",
                "status": "fail",
                "message": f"session_config.yaml — required field '{field_name}' is empty",
            }

    return {
        "name": "session_config",
        "status": "ok",
        "message": "session_config.yaml — all required fields present",
    }
