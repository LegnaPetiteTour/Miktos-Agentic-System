# Miktos Core Contract

**Status:** Active  
**ADR:** ADR-009 (adapter contract), ADR-010 (core/domain boundary)  
**Last updated:** 2026-05-08

---

## Purpose

This document defines the strict boundary between the Miktos Core engine
and every domain, adapter, UI layer, and product built on top of it.

The boundary exists to make the engine reusable. Three independent domains
(File Analyzer, Kosmos, StreamLab) have run through the same engine with
zero engine modification between them. This is only possible if the boundary
is respected.

---

## What the Core Engine Is

Miktos Core is a closed-loop orchestration engine. It receives a goal,
decomposes it into tasks, executes through adapters, reviews outcomes,
makes decisions, updates state, and loops or exits.

Core components:

```text
engine/graph/         LangGraph nodes, router, state machine
engine/messaging/     MessageBus, pub/sub, agent-to-agent messaging
engine/coordinator/   SessionCoordinator, parallel worker dispatch
engine/services/      State store, run ID generation
engine/models/        Shared schemas (RunState, TaskItem, etc.)
engine/adapters/      DeviceAdapter protocol, capability flags, registry
engine/tools/         Shared tool interfaces
```

---

## What the Core May Know About

The core engine operates on these abstractions only:

- **Goals** — intent expressed as task items
- **Tasks** — unit of work with input, expected output, success criteria
- **Plans** — ordered or parallel sequences of tasks
- **Execution steps** — single task execution through an adapter or tool
- **Review results** — pass / fail / partial against success criteria
- **State** — `RunState` — the single source of truth for a session
- **Retries** — count, backoff, exhaustion policy
- **Decisions** — continue / retry / replan / escalate / stop
- **Errors** — structured, with recovery path or escalation trigger
- **Artifacts** — opaque outputs from execution (file paths, IDs, payloads)
- **Events** — typed events published to the MessageBus
- **Adapters** — abstract capability providers conforming to `DeviceAdapter`

---

## What the Core Must Never Know About

The following are domain-specific and must never appear in `engine/`:

| Forbidden in core | Belongs in |
| --- | --- |
| OBS scene names | `engine/adapters/obs_adapter.py` or `domains/streamlab/` |
| Pearl channel IDs | `engine/adapters/pearl_adapter.py` or session config |
| YouTube video IDs | `domains/streamlab_post/workers/youtube_worker.py` |
| StreamLab pipeline stages | `domains/streamlab_post/coordinator.py` |
| ElevenLabs API behaviour | `domains/streamlab_post/workers/transcript_worker.py` |
| Google Translate API behaviour | `domains/streamlab_post/workers/translation_worker.py` |
| File organizer category rules | `domains/kosmos/` |
| MIME classifier rules | `domains/file_analyzer/` |
| UI layout decisions | `web/templates/` |
| Cockpit panel rendering | `web/api/`, `web/templates/` |
| Hardware-specific REST endpoints | `engine/adapters/` implementations |
| Hardcoded device behaviour | `engine/adapters/` implementations |
| Session config YAML structure | `domains/streamlab_post/config/` |

---

## The Boundary Rule

If the core needs something from a domain, it must arrive through one of:

1. **Adapter capability** — `adapter.capabilities().supports_layout_switch`
2. **Task schema** — structured `TaskItem` with typed inputs
3. **State object** — `RunState` fields only
4. **Execution interface** — `adapter.switch_layout(layout_id, channel)`
5. **Domain policy** — injected at runtime, never hardcoded in core

**Wrong — domain logic leaking into core:**

```python
# engine/graph/execution_node.py
if device == "pearl":
    client.switch_to_layout(channel_id=2, layout_id=9)
```

**Correct — capability-driven, adapter-abstracted:**

```python
# engine/graph/execution_node.py
if adapter.capabilities().supports_layout_switch:
    adapter.switch_layout(task.layout_id, task.channel)
```

---

## Adapter Contract

Every adapter must conform to the `DeviceAdapter` Protocol defined in
`engine/adapters/base.py`.

Key invariants:

1. `capabilities()` must never require a live hardware connection.
2. All methods may return falsy or raise when hardware is unavailable.
3. Unsupported actions must return a structured response — never silently fail.
4. `health()` must never raise — always return a dict.
5. Adapters own their hardware knowledge. The core never calls
   device-specific APIs directly.

Capability flags drive cockpit rendering:

```python
# Correct: render based on declared capabilities
if adapter.capabilities().supports_layout_switch:
    render_layout_panel()

# Wrong: render based on hardware name
if hardware_name == "epiphan":
    render_layout_panel()
```

Full capability flag list: `engine/adapters/base.py` → `AdapterCapabilities`.

---

## Engine Proof

Three domains. Zero engine changes between them.

```text
Domain 1 — File Analyzer:  FileScannerTool    → MIME alert items
Domain 2 — Kosmos:         FileScannerTool    → media alert items
Domain 3 — StreamLab:      OBSMonitorTool     → stream alert items
Domain 4 — Epiphan:        EpiphanMonitorTool → Pearl alert items
```

Verified: `git diff main -- engine/graph/` is empty between domain additions.
The engine processes identically. Only the scanner tool and classifier
function are injected at runtime.

---

## Violations

If you find domain-specific logic in `engine/`, it is a bug.
Open an issue with label `core-contract-violation`.

Examples of violations to watch for:

- An import of `domains/` inside `engine/`
- A hardcoded device name inside `engine/graph/`
- A YouTube/Pearl/OBS-specific call inside `engine/coordinator/`
- A pipeline stage name hardcoded inside `engine/`

---

## Related Documents

- `engine/adapters/base.py` — `DeviceAdapter` Protocol + `AdapterCapabilities`
- `PRODUCT_POSITIONING.md` — what Miktos is and is not
- `ROADMAP.md` — phase history and architectural decisions
- `CONTRIBUTING.md` — how to contribute
