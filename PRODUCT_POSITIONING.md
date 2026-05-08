# Miktos — Product Positioning

**Last updated:** 2026-05-08

---

## The One-Line Description

Miktos orchestrates the broadcast so professional tools can do what they do best.

---

## What Miktos Is

Miktos is an **orchestration layer**.

- Miktos coordinates tools.
- Miktos manages session state.
- Miktos automates fragile post-stream workflows.
- Miktos gives operators one cockpit for the full production lifecycle.
- Miktos produces reliable, auditable post-stream outputs.
- Miktos makes bilingual institutional live production operable by a single person.

---

## What Miktos Is Not

- Miktos is **not** an encoder.
- Miktos is **not** a compositor.
- Miktos is **not** a replacement for OBS. It coordinates OBS.
- Miktos is **not** a replacement for Epiphan Pearl. It coordinates Pearl.
- Miktos is **not** a video editor.
- Miktos is **not** a graphics engine.
- Miktos is **not** a caption renderer.
- Miktos is **not** a streaming CDN.
- Miktos is **not** a multi-tenant SaaS platform (yet).

---

## Two Products, One Engine

### Miktos Core

The reusable orchestration engine.

```text
engine/
  graph/        LangGraph closed-loop: plan → execute → review → decide
  messaging/    MessageBus, pub/sub, agent-to-agent events
  coordinator/  SessionCoordinator, parallel worker dispatch
  adapters/     DeviceAdapter protocol, capability flags, registry
  services/     State store, run ID
  models/       Shared schemas
```

The engine is domain-agnostic. It does not know about OBS, Pearl, YouTube,
or any specific device. Three independent domains have run through the same
engine with zero engine modification between them.

### Miktos StreamLab

The flagship production domain built on the Core engine.

```text
domains/streamlab/         Live production monitor
domains/streamlab_post/    Post-stream closure pipeline (7 workers, 4 stages)
domains/epiphan/           Pearl hardware integration
domains/captioning/        Bilingual caption worker
web/                       Browser cockpit (FastAPI + HTMX)
engine/adapters/pearl_adapter.py    Epiphan Pearl REST adapter
engine/adapters/obs_adapter.py      OBS WebSocket adapter
```

StreamLab is a bilingual institutional broadcast cockpit that:
- Controls Pearl and OBS from a single browser UI
- Automates post-stream archival (transcription, translation, YouTube metadata)
- Reduces live-event operation to a governed session workflow
- Produces a complete 7-file session archive after every stream

---

## Target User

**Primary:** Communications operators at bilingual institutions —
government agencies, NGOs, universities, media organizations —
who manage live streams and need post-stream processing to be
automatic and auditable.

**Secondary:** Single-operator content creators streaming to multiple
YouTube channels who want automated post-stream workflows.

**Not (yet):** Large broadcast organizations with dedicated engineering
teams and custom infrastructure.

---

## The Problem StreamLab Solves

Bilingual institutional live streaming currently requires:

- Manual recording management across multiple hardware devices
- Manual audio extraction and transcription in two languages
- Manual YouTube metadata updates for two channels
- No automatic session archive
- No transcript for media accountability
- ~30 minutes of manual work after every stream

**After Miktos:** Stream ends → session closes automatically.
One operator. One cockpit. Zero post-stream manual steps.

---

## What "Done" Looks Like

A communications operator at a bilingual institution can:

1. Install Miktos (`.dmg` or Docker)
2. Complete the guided setup wizard (YouTube OAuth, ElevenLabs, hardware)
3. Before a stream: open the cockpit, confirm session name, click Start
4. During the stream: control layouts, switch scenes, monitor health from one browser tab
5. After the stream: stop the hardware recording, click Stop in Miktos
6. Receive a complete session archive within 2 minutes
7. Never touch a terminal. Never edit a config file.

---

## Current Status (Phase 19 — Production-Ready)

| Capability | Status |
|---|---|
| Post-stream closure pipeline | ✅ Production-validated |
| Web cockpit (browser-based) | ✅ Production-validated |
| Pearl hardware control | ✅ Production-validated |
| OBS scene control | ✅ Production-validated |
| Auto-discovery (channels, inputs, scenes) | ✅ Production-validated |
| Live thumbnail preview | ✅ Production-validated |
| Rehearsal / demo mode | ✅ Implemented |
| Electron .dmg packaging | ✅ Implemented |
| Docker deployment | ✅ Implemented |
| 252 tests passing | ✅ |
| Live captions during session | ⏸ Post-session only (roadmap) |
| Multi-operator / roles | ⏸ Stage 3 (roadmap) |

---

## Commercial Boundary (Planned)

**Open Source (free, always):**
- Local cockpit
- Core orchestration engine
- OBS adapter
- Pearl adapter
- Basic YouTube integration
- Basic post-stream pipeline
- Rehearsal mode
- Adapter SDK

**Pro Self-Hosted (paid, future):**
- Docker deployment with auth and user roles
- Advanced audit logs and encrypted secrets
- Institution branding
- Advanced caption monitoring
- Storage connectors
- Priority adapters

**Managed / VIP (paid, future):**
- Installation, configuration, staff training
- Custom adapter development
- Event readiness testing
- Priority support

---

## What Will Never Be Built Into Miktos Core

- A video encoder or compositor
- A video editor
- Fancy animated transitions
- An AI director that switches live without operator confirmation
- A generic "build anything" agent
- A marketplace

These may exist as third-party adapters or integrations.
They are not the product.

---

## Related Documents

- `CORE_CONTRACT.md` — engine boundary rules
- `ROADMAP.md` — full phase history
- `CONTRIBUTING.md` — how to contribute
