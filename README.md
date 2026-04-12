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
~30 minutes of manual post-stream work after every bilingual EN/FR institutional stream. One
stream-end event triggers full session closure — backup verification, YouTube metadata, audio
extraction, translation, transcript, file organization, and notification — with no human involvement.

---

## Core Architecture

```
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

## What Has Been Built

**Phase 1 — File Analyzer** ✅  
Rule-based four-tier MIME classifier. First engine stress test. 18/18 tests.

**Phase 2 — Kosmos (Media Organizer)** ✅  
Nine-rule media classifier with EXIF probe. Second domain through the same
engine, zero engine changes. 22/22 tests.

**Phase 3 — StreamLab Monitor** ✅  
OBS WebSocket adapter. Continuous health monitoring loop. Outer-loop pattern
— the engine remains single-invocation inside. Live run confirmed. 25/25 tests.

**Phase 4a — Parallel Execution** ✅  
`parallel_execution_node` alongside `execution_node`. 4× speedup on 200-file
benchmark (0.21s → 0.05s). Additive only, backward compatible. 29/29 tests.

**Phase 4b — Agent-to-Agent Messaging** ✅  
JSON-backed `MessageBus` with atomic writes. `AgentMessage`, `post()`,
`acknowledge()`, append-only `message.log`. Live round-trip: StreamLab →
Kosmos → reply. 34/34 tests.

**Phase 4c — Task Delegation** ✅  
`SessionCoordinator` with parallel worker dispatch and retry.
`KosmosWorker`, `ThumbnailWorker`, `MetadataWorker`. 39/39 tests.

**Phase 4d — Event Bus (Pub/Sub)** ✅  
`bus.subscribe()` / `bus.publish()` fan-out. One event, N independent
reactions. Publisher names zero recipients. 44/44 tests.

**Phase 5 — Post-Stream Closure Engine** ✅  
Full production operations layer. Seven workers, four-stage pipeline,
inter-stage payload enrichment. Live validated across four real stream
sessions. 52/52 tests.

---

## StreamLab: The Post-Stream Pipeline

```
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
|--------|-------------|
| `backup_verify` | File exists, size threshold, ffprobe structural validation |
| `youtube_en` | YouTube Data API v3 — set title, description, visibility, playlist |
| `audio_extract` | ffmpeg MP3 extraction from raw recording |
| `translate` | Google Translate API v2 — EN→FR title and description |
| `transcript` | ElevenLabs Scribe — bilingual, speaker-labeled |
| `youtube_fr` | Same as youtube_en for the FR channel, using translated metadata |
| `file_rename` | `YYYY-MM-DD_EventName_NNN` convention, organized session folder |
| `notify` | Teams webhook + Graph API email with transcript attached |

**Before:** 10 manual steps after every stream, ~30 min.  
**After:** Zero. Stream ends, session closes. Human review only for flagged ❌ slots.

---

## Running a Stream Session

Two processes, both started before OBS:

```bash
# Terminal A — monitors OBS and fires the trigger
python main_streamlab.py --handoff --poll-interval 5

# Terminal B — processes the trigger through the full pipeline
python main_post_stream.py --poll-interval 5
```

Then in OBS: **Start Streaming + Start Recording** → stream → **Stop Recording + Stop Streaming**.

The monitor detects the recording→stopped transition (edge-triggered, exactly once per session)
and publishes a `recording_stopped` event to the bus. The post-stream processor picks it up and
runs the four-stage pipeline.

**Per-stream config** (`domains/streamlab_post/config/session_config.yaml`):

```yaml
event_name: "Miktos-Demo"
recording:
  local_path: "/Users/yourname/Movies"
youtube:
  en:
    video_id: "ABC123"      # from YouTube Studio after scheduling
    channel_id: "UCxxx"
    playlist_id: "PLxxx"
    visibility: "unlisted"
  fr:
    video_id: ""            # leave blank — auto-discovery finds the FR live event
    channel_id: "UCyyy"
    playlist_id: "PLyyy"
    visibility: "unlisted"
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Orchestration | LangGraph |
| Validation | Pydantic |
| Testing | pytest (52 passing) |
| State Storage | JSON (v1) |
| Messaging | JSON-backed MessageBus with atomic writes |
| YouTube | Data API v3, OAuth2 |
| Translation | Google Translate API v2 |
| Transcript | ElevenLabs Scribe |
| Audio | ffmpeg |
| Stream Control | OBS WebSocket (obs-websocket-py) |
| LLM Usage | Narrow — ambiguous classifier cases only |

---

## Repository Structure

```
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
│   └── streamlab/                # Domain 3 — live production
│       ├── tools/                # OBS monitor, client, alert classifier
│       └── streamlab_post/       # Phase 5 — post-stream closure engine
│           ├── workers/          # Seven closure workers
│           └── config/           # session_config.yaml, thresholds
├── scripts/                      # youtube_auth.py, dev utilities
├── tests/                        # 52 passing, 1 skipped (live OBS)
├── docs/                         # Architecture, decisions, roadmap, glossary
└── data/                         # Runtime: sessions, messages, state, logs
```

---

## The Adapter Model Proof

Three domains. Zero engine changes between them.

```
Domain 1 — File Analyzer:   FileScannerTool      → MIME alert items
Domain 2 — Kosmos:          FileScannerTool      → media alert items
Domain 3 — StreamLab:       OBSMonitorTool       → stream alert items
```

The engine processes identically. The only difference per domain is the
scanner tool and classifier function injected at runtime. This is the
core architectural invariant of Miktos.

---

## Status

🟢 **Phase 5 — Complete** — Post-stream closure engine live validated. 52/52 tests passing.

---

## License

MIT — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
