"""
Tests for the file analyzer classifier.
"""

from domains.file_analyzer.tools.classifier import classify_file


def test_classify_pdf():
    result = classify_file({"suffix": ".pdf", "mime_type": "application/pdf"})
    assert result["category"] == "documents"
    assert result["confidence"] >= 0.90


def test_classify_image_by_extension():
    result = classify_file({"suffix": ".jpg", "mime_type": "image/jpeg"})
    assert result["category"] == "images"
    assert result["method"] == "extension"


def test_classify_video_by_mime():
    result = classify_file({"suffix": ".unknown", "mime_type": "video/mp4"})
    assert result["category"] == "video"
    assert result["method"] == "mime"


def test_classify_unknown():
    result = classify_file({"suffix": ".xyz", "mime_type": "unknown"})
    assert result["category"] == "unclassified"
    assert result["confidence"] < 0.60


def test_classify_code():
    result = classify_file({"suffix": ".py", "mime_type": "text/plain"})
    assert result["category"] == "code"
