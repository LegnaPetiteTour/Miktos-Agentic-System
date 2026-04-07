"""
Rule-based file classifier for the file analyzer domain.

Classification priority:
1. Extension + MIME type (rule-based)  -> confidence 0.95
2. MIME type fallback                  -> confidence 0.80
3. Unclassified (for review queue)     -> confidence 0.40

LLM-assisted classification is reserved for v1.2 (ambiguous cases only).
"""

EXTENSION_MAP = {
    # Documents
    ".pdf": "documents", ".docx": "documents", ".doc": "documents",
    ".txt": "documents", ".md": "documents", ".odt": "documents",
    # Spreadsheets
    ".xlsx": "spreadsheets", ".xls": "spreadsheets", ".csv": "spreadsheets",
    # Presentations
    ".pptx": "presentations", ".ppt": "presentations",
    # Images
    ".jpg": "images", ".jpeg": "images", ".png": "images",
    ".gif": "images", ".webp": "images", ".svg": "images", ".heic": "images",
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
    "fallback": 0.40,
}


def classify_file(file_meta: dict) -> dict:
    """Classify a single file. Returns category and confidence."""
    suffix = file_meta.get("suffix", "").lower()
    mime = file_meta.get("mime_type", "")

    if suffix in EXTENSION_MAP:
        return {"category": EXTENSION_MAP[suffix], "confidence": CONFIDENCE["extension"], "method": "extension"}

    if mime.startswith("image/"):
        return {"category": "images", "confidence": CONFIDENCE["mime"], "method": "mime"}
    if mime.startswith("video/"):
        return {"category": "video", "confidence": CONFIDENCE["mime"], "method": "mime"}
    if mime.startswith("audio/"):
        return {"category": "audio", "confidence": CONFIDENCE["mime"], "method": "mime"}
    if mime == "application/pdf":
        return {"category": "documents", "confidence": CONFIDENCE["mime"], "method": "mime"}

    return {"category": "unclassified", "confidence": CONFIDENCE["fallback"], "method": "fallback"}
