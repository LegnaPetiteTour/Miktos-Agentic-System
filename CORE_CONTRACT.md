# Core Contract

This document describes the invariants the Miktos architecture depends on.
If you are extending the engine, adding a domain, or reviewing a PR, check
your changes against these rules first.

---

## 1. The Engine Does Not Know What Domain It Is In

The engine (`engine/`) has zero imports from `domains/`. It does not know
whether it is processing files, streams, or Pearl recordings. Domain knowledge
lives in scanner tools and classifier functions injected at runtime. The engine
processes the output of those tools, not the tools themselves.

**Violation test:** If you find yourself writing `if domain == "streamlab":`
inside `engine/`, stop. That logic belongs in the scanner tool.

---

## 2. The Scanner Adapter Is the Only Domain Seam

Each domain plugs into the engine through exactly one surface: a scanner tool
that converts its world into the engine's internal task shape (`AlertItem` or
equivalent). The engine's graph, state, router, and nodes are untouched.

Three domains have passed through the same engine with zero engine changes:

```text
Domain 1 — File Analyzer:   FileScannerTool     → MIME alert items
Domain 2 — Kosmos:          FileScannerTool     → media alert items
Domain 3 — StreamLab:       OBSMonitorTool      → stream alert items
Domain 4 — Epiphan:         EpiphanMonitorTool  → Pearl alert items
```

Adding a fifth domain means writing a scanner tool. It does not mean touching
`engine/graph/`, `engine/coordinator/`, or any shared module.

---

## 3. Workers Are Stateless and Side-Effect-Isolated

Every pipeline worker (`domains/streamlab_post/workers/*.py`) receives a
payload dict and returns a result dict. Workers do not share state with each
other. Side effects (file writes, API calls) happen inside the worker, not
before or after it. This is why parallel execution is safe.

```python
# Correct
result = worker.run({"file": path, "dry_run": True})

# Wrong — do not do this
worker.state["file"] = path
result = worker.run({})
```

`dry_run=True` must produce no irreversible side effects. Every worker that
touches external systems must implement `dry_run` and every test must use it.

---

## 4. The Web Layer Is a Surface, Not a Controller

`web/` renders state and forwards commands. It does not orchestrate. It does
not contain business logic. When the operator clicks "Start Session", the web
layer starts `run_session.py` — the same script the operator has always run
from a terminal. The terminal path is always preserved as a fallback.

The cockpit SSE streams (`/api/status/stream`) read from files and process
objects. They do not write state, trigger transitions, or make decisions.

---

## 5. State Is Files, Not Memory

All persistent state is written to disk as JSON before the process that wrote
it exits. There is no in-memory-only state that matters across restarts. The
SSE stream, session coordinator, action log, rehearsal mode, and run-of-show
all read from files that survive a server restart.

Consequence: every module that owns state has a `Path` constant
(`ACTION_LOG_FILE`, `RUNOFSHOW_STATE_FILE`, etc.) that is monkeypatchable in
tests. Tests must never read from or write to production data paths.

---

## 6. Tests Are the Contract, Not the Documentation

Every capability has a test. If something is not tested, it is not part of the
contract — it may be removed without warning. 252 tests must pass before any
PR merges. CI enforces this.

Test discipline:
- Tests use `dry_run=True` for workers that touch external systems
- SSE endpoints are tested by patching `_event_stream` with a finite generator
- Module-level path constants are monkeypatched — never use real data paths
- `raise_server_exceptions=False` on `TestClient` for error-path tests

---

## 7. Lint Is Enforced, Not Optional

`ruff` runs in CI before tests. An unused import fails the build. No
`# noqa` exceptions without a documented reason. Pylance errors in production
files are fixed with `# type: ignore[<code>]` — not suppressed wholesale with
`# type: ignore`.

---

## 8. The `.env` File Is Not the Source of Truth for Defaults

Defaults in code must match what is documented in `.env.example`. When you
change a default (e.g. `PEARL_CHANNEL_EN` from `1` to `2`), update both the
code and `.env.example` in the same commit. The `.env` file itself is
gitignored and never committed.

---

## Invariant Summary

| # | Rule |
|---|------|
| 1 | Engine has no domain imports |
| 2 | One scanner seam per domain |
| 3 | Workers are stateless, `dry_run` required |
| 4 | Web layer is a surface, not a controller |
| 5 | State is files, not memory |
| 6 | Tests are the contract |
| 7 | Lint is enforced |
| 8 | Code defaults match `.env.example` |
