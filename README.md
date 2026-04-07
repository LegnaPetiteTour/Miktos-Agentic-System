# Miktos Agentic System

> A reusable, controllable, self-correcting execution engine — the core nervous system of Miktos.

---

## What This Is

Miktos Agentic System is **not** a chatbot. It is not a script. It is not a single app.

It is a closed-loop agentic orchestration engine that receives a goal, decomposes it into tasks, executes through tools, validates progress, adapts through feedback, updates state, and continues until the correct outcome is reached.

The architecture is domain-agnostic. The engine does not change between products. Only the tools, rules, and success criteria change per domain.

---

## Core Architecture

```
[INPUT]
   ↓
[ORCHESTRATOR]
   ↓
[PLANNER]
   ↓
[EXECUTION]
   ↓
[REVIEW]
   ↓
[DECISION]
   ↓
[STATE UPDATE]
   ↓
[LOOP / EXIT]
```

| Layer | Responsibility |
|---|---|
| **Input** | Receives any goal, trigger, or condition |
| **Orchestrator** | Control center — routes, tracks, enforces rules |
| **Planner** | Decomposes goal into tasks, dependencies, sequence |
| **Execution** | The only layer that touches the real world via tools |
| **Review** | Validates output — correct, safe, complete, acceptable |
| **Decision** | Gates: continue / retry / replan / escalate / stop |
| **State Update** | Records everything — what happened, failed, changed |
| **Loop / Exit** | Feeds back or exits when completion criteria are met |

---

## The Maze Analogy

The system is best understood as a **3D puzzle ball maze where the maze itself actively reconfigures to guide the ball toward the correct exit.**

- **Ball** = task / request / input
- **Maze** = system architecture
- **Exit** = goal completion
- **Orchestrator** = control system
- **Planner** = path prediction
- **Execution** = moving parts
- **Review** = sensors
- **Decision + State** = reconfiguration logic
- **Loop** = continuous steering

> The ball is not solving the maze. The maze is solving the path for the ball.

---

## Product Hierarchy

```
Miktos Core Engine       ← what we are building
       ↓
File Analyzer            ← Domain 1: first stress test
       ↓
Kosmos                   ← Domain 2: media organizer
       ↓
StreamLab                ← Domain 3: live production
       ↓
DMO / broader ecosystem  ← long-term endgame
```

The engine is built **through** the first domain, not before it. Every architectural decision is evaluated twice: once for the domain, once for generalizability.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Orchestration | LangGraph |
| Validation | Pydantic |
| Testing | pytest |
| State Storage | JSON (v1) |
| LLM Usage | Narrow — ambiguous cases only |
| Editor | VS Code |

---

## Repository Structure

```
Miktos-Agentic-System/
├── docs/                    # Architecture, decisions, roadmap
├── engine/                  # Core reusable orchestration engine
│   ├── graph/               # LangGraph nodes, state, router
│   ├── services/            # Shared services (state store, memory)
│   ├── models/              # Shared schemas and decision models
│   └── tools/               # Shared tool interfaces
├── domains/                 # Domain-specific implementations
│   └── file_analyzer/       # Domain 1 — first stress test
├── tests/                   # Engine and domain tests
├── data/                    # Runtime data (state, logs, queues)
├── config/                  # Global configuration
└── scripts/                 # Dev and ops utilities
```

---

## Key Principle

> Build the maze, not just one ball path.
> Build the nervous system first, then plug products into it.

---

## Status

🟡 **Phase 0 — Foundation** — Repository initialized, architecture locked, build starting.

---

## License

MIT
