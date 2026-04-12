"""
TranscriptWorker — Phase 5 post-stream closure.

Submits the extracted MP3 to the ElevenLabs Scribe API and downloads
the bilingual transcript. Saves plain text with speaker labels to
output_dir/transcript.txt.

This is a Stage 2 slot — runs after AudioExtractWorker succeeds.
Requires: mp3_path from Stage 1 audio_extract result.
"""

import os
from pathlib import Path

import requests


class TranscriptWorker:
    """
    Submit MP3 to ElevenLabs Scribe API and download the bilingual transcript.

    ElevenLabs Speech-to-Text endpoint:
      POST https://api.elevenlabs.io/v1/speech-to-text
      Headers: xi-api-key: <ELEVENLABS_API_KEY>
      Body (multipart/form-data):
        audio: <mp3 file>
        model_id: scribe_v1
        language_code: fr   (hint — bilingual detection still runs)
        diarize: true

    The API returns the transcript directly (no polling for Scribe).
    Never raises — returns success: False with error details on failure.
    """

    name = "transcript_worker"
    _ELEVENLABS_URL = "https://api.elevenlabs.io/v1/speech-to-text"

    def run(self, payload: dict) -> dict:
        """
        Submit MP3 to ElevenLabs and save transcript.

        Payload keys:
          mp3_path (str)        — path to the MP3 file
          output_dir (str)      — directory to write transcript.txt into
          language_code (str)   — language hint (default "fr")
          dry_run (bool)        — if True, skip API call, return mock result

        Returns:
          {success, transcript_path, word_count, detected_languages}
          or {success: False, error: str}
        """
        mp3_path = payload.get("mp3_path", "")
        output_dir = payload.get("output_dir", "")
        language_code = payload.get("language_code", "fr")
        dry_run = payload.get("dry_run", False)

        if dry_run:
            transcript_text = (
                "[Speaker 1]: Good morning everyone, welcome to the meeting.\n"
                "[Speaker 2]: Bonjour à tous, nous allons commencer la réunion.\n"
                "[Speaker 1]: Today's agenda includes three items.\n"
                "[Speaker 2]: L'ordre du jour comprend trois points.\n"
            )
            out_dir = Path(output_dir or "/tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            transcript_path = out_dir / "transcript.txt"
            transcript_path.write_text(transcript_text, encoding="utf-8")
            return {
                "success": True,
                "dry_run": True,
                "transcript_path": str(transcript_path),
                "word_count": len(transcript_text.split()),
                "detected_languages": ["fr", "en"],
            }

        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            return {
                "success": False,
                "error": "ELEVENLABS_API_KEY not set — configure in .env",
            }

        if not mp3_path:
            return {"success": False, "error": "mp3_path not provided in payload"}
        if not Path(mp3_path).exists():
            return {
                "success": False,
                "error": f"MP3 file not found: {mp3_path}",
            }
        if not output_dir:
            return {"success": False, "error": "output_dir not provided in payload"}

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(mp3_path, "rb") as audio_file:
                response = requests.post(
                    self._ELEVENLABS_URL,
                    headers={"xi-api-key": api_key},
                    files={"audio": audio_file},
                    data={
                        "model_id": "scribe_v1",
                        "language_code": language_code,
                        "diarize": "true",
                    },
                    timeout=300,
                )
        except requests.RequestException as exc:
            return {"success": False, "error": f"ElevenLabs request failed: {exc}"}

        if response.status_code != 200:
            return {
                "success": False,
                "error": (
                    f"ElevenLabs API error {response.status_code}: "
                    f"{response.text[:200]}"
                ),
            }

        try:
            data = response.json()
        except ValueError:
            return {
                "success": False,
                "error": "ElevenLabs returned non-JSON response",
            }

        transcript_text = data.get("text", "")
        words = data.get("words", [])
        detected_languages: list[str] = []
        if words:
            langs = {
                w.get("language_code")
                for w in words
                if w.get("language_code")
            }
            detected_languages = sorted(langs)

        transcript_path = out_dir / "transcript.txt"
        transcript_path.write_text(transcript_text, encoding="utf-8")

        return {
            "success": True,
            "transcript_path": str(transcript_path),
            "word_count": len(transcript_text.split()),
            "detected_languages": detected_languages,
        }
