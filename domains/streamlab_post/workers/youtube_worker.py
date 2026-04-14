"""
YouTubeWorker — Phase 5 post-stream closure.

Manages a YouTube video: verifies upload completion, sets public visibility,
sets title and description metadata, and optionally adds to a playlist.

Used for both EN and FR channels — the `language` payload key selects
which refresh token to use (YOUTUBE_REFRESH_TOKEN_EN or _FR).

This is a Stage 1 slot (EN) and Stage 3 slot (FR).
Stage 1 EN: verify upload + set metadata (description_en from session_config)
Stage 3 FR: set metadata (title_fr, description_fr from TranslationWorker)
"""

import os
import time
from datetime import datetime, timedelta, timezone


class YouTubeWorker:
    """
    Manage a YouTube video: verify upload, set public, set metadata,
    optionally add to playlist.

    Uses YouTube Data API v3 with OAuth2.
    Credentials from env: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN_EN or YOUTUBE_REFRESH_TOKEN_FR based on language.

    Never raises — returns success: False with error details on failure.
    """

    name = "youtube_worker"

    def run(self, payload: dict) -> dict:
        """
        Manage a YouTube video.

        Payload keys:
          language (str)        — "en" or "fr" — selects refresh token
          channel_id (str)      — YouTube channel ID (UC...)
          video_id (str)        — pre-known; blank = auto-detect from channel
          title (str)           — video title to set
          description (str)     — video description to set
          playlist_id (str)     — optional; blank = skip
          visibility (str)      — "public", "unlisted", or "private" (default: public)
          dry_run (bool)        — if True, skip API calls, return mock result

        Returns:
          {success, video_id, title, description, visibility,
           playlist_added, playlist_id}
          or {success: False, error: str}
        """
        language = payload.get("language", "en").lower()
        channel_id = payload.get("channel_id", "")
        video_id = payload.get("video_id", "")
        title = payload.get("title", "")
        description = payload.get("description", "")
        playlist_id = payload.get("playlist_id", "")
        visibility = payload.get("visibility", "public")
        dry_run = payload.get("dry_run", False)

        if dry_run:
            mock_video_id = "xKj3dryrun001" if language == "en" else "mPq7dryrun001"
            return {
                "success": True,
                "dry_run": True,
                "video_id": video_id or mock_video_id,
                "title": title or f"Committee Meeting ({language.upper()})",
                "description": (
                    description or f"[{language.upper()} description placeholder]"
                ),
                "visibility": visibility,
                "playlist_added": bool(playlist_id),
                "playlist_id": playlist_id,
            }

        # Validate credentials
        client_id = os.environ.get("YOUTUBE_CLIENT_ID", "")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
        token_key = (
            "YOUTUBE_REFRESH_TOKEN_EN"
            if language == "en"
            else "YOUTUBE_REFRESH_TOKEN_FR"
        )
        refresh_token = os.environ.get(token_key, "")

        if not client_id or not client_secret or not refresh_token:
            missing = [
                k
                for k, v in {
                    "YOUTUBE_CLIENT_ID": client_id,
                    "YOUTUBE_CLIENT_SECRET": client_secret,
                    token_key: refresh_token,
                }.items()
                if not v
            ]
            return {
                "success": False,
                "error": (
                    f"YouTube credentials not configured — missing: "
                    f"{', '.join(missing)}"
                ),
            }

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError:
            return {
                "success": False,
                "error": (
                    "google-api-python-client not installed — "
                    "run: pip install google-api-python-client google-auth-oauthlib"
                ),
            }

        try:
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token",
            )
            youtube = build("youtube", "v3", credentials=credentials)
        except Exception as exc:
            return {
                "success": False,
                "error": f"Failed to build YouTube client: {exc}",
            }

        # Auto-detect video_id if not provided
        if not video_id:
            if not channel_id:
                return {
                    "success": False,
                    "error": "Neither video_id nor channel_id provided",
                }
            # Use the channel's uploads playlist rather than search() — the
            # uploads playlist updates within seconds of a stream ending,
            # whereas the search index can lag 10–60 minutes for new VODs.
            # Retry up to 10 times with 60-second delays (up to ~10 minutes).
            max_attempts = 10
            retry_delay = 60  # seconds between attempts
            video_id = ""
            last_error = ""
            uploads_playlist_id = ""
            # Resolve uploads playlist ID once (cached across retries)
            try:
                ch_response = (
                    youtube.channels()
                    .list(part="contentDetails", id=channel_id)
                    .execute()
                )
                ch_items = ch_response.get("items", [])
                if ch_items:
                    uploads_playlist_id = (
                        ch_items[0]
                        .get("contentDetails", {})
                        .get("relatedPlaylists", {})
                        .get("uploads", "")
                    )
            except Exception as exc:
                last_error = f"YouTube channel lookup failed: {exc}"

            if not uploads_playlist_id:
                last_error = last_error or (
                    f"Could not resolve uploads playlist for channel {channel_id}"
                )
                return {"success": False, "error": last_error}

            six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=6)
            for attempt in range(max_attempts):
                if attempt > 0:
                    time.sleep(retry_delay)
                try:
                    pl_response = (
                        youtube.playlistItems()
                        .list(
                            playlistId=uploads_playlist_id,
                            part="snippet",
                            maxResults=5,
                        )
                        .execute()
                    )
                    for item in pl_response.get("items", []):
                        snippet = item.get("snippet", {})
                        published_str = snippet.get("publishedAt", "")
                        try:
                            published_at = datetime.fromisoformat(
                                published_str.replace("Z", "+00:00")
                            )
                        except ValueError:
                            continue
                        if published_at >= six_hours_ago:
                            video_id = (
                                snippet.get("resourceId", {}).get("videoId", "")
                            )
                            if video_id:
                                break
                    if video_id:
                        break
                    last_error = (
                        f"No recent videos found in uploads playlist for "
                        f"channel {channel_id} "
                        f"(attempt {attempt + 1}/{max_attempts})"
                    )
                except Exception as exc:
                    last_error = f"YouTube playlist lookup failed: {exc}"
                    break
            if not video_id:
                return {"success": False, "error": last_error}

        # Update video metadata and visibility
        try:
            update_body: dict = {
                "id": video_id,
                "snippet": {
                    "title": title,
                    "description": description,
                    "categoryId": "22",  # People & Blogs
                },
                "status": {
                    "privacyStatus": visibility,
                },
            }
            youtube.videos().update(
                part="snippet,status",
                body=update_body,
            ).execute()
        except Exception as exc:
            return {
                "success": False,
                "error": f"YouTube video update failed: {exc}",
            }

        # Optionally add to playlist
        playlist_added = False
        if playlist_id:
            try:
                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id,
                            },
                        }
                    },
                ).execute()
                playlist_added = True
            except Exception as exc:
                # Playlist assignment is best-effort — don't fail the slot
                playlist_added = False
                _ = exc  # logged via coordinator

        return {
            "success": True,
            "video_id": video_id,
            "title": title,
            "description": description,
            "visibility": visibility,
            "playlist_added": playlist_added,
            "playlist_id": playlist_id,
        }
