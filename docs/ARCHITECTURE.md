# Architecture — Miktos Agentic System

## Overview

The Miktos Agentic System is built around one central idea:

**The real value is not in the AI model. The real value is in the orchestration system around it.**

The LLM is a reasoning engine — one component. The system is the maze.

---

## Core Loop

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

---

## Layer Definitions

### INPUT
- Receives goal, trigger, request, or condition
- Parses and normalizes
- Attaches metadata
- Does not make decisions

### ORCHESTRATOR
- The control center
- Classifies task type
- Decides workflow
- Routes to planner or directly to execution
- Allocates resources
- Creates and owns the session state
- The only layer with full visibility of the system

### PLANNER
- Decomposes goal into discrete tasks
- Defines dependencies
- Defines sequence and parallel work
- Defines success criteria per task
- Defines stopping conditions
- Does not execute

### EXECUTION
- The only layer that acts in the real world
- Calls tools, APIs, scripts
- Generates artifacts or outputs
- Reports status after each action

### REVIEW
- Checks correctness
- Checks policy, safety, quality
- Compares output against success criteria
- Detects failures, uncertainty, conflicts
- Does not decide — only evaluates

### DECISION
- The gate after review
- Chooses one of:
  - `continue` — pass to next task
  - `retry` — re-execute with same or adjusted params
  - `replan` — return to planner
  - `escalate` — surface to human
  - `stop` — terminate the run

### STATE UPDATE
- Records current progress
- Records failures and outputs
- Records changed context
- Persists to durable store
- This is what separates a loop from a reset

### LOOP / EXIT
- If work remains and bounds allow: feed back to orchestrator
- If completion criteria met: exit cleanly
- If bounds exceeded: escalate or stop

---

## Engine vs Domain

This is the critical separation.

| Belongs to ENGINE | Belongs to DOMAIN |
|---|---|
| Orchestration logic | Tool implementations |
| State management | Classification rules |
| Decision gates | Success criteria |
| Loop control | Domain-specific schemas |
| Review interface | Domain-specific services |
| Planner interface | Environment constraints |

When building a new domain, the engine does not change. Only the domain layer changes.

---

## The Maze Analogy

```
Ball           = task / request / input
Maze           = system architecture
Exit           = goal completion
Orchestrator   = control system
Planner        = path prediction
Execution      = moving parts
Review         = sensors
Decision+State = reconfiguration logic
Loop           = continuous steering
```

> The ball is not solving the maze. The maze is solving the path for the ball.

**Critical note:** The maze will eventually run multiple balls (parallel tasks, concurrent agents). The architecture must account for parallelism — not just single-threaded execution.

---

## State Design Principle

State is the spine. A system with weak state is not agentic — it is a pipeline that resets.

State must always answer:
- Where is the system right now?
- What has already succeeded?
- What has failed?
- What is pending?
- What changed since last loop?
- What are the bounds?
