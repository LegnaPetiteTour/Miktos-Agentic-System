"""
credentials_check — Pre-flight Check 6 (soft warnings).

Checks that the required API credentials are present and attempts
a lightweight token-refresh for each YouTube refresh token to confirm
the token is still valid.

All checks here are warnings (not hard failures) — a missing credential
means the corresponding slot will fail gracefully at runtime, but it
will not block the stream from starting.

Checks:
  YOUTUBE_REFRESH_TOKEN_EN   — ok if set + refresh succeeds; warn if missing/invalid
  YOUTUBE_REFRESH_TOKEN_FR   — ok if set + refresh succeeds; warn if missing/invalid
  GOOGLE_TRANSLATE_API_KEY   — ok if set; warn if missing
  ELEVENLABS_API_KEY         — ok if set; warn if missing
  youtube.en.video_id        — ok if set; warn → auto-discovery will be used
  youtube.fr.video_id        — ok if set; warn → auto-discovery will be used
  notification.recipients_teams — ok if set; warn → notify slot will skip

Token validation uses the Google OAuth token-refresh endpoint directly
(no SDK import needed) so it works even in environments that only have
requests installed.
"""

import os
from pathlib import Path

import requests  # type: ignore[import]
import yaml


_CONFIG_PATH = (
    Path(__file__).parent.parent.parent / "config" / "session_config.yaml"
)

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _load_config(config_path: Path) -> dict:
    try:
        with config_path.open() as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


def _try_refresh_token(token_name: str) -> tuple[bool, str]:
    """
    Attempt a Google OAuth token refresh.

    Returns (success, detail_message).
    """
    refresh_token = os.getenv(token_name, "")
    client_id = os.getenv("YOUTUBE_CLIENT_ID", "")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "")

    if not refresh_token:
        return False, f"{token_name} — not set"
    if not client_id or not client_secret:
        return False, f"{token_name} — set but YOUTUBE_CLIENT_ID/SECRET missing"

    try:
        resp = requests.post(
            _GOOGLE_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        if resp.status_code == 200 and resp.json().get("access_token"):
            return True, f"{token_name} — valid (refresh succeeded)"
        return False, f"{token_name} — refresh failed ({resp.status_code})"
    except Exception as exc:
        return False, f"{token_name} — refresh error: {exc}"


def run(
    dry_run: bool = False,
    config_path: str | Path | None = None,
) -> list[dict]:
    """
    Run all credential checks.

    Returns a list of result dicts (one per sub-check) rather than a
    single dict, because credentials_check generates multiple rows in
    the report. PreFlightChecker flattens this list.

    Each item: {"name": str, "status": "ok"|"warn", "message": str}
    """
    results: list[dict] = []

    # -----------------------------------------------------------------------
    # YouTube EN token
    # -----------------------------------------------------------------------
    if dry_run:
        results.append({
            "name": "youtube_token_en",
            "status": "ok",
            "message": "YOUTUBE_REFRESH_TOKEN_EN — ok (dry-run)",
        })
    else:
        ok, msg = _try_refresh_token("YOUTUBE_REFRESH_TOKEN_EN")
        results.append({
            "name": "youtube_token_en",
            "status": "ok" if ok else "warn",
            "message": msg,
        })

    # -----------------------------------------------------------------------
    # YouTube FR token
    # -----------------------------------------------------------------------
    if dry_run:
        results.append({
            "name": "youtube_token_fr",
            "status": "ok",
            "message": "YOUTUBE_REFRESH_TOKEN_FR — ok (dry-run)",
        })
    else:
        ok, msg = _try_refresh_token("YOUTUBE_REFRESH_TOKEN_FR")
        results.append({
            "name": "youtube_token_fr",
            "status": "ok" if ok else "warn",
            "message": msg,
        })

    # -----------------------------------------------------------------------
    # Google Translate API key
    # -----------------------------------------------------------------------
    if dry_run:
        results.append({
            "name": "google_translate_key",
            "status": "ok",
            "message": "GOOGLE_TRANSLATE_API_KEY — ok (dry-run)",
        })
    else:
        translate_key = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")
        results.append({
            "name": "google_translate_key",
            "status": "ok" if translate_key else "warn",
            "message": (
                "GOOGLE_TRANSLATE_API_KEY — set"
                if translate_key
                else "GOOGLE_TRANSLATE_API_KEY — not set (translation slot will fail)"
            ),
        })

    # -----------------------------------------------------------------------
    # ElevenLabs API key
    # -----------------------------------------------------------------------
    if dry_run:
        results.append({
            "name": "elevenlabs_key",
            "status": "ok",
            "message": "ELEVENLABS_API_KEY — ok (dry-run)",
        })
    else:
        el_key = os.getenv("ELEVENLABS_API_KEY", "")
        results.append({
            "name": "elevenlabs_key",
            "status": "ok" if el_key else "warn",
            "message": (
                "ELEVENLABS_API_KEY — set"
                if el_key
                else "ELEVENLABS_API_KEY — not set (transcript slot will fail)"
            ),
        })

    # -----------------------------------------------------------------------
    # Config-based checks (video_id, Teams webhook)
    # -----------------------------------------------------------------------
    cfg_path = Path(config_path) if config_path else _CONFIG_PATH
    cfg = _load_config(cfg_path) if not dry_run else {}

    en_video_id = cfg.get("youtube", {}).get("en", {}).get("video_id", "")
    if dry_run:
        results.append({
            "name": "youtube_en_video_id",
            "status": "ok",
            "message": "youtube.en.video_id — ok (dry-run)",
        })
    else:
        results.append({
            "name": "youtube_en_video_id",
            "status": "ok" if en_video_id else "warn",
            "message": (
                f"youtube.en.video_id — set ({en_video_id})"
                if en_video_id
                else "youtube.en.video_id — blank (auto-discovery will be used)"
            ),
        })

    fr_video_id = cfg.get("youtube", {}).get("fr", {}).get("video_id", "")
    if dry_run:
        results.append({
            "name": "youtube_fr_video_id",
            "status": "ok",
            "message": "youtube.fr.video_id — ok (dry-run)",
        })
    else:
        results.append({
            "name": "youtube_fr_video_id",
            "status": "ok" if fr_video_id else "warn",
            "message": (
                f"youtube.fr.video_id — set ({fr_video_id})"
                if fr_video_id
                else "youtube.fr.video_id — blank (auto-discovery will be used)"
            ),
        })

    teams_webhook = cfg.get("notification", {}).get("recipients_teams", "")
    if dry_run:
        results.append({
            "name": "teams_webhook",
            "status": "ok",
            "message": "Teams webhook URL — ok (dry-run)",
        })
    else:
        results.append({
            "name": "teams_webhook",
            "status": "ok" if teams_webhook else "warn",
            "message": (
                "Teams webhook URL — set"
                if teams_webhook
                else "Teams webhook URL — blank (notify slot will skip)"
            ),
        })

    return results
