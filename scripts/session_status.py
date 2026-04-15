"""
session_status.py — Live terminal status display for run_session.py.

Pure display utility: zero imports from domains/ or engine/.
Falls back gracefully if rich is not installed.
"""

from __future__ import annotations

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


class StatusDisplay:
    """Rich-backed live terminal panel for session progress."""

    def __init__(self) -> None:
        """Set up the rich Live display. Does not start it yet."""
        self._preflight: bool | None = None
        self._stream_state: str = "armed"
        self._done_message: str = ""
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
    # Internal rendering
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        if self._live is not None and self._live.is_started:
            self._live.update(self._build_table())

    def _build_table(self) -> "Table":
        if not _RICH_AVAILABLE:
            # Return empty object; this path should not be reached
            raise RuntimeError("rich not available")

        table = Table(
            title="Miktos Session Monitor",
            show_header=False,
            show_edge=True,
            padding=(0, 1),
        )
        table.add_column("stage", style="dim", width=9)
        table.add_column("slot", width=20)
        table.add_column("bar", width=6)
        table.add_column("status", width=20)

        # Header row — preflight + stream state
        pf_icon = (
            "✅" if self._preflight is True
            else "❌" if self._preflight is False
            else "…"
        )
        stream_raw = _STREAM_STATE_DISPLAY.get(self._stream_state, self._stream_state)
        if self._stream_state == "live":
            stream_text = Text(stream_raw, style="bold green")
        elif self._stream_state == "recording_stopped":
            stream_text = Text(stream_raw, style="yellow")
        elif self._stream_state == "done":
            stream_text = Text(stream_raw, style="green")
        else:
            stream_text = Text(stream_raw, style="dim")

        table.add_row(
            Text("Pre-flight", style="bold"),
            pf_icon,
            Text("Stream", style="bold"),
            stream_text,
        )
        table.add_section()

        # Pipeline rows grouped by stage
        for stage_num, slots in _STAGE_SLOTS.items():
            first = True
            for slot in slots:
                status = self._slots.get(slot, "pending")
                bar = _STATUS_DISPLAY.get(status, status)
                stage_label = (
                    Text(f"Stage {stage_num}", style="bold") if first
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

                table.add_row(stage_label, slot, bar_text, Text(status, style="dim"))

        # Completion message
        if self._done_message:
            table.add_section()
            table.add_row(
                Text(""),
                Text(
                    f"✅ Session complete — report: {self._done_message}",
                    style="green",
                ),
                Text(""),
                Text(""),
            )

        return table
