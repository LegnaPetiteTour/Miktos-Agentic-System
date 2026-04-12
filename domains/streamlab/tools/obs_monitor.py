"""
OBS health monitor — the StreamLab equivalent of FileScannerTool.

Polls OBS via WebSocket and returns a list of metric alert items.
Each item represents one stream health threshold violation.

This is the adapter layer between OBS and the Miktos engine:
  - The engine's planner calls scanner.safe_run({"root_path": ...})
  - OBSMonitorTool.run() ignores root_path and queries OBS instead
  - Returns {"files": [alert_items], "count": N} — the exact shape
    the planner expects from a scanner tool

A healthy stream with no violations returns {"files": [], "count": 0}.
The engine's planner then creates zero tasks and exits with success.

Alert item shape (mirrors file scanner output for engine compatibility):
  path         str  virtual URI, e.g. "obs://stream/dropped_frames"
  name         str  human label, e.g. "dropped_frames_alert"
  suffix       str  always ".alert"
  size_bytes   int  always 0 (no file size concept)
  mime_type    str  "application/vnd.miktos.stream-alert"
  parent       str  "obs://stream"
  metric_type  str  machine-readable metric key
  value        float  measured value at time of poll
  threshold    float  the crossing threshold
  severity     str  "critical" | "warning"
  description  str  human-readable summary
  scene        str  active OBS scene name at time of poll
"""

import os
from typing import Any

from engine.tools.base_tool import BaseTool
from domains.streamlab.tools.obs_client import OBSClientTool

_ALERT_MIME = "application/vnd.miktos.stream-alert"
_PARENT_URI = "obs://stream"


def _make_alert_item(
    metric_type: str,
    value: float,
    threshold: float,
    severity: str,
    description: str,
    scene: str = "",
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
        "scene": scene,
    }


class OBSMonitorTool(BaseTool):
    """
    Polls OBS and converts threshold violations into alert items.

    Thresholds are injected at instantiation from thresholds.yaml
    (the "stream" sub-dict). This decouples the monitor from YAML I/O.
    """

    name = "obs_monitor"
    description = "Polls OBS WebSocket for stream health violations."

    def __init__(self, thresholds: dict[str, float]) -> None:
        self._thresholds = thresholds
        self._client_tool = OBSClientTool()

    def run(self, input: dict) -> dict[str, Any]:
        """
        Poll OBS and return alert items for any threshold violations.

        The 'root_path' key in input is ignored — OBS has no filesystem
        root. The planner passes it as a convention; we adapt it away.

        Raises an exception if OBS is unreachable so the engine's
        retry / stop logic can handle it.
        """
        client = self._client_tool.connect()
        try:
            return self._poll(client)
        finally:
            self._client_tool.disconnect()

    def _poll(self, client: Any) -> dict[str, Any]:
        t = self._thresholds
        items: list[dict] = []

        stream_status = client.get_stream_status()
        stats = client.get_stats()
        record_status = client.get_record_status()
        scene_resp = client.get_current_program_scene()

        scene_name: str = getattr(
            scene_resp, "current_program_scene_name", ""
        )

        # ── Recording stopped check ─────────────────────────────────────────
        recording_active: bool = getattr(record_status, "output_active", False)

        if not recording_active:
            items.append(_make_alert_item(
                metric_type="recording_stopped",
                value=0.0,
                threshold=1.0,
                severity="critical",
                description="OBS recording is not active",
                scene=scene_name,
            ))

        # ── Stream active check ──────────────────────────────────────────
        stream_active: bool = getattr(stream_status, "output_active", False)

        if not stream_active:
            items.append(_make_alert_item(
                metric_type="stream_down",
                value=0.0,
                threshold=1.0,
                severity="critical",
                description="Stream output is not active",
                scene=scene_name,
            ))
        else:
            # Dropped frames — only meaningful while stream is live
            total_frames: int = (
                getattr(stream_status, "output_total_frames", 0) or 1
            )
            skipped_frames: int = getattr(
                stream_status, "output_skipped_frames", 0
            )
            dropped_pct = (skipped_frames / total_frames) * 100

            if dropped_pct > t["dropped_frames_pct_critical"]:
                items.append(_make_alert_item(
                    metric_type="dropped_frames",
                    value=round(dropped_pct, 2),
                    threshold=t["dropped_frames_pct_critical"],
                    severity="critical",
                    description=(
                        f"Dropped frames at {dropped_pct:.2f}% "
                        f"(threshold: {t['dropped_frames_pct_critical']}%)"
                    ),
                    scene=scene_name,
                ))
            elif dropped_pct > t["dropped_frames_pct_warning"]:
                items.append(_make_alert_item(
                    metric_type="dropped_frames",
                    value=round(dropped_pct, 2),
                    threshold=t["dropped_frames_pct_warning"],
                    severity="warning",
                    description=(
                        f"Dropped frames at {dropped_pct:.2f}% "
                        f"(threshold: {t['dropped_frames_pct_warning']}%)"
                    ),
                    scene=scene_name,
                ))

        # ── CPU usage ────────────────────────────────────────────────────
        cpu_usage: float = getattr(stats, "cpu_usage", 0.0)

        if cpu_usage > t["cpu_usage_critical"]:
            items.append(_make_alert_item(
                metric_type="cpu_overload",
                value=round(cpu_usage, 2),
                threshold=t["cpu_usage_critical"],
                severity="critical",
                description=(
                    f"CPU usage at {cpu_usage:.1f}% "
                    f"(threshold: {t['cpu_usage_critical']}%)"
                ),
                scene=scene_name,
            ))
        elif cpu_usage > t["cpu_usage_warning"]:
            items.append(_make_alert_item(
                metric_type="cpu_overload",
                value=round(cpu_usage, 2),
                threshold=t["cpu_usage_warning"],
                severity="warning",
                description=(
                    f"CPU usage at {cpu_usage:.1f}% "
                    f"(threshold: {t['cpu_usage_warning']}%)"
                ),
                scene=scene_name,
            ))

        # ── Render lag ───────────────────────────────────────────────────
        render_time_ms: float = getattr(
            stats, "average_frame_render_time", 0.0
        )

        if render_time_ms > t["render_lag_ms_warning"]:
            items.append(_make_alert_item(
                metric_type="render_lag",
                value=round(render_time_ms, 2),
                threshold=t["render_lag_ms_warning"],
                severity="warning",
                description=(
                    f"Render time {render_time_ms:.1f}ms "
                    f"(threshold: {t['render_lag_ms_warning']}ms)"
                ),
                scene=scene_name,
            ))

        # ── Memory usage (as % of system RAM) ───────────────────────────
        memory_usage_mb: float = getattr(stats, "memory_usage", 0.0)

        try:
            total_mb = (
                os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
            ) / (1024 * 1024)
        except (AttributeError, ValueError):
            total_mb = 8192.0  # fallback: assume 8 GB

        memory_pct = (memory_usage_mb / total_mb * 100) if total_mb > 0 else 0.0

        if memory_pct > t["memory_usage_warning"]:
            items.append(_make_alert_item(
                metric_type="memory_pressure",
                value=round(memory_pct, 2),
                threshold=t["memory_usage_warning"],
                severity="warning",
                description=(
                    f"OBS memory usage at {memory_pct:.1f}% "
                    f"({memory_usage_mb:.0f} MB, "
                    f"threshold: {t['memory_usage_warning']}%)"
                ),
                scene=scene_name,
            ))

        return {"files": items, "count": len(items)}
