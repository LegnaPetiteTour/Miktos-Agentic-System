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

### Milestone 1.1 — Deterministic Engine
- [ ] Project skeleton created
- [ ] State schema defined
- [ ] LangGraph graph wired (all 8 nodes)
- [ ] File scanner implemented
- [ ] Rule-based classifier implemented
- [ ] Dry-run mode working
- [ ] State persists and resumes after interruption

**Success condition:** Given a folder of 200+ mixed files, the system completes a dry run, produces a categorized action plan, and recovers from interruption without corrupting the source.

### Milestone 1.2 — Review Queue + Confidence Thresholds
- [ ] Confidence bands implemented (auto / review / skip)
- [ ] Review queue file generated
- [ ] Manual review workflow defined
- [ ] Optional LLM classifier for ambiguous cases

### Milestone 1.3 — Closed-Loop Correction
- [ ] Retry logic implemented
- [ ] Fallback strategies defined
- [ ] Unresolved exception bucket
- [ ] Loop bounds enforced (max retries, time budget)

### Milestone 1.4 — Engine Extraction
- [ ] Engine layer separated from file domain
- [ ] Engine is importable as standalone package
- [ ] File analyzer depends on engine, not the reverse
- [ ] Engine has no file-specific logic

---

## Phase 2 — Domain 2 (Kosmos / Media Organizer)

Goal: Prove the engine is reusable without modification.

- [ ] New domain created under `domains/`
- [ ] Engine imported unchanged
- [ ] New tools registered (media metadata, EXIF, video info)
- [ ] New classification rules defined
- [ ] System runs against media library

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
