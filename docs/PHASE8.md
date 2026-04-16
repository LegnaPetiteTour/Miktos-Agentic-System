# Phase 8 Spec — Epiphan Pearl Domain Adapter

**Branch:** `phase-8/epiphan-pearl`
**Vision:** Miktos as the operations hub above the stack — not replacing Pearl,
but extracting its full power through a unified workflow.

---

## Phase 8a ✅ COMPLETE

**Completed:** 2026-04-16
**Latest commit after commissioning:** `1e095c3`
**Tests:** 103 passed, 1 skipped

See Phase 8a section in prior spec history for full detail.
6 bugs found and fixed (1 by disk audit, 5 by live commissioning).
3 clean Pearl sessions run 2026-04-16 to meet Phase 8b gate.

---

## Phase 8b — Live Layout Control ✅ COMPLETE

**Completed:** 2026-04-16
**Commit:** `190d957`
**Tests:** 108 passed, 1 skipped

### What was built

**`scripts/pearl_control.py`** — 3 subcommands:

```bash
# List all layouts on a channel, marks the active one
python scripts/pearl_control.py layouts --channel 2

# Switch by name (fuzzy) or exact ID
python scripts/pearl_control.py switch --channel 2 --layout speaker
python scripts/pearl_control.py switch --channel 2 --layout 3

# Show active layout — one channel or all
python scripts/pearl_control.py status
python scripts/pearl_control.py status --channel 2
```

Name resolution order: exact ID → exact name (case-insensitive) → substring match.
Unknown layout returns a clear error with available names listed.
`switch_layout` is never called if name resolution fails.

**`pearl_client.py`** — 2 new methods:

```python
get_layouts(channel_id)        # GET /api/channels/{cid}/layouts
get_active_layout(channel_id)  # GET /api/channels/{cid}/layouts/active
```

**`tests/test_phase_8b_layout_control.py`** — 5 tests:

1. `test_layout_list_parsed` — mock layouts list, active marked correctly
2. `test_layout_fuzzy_match` — substring / exact-ID / no-match branches
3. `test_layout_switch_calls_api` — name resolved, `switch_layout` called with correct ID
4. `test_layout_switch_unknown_returns_error` — error returned, API never called
5. `test_status_shows_current_layout` — all channels shown with active layout name

### Architecture invariant confirmed

- Engine unchanged
- Layout switching is additive — no changes to `PostStreamCoordinator` or any worker
- All 103 prior tests pass unmodified
- `PearlClient` never stores credentials

---

## Phase 8 ✅ COMPLETE

Both sub-phases sealed. The system now has:
- OBS domain: post-stream automation (reactive)
- Pearl domain: post-stream automation + live layout control (active)
- Two proven patterns: reactive and active

**Gate to Phase 9:** 10 total clean sessions (currently 5 of 10).

---

## Pearl API Surface (confirmed from live device)

**Device:** Pearl-2 at 192.168.2.45, firmware 4.24.3
**REST API v2.0 base:** `http://{pearl_ip}/api/`
**Swagger:** `http://192.168.2.45/swagger/`

### Confirmed state strings (corrected from commissioning)

| Property | Value |
|---|---|
| Recorder active | `"started"` |
| Recorder stopped | `"stopped"` |
| Publisher active | `result[n]["status"]["state"] == "started"` |

### Test channel config

| Field | Value |
|---|---|
| EN channel/recorder | `2` — PIMR Test Master-EN |
| FR channel/recorder | `3` — PIMR Test Master-FR |

---

## What Phase 9 Becomes

With Phase 8 complete, Phase 9 is the production cockpit — the `rich` terminal
interface from Phase 7b extended into a unified panel:
- Hardware selector (OBS or Pearl)
- Live health per domain
- Current layout per Pearl channel
- Layout switching via keypress
- Post-stream stage progress

Terminal-first. Web GUI (Stage 3 of vision) after Phase 9 validated.

---

*Phase 8a sealed 2026-04-16 at 1e095c3, 103 passed.*
*Phase 8b sealed 2026-04-16 at 190d957, 108 passed.*
