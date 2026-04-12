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
**Commit:** PR #18 + PR #19 (live validation fixes)
**Tests:** 52/52 passing, 1 skipped

**Product:** Multilingual live production operations layer for OBS/Zoom/Epiphan
workflows. Eliminates the manual post-stream checklist entirely.

**Multistream note:** obs-multi-rtmp plugin handles simultaneous EN + FR YouTube
delivery from a single OBS instance — no Epiphan required for simple streams.

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

**5 production bugs found and fixed in PR #19 (2026-04-11):**
```
Bug 1: obs_monitor.py      recording_stopped alert never emitted
       Fix: added get_record_status() + alert when output_active=False

Bug 2: main_streamlab.py   _has_recording_stopped() never matched
       Fix: added "stream_down" to match set

Bug 3: coordinator.py      received folder path, not file path
       Fix: most-recent-file resolution from directory

Bug 4: youtube_worker.py   always set public unconditionally
       Fix: read visibility from payload/config

Bug 5: main_streamlab.py   flood-published (11+ events per run, level-triggered)
       Fix: edge-triggered — publish only on True→False recording transition
```

**Live validation — 2026-04-11 — 4 real sessions:**
```
Sessions: 2026-04-11_Miktos-Demo_001 through _004
6/8 slots ✅ per session

transcript ❌ — ElevenLabs minimum duration; will work on full-length streams
youtube_fr ❌ — FR channel pending ~24h YouTube approval; no code change needed

Artifacts confirmed on disk (independently audited):
  2026-04-11_Miktos-Demo_001_EN.mov  34.70 MB  ← naming convention applied
  2026-04-11_Miktos-Demo_001.mp3     1.29 MB   ← audio extracted by ffmpeg

message.log — 4 pub/sub cycles at 06:42 UTC:
  PUBLISHED streamlab_monitor -> [3 subscriber(s)] recording_stopped
  (session_coordinator, kosmos_organizer, post_stream_processor)
  ACKNOWLEDGED by post_stream_processor (×4)
```

**Before/after — manual steps eliminated:**
```
Before: ~30 min manual work after every stream
  Check EN upload → Check FR upload → Translate description →
  Set titles + descriptions → Verify playlists → Confirm backup →
  Extract audio in Premiere → Upload to ElevenLabs → Download transcript →
  Rename files → Share via Teams/Outlook

After: Zero manual steps
  Stream ends → Miktos closes the session automatically
  Human review only for flagged ❌ slots in session report
```

**Naming convention:** YYYY-MM-DD_EventName_NNN_EN.mov
NNN increments automatically for same-day multiple streams.

---

## Pending — FR Channel + First Full-Length Stream

- [ ] FR YouTube channel approved (~24h from 2026-04-11) — no code change needed
- [ ] Run against a full-length stream to clear ElevenLabs minimum duration
- [ ] Update session_config.yaml with real video_id before each stream
- [ ] Configure Teams webhook or Outlook recipients for Stage 4 notifications

**When FR channel is approved — run checklist:**
```
Terminal A: python main_streamlab.py --handoff --poll-interval 5
Terminal B: python main_post_stream.py --poll-interval 5
Start OBS with obs-multi-rtmp → both EN + FR channels live
Run the stream → stop OBS → all 8 slots should be ✅
```
