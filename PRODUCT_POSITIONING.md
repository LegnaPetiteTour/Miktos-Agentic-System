# Product Positioning

What Miktos is. What it is not. Who it is for.

---

## What Miktos Is

Miktos is a **live production operations system** for institutional bilingual
EN/FR streams. It connects OBS Studio, Pearl (Epiphan) encoding hardware, and
a suite of post-production services into a single closed-loop pipeline
operated from a web cockpit.

When a stream ends, Miktos closes the session automatically: it verifies the
backup, uploads metadata to YouTube in both languages, extracts audio,
generates bilingual transcripts, renames and organizes the session folder, and
sends a completion notification — with no human involvement.

Before Miktos, this was ~30 minutes of manual work after every stream.
After Miktos, it is zero.

---

## What Miktos Is Not

**Not a chatbot.** There is no conversational interface. The system receives
events, not prompts. LLM usage is narrow and isolated — ambiguous classifier
cases only.

**Not a general-purpose workflow tool.** Miktos is opinionated about its
production context: bilingual institutional streams, Pearl hardware, OBS,
YouTube. It is not a generic automation platform.

**Not a SaaS product.** It runs on-premises, self-hosted, with credentials
you own. There is no cloud dependency beyond third-party APIs (YouTube,
Google Translate, ElevenLabs).

**Not a replacement for the operator.** The operator sets up the session,
monitors the event, and reviews flagged ❌ slots in the post-stream report.
Miktos removes the mechanical work, not the editorial judgment.

---

## Who It Is For

The primary user is a **broadcast technician or producer** running bilingual
institutional live events — conferences, committee hearings, public sessions —
who has to manage OBS, Pearl hardware, multilingual metadata, and post-stream
file organization simultaneously.

Secondary users: developers extending the system with new domains or workers.

---

## The Two Layers

### Layer 1 — The Engine (domain-agnostic)

`engine/` is a closed-loop orchestration engine. It receives a goal,
decomposes it into tasks, executes through tools, reviews results, and loops
until the goal is reached. It knows nothing about streams, files, or Pearl.

This layer does not change between use cases. It has been validated across
four independent domains without modification.

### Layer 2 — The Production Operations Layer (domain-specific)

Everything in `domains/` and `web/` is the StreamLab production use case:
stream monitoring, Pearl hardware control, the post-stream pipeline, and the
web cockpit. This layer knows about bilingual streams, YouTube, and Epiphan.

The engine is reusable infrastructure. The production layer is the product.

---

## The Cockpit Model

The web cockpit (`http://localhost:8000`) is designed around one principle:
**the operator should not need to know Python, YAML, or channel IDs.**

At the start of an event:
- The cockpit queries Pearl live and shows all available channels by name
- The operator clicks EN next to the English channel, FR next to the French
  channel — or reassigns them for a different Pearl configuration
- OBS scenes populate from the hardware — no manual entry

During the event:
- Session start/stop from the browser
- Live thumbnail previews of Pearl channels and OBS program feed
- Health widget showing Pearl and OBS connectivity status
- Layout control for Pearl encoder switching
- Rehearsal mode for dry-run testing before the event

After the event:
- The pipeline runs automatically
- The action log shows what happened and when
- The session report flags any ❌ slots for human review

---

## The Discovering vs. Configured Distinction

Before Phase 19, Miktos was a **configured** system: you told it which channel
was EN, which was FR, what the OBS scene names were. This worked but required
the operator to know the hardware configuration and edit YAML by hand.

After Phase 19, Miktos is a **discovering** system: it queries Pearl and OBS
at startup and shows what is actually connected. The operator clicks to assign
roles. Configuration writes itself.

This distinction matters at live events where:
- The Pearl may have different channel assignments than the last event
- A backup Pearl may be substituted with a different channel layout
- The OBS scene list may have changed since the last session

A discovering system handles these cases without operator intervention.
A configured system requires YAML edits under time pressure.

---

## Boundaries: What Belongs Where

| Concern | Belongs in |
|---|---|
| Orchestration logic | `engine/` |
| Domain tools (OBS, Pearl, YouTube) | `domains/` |
| Web UI and REST endpoints | `web/` |
| Credentials and environment config | `.env` (gitignored) |
| Session configuration (event-specific) | `session_config.yaml` |
| Defaults and documentation | `.env.example`, `CORE_CONTRACT.md` |
| Architecture decisions | `docs/ADR-*.md`, `docs/DECISIONS.md` |
| Production scripts | `scripts/` |
| Runtime data | `data/` (gitignored where sensitive) |

---

## Phase History

| Phase | What was built | Tests |
|---|---|---|
| 1 | File Analyzer — MIME classifier, first engine stress test | 18 |
| 2 | Kosmos — media organizer, second domain through same engine | 22 |
| 3 | StreamLab Monitor — OBS WebSocket adapter, health loop | 25 |
| 4a | Parallel execution — 4× speedup on batch workloads | 29 |
| 4b | Agent messaging — JSON MessageBus, atomic writes | 34 |
| 4c | Task delegation — SessionCoordinator, parallel workers | 39 |
| 4d | Event pub/sub — fan-out bus, N independent reactions | 44 |
| 5 | Post-stream closure — 7 workers, 4 stages, live validated | 52 |
| 6 | Pre-flight checks | 78 |
| 7a | Run-of-show report | 88 |
| 7b | Session status | 95 |
| 8a | Pearl (Epiphan) client and monitor | 103 |
| 8b | Pearl layout control | 108 |
| 9 | Production cockpit v1 | — |
| 10a | Web cockpit — health, status, SSE | — |
| 10b | Session start/stop from browser | — |
| 11 | Dual-channel bilingual pipeline | — |
| 18 | Docker, JWT auth, cockpit grid | — |
| 19 | Pearl + OBS auto-discovery, full validation | **252** |

---

## Current Status

🟢 **Production-ready.** Phase 19 complete. All cockpit acceptance tests
passed. 252 automated tests passing. Live event ready.
