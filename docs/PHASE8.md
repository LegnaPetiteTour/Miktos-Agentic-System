# Phase 8 Spec — Epiphan Pearl Domain Adapter

**Branch:** `phase-8/epiphan-pearl`
**Vision:** Miktos as the operations hub above the stack — not replacing Pearl,
but extracting its full power through a unified workflow.

This spec governs two sub-phases with a gate between them.

---

## Context: What Phase 8 Proves

Phase 5 proved the post-stream pipeline works for one hardware backend (OBS).
Phase 8 proves the engine is genuinely multi-domain: a second hardware backend
(Epiphan Pearl) plugs into the same engine, uses the same post-stream workers,
and the engine requires zero changes.

Phase 8b then proves the second dimension of the vision: Miktos can issue
commands to hardware during a live stream, not just react after it ends.

---

## Pearl API Surface (confirmed from live device at 192.168.2.45)

**Device confirmed:** Pearl-2, firmware 4.24.3
**Swagger UI:** `http://192.168.2.45/swagger/` (REST API v2.0, OAS 3.0)

### Modern REST API (v2.0) — preferred
- Base URL: `http://{pearl_ip}/api/`
- Auth: HTTP Basic Auth (`admin:{password}`)
- JSON responses

### Confirmed working endpoints

```
GET  /api/channels
     → {"status":"ok","result":[{"id":"1","name":"Master-EN"}, ...]}

GET  /api/recorders
     → 11 recorders: same IDs as channels + {"id":"m1","multisource":true}

GET  /api/recorders/{rid}/archive/files
GET  /api/recorders/{rid}/archive/files/{fid}  ← download
GET  /api/system/firmware
GET  /api/system/ident
GET  /api/channels/{cid}/publishers/status
POST /api/channels/{cid}/publishers/control/start
POST /api/channels/{cid}/publishers/control/stop
PUT  /api/channels/{cid}/layouts/active
GET  /api/inputs
```

### Live API state strings (corrected from commissioning 2026-04-16)

These values were wrong in the initial spec. Corrected from live device behaviour:

| Field | Wrong assumption | Actual value |
|---|---|---|
| Recorder active | `state == "recording"` | `state == "started"` |
| Recorder stopped | `state == "stopped"` | `state == "stopped"` ✅ |
| Publisher active | `result[n]["state"] == "publishing"` | `result[n]["status"]["state"] == "started"` |
| Publisher stopped | — | `result[n]["status"]["state"] != "started"` |

Publisher status is a **nested object**: `result` is a list, each item has a
`"status"` key containing `{"state": "started"}` — not a flat `"state"` key.

### Test recorder configuration (live device, 2026-04-16)

| Field | Value |
|---|---|
| Test EN channel/recorder | `2` — "PIMR - Test Master-EN" |
| Test FR channel/recorder | `3` — "PIMR - Test Master-FR" |
| Production EN | `1` — "Master-EN" (inactive during testing) |
| Production FR | `4` — "Master-FR" (inactive during testing) |

`session_config.yaml` uses `channel_en: 2, channel_fr: 3` for all commissioning runs.

### Environment variables

```
PEARL_HOST=192.168.2.45
PEARL_PORT=80
PEARL_PASSWORD=       # empty — no admin password set on this device
```

---

## Phase 8a — Pearl Monitor + Post-Stream Automation ✅ COMPLETE

**Completed:** 2026-04-16
**Latest commit:** `1e095c3`
**Tests:** 103 passed, 1 skipped

### Files delivered

| File | Description |
|---|---|
| `domains/epiphan/tools/pearl_client.py` | REST + legacy HTTP client, auth, chunked download |
| `domains/epiphan/tools/pearl_monitor.py` | EpiphanMonitorTool — health → alert items |
| `domains/epiphan/tools/alert_classifier.py` | classify_alert for Pearl alert items |
| `domains/epiphan/config/thresholds.yaml` | Pearl health thresholds |
| `domains/epiphan/config/pearl_config.example.yaml` | Connection + channel config reference |
| `domains/streamlab_post/workers/recording_download_worker.py` | Pre-Stage 1 HTTP pull from Pearl |
| `main_epiphan.py` | Entry point — outer loop, `--recorder` flag, edge-triggered handoff |
| `scripts/prepare_session.py` | Extended with hardware selector + Pearl channel prompts |
| `scripts/run_session.py` | Routes to `main_epiphan.py` or `main_streamlab.py` |
| `domains/streamlab_post/coordinator.py` | Pre-Stage 1 Epiphan block |
| `domains/streamlab_post/pre_flight/checker.py` | Skip OBS check when `hardware: epiphan` |
| `tests/test_phase_8a_epiphan.py` | 9 tests |
| `tests/test_hardening_prepare_session.py` | Fixed 3 tests for hardware prompt |

### Bugs — audit-caught before sealing

**`coordinator.py` NameError (caught by disk audit, fixed `77a2a7e`):**
`all_results` referenced before initialization in the Pre-Stage 1 Epiphan block.
Fixed by moving `accumulated`/`all_results` initialization before the block.
Test `test_coordinator_epiphan_pre_stage1` added to cover this path.

### Bugs — found during live commissioning (2026-04-16)

Five bugs found across two live session attempts. All fixed before a clean run.

**Bug 1 — `checker.py` crashed on OBS check for epiphan sessions (`3a2bdb2`):**
`PreFlightChecker` unconditionally called `obs_check.run()` which tried to
connect to OBS WebSocket. OBS is not running for Pearl sessions.
Fix: read `session_config.yaml`, inject synthetic ✅ result when `hardware: epiphan`.

**Bug 2 — Wrong recorder state string in `pearl_monitor.py` (`3a2bdb2`):**
Code checked `state == "recording"` — Pearl actually returns `"started"`.
Fix: `state == "started"`.

**Bug 3 — Wrong publisher status path in `pearl_monitor.py` (`3a2bdb2`):**
Code read `p.get("state")` — Pearl actually returns `p["status"]["state"]`.
Fix: `p.get("status", {}).get("state") == "started"`.

**Bug 4 — `str(Path("")) == "."` bypass in `coordinator.py` (`5f59720`):**
Epiphan handoff payload has no `file_path` or `recordings_path` key.
`Path("") → "."` → `"."` is truthy → `not file_path` was False →
the `if hardware == "epiphan" and not file_path:` guard never fired.
Fix: treat `"."` same as `""` — `rp_str if rp_str not in ("", ".") else ""`.

**Bug 5 — `post.wait(timeout=5)` killed pipeline before completion (`fccaef0`):**
`run_session.py` `finally` block sent SIGTERM to `main_post_stream.py` with
only 5s timeout. Pearl recording download + 4-stage pipeline needs 60–120s+.
Fix: `post.wait(timeout=300)`.

**Bug 6 — Ctrl+C SIGINT propagated to post-stream subprocess (`1e095c3`):**
macOS propagates Ctrl+C to all child processes in the foreground group.
`main_post_stream.py` received SIGINT and exited before polling its inbox.
Fix: `start_new_session=True` in `subprocess.Popen` — shields the listener
from terminal SIGINT.

### Architecture invariant confirmed

```
grep -r 'from engine.graph' domains/epiphan/  → (no output)
```

Engine unchanged. All 94 prior tests pass unmodified.

---

## Correct Procedure for Pearl Sessions

**Order matters. Follow exactly.**

```
1. On Pearl-2: start recording on the test channel
2. python scripts/run_session.py
3. Watch ticks — alerts=0 means recording active and healthy
4. On Pearl-2: stop recording
5. Terminal prints: → Published recording_stopped to N subscriber(s)
6. Press Ctrl+C once
7. Terminal prints: Waiting for post-stream pipeline to finish…
8. DO NOT press Ctrl+C again — wait ~2-3 minutes
9. Pipeline completes, session report prints, prompt returns
10. Verify: data/sessions/{session_name}/ contains .mp4/.mov, .mp3, _report.html
```

**Common mistakes:**
- Starting `run_session.py` when recording is already stopped →
  `was_recording_active` never becomes True → handoff never fires
- Pressing Ctrl+C twice → SIGINT propagated → pipeline killed mid-run

---

## Phase 8b — Live Layout Control 🔜 NEXT

**Depends on:** 3 clean Pearl sessions (0 of 3 complete as of 2026-04-16).

### Objective

`scripts/pearl_control.py` — CLI to switch Pearl layouts during a live stream.
Stage 2 of the vision: Miktos moves from observer to coordinator.

### API endpoint (confirmed from Swagger)

```
PUT /api/channels/{cid}/layouts/active
Body: {"id": "{layout_id}"}
```

### CLI

```bash
python scripts/pearl_control.py layouts --channel 2
python scripts/pearl_control.py switch --channel 2 --layout speaker
python scripts/pearl_control.py switch --channel 3 --layout interpreter
python scripts/pearl_control.py status
```

### Tests (`tests/test_phase_8b_layout_control.py`) — ~4 tests

1. `test_layout_list_parsed`
2. `test_layout_fuzzy_match`
3. `test_layout_switch_calls_api`
4. `test_status_shows_current_layout`

### Seal criteria

- Tests pass, prior tests unmodified
- `layouts --channel 2` returns layout names from live Pearl-2
- `switch --channel 2 --layout speaker` verified on Pearl-2 touch screen
- No disruption to recording or streaming during switch

---

## Architecture Invariants

- Engine unchanged across both sub-phases
- No imports from `engine/graph/` in any new domain file
- All prior tests pass unmodified
- `PearlClient` never stores credentials — reads from env vars only
- `RecordingDownloadWorker` never raises exceptions
- Layout switching additive — no changes to `PostStreamCoordinator` or any existing worker

---

## Pre-Implementation Gate: MET ✅ (2026-04-16)

```
GET /api/channels  → 200 OK, 10 channels
GET /api/recorders → 200 OK, 11 recorders
Legacy API confirmed: product_name=Pearl-2, firmware_version=4.24.3
Swagger: http://192.168.2.45/swagger/ (REST API v2.0, OAS 3.0)
RecordingDownloadWorker verified: 183 MB downloaded in 3.6s
```

---

*Spec written 2026-04-15. API paths corrected 2026-04-16.*
*Phase 8a sealed at 77a2a7e; commissioning bugs fixed through 1e095c3.*
*6 bugs total: 1 caught by disk audit, 5 caught by live commissioning.*
