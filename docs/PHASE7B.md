# Phase 7b Spec — Live Terminal Status View

**Branch:** `phase-7b/terminal-status`
**Objective:** Show real-time session progress in the terminal while
`run_session.py` is running. The operator can see what stage the pipeline
is on without tailing a log file.

This document is the authoritative implementation spec for VS Code.

---

## Context

`run_session.py` currently runs `main_streamlab.py --handoff` in the foreground
and pipes post-stream output to the terminal via a daemon thread. The operator
sees raw log lines. Phase 7b replaces that raw output with a structured status
panel using the `rich` library.

The HTML report (Phase 7a) is the permanent record of what happened.
The terminal view is the live indicator while it is happening.

---

## New Dependency

```toml
# pyproject.toml — add to dependencies:
"rich>=13.0",
```

---

## Architecture: Two New Files + One Modified

```
scripts/session_status.py          ← NEW: StatusDisplay class
scripts/run_session.py             ← MODIFIED: use StatusDisplay
tests/test_phase_7b_status.py      ← NEW: ~5 tests
```

No domain or engine changes. `session_status.py` is a pure display utility
with no imports from `domains/` or `engine/`.

---

## `scripts/session_status.py` — StatusDisplay

### Purpose
A thin wrapper around `rich.live.Live` and `rich.table.Table` that
`run_session.py` drives by calling simple update methods.

### Class interface

```python
class StatusDisplay:
    def __init__(self) -> None:
        """Set up the rich Live display. Does not start it yet."""

    def start(self) -> None:
        """Begin rendering. Call before streaming starts."""

    def stop(self) -> None:
        """Stop rendering. Call in the finally block."""

    def set_preflight(self, passed: bool) -> None:
        """✅ / ❌ pre-flight result."""

    def set_stream_state(self, state: str) -> None:
        """
        Update the stream state indicator.
        state: 'armed' | 'live' | 'recording_stopped' | 'done'
        """

    def set_stage(self, stage: int, slot: str, status: str) -> None:
        """
        Update a slot row in the pipeline table.
        stage: 1–4
        slot:  e.g. 'backup_verify'
        status: 'pending' | 'running' | 'ok' | 'failed' | 'skipped'
        """

    def set_session_done(self, report_path: str) -> None:
        """Show the final completion line with report path."""
```

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  Miktos Session Monitor                                          │
│  Pre-flight  ✅  Stream  ● LIVE                                    │
├──────────────────────────────────────────────────────────────────────┤
│  Stage 1  backup_verify  ━━━━  running                         │
│           youtube_en     ····  pending                         │
│           audio_extract  ····  pending                         │
│  Stage 2  —              ····  waiting                         │
│  Stage 3  —              ····  waiting                         │
│  Stage 4  —              ····  waiting                         │
└──────────────────────────────────────────────────────────────────────┘
```

After session completes:
```
│  ✅ Session complete — report: 2026-04-15_Miktos-Demo_005_report.html      │
```

### Status icons

| status | display |
|---|---|
| `pending` | `····` (dim) |
| `running` | `━━━━` (yellow spinner or static bar) |
| `ok` | `✅` |
| `failed` | `❌` |
| `skipped` | `—` (dim) |

### Stream state indicators

| state | display |
|---|---|
| `armed` | `○ ARMED` (dim) |
| `live` | `● LIVE` (green bold) |
| `recording_stopped` | `■ STOPPED` (yellow) |
| `done` | `✓ DONE` (green) |

---

## `scripts/run_session.py` — Changes Required

The current `run_session.py` forwards post-stream output via `_forward_output()`
and runs the monitor in the foreground. Phase 7b replaces the raw output
forwarding with structured status updates.

### Graceful fallback

If `rich` is not installed, `run_session.py` must fall back to the current
behavior (raw output forwarding) without crashing:

```python
try:
    from scripts.session_status import StatusDisplay
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False
```

### How status updates reach the display

The post-stream coordinator logs to `message.log`. `run_session.py` already
forwards post-stream stdout. The cleanest approach for Phase 7b is to parse
the forwarded lines and call `display.set_stage()` when recognizable patterns
appear.

**Line patterns to match** (from existing coordinator/worker log output):

```
# Stage start (logged by coordinator before dispatching a stage):
"Stage 1"  → set_stage(1, slot, 'running') for each slot in stage
"Stage 2"  → same
...

# Slot completion (logged by workers):
"backup_verify" + (success indicator)  → set_stage(1, 'backup_verify', 'ok'/'failed')
```

IMPORTANT: Do not parse `message.log` directly. Parse the stdout lines that
`main_post_stream.py` already emits. If the line format changes, the fallback
is graceful: the status display just stays in its last known state.

**Stream state updates** come from `main_streamlab.py` stdout:
```
"Monitoring" or "Armed"     → set_stream_state('armed')
"recording_stopped"         → set_stream_state('recording_stopped')
```

### Modified `_forward_output` pattern

```python
def _forward_output(proc, display=None):
    for line in proc.stdout:
        text = line.decode()
        print(text, end="", flush=True)   # still print raw output
        if display:
            _update_display_from_line(display, text)
```

The raw output must still be printed. The display is additive, not a replacement.

---

## Tests — `tests/test_phase_7b_status.py`

Target: ~5 tests. All tests must run without a real terminal (mock `rich.live.Live`).

**Required tests:**

1. `test_status_display_instantiates_without_rich_crash`
   — `StatusDisplay()` succeeds

2. `test_set_preflight_passed`
   — `set_preflight(True)` updates internal state without raising

3. `test_set_preflight_failed`
   — `set_preflight(False)` updates internal state without raising

4. `test_set_stage_transitions`
   — calling `set_stage(1, 'backup_verify', 'running')` then
   `set_stage(1, 'backup_verify', 'ok')` produces correct state

5. `test_fallback_when_rich_not_available`
   — mock `ImportError` on `rich` import → `run_session.py` still starts
   without crashing (use `monkeypatch` to simulate missing `rich`)

---

## What to Report Back

When complete:
- Test count (88 prior + ~5 new, all passing, 1 permanent skip)
- `python scripts/run_session.py` output with OBS running — show what the
  terminal panel looks like during a real (or dry-run) session
- Confirm `python scripts/run_session.py` still works correctly when
  `rich` is uninstalled (`pip uninstall rich`)

This conversation audits `session_status.py`, the `run_session.py` changes,
and the test file on disk before sealing. Same protocol as all prior phases.

---

## Architecture Invariants

- No engine/ changes
- No domain/ changes
- `session_status.py` has zero imports from `domains/` or `engine/`
- All prior 88 tests pass unmodified
- `run_session.py` falls back gracefully if `rich` is not installed
- Raw stdout output from subprocesses is still printed (display is additive)
