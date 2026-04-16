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

### Key architectural insight

Recorder IDs mirror channel IDs — `channel_en` and `recorder_id` are the same value.
Channel IDs are NOT sequential: `1, 4, 8, 9, 13, 14, 17, 18, 19, 20`.

### Environment variables

```
PEARL_HOST      # Pearl-2 IP address (e.g. 192.168.2.45)
PEARL_PORT      # default: 80
PEARL_PASSWORD  # admin password (empty string if not set)
```

---

## Phase 8a — Pearl Monitor + Post-Stream Automation ✅ COMPLETE

**Completed:** 2026-04-16
**Commit:** `77a2a7e`
**Tests:** 103 passed, 1 skipped

### What was built

| File | Description |
|---|---|
| `domains/epiphan/tools/pearl_client.py` | REST + legacy HTTP client, auth, chunked download |
| `domains/epiphan/tools/pearl_monitor.py` | EpiphanMonitorTool — health → alert items |
| `domains/epiphan/tools/alert_classifier.py` | classify_alert for Pearl alert items |
| `domains/epiphan/config/thresholds.yaml` | Pearl health thresholds |
| `domains/epiphan/config/pearl_config.example.yaml` | Connection + channel config reference |
| `domains/streamlab_post/workers/recording_download_worker.py` | Pre-Stage 1 HTTP pull from Pearl |
| `main_epiphan.py` | Entry point — outer loop, `--recorder` flag, edge-triggered handoff |
| `scripts/prepare_session.py` | Extended with hardware selector + Pearl channel_en/fr prompts |
| `scripts/run_session.py` | Routes to `main_epiphan.py` or `main_streamlab.py` based on `hardware` |
| `domains/streamlab_post/coordinator.py` | Pre-Stage 1 Epiphan block; `accumulated`/`all_results` init fix |
| `tests/test_phase_8a_epiphan.py` | 9 tests (8 + coordinator integration test) |
| `tests/test_hardening_prepare_session.py` | Fixed 3 tests for extra hardware prompt |

### Bug caught during audit

`coordinator.py` Pre-Stage 1 block referenced `all_results` before it was
initialized. Caught by independent disk audit, fixed in `77a2a7e`.
Test 9 (`test_coordinator_epiphan_pre_stage1`) was added to cover this path.

### Architecture invariant confirmed

```
grep -r 'from engine.graph' domains/epiphan/  → (no output)
```

Engine unchanged. All 94 prior tests pass unmodified. 9 new tests added.

---

## Phase 8b — Live Layout Control 🔜 NEXT

**Depends on:** Phase 8a complete ✅ + 3 clean Pearl sessions.

### Objective

Miktos issues layout switch commands to Pearl during a live stream.
`pearl_control.py` lets the operator switch which Zoom participant feed
goes to which YouTube channel in real time. Stage 2 of the vision.

### API endpoint (confirmed from Swagger)

```
PUT /api/channels/{cid}/layouts/active
Body: {"id": "{layout_id}"}
```

### New file

```
scripts/pearl_control.py
```

### CLI

```bash
python scripts/pearl_control.py layouts --channel 1
python scripts/pearl_control.py switch --channel 1 --layout speaker
python scripts/pearl_control.py switch --channel 4 --layout interpreter
python scripts/pearl_control.py status
```

### Tests

`tests/test_phase_8b_layout_control.py` — ~4 tests:

1. `test_layout_list_parsed`
2. `test_layout_fuzzy_match`
3. `test_layout_switch_calls_api`
4. `test_status_shows_current_layout`

### Seal criteria

- Tests pass, prior tests unmodified
- `python scripts/pearl_control.py layouts --channel 1` returns layout names from live Pearl-2
- `python scripts/pearl_control.py switch --channel 1 --layout speaker` verified on touch screen
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
GET /api/recorders → 200 OK, 11 recorders (10 single + m1 multitrack)
GET /admin/channel1/get_params.cgi?firmware_version → 4.24.3
GET /admin/channel1/get_params.cgi?product_name → Pearl-2
Swagger: http://192.168.2.45/swagger/ (REST API v2.0, OAS 3.0)
```

---

*Spec written 2026-04-15. API paths corrected from live device 2026-04-16.*
*Phase 8a sealed 2026-04-16 at commit 77a2a7e, 103 passed, 1 skipped.*
