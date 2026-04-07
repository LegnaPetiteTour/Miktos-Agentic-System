# Glossary — Miktos Agentic System

---

**Agentic Orchestration System with a Closed-Loop Execution Model**
The full name for the Miktos engine. A system that receives a goal, decomposes it, executes through tools, validates progress, adapts through feedback, and continues until the correct outcome is reached.

**Orchestrator**
The control center. The only layer that sees the full picture. Routes work, tracks progress, enforces rules, owns the session.

**Planner**
The layer that decomposes goals into tasks and defines dependencies, sequence, and success criteria. Does not execute.

**Executor**
The layer that performs real-world actions through tools. The only layer that touches the environment.

**Reviewer**
The layer that evaluates outputs against success criteria. Does not decide — only evaluates.

**Decision Gate**
The control point after review. Chooses: continue, retry, replan, escalate, or stop.

**State**
The persistent record of everything the system knows about the current run — what happened, what failed, what changed, what's next.

**Loop**
The feedback cycle that makes the system agentic. Without a loop, it is a pipeline.

**Domain**
A specific use case plugged into the engine. The engine does not change between domains. Only tools, rules, and success criteria change.

**Engine**
The reusable core orchestration system. Domain-agnostic. The maze.

**The Maze**
The primary analogy for the system. The maze actively reconfigures to guide the ball (task) toward the correct exit (goal completion). The ball does not solve the maze. The maze solves the path for the ball.

**Ball**
The task or request moving through the system.

**Dry-Run Mode**
Execution mode where no real-world changes are made. The system produces a plan and proposed actions only. Used for validation before live mode.

**Review Queue**
The holding area for tasks that fall below the confidence threshold and require human review.

**Confidence Band**
The threshold system for automated decisions:
- >= 0.90 → auto-approve
- 0.60–0.89 → send to review queue
- < 0.60 → skip and log
