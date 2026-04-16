"""
alert_classifier.py — Alert classifier for the Epiphan Pearl domain.

Same contract as the StreamLab classifier: receives an alert item dict
and returns category / confidence / method.

Confidence tier table:

  Rule                   Category           Confidence  Method
  ────────────────────────────────────────────────────────────
  recording_stopped      recording_stopped  0.95        threshold_critical
  streaming_stopped      streaming_stopped  0.95        threshold_critical
  disk_low               disk_low           0.80        threshold_warning
  unknown with MIME      unknown_metric     0.60        threshold_info
  missing MIME           unclassified       0.40        fallback

This function never raises.
"""

_NO_MIME: set[str] = {"", "unknown"}

_CRITICAL_METRIC_TYPES = {
    "recording_stopped",
    "streaming_stopped",
}

_WARNING_METRIC_TYPES = {
    "disk_low",
}


def classify_alert(item: dict) -> dict:
    """
    Classify an Epiphan alert item.

    Returns:
      {"category": str, "confidence": float, "method": str}
    """
    mime = item.get("mime_type", "")
    metric = item.get("metric_type", "")

    if mime in _NO_MIME:
        return {
            "category": "unclassified",
            "confidence": 0.40,
            "method": "fallback",
        }

    if metric in _CRITICAL_METRIC_TYPES:
        return {
            "category": metric,
            "confidence": 0.95,
            "method": "threshold_critical",
        }

    if metric in _WARNING_METRIC_TYPES:
        return {
            "category": metric,
            "confidence": 0.80,
            "method": "threshold_warning",
        }

    return {
        "category": "unknown_metric",
        "confidence": 0.60,
        "method": "threshold_info",
    }
