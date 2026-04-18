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

**Live round-trip proof:**

```text
1. Inbox polled  → recording_ready from streamlab_monitor
2. Kosmos ran    → 159 files classified from ~/Movies, exit=success
3. Acknowledged  → moved to kosmos_organizer/delivered/
4. Reply posted  → recording_organized, files_processed: 159
```

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

**Live proof (session 05b7a3154d20 confirmed on disk):**

```text
Session 05b7a3154d20
├── organize   ✅  videos (0.95)
├── thumbnail  ❌  moov atom not found  (stub — expected)
└── metadata   ✅  session.json  (0.0s)
exit: success | posted session_complete → streamlab_monitor
```

---

## Phase 4d — Event Bus (Pub/Sub) ✅ COMPLETE

**Completed:** 2026-04-09
**Commit:** PR #17
**Tests:** 44/44 passing, 1 skipped

**One event, multiple independent reactions. Publisher names zero recipients.**

- [x] bus.subscribe(topic, agent_id) — atomic JSON registry, idempotent
- [x] bus.unsubscribe(topic, agent_id) — atomic removal, no-op if absent
- [x] bus.publish(topic, from_agent, payload) — fan-out to N subscribers
- [x] data/messages/subscriptions.example.json — format reference, committed
- [x] main_streamlab.py --handoff now uses publish("recording_stopped")
- [x] scripts/dmo_preview.py — live one-publish two-delivery proof

**Live proof — message.log (confirmed on disk at 2026-04-09T23:05:55Z):**

```text
PUBLISHED  streamlab_monitor -> [2 subscriber(s)]  recording_stopped
POSTED     streamlab_monitor -> session_coordinator  recording_stopped
POSTED     streamlab_monitor -> kosmos_organizer    recording_stopped
ACKNOWLEDGED  (both)
```

---

## Phase 5 — Post-Stream Closure Engine ✅ COMPLETE

**Completed:** 2026-04-14
**Commits:** PR #18 (initial) + PR #19 (5 bugs) + PR #20 (3 bugs from live validation)
**Tests:** 52/52 passing, 1 skipped

**Product:** Eliminates the manual post-stream checklist for bilingual EN/FR
institutional live streams. One stream-end event → full session closure.

- [x] domains/streamlab_post/ — new domain, engine unchanged
- [x] BackupVerificationWorker — file exists, size threshold, ffprobe validation
- [x] AudioExtractWorker — ffmpeg MP3 extraction from recording
- [x] YouTubeWorker — Data API v3, EN + FR channels, uploads playlist auto-detect
- [x] TranslationWorker — Google Translate API v2, EN→FR title + description
- [x] TranscriptWorker — ElevenLabs Scribe API, bilingual, speaker-labeled
- [x] FileRenameWorker — YYYY-MM-DD_EventName_NNN_EN convention
- [x] NotificationWorker — Teams webhook + Graph API email, transcript attached
- [x] PostStreamCoordinator — 4-stage execution, inter-stage payload enrichment
- [x] main_post_stream.py — --dry-run / --once / --poll-interval entry point
- [x] scripts/youtube_auth.py — one-time OAuth2 refresh token setup
- [x] session_config.example.yaml — operator config reference

**4-stage execution model:**

```text
Stage 1 (parallel, required):  backup_verify   youtube_en    audio_extract
Stage 2 (parallel, optional):  translate       transcript
Stage 3 (parallel, optional):  youtube_fr      file_rename
Stage 4 (optional):            notify
```

**Live proof — session `2026-04-13_Miktos-Demo_005` (confirmed on disk):**

```text
Stage 1:  backup_verify ✅  youtube_en ✅  audio_extract ✅
Stage 2:  translate ✅     transcript ✅ (105 words)
Stage 3:  youtube_fr ✅    file_rename ✅
Stage 4:  notify ✅ (skipped cleanly)

Session closed in 7 seconds. No human involvement.
```

---

## Phase 6 — Pre-Stream Readiness Check ✅ COMPLETE

**Completed:** 2026-04-14
**Commit:** `7a12e05` (PR #22)
**Tests:** 66 passed, 1 skipped

**Command to run before every stream:**

```bash
python main_preflight.py
```

---

## Pre-Phase 7 — Operational Hardening ✅ COMPLETE

**Classification:** Not a numbered phase. Scripts and minor improvements only.
**Commit:** `afa3ba9` (PR #26)
**Tests:** 82 passed, 1 skipped

| Script | What it does |
| --- | --- |
| `scripts/prepare_session.py` | Prompts for event_name + video_ids, updates session_config.yaml |
| `scripts/run_session.py` | Single launcher: pre-flight → post-stream → monitor, enforces correct order |
| `scripts/clear_inbox.py` | Safely moves stale pending messages to delivered/, logs to message.log |
| `scripts/clean_sessions.py` | Archives hex-UUID test sessions, leaves production sessions untouched |

---

## Phase 7 — Operations Dashboard ✅ COMPLETE

### Phase 7a — Post-Session HTML Report ✅ COMPLETE

**Commit:** `05b28fa` (PR #28)
**Tests:** 88 passed, 1 skipped

Optional Stage 4 worker (`report_worker.py`) generates `{session_name}_report.html`
in the session folder after each closure. Self-contained HTML, no server required.

### Phase 7b — Live Terminal Status View ✅ COMPLETE

**Completed:** 2026-04-15
**Commit:** `9b7d14e` (PR #30)
**Tests:** 94 passed, 1 skipped

`rich`-based terminal panel showing real-time stage progress. Integrated into
`run_session.py` with graceful fallback. New dependency: `rich>=13.0`.

---

## Phase 8 — Epiphan Pearl Domain Adapter ✅ COMPLETE

**Completed:** 2026-04-16
**Branch:** `phase-8/epiphan-pearl`

### Phase 8a — Pearl Monitor + Post-Stream Automation ✅

**Commit:** `1e095c3`
**Tests:** 103 passed, 1 skipped

Proves the engine is genuinely multi-domain. Pearl plugs into the same engine
and post-stream pipeline as OBS with zero engine changes.

- [x] `domains/epiphan/` — PearlClient, EpiphanMonitorTool, alert_classifier
- [x] `recording_download_worker.py` — Pre-Stage 1 HTTP pull from Pearl
- [x] `main_epiphan.py` — outer loop, edge-triggered handoff
- [x] `session_config.yaml` extended with `hardware: epiphan` discriminator
- [x] `prepare_session.py` / `run_session.py` — hardware-aware routing

#### Live proof — 3 clean Pearl sessions on disk (2026-04-16)

### Phase 8b — Live Layout Control ✅

**Commit:** `190d957`
**Tests:** 108 passed, 1 skipped

Proves Miktos can issue commands to hardware during a live stream.

- [x] `scripts/pearl_control.py` — layouts / switch / status subcommands
- [x] `pearl_client.py` — `get_layouts()` + `get_active_layout()` added
- [x] Name resolution: exact ID → exact name → substring match

```bash
python scripts/pearl_control.py switch --channel 2 --layout speaker
```

---

## Phase 9 — Production Cockpit ✅ COMPLETE

**Completed:** 2026-04-17
**Commit:** `6db849d` (PR #32)
**Tests:** 108 passed, 1 skipped

Unified `rich` terminal panel replacing the split-terminal workflow.
All prior behaviour preserved — Phase 9 is purely additive.

- [x] `scripts/session_status.py` — `StatusDisplay` extended with hardware context:
  - Hardware header: `Epiphan Pearl {host}` or `OBS`; pre-flight indicator
  - Live health: stream state, tick counter `#0042`, alert level, elapsed `HH:MM:SS`
  - Pearl layouts section (epiphan only): active layout per channel, live from `layout_log.jsonl`
  - Pipeline: Stages 1–4 per-slot status (pending / running / ✅ / ❌ / —)
  - Completion row: session folder path + elapsed time
- [x] `scripts/run_session.py` — config read unified, `_RE_TICK` regex, hardware-aware init
- [x] `scripts/pearl_control.py` — layout log writer appended on every switch
- [x] `_kill_stale_listener()` — orphaned `main_post_stream.py` cleanup on startup

**Gate met:** 10 clean production sessions on disk before Phase 9 began
(5 × OBS, 5 × Pearl, 2026-04-15 through 2026-04-17).

---

## Phase 10 — Web GUI / Unified Operating Surface 🔜 FUTURE

**Depends on:** Phase 9 validated in production + commercial validation.

Stage 3 of the vision: Miktos as the primary interface, with OBS, Pearl,
Zoom, YouTube, ElevenLabs as underlying adapters. Not yet scoped.
