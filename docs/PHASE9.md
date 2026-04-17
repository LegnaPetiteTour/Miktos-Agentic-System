# Phase 9 Spec — Production Cockpit

**Branch:** `phase-9/production-cockpit`
**Vision:** A unified terminal panel that replaces the split-terminal
workflow and surfaces hardware state, live health, and pipeline progress
in one place.

---

## Phase 9 ✅ COMPLETE

**Completed:** 2026-04-17
**Commit:** `e29c949`
**Tests:** 108 passed, 1 skipped

---

## What Was Built

### `scripts/session_status.py` — StatusDisplay extended

`StatusDisplay` now accepts hardware context at construction and renders
a unified `rich.live.Live` panel with four sections:

**Hardware header**
- Shows `Epiphan Pearl {host}` or `OBS`
- Pre-flight pass/fail indicator

**Live health section**
- Stream state: `○ ARMED` / `● LIVE` / `■ STOPPED` / `✓ DONE`
- Tick counter `#0042`
- Alert state: 🔴 critical / ⚠️  warning / none (with approved count)
- Elapsed timer `HH:MM:SS` tracked from `start()`

**Pearl layouts section** (only shown when `hardware=epiphan`)
- Reads `data/logs/layout_log.jsonl` at 4 Hz refresh
- Displays last known layout per channel (e.g. `Ch 2 (EN): Speaker View`)
- Hidden entirely for OBS sessions

**Pipeline section**
- Stages 1–4 with per-slot status: `pending / running / ✅ / ❌ / —`
- 2-column layout: stage label + slot+status

**Completion row**
- Session folder path + elapsed time on success

### `scripts/run_session.py` — integration

- Session config read moved before display init so `hardware` and Pearl
  info are available at construction
- `StatusDisplay(hardware=, pearl_host=, pearl_channels=, layout_log=)` wired
- `_RE_TICK` regex parses monitor tick lines → calls `set_tick(tick, alert, approved)`
- Duplicate config read in Step 3 removed
- `_kill_stale_listener()` added (orphan fix, commit `a6532ee`)

### `scripts/pearl_control.py` — layout log writer

`cmd_switch` appends a JSON line to `data/logs/layout_log.jsonl` after
every successful layout switch. The cockpit picks it up on the next 4 Hz
refresh. Format:
```json
{"ts": "2026-04-17T...", "channel": "2", "layout_id": "3", "layout_name": "Speaker View"}
```

---

## Architecture Invariants

- Engine unchanged
- `session_status.py` has zero imports from `domains/` or `engine/`
- All prior behaviour preserved — Phase 9 is purely additive
- Graceful fallback if `rich` not installed (raw stdout still printed)
- 108 prior tests pass unmodified

---

*Spec written 2026-04-17. Phase 9 sealed at e29c949.*
