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
- [x] Engine/domain separation verified — engine nodes never import from domain

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
**Commit:** `7980fa1` (PR #13)
**Tests:** 29/29 passing, 1 skipped

**First legitimate engine modification — additive only, backward compatible.**

- [x] parallel_execution_node added to engine/graph/nodes.py
      Uses ThreadPoolExecutor — identical signature to execution_node
- [x] _execution_target() + route_to_execution() added to router.py
      Routes based on context["execution_mode"] — sequential is default
- [x] graph_builder.py wires both nodes — both paths feed into review_node
- [x] main_kosmos.py --parallel and --workers flags added
- [x] engine/benchmarks/parallel_benchmark.py — standalone timing script
- [x] All 25 pre-existing tests pass unmodified

**Benchmark proof (200 synthetic Kosmos files, 8 workers):**

```text
Phase 4a — Parallel Execution Benchmark
============================================
Files       : 200
Sequential  : 0.21s  (973.5 files/sec)
Parallel    : 0.05s  (3904.7 files/sec)  [8 workers]
Speedup     : 4.0x
Correctness : PASS (200/200 actions match)
============================================
```

**New invariant (replaces "engine unchanged"):**
Additive only. Backward compatible. All pre-existing domain tests pass.
Sequential mode remains the default — no existing domain is affected.

---

## Phase 4b — Agent-to-Agent Messaging

Goal: Introduce agent identity and communication layer.

- [ ] Agent identity model defined
- [ ] Inbox/outbox mechanism per agent
- [ ] Orchestrator routes messages between agents
- [ ] At least one real workflow uses inter-agent communication

---

## Phase 4c — Team / Task Delegation

Goal: Hierarchical orchestration — coordinator assigns to specialized workers.

*Requires Phase 4b.*

- [ ] Coordinator agent role defined
- [ ] Worker agent roles defined
- [ ] Delegation and result aggregation working
- [ ] Progress tracking across the team

---

## Phase 4d — Event Bus

Goal: Infrastructure layer for multi-domain coordination.

*Requires Phase 4b and 4c.*

- [ ] Shared message broker defined
- [ ] Publish/subscribe across domains
- [ ] Events trigger cross-domain actions

---

## Phase 5 — DMO / Ecosystem

Goal: The engine becomes the nervous system of the full Miktos product family.

*Requires Phase 4d.*

- [ ] Multiple domains running concurrently
- [ ] Shared memory across domains
- [ ] Cross-domain orchestration
- [ ] Full observability dashboard
