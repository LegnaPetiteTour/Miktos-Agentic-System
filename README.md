# Miktos Agentic System

> A domain-agnostic closed-loop orchestration engine — the operations brain for live production workflows.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-52%20passing-brightgreen)](#)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](#)

---

## What This Is

Miktos is a **live production operations layer** that sits above your existing tools — OBS, Zoom, Epiphan Pearl, YouTube, ElevenLabs, Teams — and coordinates the full session lifecycle automatically.

It is not a streaming app. It does not replace OBS or Epiphan. It is the **orchestration brain** that removes the manual handoffs before, during, and after a live stream.

**Current first-party workflow:** bilingual EN/FR live production for institutional and public-sector streams, with full post-stream automation including backup verification, YouTube management, audio extraction, bilingual transcript generation, file organization, and notification delivery.

---

## What It Solves

**Before Miktos** — after every stream, manually:
- Check EN YouTube upload status, visibility, playlist
- Check FR YouTube upload status, visibility, playlist
- Translate description to French
- Set titles and descriptions on both channels
- Confirm local backup recording exists and is valid
- Extract audio from recording
- Upload MP3 to ElevenLabs, wait, download bilingual transcript
- Rename and file all artifacts with correct naming convention
- Share transcript via Teams or Outlook

**After Miktos** — stream ends, Miktos closes the session:
- All of the above happens automatically
- Human review only for flagged failures
- Session report shows pass/fail per step

---

## Core Architecture

The engine is a **closed-loop orchestration system** that receives a goal, decomposes it into tasks, executes through tools, validates progress, and adapts through feedback until the correct outcome is reached.

```
[INPUT / EVENT]
      ↓
[ORCHESTRATOR]    ← control center
      ↓
[PLANNER]         ← task decomposition
      ↓
[EXECUTION]       ← tool calls, parallel workers
      ↓
[REVIEW]          ← confidence bands, validation
      ↓
[DECISION]        ← continue / retry / escalate / stop
      ↓
[STATE UPDATE]    ← durable JSON state, message log
      ↓
[LOOP / EXIT]
```

The engine is **domain-agnostic**. The same core has run across file analysis, media organization, live stream monitoring, and post-stream closure without modification. New domains plug in through adapters — not engine changes.

---

## What Has Been Built

| Phase | What Was Proven |
|---|---|
| Engine + File Analyzer | Closed-loop works end-to-end |
| Kosmos / Media Organizer | Same engine, second domain, zero engine changes |
| StreamLab | Continuous monitoring mode, live OBS integration |
| Parallel Execution | 4.0× speedup, 200/200 correctness |
| Agent Messaging | Durable JSON message bus, round-trip proven |
| Coordinator / Delegation | 3-worker parallel dispatch, deterministic aggregation |
| Event Bus (Pub/Sub) | 1 publish → N deliveries, publisher names zero recipients |
| Post-Stream Engine | 7 workers, 4-stage pipeline, 4 real sessions validated |

**Live validation:** 4 real recording sessions on 2026-04-11. Naming convention applied correctly (`YYYY-MM-DD_EventName_NNN_EN.mov`). 5 production bugs found and fixed.

---

## Repository Structure

```
Miktos-Agentic-System/
├── engine/                      # Core orchestration engine (MIT)
│   ├── graph/                   # LangGraph nodes, state, router
│   ├── messaging/               # Message bus, pub/sub, AgentMessage
│   ├── coordinator/             # SessionCoordinator, workers
│   ├── services/                # State store, memory
│   └── tools/                   # Shared tool interfaces
├── domains/                     # Domain implementations
│   ├── file_analyzer/           # File classification domain
│   ├── kosmos/                  # Media organization domain
│   ├── streamlab/               # Live stream monitoring domain
│   └── streamlab_post/          # Post-stream closure domain
│       ├── coordinator.py       # 4-stage PostStreamCoordinator
│       └── workers/             # 7 production workers
├── docs/                        # Architecture, decisions, roadmap
├── tests/                       # 52 tests passing
├── scripts/                     # OAuth setup and demo scripts
├── data/                        # Runtime state, message bus, sessions
└── main_post_stream.py          # Primary entry point
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- ffmpeg 8.0+ (`brew install ffmpeg`)
- OBS with WebSocket plugin enabled
- Credentials: YouTube OAuth2, Google Translate API, ElevenLabs API

### Install

```bash
git clone https://github.com/LegnaPetiteTour/Miktos-Agentic-System.git
cd Miktos-Agentic-System
pip install -e .
```

### Configure

```bash
cp .env.example .env
# Fill in: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, ELEVENLABS_API_KEY,
# GOOGLE_TRANSLATE_API_KEY, OBS_HOST, OBS_PORT, OBS_PASSWORD

# One-time YouTube OAuth setup:
python scripts/youtube_auth.py --channel en
python scripts/youtube_auth.py --channel fr

# Configure your session:
cp domains/streamlab_post/config/session_config.example.yaml \
   domains/streamlab_post/config/session_config.yaml
# Fill in event_name, channel IDs, playlist IDs
```

### Run (before your stream)

```bash
# Terminal A — stream monitor with post-stream handoff
python main_streamlab.py --handoff --poll-interval 5

# Terminal B — post-stream closure engine
python main_post_stream.py --poll-interval 5

# Start OBS → run the stream → stop OBS
# Miktos closes the session automatically.
```

### Dry run (no credentials needed)

```bash
python main_post_stream.py --once --dry-run
```

---

## Post-Stream Pipeline

```
Stage 1 (parallel):  backup_verify  |  youtube_en   |  audio_extract
Stage 2 (parallel):  translate      |  transcript
Stage 3 (parallel):  youtube_fr     |  file_rename
Stage 4 (optional):  notify
```

If Stage 1 has a required failure, the coordinator stops and reports exactly which slot failed and why. Optional slots never block the session.

---

## Adapter Model

Miktos is designed as a **hub with adapters**, not a monolithic app. Integration depth varies by tool:

| Level | What it means | Examples |
|---|---|---|
| 1 — Manual companion | Miktos tracks state only | Epiphan Pearl (initially) |
| 2 — Read-only monitoring | Miktos observes but does not control | Stream health metrics |
| 3 — Assisted control | Miktos triggers actions and verifies | YouTube metadata, ElevenLabs |
| 4 — Full orchestration | Miktos monitors, acts, and closes the loop | OBS WebSocket, post-stream pipeline |

New adapters plug in as domain workers. The engine does not change.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Orchestration | LangGraph 1.x |
| Validation | Pydantic v2 |
| Testing | pytest |
| Message Bus | JSON-backed pub/sub (Redis upgrade path built in) |
| Media Processing | ffmpeg 8.0 / ffprobe |
| Live Stream Control | OBS WebSocket |
| Transcript | ElevenLabs Scribe API |
| Translation | Google Translate API v2 |
| Publishing | YouTube Data API v3 |
| Notifications | Teams webhook + Microsoft Graph API |

---

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full phase-by-phase build history with commit hashes and live proof for every milestone.

Next: pre-stream readiness checks, Zoom/Epiphan scenario support, operations dashboard frontend.

---

## License and Commercial Use

Miktos Core (engine, message bus, coordinator pattern, adapter SDK) is open source under the [MIT License](LICENSE).

Commercial hosted services, managed integrations, enterprise features, and premium workflow packs are separate offerings. See [NOTICE](NOTICE) for details.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). New adapters, domain workflows, and bug fixes are welcome. The engine architecture is frozen — contributions should be additive.
