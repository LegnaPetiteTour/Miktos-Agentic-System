# Architecture Decision Records (ADR)

This file tracks key architectural decisions, the reasoning behind them, and alternatives considered.

---

## ADR-001 — Python as primary language

**Date:** 2026-04-07
**Status:** Accepted

**Decision:** Use Python 3.11+ as the primary language for the engine and all v1 domains.

**Reasoning:**
- LangGraph, CrewAI, and AutoGen are all Python-first
- File system tooling (pathlib, shutil, hashlib) is mature in Python
- Fastest path from concept to working loop
- Strong Pydantic integration for typed state

**Alternatives considered:**
- TypeScript — rejected for v1 due to higher friction with local tooling and framework maturity

---

## ADR-002 — LangGraph as orchestration backbone

**Date:** 2026-04-07
**Status:** Accepted

**Decision:** Use LangGraph as the core orchestration framework.

**Reasoning:**
- Graph-based model maps directly to the defined architecture (nodes = layers)
- Native support for durable state, checkpoints, and resumability
- Human-in-the-loop controls built in
- State flows through typed objects across nodes

**Alternatives considered:**
- CrewAI — useful for role/task specialization, reserved for future multi-agent expansion
- AutoGen — strong for event-driven multi-agent, reserved for future expansion
- Raw Python — rejected, too much reinvention of solved problems

---

## ADR-003 — Build engine through domain, not before it

**Date:** 2026-04-07
**Status:** Accepted

**Decision:** Build the engine and the file analyzer simultaneously. The engine is extracted and generalized as the domain is built, not designed in the abstract first.

**Reasoning:**
- Platform-before-product is one of the most common failure modes for system thinkers
- Real requirements only emerge under real domain pressure
- The file analyzer is the proving ground, not a test after the fact

**Rule:** Every decision is evaluated twice — once for the domain, once for generalizability.

---

## ADR-004 — JSON state storage for v1

**Date:** 2026-04-07
**Status:** Accepted

**Decision:** Use JSON files for state persistence in v1. No database.

**Reasoning:**
- Simpler to inspect, debug, and audit
- No infrastructure dependencies
- Sufficient for single-node, local execution
- Easy to migrate to SQLite or a real store in v2

---

## ADR-005 — LLM usage is narrow and optional in v1

**Date:** 2026-04-07
**Status:** Accepted

**Decision:** Rules and metadata drive classification. LLM is called only for ambiguous cases.

**Reasoning:**
- Reduces cost
- Improves determinism
- Avoids hallucinated categorization
- Forces the system to be testable without model dependency

**Classification priority:**
1. Rule-based (extension, MIME, filename patterns)
2. Metadata (timestamps, size, EXIF)
3. LLM-assisted (ambiguous only)
