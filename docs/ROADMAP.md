# Roadmap — Miktos Agentic System

---

## Phase 0 — Foundation ✅ COMPLETE

**Completed:** 2026-04-07

- [x] Repository initialized
- [x] Architecture locked
- [x] Tech stack decided
- [x] ADRs written
- [x] Repo structure defined

---

## Phase 1 — Engine + File Analyzer (Domain 1) ✅ COMPLETE

**Completed:** 2026-04-07
**Commit:** `e5466dd`
**Tests:** 18/18 passing

- [x] LangGraph graph wired (6 nodes)
- [x] File scanner + rule-based four-tier MIME classifier
- [x] Confidence bands, review queue, retry/exhaustion logic
- [x] Engine/domain separation verified

---

## Phase 2 — Domain 2 (Kosmos / Media Organizer) ✅ COMPLETE

**Completed:** 2026-04-08
**Commit:** `b7fcea4`
**Tests:** 22/22 passing

- [x] FileScannerTool promoted to engine/tools/shared_tools.py
- [x] Nine-rule media classifier with EXIF probe via Pillow
- [x] git diff main -- engine/graph/ empty — engine unchanged
- [x] Proof: second domain ran through the same engine without modification

---

## Phase 3 — StreamLab Integration ✅ COMPLETE

**Completed:** 2026-04-08
**Commit:** `0a2c894`
**Tests:** 25/25 passing, 1 skipped (live OBS)

- [x] OBS WebSocket client — credentials from env vars only
- [x] OBSMonitorTool adapts stream health violations to engine task shape
- [x] Outer-loop pattern — continuous monitoring without engine modification
- [x] Live run confirmed: domain="streamlab", scene="Testing Scene with Mac Camera"
- [x] git diff main -- engine/graph/ empty — engine unchanged across 3 phases

---

## Phase 4a — Parallel Execution ✅ COMPLETE

**Completed:** 2026-04-09
**Commit:** `7980fa1`
**Tests:** 29/29 passing, 1 skipped

**First legitimate engine modification — additive only, backward compatible.**

- [x] parallel_execution_node added alongside execution_node
- [x] _execution_target() + route_to_execution() in router.py
- [x] main_kosmos.py --parallel and --workers flags
- [x] engine/benchmarks/parallel_benchmark.py

**Benchmark proof (200 files, 8 workers):**

```text
Sequential  : 0.21s  (973.5 files/sec)
Parallel    : 0.05s  (3904.7 files/sec)
Speedup     : 4.0x
Correctness : PASS (200/200 actions match)
```

---

## Phase 4b — Agent-to-Agent Messaging ✅ COMPLETE

**Completed:** 2026-04-09
**Commit:** `ee259e2`
**Tests:** 34/34 passing, 1 skipped

- [x] engine/messaging/models.py — AgentMessage dataclass
- [x] engine/messaging/bus.py — MessageBus with atomic writes
- [x] agent_id + inbox_messages added to RunState (backward compatible)
- [x] message_trigger_node + build_graph_with_messaging() — additive
- [x] main_streamlab.py --handoff / main_kosmos.py --listen

---

## Phase 4c — Team / Task Delegation ✅ COMPLETE

**Completed:** 2026-04-09
**Commit:** PR #16
**Tests:** 39/39 passing, 1 skipped

- [x] engine/coordinator/workers.py — KosmosWorker, ThumbnailWorker, MetadataWorker
- [x] engine/coordinator/coordinator.py — SessionCoordinator, parallel dispatch, retry
- [x] engine/messaging/bus.py — append_log() wired into post()/acknowledge()
- [x] data/messages/message.log — append-only observability log
- [x] main_coordinator.py — --poll-interval / --once entry point
- [x] data/sessions/ — session artifacts per run

---

## Phase 4d — Event Bus (Pub/Sub) ✅ COMPLETE

**Completed:** 2026-04-09
**Commit:** PR #17
**Tests:** 44/44 passing, 1 skipped

**One event, multiple independent reactions. Publisher names zero recipients.**

- [x] bus.subscribe(topic, agent_id) — atomic JSON registry, idempotent
- [x] bus.unsubscribe(topic, agent_id) — atomic removal, no-op if absent
- [x] bus.publish(topic, from_agent, payload) — fan-out to N subscribers
- [x] main_streamlab.py --handoff now uses publish("recording_stopped")

---

## Phase 5 — Post-Stream Closure Engine ✅ COMPLETE

**Completed:** 2026-04-14
**Commits:** PR #18 + PR #19 + PR #20
**Tests:** 52/52 passing, 1 skipped

**Product:** Eliminates the manual post-stream checklist for bilingual EN/FR
institutional live streams. One stream-end event → full session closure.

- [x] domains/streamlab_post/ — new domain, engine unchanged
- [x] BackupVerificationWorker, AudioExtractWorker, YouTubeWorker
- [x] TranslationWorker, TranscriptWorker, FileRenameWorker, NotificationWorker
- [x] PostStreamCoordinator — 4-stage execution, inter-stage payload enrichment
- [x] main_post_stream.py — --dry-run / --once / --poll-interval entry point
- [x] scripts/youtube_auth.py — one-time OAuth2 refresh token setup

**4-stage execution model:**

```text
Stage 1 (parallel, required):  backup_verify   youtube_en    audio_extract
Stage 2 (parallel, optional):  translate       transcript
Stage 3 (parallel, optional):  youtube_fr      file_rename
Stage 4 (optional):            notify
```

---

## Phase 6 — Pre-Stream Readiness Check ✅ COMPLETE

**Completed:** 2026-04-14
**Commit:** `7a12e05` (PR #22)
**Tests:** 66 passed, 1 skipped

---

## Pre-Phase 7 — Operational Hardening ✅ COMPLETE

**Commit:** `afa3ba9` (PR #26)
**Tests:** 82 passed, 1 skipped

---

## Phase 7 — Operations Dashboard ✅ COMPLETE

### Phase 7a — Post-Session HTML Report ✅

**Commit:** `05b28fa` (PR #28) | **Tests:** 88 passed, 1 skipped

### Phase 7b — Live Terminal Status View ✅

**Commit:** `9b7d14e` (PR #30) | **Tests:** 94 passed, 1 skipped

---

## Phase 8 — Epiphan Pearl Domain Adapter ✅ COMPLETE

**Completed:** 2026-04-16

### Phase 8a — Pearl Monitor + Post-Stream Automation ✅

**Commit:** `1e095c3` | **Tests:** 103 passed, 1 skipped

### Phase 8b — Live Layout Control ✅

**Commit:** `190d957` | **Tests:** 108 passed, 1 skipped

---

## Phase 9 — Production Cockpit ✅ COMPLETE

**Completed:** 2026-04-17
**Commit:** `6db849d` (PR #32+#33)
**Tests:** 108 passed, 1 skipped

Unified `rich` terminal panel. Hardware header, live health, Pearl layouts,
pipeline progress, completion row. Gate: 10 clean production sessions.

---

## Phase 10 — Web Cockpit ✅ COMPLETE

### Phase 10a — Local Web Cockpit ✅

**Completed:** 2026-04-17 | **Commit:** `0e4c392` (PR #36) | **Tests:** 116 passed

FastAPI + HTMX browser cockpit. SSE live status, Pearl layout control,
session history, inline report viewer.

**Launch:** `.venv/bin/python -m web.server` → `http://localhost:8000`

### Phase 10b — Session Launch from GUI ✅

**Completed:** 2026-04-18 | **Commit:** `35201ae` (PR #37) | **Tests:** 122 passed

Start/Stop session from browser. SIGINT-based clean shutdown. Terminal fallback preserved.

**Phase 10c** (remote access, auth) — deferred until operational need arises.

---

## Phase 11 — Dual-Channel Bilingual Pipeline ✅ COMPLETE

**Completed:** 2026-04-19
**Commit:** `18c0f07` (PR #44)
**Tests:** 130 passed, 1 skipped

Both Pearl channels (EN recorder 2 + FR recorder 3) downloaded and processed
in a single session. All FR slots `required: False`.

**Session folder (7 files, 420 MB live proof):**

```text
EventName_EN, EventName_FR, EventName.mp3, EventName_FR.mp3
EventName_transcript.txt, EventName_FR_transcript.txt, EventName_report.html
```

---

## Stage 2 — Local Installable App

---

## Phase 12 — Operator Onboarding Wizard ✅ COMPLETE

**Completed:** 2026-04-30
**Commit:** `145fd99` (PR #48)
**Tests:** 140 passed, 1 skipped

Five-step browser wizard. New operator: zero to first session without
touching a terminal or editing a config file.

Steps: YouTube OAuth (EN + FR) → Google Translate → ElevenLabs
→ Hardware connection test → Ready.

`write_env_key()` atomic, preserves existing keys, never exposes values.

---

## Phase 13 — Electron Packaging (.dmg) ✅ COMPLETE

**Completed:** 2026-04-30
**Commit:** `39eb65e` + `937c9ea`
**Tests:** 140 passed, 1 skipped
**Artifact:** `Miktos-0.1.1.dmg` — 127 MB, arm64 + x64

Double-click install. Python runtime bundled via PyInstaller.
No terminal, no Python installation, no config files required.

- [x] `engine/paths.py` — portable path resolver (`MIKTOS_DATA_DIR`)
- [x] `miktos_entry.py` — PyInstaller entry point
- [x] `electron/main.js` — spawns server, polls :8000, BrowserWindow + Tray
- [x] Fresh install validated: all credentials written to Application Support

**Lesson:** `uvicorn.run("module:attr")` string form silently excludes the
module from the PYZ archive. Fix: direct import with explanatory comment.

---

## Phase 14 — Live Production Panel ✅ COMPLETE

**Completed:** 2026-05-02
**Commit:** `1208ecc` (PR #59)
**Tests:** 152 passed, 1 skipped

Four new cockpit panels covering the full live production workflow:

- [x] `web/api/switcher.py` — OBS scene list/switch + Pearl channel list
- [x] `web/api/health.py` — hardware + network health snapshot (always 200)
- [x] `web/api/audio_control.py` — OBS mute/volume control
- [x] `domains/captioning/caption_worker.py` — async tail-reader for captions.jsonl
- [x] `web/api/captions.py` — SSE caption stream + append endpoint
- [x] 4 HTMX panel templates (`panel_switcher`, `panel_health`, `panel_audio`, `panel_captions`)

**Caption worker architecture:** tail-reader pattern — any STT process writes
JSON lines to `data/captions/captions.jsonl`; the worker streams them to the
cockpit and pushes to YouTube caption ingestion URL. STT engine fully decoupled.

---

## Phase 15 — Visual Production Surface ✅ COMPLETE

**Completed:** 2026-05-02
**Commit:** `2ed7c4e` (PR #61)
**Tests:** 162 passed, 1 skipped

Visual confidence layer: operators see what is on air, not just names.

- [x] `web/api/preview.py` — `GET /api/preview/thumbnail?source=pearl_en|pearl_fr|obs`
  Returns base64 JPEG, always HTTP 200 (advisory, never blocking)
- [x] `web/api/graphics.py` — lower thirds, transitions, intro/outro
  - `POST /api/graphics/lower_third` — push text overlay to OBS Browser Source
  - `DELETE /api/graphics/lower_third` — clear overlay
  - `POST /api/graphics/transition` — trigger studio-mode transition
  - `POST /api/graphics/intro` and `/outro` — switch to intro/outro scenes
- [x] `web/templates/panel_preview.html` — 3-column thumbnail grid, polls every 2s
- [x] `web/templates/panel_graphics.html` — lower-third form, transition selector, intro/outro

**Thumbnails are advisory:** timestamped, fallback-safe. Device state and
active layout remain authoritative for switching decisions.

---

## Phase 16 — Adapter Contract + Operational Hardening ✅ COMPLETE

**Completed:** 2026-05-02
**Commit:** `8999412` (PR #62)
**Tests:** 175 passed, 1 skipped

Formal adapter contract (ADR-009) implemented. Cockpit renders controls
based on capabilities, not hardcoded hardware names.

- [x] `engine/adapters/base.py` — `DeviceAdapter` Protocol + `AdapterCapabilities` dataclass
- [x] `engine/adapters/pearl_adapter.py` — Pearl conforming to contract
- [x] `engine/adapters/obs_adapter.py` — OBS conforming to contract
- [x] `engine/adapters/registry.py` — `get_adapter()` via `HARDWARE_ADAPTER` env var
- [x] `web/api/action_log.py` — `GET /api/action_log/recent`, `POST /api/action_log/entry`
  Every operator action logged with timestamp, channel, result, error
- [x] `web/templates/panel_action_log.html` — last 10 actions panel
- [x] Caption reliability dashboard — LIVE/STALE badge, rate, lag, polls every 10s
- [x] `web/api/safe_mode.py` — `GET/POST /api/safe_mode/{state,activate,deactivate}`
  Best-effort OBS + Pearl stop on activate; state persisted to `data/state/safe_mode.json`
- [x] `web/templates/panel_safe_mode.html` — large red Emergency Stop button

**Adapter contract rule:** `capabilities()` must never require a live hardware
connection. All cockpit `{% if hardware == 'epiphan' %}` replaced by capability flags.

---

## Phase 17 — Run-of-Show + Rehearsal Mode ✅ COMPLETE

Session intelligence: structured event sequence, safe practice mode,
and session templates.

- Run-of-show engine (pre-defined sequence; AI compares reality against it)
- Rehearsal / simulation mode (practice without live systems)
- Session templates (press conference, council announcement, training, etc.)
- Improved post-event reports with run-of-show adherence

**Result:** 187 passed, 1 skip

---

## Phase 18 — Docker + Cockpit Layout 🔜 NEXT

Self-hosted deployment and cockpit multi-column grid restructure.

- Docker container + `docker-compose.yml` for institutional IT deployment
- Cockpit layout: multi-column grid (left: EN channel, right: FR channel,
  centre: production actions, right sidebar: health + automation)
- Single-password auth: shared password in `.env`, JWT tokens, no user database
  (full role management is Pro tier / Stage 3)
- Audit log persistence across container restarts

**Target:** ~200 passed, 1 skip

---

## Stage 3 — Self-Hosted Web App 🔜 FUTURE

Docker container, multi-operator, institutional IT deployment.
Auth, roles, audit, backup/restore. Depends on Stage 2 validated.

## Stage 4 — Hosted SaaS 🔜 FUTURE

Cloud-hosted, multi-tenant. Depends on Stage 3 validated.

---

*Last updated: 2026-05-03*
*Phases 0–17: complete and validated.*
*See docs/VISION.md and docs/PRODUCT.md for full product direction.*
