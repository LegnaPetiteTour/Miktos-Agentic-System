"""
Rule-based file classifier for the file analyzer domain.

Confidence tier table (four levels):

  Tier              Confidence  Method           Outcome
  ─────────────────────────────────────────────────────────
  Extension match   0.95        "extension"      approved
  Handled MIME      0.80        "mime"           approved
  Detected, unmapped 0.60       "mime_unhandled" review_queue
  No MIME at all    0.40        "fallback"       skipped

The critical distinction between tier 3 and tier 4:
  - tier 3: mime_type is a non-empty, non-"unknown" string that does
            not match any handled prefix — Python detected a MIME type
            but the classifier has no rule for it.
  - tier 4: mime_type is missing, empty, or exactly "unknown" — the
            file has no detectable MIME at all.

"mime_unhandled" must NEVER be applied when mime_type == "unknown".

Handled MIME prefixes (tier 2 — confidence 0.80):
  image/          → images
  video/          → video
  audio/          → audio
  text/           → documents
  application/    → documents  (catch-all beyond application/pdf)
  font/           → documents
  model/          → unclassified (known type, no category mapping)

LLM-assisted classification reserved for v1.5 (ambiguous cases only).
"""

EXTENSION_MAP = {
    # Documents
    ".pdf": "documents", ".docx": "documents", ".doc": "documents",
    ".txt": "documents", ".md": "documents", ".odt": "documents",
    # Spreadsheets
    ".xlsx": "spreadsheets", ".xls": "spreadsheets",
    ".csv": "spreadsheets",
    # Presentations
    ".pptx": "presentations", ".ppt": "presentations",
    # Images
    ".jpg": "images", ".jpeg": "images", ".png": "images",
    ".gif": "images", ".webp": "images", ".svg": "images",
    ".heic": "images",
    # Video
    ".mp4": "video", ".mov": "video", ".avi": "video",
    ".mkv": "video", ".webm": "video",
    # Audio
    ".mp3": "audio", ".wav": "audio", ".aac": "audio", ".flac": "audio",
    # Code
    ".py": "code", ".js": "code", ".ts": "code", ".json": "code",
    ".yaml": "code", ".yml": "code", ".toml": "code", ".sh": "code",
    # Archives
    ".zip": "archives", ".tar": "archives", ".gz": "archives",
    ".rar": "archives", ".7z": "archives",
}

CONFIDENCE = {
    "extension": 0.95,
    "mime": 0.80,
    "mime_unhandled": 0.60,
    "fallback": 0.40,
}

# Handled MIME prefixes → (category, method="mime")
_MIME_PREFIX_MAP = [
    ("image/",       "images"),
    ("video/",       "video"),
    ("audio/",       "audio"),
    ("text/",        "documents"),
    ("application/", "documents"),
    ("font/",        "documents"),
    ("model/",       "unclassified"),
]

# Sentinel values that mean "no MIME detected"
_NO_MIME = {"", "unknown"}


def classify_file(file_meta: dict) -> dict:
    """
    Classify a single file. Returns category, confidence, and method.

    See module docstring for the full four-tier confidence table.
    """
    suffix = file_meta.get("suffix", "").lower()
    mime = file_meta.get("mime_type", "") or ""

    # Tier 1 — extension match
    if suffix in EXTENSION_MAP:
        return {
            "category": EXTENSION_MAP[suffix],
            "confidence": CONFIDENCE["extension"],
            "method": "extension",
        }

    # Tier 2 — handled MIME prefix
    for prefix, category in _MIME_PREFIX_MAP:
        if mime.startswith(prefix):
            return {
                "category": category,
                "confidence": CONFIDENCE["mime"],
                "method": "mime",
            }

    # Tier 3 — MIME was detected by Python but prefix not handled
    # MUST NOT apply when mime is missing/unknown (that is tier 4)
    if mime and mime not in _NO_MIME:
        return {
            "category": "unclassified",
            "confidence": CONFIDENCE["mime_unhandled"],
            "method": "mime_unhandled",
        }

    # Tier 4 — no MIME at all
    return {
        "category": "unclassified",
        "confidence": CONFIDENCE["fallback"],
        "method": "fallback",
    }
