
---

## ADR-006 — Python version target is 3.11, not 3.14

**Date:** 2026-04-07
**Status:** Accepted

**Context:**
First dry run completed successfully on Python 3.14. LangGraph emitted a
Pydantic v1 compatibility warning on that version. The run did not fail,
but the warning signals an untested compatibility surface.

**Decision:** Pin the stable baseline to Python 3.11.

**Reasoning:**
- LangGraph and Pydantic v2 are explicitly tested against Python 3.11/3.12
- Python 3.14 is too new for the current dependency graph to fully support
- The .venv in the repo should target 3.11 for reproducible CI behavior

**Action required:**
If running on 3.14, recreate the venv against 3.11:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Does not block Milestone 1.1.** Runs complete correctly on 3.14.
This is a stability and reproducibility concern for Milestone 1.2+.
