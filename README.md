# Miktos Agentic System

> A domain-agnostic closed-loop orchestration engine and live production operations layer for multilingual streams.

---

## What This Is

Miktos Agentic System is **not** a chatbot. It is not a script. It is not a single app.

It is a closed-loop agentic orchestration engine that receives a goal, decomposes it into tasks,
executes through tools, validates progress, adapts through feedback, updates state, and continues
until the correct outcome is reached — then stops.

The engine is domain-agnostic. It does not change between products. Only the tools, rules, and
success criteria change per domain. Three independent domains have been plugged into the same
engine with zero engine modification between them.

The first production use case is **StreamLab**: a live production operations layer that eliminates
~30 minutes of manual post-stream work after every bilingual EN/FR institutional stream. A web
cockpit (Phase 10+) gives operators a browser-based control surface for sessions, hardware, and
health — no terminal required.

---

## What Works Today (Phase 19 — Production-Ready)

| Capability | Status |
| --- | --- |
| Post-stream closure pipeline (7 workers, 4 stages) | ✅ Live |
| OBS WebSocket monitoring | ✅ Live |
| Pearl (Epiphan) hardware integration | ✅ Live |
| Web cockpit — session start/stop from browser | ✅ Live |
| Web cockpit — Pearl layout control | ✅ Live |
| Web cockpit — health monitoring widget | ✅ Live |
| Web cockpit — rehearsal mode | ✅ Live |
| Web cockpit — live thumbnail preview | ✅ Live |
| Web cockpit — Pearl + OBS auto-discovery | ✅ Live |
| Pre-flight checks | ✅ Live |
| Action log | ✅ Live |
| JWT auth + single-password protection | ✅ Live |
| Docker deployment | ✅ Live |
| Test suite | ✅ 252 passing |

---

## Installation

### Requirements

- Python 3.12+
- OBS Studio with WebSocket server enabled (Tools → WebSocket Server Settings)
- Pearl (Epiphan) hardware (optional — OBS-only mode is fully supported)
- ffmpeg on PATH

### Setup

```bash
git clone https://github.com/LegnaPetiteTour/Miktos-Agentic-System.git
cd Miktos-Agentic-System
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then edit .env with your credentials
```

### Configure `.env`

```env
# OBS WebSocket (Tools → WebSocket Server Settings in OBS)
OBS_HOST=localhost
OBS_PORT=4455
OBS_PASSWORD=your_obs_password

# Pearl hardware (optional)
PEARL_HOST=192.168.x.x
PEARL_PASSWORD=your_pearl_password
PEARL_CHANNEL_EN=2
PEARL_CHANNEL_FR=3

# YouTube OAuth2 (run scripts/youtube_auth.py to generate tokens)
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN_EN=
YOUTUBE_REFRESH_TOKEN_FR=

# Auth (set AUTH_ENABLED=true to require login)
AUTH_ENABLED=false
AUTH_PASSWORD=change-me
JWT_SECRET=
```

### Run the web cockpit

```bash
python main.py
# open http://localhost:8000
```

### Run a stream session (terminal mode)

```bash
# Terminal A — OBS monitor + trigger
python main_streamlab.py --handoff --poll-interval 5

# Terminal B — post-stream pipeline
python main_post_stream.py --poll-interval 5
```

Or click **Start Session** in the web cockpit.

### Run tests

```bash
pytest
```

---

## Screenshots

<!-- TODO: add cockpit screenshots after first live event -->

---

## Core Architecture

```text
[INPUT / TRIGGER]
       ↓
[SCANNER / ADAPTER]     ← domain swaps this layer only
       ↓
[PLANNER]               ← decomposes goal into tasks
       ↓
[EXECUTION]             ← the only layer that touches the real world
       ↓
[REVIEW]                ← validates output against success criteria
       ↓
[DECISION]              ← continue / retry / replan / escalate / stop
       ↓
[STATE UPDATE]          ← records everything
       ↓
[LOOP / EXIT]           ← feeds back or exits on completion
```

The adapter model: each domain provides a scanner tool that converts its
world (files, OBS health metrics, stream events) into the engine's task
shape. The engine processes identically regardless of domain.

---

## The Post-Stream Pipeline

```text
Stream ends (OBS recording stopped)
         ↓
Stage 1 (parallel):  backup_verify  |  youtube_en    |  audio_extract
         ↓                ↓                ↓                ↓
Stage 2 (parallel):              translate          transcript
         ↓                          ↓                    ↓
Stage 3 (parallel):            youtube_fr            file_rename
         ↓
Stage 4 (optional):                notify
```

| Worker | What it does |
| -------- | ------------- |
| `backup_verify` | File exists, size threshold, ffprobe structural validation |
| `youtube_en` | YouTube Data API v3 — set title, description, visibility, playlist |
| `audio_extract` | ffmpeg MP3 extraction from raw recording |
| `translate` | Google Translate API v2 — EN→FR title and description |
| `transcript` | ElevenLabs Scribe — bilingual, speaker-labeled |
| `youtube_fr` | Same as `youtube_en` for the FR channel, using translated metadata |
| `file_rename` | `YYYY-MM-DD_EventName_NNN` convention, organized session folder |
| `notify` | Teams webhook + Graph API email with transcript attached |

**Before:** 10 manual steps after every stream, ~30 min.  
**After:** Zero. Stream ends, session closes. Human review only for flagged ❌ slots.

---

## Tech Stack

| Layer | Choice |
| --- | --- |
| Language | Python 3.12+ |
| Web framework | FastAPI + Jinja2 + HTMX |
| Orchestration | LangGraph |
| Validation | Pydantic |
| Testing | pytest (252 passing) |
| State storage | JSON (file-backed) |
| Messaging | JSON-backed MessageBus with atomic writes |
| Stream control | OBS WebSocket (`obsws-python`) |
| Hardware control | Pearl (Epiphan) REST API |
| YouTube | Data API v3, OAuth2 |
| Translation | Google Translate API v2 |
| Transcript | ElevenLabs Scribe |
| Audio | ffmpeg |
| Auth | JWT (PyJWT), single-password |
| Deployment | Docker + docker-compose |

---

## Repository Structure

```text
Miktos-Agentic-System/
├── engine/                       # Core reusable orchestration engine
│   ├── graph/                    # LangGraph nodes, state, router
│   ├── messaging/                # MessageBus, AgentMessage, pub/sub
│   ├── coordinator/              # SessionCoordinator, base workers
│   ├── services/                 # State store, run ID generation
│   ├── models/                   # Shared schemas
│   └── tools/                    # Shared tool interfaces
├── domains/
│   ├── file_analyzer/            # Domain 1 — MIME classifier
│   ├── kosmos/                   # Domain 2 — media organizer
│   ├── streamlab/                # Domain 3 — live production monitor
│   ├── streamlab_post/           # Post-stream closure engine (7 workers)
│   └── epiphan/                  # Pearl hardware integration
├── web/                          # Web cockpit (FastAPI)
│   ├── api/                      # REST endpoints
│   ├── templates/                # Jinja2 + HTMX panels
│   └── static/                   # CSS, JS
├── scripts/                      # youtube_auth.py, dev utilities
├── tests/                        # 252 passing
├── docs/                         # Architecture, decisions, phase specs
└── data/                         # Runtime: sessions, messages, state, logs
```

---

## The Adapter Model Proof

Three domains. Zero engine changes between them.

```text
Domain 1 — File Analyzer:   FileScannerTool      → MIME alert items
Domain 2 — Kosmos:          FileScannerTool      → media alert items
Domain 3 — StreamLab:       OBSMonitorTool       → stream alert items
Domain 4 — Epiphan:         EpiphanMonitorTool   → Pearl alert items
```

The engine processes identically. The only difference per domain is the
scanner tool and classifier function injected at runtime.

See [CORE_CONTRACT.md](CORE_CONTRACT.md) for the invariants this architecture depends on.  
See [PRODUCT_POSITIONING.md](PRODUCT_POSITIONING.md) for what Miktos is and is not.

---

## Status

🟢 **Phase 19 — Production-Ready** — 252 tests passing. Cockpit validated. Live event ready.

---

## License

MIT — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
