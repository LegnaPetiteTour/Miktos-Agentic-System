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
      Returns list[AgentMessage], one per subscriber
- [x] data/messages/subscriptions.example.json — format reference, committed
- [x] data/messages/subscriptions.json — runtime registry, gitignored
- [x] main_streamlab.py --handoff now uses publish("recording_stopped")
      Publisher no longer names session_coordinator or kosmos_organizer
- [x] scripts/dmo_preview.py — live one-publish two-delivery proof
- [x] All 39 prior tests pass unmodified

**Live proof — message.log (independently audited on disk):**
```
PUBLISHED  streamlab_monitor -> [2 subscriber(s)]  recording_stopped  session_coordinator, kosmos_organizer
POSTED     streamlab_monitor -> session_coordinator  recording_stopped
POSTED     streamlab_monitor -> kosmos_organizer    recording_stopped
ACKNOWLEDGED  ... session_coordinator  recording_stopped
ACKNOWLEDGED  ... kosmos_organizer    recording_stopped
```

**What Phase 4d proved:**
One publish() call reached two independent agents. The publisher named
neither recipient. Adding a third subscriber requires one line in
subscriptions.json — zero code changes. The interface is stable for Phase 5.
Redis upgrade path: replace MessageBus backing store when distribution demands it.

**Invariant:** pub/sub is additive. All point-to-point usage (post(), acknowledge())
is unchanged. All 39 prior tests pass unmodified.

---

## Phase 5 — Post-Stream Closure Engine (DMO v1)

**Product target:** Multilingual live production operations for OBS/Zoom/Epiphan
workflows. Miktos becomes the orchestration layer above the existing tool stack.

**Vertical wedge:** Post-stream operations automation — the manual checklist
that runs after every bilingual EN/FR stream is eliminated.

**The before/after:**
```
Before (manual, after every stream):
  - Check YouTube EN upload status and visibility
  - Check YouTube FR upload status and visibility
  - Translate description to French manually (Google Translate)
  - Add title + description to both channels
  - Verify video is in correct playlist on both channels
  - Confirm local backup recording exists and is valid
  - Extract audio from recording (Premiere or equivalent)
  - Upload MP3 to ElevenLabs, wait, download bilingual transcript
  - Rename and file all artifacts with correct naming convention
  - Share transcript via Teams/Outlook

After (Miktos, triggered by stream end):
  - Detects recording_stopped via OBS WebSocket
  - Verifies backup file exists, size valid, not corrupt
  - Checks YouTube EN: upload complete, public, in playlist
  - Checks YouTube FR: upload complete, public, in playlist
  - Generates FR description via translation (Google Translate API)
  - Sets title + description on both channels via YouTube Data API
  - Extracts audio via ffmpeg (already in engine)
  - Submits MP3 to ElevenLabs, polls, downloads bilingual transcript
  - Renames and files all artifacts into dated session folder
  - Sends transcript via Teams/Outlook (or writes share-ready package)
  - Produces session report: pass/fail per step, flags for human review
```

**New workers required (Phase 5 slots):**
- YouTubeVerificationWorker — YouTube Data API v3, dual-channel EN/FR
- TranscriptPipelineWorker — ffmpeg audio extract + ElevenLabs API + download
- BackupVerificationWorker — file exists, size threshold, not corrupt
- TranslationWorker — Google Translate API, EN→FR description
- NotificationWorker — Teams webhook or Outlook/Graph API, share transcript

**Engine unchanged. Coordinator extended with new slot definitions.**
**All existing tests continue to pass.**

Goal: Eliminate the post-stream manual checklist entirely.
Every step above runs automatically from a single stream-end event.
Human review only for flagged failures.
