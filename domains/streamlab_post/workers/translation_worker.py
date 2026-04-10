"""
TranslationWorker — Phase 5 post-stream closure.

Translates English title and description to French using the
Google Translate REST API v2. The translated content is passed to
YouTubeWorker (FR) in Stage 3.

This is a Stage 2 slot — runs after YouTubeWorker (EN) provides
the English title and description from the live video.
"""

import os

import requests


class TranslationWorker:
    """
    Translate title and description from EN to FR using Google Translate API v2.

    REST endpoint:
      POST https://translation.googleapis.com/language/translate/v2
      Key: GOOGLE_TRANSLATE_API_KEY (query param)
      Body: {"q": ["title", "description"], "source": "en", "target": "fr",
             "format": "text"}

    Never raises — returns success: False with error details on failure.
    """

    name = "translation_worker"
    _TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"

    def run(self, payload: dict) -> dict:
        """
        Translate title and description EN → FR.

        Payload keys:
          title_en (str)       — English title
          description_en (str) — English description
          dry_run (bool)       — if True, skip API call, return mock result

        Returns:
          {success, title_fr, description_fr}
          or {success: False, error: str}
        """
        title_en = payload.get("title_en", "")
        description_en = payload.get("description_en", "")
        dry_run = payload.get("dry_run", False)

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "title_fr": f"[FR] {title_en}" if title_en else "[FR] Titre",
                "description_fr": (
                    f"[Traduction automatique]\n{description_en}"
                    if description_en
                    else "[FR] Description"
                ),
            }

        api_key = os.environ.get("GOOGLE_TRANSLATE_API_KEY", "")
        if not api_key:
            return {
                "success": False,
                "error": "GOOGLE_TRANSLATE_API_KEY not set — configure in .env",
            }

        if not title_en and not description_en:
            return {
                "success": False,
                "error": "Both title_en and description_en are empty",
            }

        texts = [title_en or "", description_en or ""]

        try:
            response = requests.post(
                self._TRANSLATE_URL,
                params={"key": api_key},
                json={
                    "q": texts,
                    "source": "en",
                    "target": "fr",
                    "format": "text",
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            return {
                "success": False,
                "error": f"Google Translate request failed: {exc}",
            }

        if response.status_code != 200:
            return {
                "success": False,
                "error": (
                    f"Google Translate API error {response.status_code}: "
                    f"{response.text[:200]}"
                ),
            }

        try:
            data = response.json()
            translations = data["data"]["translations"]
            title_fr = translations[0]["translatedText"]
            description_fr = translations[1]["translatedText"]
        except (ValueError, KeyError, IndexError) as exc:
            return {
                "success": False,
                "error": f"Failed to parse Google Translate response: {exc}",
            }

        return {
            "success": True,
            "title_fr": title_fr,
            "description_fr": description_fr,
        }
