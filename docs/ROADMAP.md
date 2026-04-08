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

Goal: Prove the core loop works under real conditions.

### Milestone 1.1 — Deterministic Engine ✅

- [x] Project skeleton created
- [x] State schema defined
- [x] LangGraph graph wired (all 6 nodes)
- [x] File scanner implemented
- [x] Rule-based classifier implemented
- [x] Dry-run mode working
- [x] Engine/domain separation verified
- [x] State saves to disk on every iteration

### Milestone 1.2 — Review Queue + Confidence Thresholds ✅

- [x] Confidence bands implemented (>= 0.90 approved / 0.60-0.89 queued / < 0.60 skipped)
- [x] Review queue JSON written to data/review_queue/
- [x] Skipped files logged with reason and confidence score
- [x] Mixed folder fixture (10 files) — 7 approved, 3 skipped

### Milestone 1.3 — Closed-Loop Correction ✅

- [x] Retry logic fires on execution failure
- [x] exhausted_tasks bucket separate from skipped_tasks
- [x] Unrecoverable error detection (_is_unrecoverable)
- [x] Stop condition: exhausted rate threshold + unrecoverable guard
- [x] Loop bounds enforced (max_retries, max_replans)

### Milestone 1.4 — Classifier Coverage ✅

- [x] Four-tier confidence system implemented
- [x] mime_unhandled tier at 0.60 (detected MIME, unmapped prefix)
- [x] _NO_MIME invariant: "unknown" never promoted to tier 3
- [x] Expanded MIME prefix rules: text/, application/, font/, model/
- [x] molecule.xyz confirmed in review_queue, not skipped_tasks

**What Phase 1 proved:**
1. The loop executes end-to-end cleanly
2. Engine/domain separation holds — nodes never import from domain
3. The system recovers from failure without human intervention
4. The classifier is honest about what it knows vs what it doesn't

---

## Phase 2 — Domain 2 (Kosmos / Media Organizer) ✅ COMPLETE

**Completed:** 2026-04-08
**Commit:** `b7fcea4`
**Tests:** 22/22 passing

Goal: Prove the engine is reusable without modification to the core.

- [x] FileScannerTool promoted to engine/tools/shared_tools.py
- [x] fs_tools.py converted to thin re-export shim — 0 existing tests broken
- [x] domains/kosmos/ created with media_classifier.py and media_metadata.py
- [x] Nine-rule, four-tier media classifier implemented
- [x] EXIF probe via Pillow — photos vs screenshots distinction working
- [x] RAW camera formats handled (.cr2, .nef, .arw, .dng, .orf, .rw2, .pef)
- [x] main_kosmos.py entry point — EXIF split line in summary
- [x] media_folder fixture: real JPEG with EXIF + real PNG without EXIF
- [x] git diff main -- engine/graph/ is empty — engine unchanged

**Verified result (state file 20260407_195350_b51d67a3):**
```
domain     : kosmos
Exit       : success
Approved   : videos, raw_photos, documents, photos (exif), audio
Queued     : screenshots (0.80 mime), unknown_media.xyz (0.60 mime_unhandled)
Skipped    : noextension (0.40 fallback)
```

**What Phase 2 proved:**
The engine ran a completely different domain without a single change
to engine/graph/. The maze is genuinely reusable. A new ball ran
through the same maze and reached the correct exit.

**Design note:** screenshot.png queuing at 0.80 is correct by design.
Images without camera EXIF require human review before action.
This is the conservative default for the Kosmos domain.

---

## Phase 3 — StreamLab Integration ✅ COMPLETE

**Completed:** 2026-04-08
**Commit:** `0a2c894`
**Tests:** 25/25 passing (1 skipped when OBS not running)

Goal: Prove the engine works in a real-time, event-driven context.

- [x] OBS WebSocket client tool defined (env-var credentials only — never committed)
- [x] OBSMonitorTool adapter: polls OBS, emits file-scanner-shaped alert payloads
- [x] Eight-rule alert classifier — three confidence tiers (0.95 / 0.80 / 0.60 / 0.40 fallback)
- [x] Outer-loop entry point (main_streamlab.py): continuous monitoring, --duration and --poll-interval args
- [x] Tick summary output: icon, exit reason, alert counts, category breakdown
- [x] Configurable thresholds via domains/streamlab/config/thresholds.yaml
- [x] git diff main -- engine/graph/ is empty — engine unchanged

**Classifier confidence table:**
| Rule | Confidence | Engine routing |
|---|---|---|
| stream_down, recording_stopped | 0.95 | auto_approve |
| dropped_frames / cpu_overload (critical) | 0.95 | auto_approve |
| dropped_frames / cpu_overload (warning) | 0.80 | review_queue |
| render_lag, memory_pressure | 0.80 | review_queue |
| unknown metric (valid MIME) | 0.60 | review_queue |
| missing / unknown MIME | 0.40 | skipped |

**Live OBS run (4 ticks × 5s, stream not active):**
```
  [  1] 🔴 exit=success | alerts=1 (approved=1, queued=0, errors=0)  stream_down×1
  [  2] 🔴 exit=success | alerts=1 (approved=1, queued=0, errors=0)  stream_down×1
  [  3] 🔴 exit=success | alerts=1 (approved=1, queued=0, errors=0)  stream_down×1
  [  4] 🔴 exit=success | alerts=1 (approved=1, queued=0, errors=0)  stream_down×1
  Duration 18s reached. Exiting cleanly.
```

**What Phase 3 proved:**
The engine runs equally well in a real-time polling context. The outer-loop
pattern keeps each tick stateless and deterministic. A completely different
class of input (live OBS metrics vs filesystem files) ran through the same
maze unchanged.

**Adapter note:** OBSMonitorTool returns `{"files": [alert_items], "count": N}` —
identical shape to FileScannerTool. The planner node never knew the difference.

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
