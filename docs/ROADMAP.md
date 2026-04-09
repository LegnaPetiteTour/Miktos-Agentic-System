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
**Commit:** `ee259e2` (PR #14)
**Tests:** 34/34 passing, 1 skipped

**Two agents communicate through a durable JSON message bus.**

- [x] engine/messaging/models.py — AgentMessage dataclass
- [x] engine/messaging/bus.py — MessageBus with atomic writes (tempfile + rename)
- [x] agent_id + inbox_messages added to RunState (backward compatible defaults)
- [x] message_trigger_node — reads inbox, acknowledges, injects into state
- [x] build_graph_with_messaging() — additive, build_graph() unchanged
- [x] main_streamlab.py --handoff flag — posts recording_ready on stream stop
- [x] main_kosmos.py --listen flag — polls inbox, processes recording_ready messages
- [x] data/messages/ directory structure with pending/ and delivered/ per agent

**Live round-trip proof:**

```text
1. Inbox polled  → 1 recording_ready message from streamlab_monitor
2. Kosmos ran    → scanned /Users/atorrella/Movies
                   159 files classified, exit=success
3. Acknowledged  → message moved to kosmos_organizer/delivered/
4. Reply posted  → recording_organized to streamlab_monitor/pending/
5. Verified      → files_processed: 159, exit_reason: success
```

**Message chain on disk (independently audited):**

- kosmos_organizer/delivered/f70b2df1...json  <- recording_ready, acknowledged
- streamlab_monitor/pending/fc25c709...json   <- recording_organized, files_processed: 159

**What Phase 4b proved:**
The system is no longer just a loop. It is a network. One agent triggers
another without human involvement. The message bus interface is stable —
backing store swapped to Redis in Phase 4d with a one-file change.

**Invariant:** Messaging is opt-in. No existing domain is affected.
build_graph() and all three existing entry points are unchanged.

---

## Phase 4c — Team / Task Delegation

Goal: Hierarchical orchestration — coordinator assigns to specialized workers.

*Requires Phase 4b — agent identity and messaging already exist.*

- [ ] Coordinator agent role defined
- [ ] Worker agent roles defined
- [ ] Delegation and result aggregation working
- [ ] Progress tracking across the team

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
