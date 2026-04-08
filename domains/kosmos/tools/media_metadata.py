"""
Lightweight media metadata extractor for the Kosmos domain.

Uses only Pillow (already in the venv) and stdlib — no ffprobe or
pymediainfo in v1. For non-image files the extractor returns empty
metadata gracefully; the classifier degrades to extension/MIME rules.

EXIF tag reference:
  271 = Make   (camera manufacturer)
  272 = Model  (camera model)

Returned dict keys:
  has_exif        bool  — True if any EXIF block was present
  has_camera_data bool  — True if Make AND Model tags were found
  width           int   — image width in pixels (0 if unavailable)
  height          int   — image height in pixels (0 if unavailable)
  format          str   — Pillow format string e.g. "JPEG", "" if none
"""

from pathlib import Path

try:
    from PIL import Image
    _PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PILLOW_AVAILABLE = False

# EXIF tags that indicate the image came from a physical camera
_MAKE_TAG = 271   # Make
_MODEL_TAG = 272  # Model


def extract_media_metadata(file_path: str) -> dict:
    """
    Extract lightweight metadata from a media file.

    Returns a dict with has_exif, has_camera_data, width, height, format.
    All failures are caught — the function never raises.
    """
    empty = {
        "has_exif": False,
        "has_camera_data": False,
        "width": 0,
        "height": 0,
        "format": "",
    }

    if not _PILLOW_AVAILABLE:
        return empty  # pragma: no cover

    path = Path(file_path)
    if not path.exists():
        return empty

    try:
        with Image.open(path) as img:
            width, height = img.size
            fmt = img.format or ""

            # Pillow ≥ 7.2 exposes getexif(); older versions use _getexif()
            # Use getattr to avoid Pylance attribute check on the base type.
            exif_data = None
            get_exif = getattr(img, "getexif", None)
            get_exif_legacy = getattr(img, "_getexif", None)
            if callable(get_exif):
                exif_data = get_exif()
            elif callable(get_exif_legacy):
                exif_data = get_exif_legacy()

            if not exif_data:
                return {
                    "has_exif": False,
                    "has_camera_data": False,
                    "width": width,
                    "height": height,
                    "format": fmt,
                }

            has_make = bool(exif_data.get(_MAKE_TAG, "").strip())
            has_model = bool(exif_data.get(_MODEL_TAG, "").strip())

            return {
                "has_exif": True,
                "has_camera_data": has_make and has_model,
                "width": width,
                "height": height,
                "format": fmt,
            }

    except Exception:
        return empty
