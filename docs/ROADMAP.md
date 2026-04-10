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
```
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
```
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

**Live proof:**
```
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

**Live proof — message.log:**
```
PUBLISHED  streamlab_monitor -> [2 subscriber(s)]  recording_stopped
POSTED     streamlab_monitor -> session_coordinator  recording_stopped
POSTED     streamlab_monitor -> kosmos_organizer    recording_stopped
ACKNOWLEDGED  (both)
```

---

## Phase 5 — Post-Stream Closure Engine (DMO v1) ✅ COMPLETE

**Completed:** 2026-04-10
**Commit:** PR #18
**Tests:** 52/52 passing, 1 skipped

**Product:** Multilingual live production operations layer for OBS/Zoom/Epiphan
workflows. Eliminates the manual post-stream checklist entirely.

**Vertical wedge:** Post-stream closure automation for bilingual EN/FR streams.
One stream-end event → full session closure, no human involvement.

- [x] domains/streamlab_post/ — new domain, engine unchanged
- [x] BackupVerificationWorker — file exists, size threshold, ffprobe validation
- [x] AudioExtractWorker — ffmpeg MP3 extraction from recording
- [x] YouTubeWorker — Data API v3, EN + FR channels, auto-detect video_id
- [x] TranslationWorker — Google Translate API v2, EN→FR title + description
- [x] TranscriptWorker — ElevenLabs Scribe API, bilingual, speaker-labeled
- [x] FileRenameWorker — YYYY-MM-DD_EventName_NNN_EN convention, organized folder
- [x] NotificationWorker — Teams webhook + Graph API email, transcript attached
- [x] PostStreamCoordinator — 4-stage execution, inter-stage payload enrichment
- [x] main_post_stream.py — --dry-run / --once / --poll-interval entry point
- [x] scripts/youtube_auth.py — one-time OAuth2 refresh token setup
- [x] session_config.example.yaml — operator config reference, committed
- [x] All 44 prior tests pass unmodified

**4-stage execution model:**
```
Stage 1 (parallel):  backup_verify   youtube_en    audio_extract
Stage 2 (parallel):  translate       transcript
Stage 3 (parallel):  youtube_fr      file_rename
Stage 4 (optional):  notify
```

**Dry-run proof — message.log (independently audited):**
```
PUBLISHED  streamlab_monitor -> [3 subscriber(s)]  recording_stopped
           session_coordinator, kosmos_organizer, post_stream_processor
POSTED     → post_stream_processor  recording_stopped
ACKNOWLEDGED  post_stream_processor ← recording_stopped  (×2 runs)
```

**Dry-run session artifacts on disk:**
- data/sessions/b0d6b6561fa2/transcript.txt — bilingual mock transcript written
- data/sessions/111743134184/transcript.txt — second dry-run run confirmed

**The before/after — manual steps eliminated:**
```
Before: 10 manual steps after every stream (avg ~30 min)
  Check EN upload → Check FR upload → Translate description →
  Set titles/descriptions → Verify playlists → Confirm backup →
  Extract audio in Premiere → Upload to ElevenLabs → Download transcript →
  Rename files → Share via Teams/Outlook

After: Zero manual steps
  Stream ends → Miktos closes the session automatically
  Human review only for flagged failures (❌ slots in session report)
```

**Naming convention:** YYYY-MM-DD_EventName_NNN_EN.mp4
  NNN increments automatically for same-day multiple streams.

**Invariant:** Engine unchanged. PostStreamCoordinator is a domain-layer
component. All prior domains and tests unaffected.

---

## Next — Live Credential Setup

Before running against a real stream:

1. Create Google Cloud OAuth2 Desktop App credentials
2. Run `python scripts/youtube_auth.py --channel en` → copy token to .env
3. Run `python scripts/youtube_auth.py --channel fr` → copy token to .env
4. Add GOOGLE_TRANSLATE_API_KEY to .env
5. Add ELEVENLABS_API_KEY to .env
6. Fill in domains/streamlab_post/config/session_config.yaml
7. Run `python main_post_stream.py --poll-interval 5` before next stream
8. End the stream → observe full session closure without touching anything
