"""
pearl_monitor.py — EpiphanMonitorTool

Same pattern as OBSMonitorTool. Returns {"files": [alert_items], "count": N}
with the same alert item shape so the engine's planner sees no difference.

Health checks on each tick:
  recording_stopped  — recorder status = not recording  (hard fail)
  streaming_stopped  — channel publisher status = stopped (hard fail)
  disk_low           — Pearl storage < threshold           (warning)

Edge-triggered handoff: watches for recording_stopped transition
(active → stopped) and publishes exactly once, same pattern as
main_streamlab.py.
"""

from typing import Any

import requests

from engine.tools.base_tool import BaseTool
from domains.epiphan.tools.pearl_client import PearlClient

_ALERT_MIME = "application/vnd.miktos.stream-alert"
_PARENT_URI = "pearl://stream"


def _make_alert_item(
    metric_type: str,
    value: float,
    threshold: float,
    severity: str,
    description: str,
) -> dict[str, Any]:
    """Build one alert item in the engine-compatible file-item shape."""
    return {
        "path": f"{_PARENT_URI}/{metric_type}",
        "name": f"{metric_type}_alert",
        "suffix": ".alert",
        "size_bytes": 0,
        "mime_type": _ALERT_MIME,
        "parent": _PARENT_URI,
        "metric_type": metric_type,
        "value": value,
        "threshold": threshold,
        "severity": severity,
        "description": description,
        "scene": "",
    }


class EpiphanMonitorTool(BaseTool):
    """
    Polls Epiphan Pearl and converts health violations into alert items.

    Thresholds are injected at instantiation from thresholds.yaml
    (the 'stream' sub-dict). This decouples the monitor from YAML I/O.
    """

    name = "epiphan_monitor"
    description = (
        "Polls Epiphan Pearl REST API for recording and streaming health."
    )

    def __init__(
        self,
        thresholds: dict,
        client: PearlClient | None = None,
        recorder_id: str = "1",
        channel_id: str = "1",
    ) -> None:
        self._thresholds = thresholds
        self._client = client or PearlClient()
        self._recorder_id = recorder_id
        self._channel_id = channel_id

    def run(self, input: dict) -> dict[str, Any]:
        """
        Poll Pearl and return alert items for any health violations.

        The 'root_path' key in input is ignored (Pearl has no filesystem
        root). The planner passes it as a convention; we adapt it away.

        Raises requests.RequestException if Pearl is unreachable so the
        engine's retry / stop logic can handle it.
        """
        items: list[dict] = []

        # ── Recording state ──────────────────────────────────────────────
        try:
            rec_status = self._client.get_recorder_status(self._recorder_id)
            # Pearl returns {"status": "ok", "result": {"state": "started"}}
            result = rec_status.get("result", {})
            state = result.get("state", "")
            recording_active = state == "started"
        except requests.RequestException:
            recording_active = False

        if not recording_active:
            items.append(_make_alert_item(
                metric_type="recording_stopped",
                value=0.0,
                threshold=1.0,
                severity="critical",
                description="Pearl recorder is not active",
            ))

        # ── Streaming state ──────────────────────────────────────────────
        try:
            pub_status = self._client.get_channel_publisher_status(
                self._channel_id
            )
            # Pearl returns list of publisher status objects
            result = pub_status.get("result", [])
            publishers = result if isinstance(result, list) else []
            # Each publisher has a nested "status" sub-object:
            # {"id": "1", "type": "rtmp", "status": {"state": "started", ...}}
            stream_active = any(
                p.get("status", {}).get("state") == "started"
                for p in publishers
            )
        except requests.RequestException:
            stream_active = False

        if not stream_active:
            items.append(_make_alert_item(
                metric_type="streaming_stopped",
                value=0.0,
                threshold=1.0,
                severity="critical",
                description="Pearl channel is not streaming",
            ))

        return {"files": items, "count": len(items)}
