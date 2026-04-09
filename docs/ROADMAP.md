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

**Hierarchical orchestration — coordinator dispatches three workers in parallel.**

- [x] engine/coordinator/workers.py — KosmosWorker, ThumbnailWorker, MetadataWorker
      Each worker: one responsibility, independently testable, never raises
- [x] engine/coordinator/coordinator.py — SessionCoordinator
      ThreadPoolExecutor(max_workers=3), named slot aggregation, retry loop
- [x] engine/messaging/bus.py — append_log() added, auto-wired into post()/acknowledge()
- [x] data/messages/message.log — append-only event log, full observability
- [x] main_coordinator.py — --poll-interval / --once entry point
- [x] data/sessions/ — session artifacts written per run
- [x] All 34 prior tests pass unmodified — coordinator is a separate layer

**Slot definitions:**

```text
organize   (required)  KosmosWorker    — classify and propose file path
thumbnail  (optional)  ThumbnailWorker — extract first-frame JPEG via ffmpeg
metadata   (required)  MetadataWorker  — write session.json via ffprobe
```

**Live proof — coordinator stdout:**

```text
Session 05b7a3154d20
├── organize   ✅  videos (0.95)  →  data/sessions/05b7a3154d20/videos/video_clip.mp4
├── thumbnail  ❌  moov atom not found  (stub fixture — 8-byte ASCII, not a real video)
└── metadata   ✅  data/sessions/05b7a3154d20/session.json  (0.0s)
exit: success | posted session_complete → streamlab_monitor
```

**message.log event chain (12 lines, independently audited):**

```text
POSTED      streamlab_monitor → session_coordinator  recording_ready
DISPATCHED  coordinator → kosmos_worker              organize       attempt 1
DISPATCHED  coordinator → thumbnail_worker           thumbnail      attempt 1
DISPATCHED  coordinator → metadata_worker            metadata       attempt 1
COMPLETED   kosmos_worker → coordinator              organize
FAILED      thumbnail_worker → coordinator           thumbnail      [moov atom not found]
COMPLETED   metadata_worker → coordinator            metadata
DISPATCHED  coordinator → metadata_worker            metadata       (category enrichment)
COMPLETED   metadata_worker → coordinator            metadata
POSTED      coordinator → streamlab_monitor          session_complete  success
ACKNOWLEDGED coordinator ← recording_ready
```

**What Phase 4c proved — all three architecture contract criteria met:**

1. Delegation reduced complexity for the coordinator — it never touches domain logic
2. Aggregation is deterministic — slot-filling, no inference, no LLM
3. Failure ownership is clear — thumbnail failed, coordinator recorded which slot,
   why, and that it was optional. Required slots all succeeded. exit_reason: success.

**Invariant:** Coordinator is a capability layer above the engine, not inside it.
build_graph() and all three existing entry points are completely unchanged.

---

## Phase 4d — Event Bus

Goal: Infrastructure layer for multi-domain coordination.

*Requires Phase 4b and 4c.*

- [ ] Shared message broker defined (Redis or equivalent)
- [ ] Publish/subscribe across domains
- [ ] Events trigger cross-domain actions
- [ ] MessageBus backing store swapped from JSON to broker

---

## Phase 5 — DMO / Ecosystem

Goal: The engine becomes the nervous system of the full Miktos product family.

*Requires Phase 4d.*

- [ ] Multiple domains running concurrently
- [ ] Shared memory across domains
- [ ] Cross-domain orchestration
- [ ] Full observability dashboard
