# Roadmap — Miktos Agentic System

---

## Phase 0 — Foundation ✅

- [x] Repository initialized
- [x] Architecture locked
- [x] Tech stack decided
- [x] ADRs written
- [x] Repo structure defined

---

## Phase 1 — Engine + File Analyzer (Domain 1)

Goal: Prove the core loop works under real conditions.

### Milestone 1.1 — Deterministic Engine ✅ COMPLETE

**Completed:** 2026-04-07

- [x] Project skeleton created
- [x] State schema defined
- [x] LangGraph graph wired (all 6 nodes)
- [x] File scanner implemented
- [x] Rule-based classifier implemented
- [x] Dry-run mode working
- [x] Engine/domain separation verified
- [x] State saves to disk on every iteration

**Verified result:**
```
python main.py --path "docs"

Exit       : success
Completed  : 5
Failed     : 0
Skipped    : 0
Review Q   : 0
Category   : documents (5)
```

**Known issue — Python 3.14 + Pydantic:**
LangGraph emits a Pydantic v1 compatibility warning on Python 3.14.
Run does not fail, but the stable baseline target is Python 3.11.
See ADR-001. Fix: use the .venv pinned to 3.11 for all runs.

---

### Milestone 1.2 — Review Queue + Confidence Thresholds

Goal: Prove the system correctly separates high-confidence from ambiguous files.

- [ ] Test against a large mixed folder (200+ files, multiple types)
- [ ] Confirm confidence bands working correctly:
  - `>= 0.90` → auto-approved
  - `0.60–0.89` → review queue JSON written
  - `< 0.60` → skipped and logged
- [ ] Review queue file written to `data/review_queue/`
- [ ] Skipped files logged with reason and confidence score
- [ ] Optional LLM classifier for genuinely ambiguous files

**Success condition:** Given 200+ mixed files, the system produces a clean
action plan, correctly separates uncertain files into the review queue,
and writes a readable review file without corrupting the source folder.

---

### Milestone 1.3 — Closed-Loop Correction

Goal: Prove the loop can recover and adapt, not just succeed on clean input.

- [ ] Retry logic fires on execution failure
- [ ] Fallback strategies defined per failure type
- [ ] Unresolved exception bucket (files that exhaust retries)
- [ ] Loop bounds enforced (max retries, max replans)
- [ ] Test: inject bad files and confirm recovery behavior

---

### Milestone 1.4 — Engine Extraction

Goal: Prove the engine is genuinely domain-agnostic.

- [ ] Engine layer verified to have zero domain-specific imports
- [ ] Engine importable as standalone package
- [ ] File analyzer depends on engine, not the reverse
- [ ] Domain swap test: swap file_analyzer tools for mock domain tools,
      confirm engine runs without modification

---

## Phase 2 — Domain 2 (Kosmos / Media Organizer)

Goal: Prove the engine is reusable without modification to the core.

- [ ] New domain created under `domains/kosmos/`
- [ ] Engine imported unchanged
- [ ] New tools: media metadata, EXIF, video/audio info
- [ ] New classification rules
- [ ] System runs against real media library

**Success condition:** Engine core requires zero changes. Only domain layer is new.

---

## Phase 3 — StreamLab Integration

Goal: Prove the engine works in a real-time, event-driven context.

- [ ] Event-driven trigger mode added to input layer
- [ ] OBS tool interface defined
- [ ] Network monitoring tool defined
- [ ] Stream health review rules defined
- [ ] Continuous monitoring mode (no exit until stream ends)

---

## Phase 4 — Multi-Agent Expansion

Goal: Prove the engine scales to parallel agents.

- [ ] Parallel task execution
- [ ] Agent-to-agent messaging through orchestrator
- [ ] Team and task delegation patterns
- [ ] Event bus integration

---

## Phase 5 — DMO / Ecosystem

Goal: The engine becomes the nervous system of the full Miktos product family.

- [ ] Multiple domains running concurrently
- [ ] Shared memory across domains
- [ ] Cross-domain orchestration
- [ ] Full observability dashboard
