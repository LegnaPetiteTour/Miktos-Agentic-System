"""
Alert classifier for the StreamLab domain.

Receives a metric alert item dict (as produced by OBSMonitorTool) and
returns category / confidence / method — the exact contract the engine's
execution node expects from any classifier callable.

Confidence tier table (eight rules):

  Rule                              Category          Confidence  Method
  ──────────────────────────────────────────────────────────────────────
  stream_down                       stream_down       0.95        threshold_critical
  dropped_frames, severity=critical dropped_frames    0.95        threshold_critical
  dropped_frames, severity=warning  dropped_frames    0.80        threshold_warning
  cpu_overload,   severity=critical cpu_overload      0.95        threshold_critical
  cpu_overload,   severity=warning  cpu_overload      0.80        threshold_warning
  render_lag      (always warning)  render_lag        0.80        threshold_warning
  memory_pressure (always warning)  memory_pressure   0.80        threshold_warning
  recording_stopped                 recording_stopped 0.95        threshold_critical
  unknown metric with valid MIME    unknown_metric    0.60        threshold_info
  missing / "unknown" MIME          unclassified      0.40        fallback

Confidence → engine threshold mapping:
  0.95 → auto_approve (immediate action)
  0.80 → review_queue (warning — human review)
  0.60 → review_queue (info — borderline)
  0.40 → skipped      (fallback — no MIME)

Design constraints:
  - The _NO_MIME invariant from the file_analyzer pattern applies:
    items with no mime_type or mime_type == "unknown" fall back to
    0.40 (skipped) — they are never promoted to a higher tier.
  - metric_type is the primary classifier signal. severity is used
    only to distinguish critical vs. warning within the same metric.
  - This function never raises.
"""

# Items without a recognisable MIME type signal a malformed payload.
_NO_MIME: set[str] = {"", "unknown"}

_CRITICAL_METRIC_TYPES = {
    "stream_down",
    "recording_stopped",
}

_TIERED_METRIC_TYPES = {
    "dropped_frames",
    "cpu_overload",
}

_WARNING_ONLY_METRIC_TYPES = {
    "render_lag",
    "memory_pressure",
}


def classify_alert(item: dict) -> dict:
    """
    Classify a stream metric alert item.

    Args:
        item: dict with at least 'metric_type', 'severity', 'mime_type'.

    Returns:
        dict with 'category', 'confidence', 'method'.
    """
    mime_type: str = item.get("mime_type", "")
    metric_type: str = item.get("metric_type", "")
    severity: str = item.get("severity", "")

    # _NO_MIME invariant — malformed items are never promoted
    if mime_type in _NO_MIME:
        return {
            "category": "unclassified",
            "confidence": 0.40,
            "method": "fallback",
        }

    # Always-critical metrics
    if metric_type in _CRITICAL_METRIC_TYPES:
        return {
            "category": metric_type,
            "confidence": 0.95,
            "method": "threshold_critical",
        }

    # Metrics with critical / warning tiers
    if metric_type in _TIERED_METRIC_TYPES:
        if severity == "critical":
            return {
                "category": metric_type,
                "confidence": 0.95,
                "method": "threshold_critical",
            }
        return {
            "category": metric_type,
            "confidence": 0.80,
            "method": "threshold_warning",
        }

    # Warning-only metrics
    if metric_type in _WARNING_ONLY_METRIC_TYPES:
        return {
            "category": metric_type,
            "confidence": 0.80,
            "method": "threshold_warning",
        }

    # Known MIME, unrecognised metric_type → info tier
    return {
        "category": "unknown_metric",
        "confidence": 0.60,
        "method": "threshold_info",
    }
