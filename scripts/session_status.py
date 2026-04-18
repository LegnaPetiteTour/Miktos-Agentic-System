"""
session_status.py — Unified production cockpit display for run_session.py.

Pure display utility: zero imports from domains/ or engine/.
Falls back gracefully if rich is not installed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.text import Text

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False

# Canonical slot order (matches coordinator Stage 1–4 definitions)
_STAGE_SLOTS: dict[int, list[str]] = {
    1: ["backup_verify", "youtube_en", "audio_extract"],
    2: ["translate", "transcript"],
    3: ["youtube_fr", "file_rename"],
    4: ["notify", "report"],
}

_STATUS_DISPLAY: dict[str, str] = {
    "pending": "····",
    "running": "━━━━",
    "ok": "✅",
    "failed": "❌",
    "skipped": "—",
}

_STREAM_STATE_DISPLAY: dict[str, str] = {
    "armed": "○ ARMED",
    "live": "● LIVE",
    "recording_stopped": "■ STOPPED",
    "done": "✓ DONE",
}


def _fmt_elapsed(seconds: float) -> str:
    """Format elapsed seconds as HH:MM:SS."""
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


class StatusDisplay:
    """Rich-backed unified production cockpit for session progress."""

    def __init__(
        self,
        hardware: str = "obs",
        pearl_host: str = "",
        pearl_channels: dict[str, str] | None = None,
        layout_log: Path | None = None,
    ) -> None:
        """
        Set up the rich Live display. Does not start it yet.

        Args:
            hardware:        'obs' or 'epiphan'
            pearl_host:      Pearl device IP/hostname (shown in header)
            pearl_channels:  Mapping of channel_id -> label, e.g. {'2': 'EN', '3': 'FR'}
            layout_log:      Path to layout_log.jsonl written by pearl_control.py
        """
        self._hardware = hardware.lower()
        self._pearl_host = pearl_host
        self._pearl_channels: dict[str, str] = pearl_channels or {}
        self._layout_log = layout_log

        self._preflight: bool | None = None
        self._stream_state: str = "armed"
        self._done_message: str = ""
        self._tick: int = 0
        self._alert: str = "none"       # none | warning | critical
        self._approved_count: int = 0
        self._start_time: float | None = None

        # slot_key -> status string
        self._slots: dict[str, str] = {}
        for slots in _STAGE_SLOTS.values():
            for slot in slots:
                self._slots[slot] = "pending"

        if _RICH_AVAILABLE:
            self._console = Console()
            self._live = Live(
                self._build_table(),
                console=self._console,
                refresh_per_second=4,
                transient=False,
            )
        else:
            self._live = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin rendering. Call before streaming starts."""
        self._start_time = time.monotonic()
        if self._live is not None:
            self._live.start()

    def stop(self) -> None:
        """Stop rendering. Call in the finally block."""
        if self._live is not None:
            try:
                self._live.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # State setters
    # ------------------------------------------------------------------

    def set_preflight(self, passed: bool) -> None:
        """✅ / ❌ pre-flight result."""
        self._preflight = passed
        self._refresh()

    def set_stream_state(self, state: str) -> None:
        """
        Update the stream state indicator.
        state: 'armed' | 'live' | 'recording_stopped' | 'done'
        """
        self._stream_state = state
        self._refresh()

    def set_tick(
        self, tick: int, alert: str = "none", approved: int = 0
    ) -> None:
        """Update tick counter and alert state from the monitor loop output."""
        self._tick = tick
        self._alert = alert
        self._approved_count = approved
        self._refresh()

    def set_stage(self, stage: int, slot: str, status: str) -> None:
        """
        Update a slot row in the pipeline table.
        stage: 1–4 (used for context only; slot name is the key)
        slot:  e.g. 'backup_verify'
        status: 'pending' | 'running' | 'ok' | 'failed' | 'skipped'
        """
        self._slots[slot] = status
        self._refresh()

    def set_session_done(self, report_path: str) -> None:
        """Show the final completion line with report path."""
        self._done_message = report_path
        self._refresh()

    # ------------------------------------------------------------------
    # Pearl layout log reader
    # ------------------------------------------------------------------

    def _read_pearl_layouts(self) -> dict[str, str]:
        """
        Read the last active layout per channel from layout_log.jsonl.
        Returns {channel_id: layout_name}.
        """
        if not self._layout_log or not self._layout_log.exists():
            return {}
        layouts: dict[str, str] = {}
        try:
            for raw in self._layout_log.read_text().splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                    cid = str(entry.get("channel", ""))
                    name = entry.get("layout_name", entry.get("layout_id", "—"))
                    if cid:
                        layouts[cid] = name
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
        return layouts

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        if self._live is not None and self._live.is_started:
            self._live.update(self._build_table())

    def _build_table(self) -> "Table":
        if not _RICH_AVAILABLE:
            raise RuntimeError("rich not available")

        elapsed_str = (
            _fmt_elapsed(time.monotonic() - self._start_time)
            if self._start_time is not None
            else "00:00:00"
        )

        table = Table(
            title="Miktos Production Cockpit",
            show_header=False,
            show_edge=True,
            padding=(0, 1),
        )
        table.add_column("label", style="dim", width=18)
        table.add_column("value", width=40)

        # ── Hardware header ──────────────────────────────────────────────
        hw_label = "Epiphan Pearl" if self._hardware == "epiphan" else "OBS"
        hw_suffix = (
            f"  {self._pearl_host}"
            if self._pearl_host and self._hardware == "epiphan"
            else ""
        )
        table.add_row(
            Text("Hardware", style="bold"),
            Text(f"{hw_label}{hw_suffix}", style="bold cyan"),
        )
        pf_icon = (
            "✅ pre-flight passed" if self._preflight is True
            else "❌ pre-flight FAILED" if self._preflight is False
            else "… pre-flight pending"
        )
        pf_style = (
            "green" if self._preflight is True
            else "bold red" if self._preflight is False
            else "dim"
        )
        table.add_row(Text(""), Text(pf_icon, style=pf_style))
        table.add_section()

        # ── Live health ───────────────────────────────────────────────────
        table.add_row(Text("LIVE HEALTH", style="bold"), Text(""))

        stream_raw = _STREAM_STATE_DISPLAY.get(self._stream_state, self._stream_state)
        if self._stream_state == "live":
            stream_text = Text(stream_raw, style="bold green")
        elif self._stream_state == "recording_stopped":
            stream_text = Text(stream_raw, style="yellow")
        elif self._stream_state == "done":
            stream_text = Text(stream_raw, style="green")
        else:
            stream_text = Text(stream_raw, style="dim")
        table.add_row(Text("  Stream"), stream_text)

        tick_str = f"#{self._tick:>4}" if self._tick else "—"
        table.add_row(Text("  Tick"), Text(tick_str, style="dim"))

        if self._alert == "critical":
            alert_text = Text(
                f"🔴  {self._approved_count} alert(s) approved", style="bold red"
            )
        elif self._alert == "warning":
            alert_text = Text(
                f"⚠️   {self._approved_count} alert(s) queued", style="yellow"
            )
        else:
            alert_text = Text("none", style="dim green")
        table.add_row(Text("  Alert"), alert_text)
        table.add_row(Text("  Elapsed"), Text(elapsed_str, style="dim"))
        table.add_section()

        # ── Pearl Layouts ─────────────────────────────────────────────────
        if self._hardware == "epiphan" and self._pearl_channels:
            table.add_row(Text("PEARL LAYOUTS", style="bold"), Text(""))
            pearl_layouts = self._read_pearl_layouts()
            for cid, clabel in sorted(self._pearl_channels.items()):
                layout_name = pearl_layouts.get(cid, "—")
                table.add_row(
                    Text(f"  Ch {cid} ({clabel})"),
                    Text(layout_name, style="cyan"),
                )
            table.add_section()

        # ── Post-stream pipeline ──────────────────────────────────────────
        table.add_row(Text("PIPELINE", style="bold"), Text(""))
        for stage_num, slots in _STAGE_SLOTS.items():
            first = True
            for slot in slots:
                status = self._slots.get(slot, "pending")
                bar = _STATUS_DISPLAY.get(status, status)
                stage_label = (
                    Text(f"  Stage {stage_num}", style="bold") if first
                    else Text("")
                )
                first = False

                if status == "ok":
                    bar_text = Text(bar, style="green")
                elif status == "failed":
                    bar_text = Text(bar, style="red")
                elif status == "running":
                    bar_text = Text(bar, style="yellow")
                else:
                    bar_text = Text(bar, style="dim")

                row_val = Text()
                row_val.append(f"{slot:<22}", style="default")
                row_val.append_text(bar_text)
                table.add_row(stage_label, row_val)

        # ── Session complete ──────────────────────────────────────────────
        if self._done_message:
            table.add_section()
            table.add_row(
                Text(""),
                Text(
                    f"✅  Session complete — {self._done_message}  •  {elapsed_str}",
                    style="green",
                ),
            )

        return table
