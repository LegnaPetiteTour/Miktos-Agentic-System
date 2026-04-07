"""
State persistence service.

Handles saving and loading RunState to/from JSON.
Version 1 uses local JSON files.
Designed to be swappable for SQLite or a real DB in v2.
"""

import json
import uuid
from pathlib import Path
from datetime import datetime
from engine.graph.state import RunState


STATE_DIR = Path("data/state")


def generate_run_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def save_state(state: RunState) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{state['run_id']}.json"
    with open(path, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_state(run_id: str) -> RunState:
    path = STATE_DIR / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No state found for run_id: {run_id}")
    with open(path) as f:
        return json.load(f)


def list_runs() -> list[str]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return [p.stem for p in sorted(STATE_DIR.glob("*.json"))]
