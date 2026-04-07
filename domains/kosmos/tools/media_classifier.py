"""
Media-aware classifier for the Kosmos domain.

Confidence tier table (nine rules, four tiers):

  Rule                              Category      Confidence  Method
  ─────────────────────────────────────────────────────────────────────
  RAW extension                     raw_photos    0.95        extension
  Image ext + EXIF camera data      photos        0.95        exif
  Image ext + no EXIF / no camera   screenshots   0.80        mime
  Image ext, Pillow open fails      images        0.75        extension
  Video extension or video/ MIME    videos        0.95        extension
  Audio extension or audio/ MIME    audio         0.95        extension
  Document extension (.pdf/.docx)   documents     0.95        extension
  Detected MIME, unmapped prefix    unclassified  0.60        mime_unhandled
  No MIME at all ("unknown"/empty)  unclassified  0.40        fallback

Design constraints:
  - mime_type == "unknown" NEVER triggers mime_unhandled (identical
    invariant to the file_analyzer classifier).
  - EXIF probe is only attempted for image extensions to keep the
    classifier fast for non-image files.
  - All Pillow errors are caught — the classifier never raises.

Shared constants for easy future extension:
  CONFIDENCE   — tier values keyed by string
  RAW_EXTS     — set of RAW camera extensions
  IMAGE_EXTS   — set of raster image extensions
  VIDEO_EXTS   — set of video extensions
  AUDIO_EXTS   — set of audio extensions
  DOCUMENT_EXTS — set of document extensions
"""

from domains.kosmos.tools.media_metadata import extract_media_metadata

# ---------------------------------------------------------------------------
# Extension sets
# ---------------------------------------------------------------------------

RAW_EXTS = {
    ".cr2", ".nef", ".arw", ".raw", ".dng",
    ".orf", ".rw2", ".pef",
}

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".svg", ".heic", ".bmp", ".tiff", ".tif",
}

VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".flv", ".wmv", ".m4v",
}

AUDIO_EXTS = {
    ".mp3", ".wav", ".aac", ".flac", ".ogg",
    ".m4a", ".wma", ".opus",
}

DOCUMENT_EXTS = {
    ".pdf", ".docx", ".doc", ".odt",
}

# Sentinel values that mean "no MIME detected" (mirrors file_analyzer)
_NO_MIME = {"", "unknown"}

# ---------------------------------------------------------------------------
# Confidence tiers
# ---------------------------------------------------------------------------

CONFIDENCE = {
    "extension": 0.95,
    "exif": 0.95,
    "mime": 0.80,
    "extension_fallback": 0.75,
    "mime_unhandled": 0.60,
    "fallback": 0.40,
}


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify_media_file(file_meta: dict) -> dict:
    """
    Classify a single media file. Returns category, confidence, and method.

    file_meta must contain at least:
      suffix    str  — lowercased file extension e.g. ".jpg"
      mime_type str  — MIME string or "unknown"
      path      str  — absolute file path (used for EXIF probe)

    See module docstring for the full nine-rule tier table.
    """
    suffix = file_meta.get("suffix", "").lower()
    mime = file_meta.get("mime_type", "") or ""
    file_path = file_meta.get("path", "")

    # Rule 1 — RAW camera extension
    if suffix in RAW_EXTS:
        return {
            "category": "raw_photos",
            "confidence": CONFIDENCE["extension"],
            "method": "extension",
        }

    # Rules 2–4 — Image extensions (EXIF-driven split)
    if suffix in IMAGE_EXTS:
        meta = extract_media_metadata(file_path)

        if meta["has_camera_data"]:
            # Rule 2 — image with camera EXIF → photo
            return {
                "category": "photos",
                "confidence": CONFIDENCE["exif"],
                "method": "exif",
            }

        if meta["width"] > 0:
            # Rule 3 — image opened by Pillow but no camera EXIF → screenshot
            return {
                "category": "screenshots",
                "confidence": CONFIDENCE["mime"],
                "method": "mime",
            }

        # Rule 4 — Pillow could not open it (corrupt / unsupported)
        return {
            "category": "images",
            "confidence": CONFIDENCE["extension_fallback"],
            "method": "extension",
        }

    # Rule 5 — Video
    if suffix in VIDEO_EXTS or mime.startswith("video/"):
        return {
            "category": "videos",
            "confidence": CONFIDENCE["extension"],
            "method": "extension",
        }

    # Rule 6 — Audio
    if suffix in AUDIO_EXTS or mime.startswith("audio/"):
        return {
            "category": "audio",
            "confidence": CONFIDENCE["extension"],
            "method": "extension",
        }

    # Rule 7 — Documents
    if suffix in DOCUMENT_EXTS:
        return {
            "category": "documents",
            "confidence": CONFIDENCE["extension"],
            "method": "extension",
        }

    # Rule 8 — MIME detected but no prefix rule matches
    # MUST NOT apply when mime is missing/unknown (that is rule 9)
    if mime and mime not in _NO_MIME:
        return {
            "category": "unclassified",
            "confidence": CONFIDENCE["mime_unhandled"],
            "method": "mime_unhandled",
        }

    # Rule 9 — No MIME at all
    return {
        "category": "unclassified",
        "confidence": CONFIDENCE["fallback"],
        "method": "fallback",
    }
