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

**PR #20 bug fixes (found during live validation 2026-04-13):**

1. `_has_recording_stopped()` included `stream_down` — obs-multi-rtmp plugin
   keeps `stream_down` permanently present; edge trigger never armed.
   Fix: check only `recording_stopped`.
2. `youtube_fr` used YouTube search API — lags 10–60 minutes for new VODs.
   Fix: switched to uploads playlist API (near-instant).
3. `transcript` multipart field named `"audio"` instead of `"file"`.
   Fix: renamed per ElevenLabs Scribe API spec.

**Live proof — session `2026-04-13_Miktos-Demo_005` (confirmed on disk):**

```text
Stage 1:  backup_verify ✅  youtube_en ✅  audio_extract ✅
Stage 2:  translate ✅     transcript ✅ (105 words)
Stage 3:  youtube_fr ✅    file_rename ✅
Stage 4:  notify ✅ (skipped cleanly)

Session closed in 7 seconds. No human involvement.

Files on disk:
  2026-04-13_Miktos-Demo_005_EN.mov   305.77 MB
  2026-04-13_Miktos-Demo_005.mp3       11.37 MB

Message log (2026-04-14T05:04:18Z UTC):
  PUBLISHED  streamlab_monitor -> [3 subscriber(s)]  recording_stopped
  ACKNOWLEDGED  post_stream_processor  (6 seconds)
```

---

## Phase 6 — Pre-Stream Readiness Check ✅ COMPLETE

**Completed:** 2026-04-14
**Commit:** `7a12e05` (PR #22)
**Tests:** 66 passed, 1 skipped — pytest collects 67 items; the 1 skipped is
`tests/test_streamlab_domain.py::test_obs_connection_live`, which requires a
live OBS WebSocket and has been conditionally skipped since Phase 3.

**Command to run before every stream:**

```bash
python main_preflight.py
```

Catches configuration, credential, process, and connectivity problems
before they propagate into post-stream failures.

**Six checks:**

```text
1. OBS WebSocket       — can the monitor connect?          hard fail
2. session_config.yaml — required fields non-empty?        hard fail
3. Recording path      — exists and writable?              hard fail
4. Pending inbox       — stale messages present?           hard fail
5. Duplicate process   — main_streamlab --handoff running? hard fail
6. Credentials         — tokens valid, API keys set?       soft warn
    YOUTUBE_REFRESH_TOKEN_EN  — refresh attempted
    YOUTUBE_REFRESH_TOKEN_FR  — refresh attempted
    GOOGLE_TRANSLATE_API_KEY  — env var present?
    ELEVENLABS_API_KEY        — env var present?
    youtube.en.video_id       — blank = auto-discovery
    youtube.fr.video_id       — blank = auto-discovery
    Teams webhook URL         — blank = notify skips
```

**Output format:**

```text
  Miktos Pre-Flight Check
  ───────────────────────────────────────
  ✅  OBS WebSocket — reachable at localhost:4455
  ✅  session_config.yaml — all required fields present
  ✅  Recording path — exists and writable: /Users/…/Movies
  ✅  Inbox — empty
  ✅  Duplicate process — none found
  ✅  YOUTUBE_REFRESH_TOKEN_EN — valid (refresh succeeded)
  ✅  YOUTUBE_REFRESH_TOKEN_FR — valid (refresh succeeded)
  ✅  GOOGLE_TRANSLATE_API_KEY — set
  ✅  ELEVENLABS_API_KEY — set
  ✅  youtube.en.video_id — set (vz9ecJuLhLs)
  ⚠️   youtube.fr.video_id — blank (auto-discovery will be used)
  ⚠️   Teams webhook URL — blank (notify slot will skip)
  ───────────────────────────────────────
  READY TO STREAM  (2 warning(s), 0 errors)
```

**File structure added:**

```text
domains/streamlab_post/pre_flight/
  __init__.py
  checker.py              ← PreFlightChecker
  checks/
    __init__.py
    obs_check.py
    config_check.py
    path_check.py
    inbox_check.py
    process_check.py
    credentials_check.py
main_preflight.py         ← entry point (--dry-run flag)
tests/test_phase_6_preflight.py  ← 14 new tests
```

**Live proof — 2026-04-14 (this machine):**

- `--dry-run`: all 12 checks ✅, exit 0
- Live run: OBS ✅, config ✅, path ✅, inbox ✅, credentials ✅, caught stale
  `main_streamlab.py --handoff` process (PID 35558) ❌ → exit 1 (correct)

**Invariant:** No engine/ changes. No changes to any existing Phase 1–5 file.
`PreFlightChecker` is a domain-layer class. All 52 prior tests pass unmodified.

---

## Future Phases (not yet scoped)

- **Phase 7:** Operations dashboard frontend (Stage 1 — session visibility)
- **Phase 8:** Zoom/Epiphan scenario (separate domain adapter)
- **Phase 9:** Multi-user / cloud deployment
