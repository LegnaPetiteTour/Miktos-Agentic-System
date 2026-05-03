"""
engine/runofshow.py — Run-of-show engine.

A run-of-show is an ordered list of Cues.  The operator advances through
them during a live event; Miktos tracks position and writes every advance
to the action log.

This is the structural foundation for Phase 19 AI comparison: the engine
produces a reference timeline; the AI compares the action log against it
to detect and flag divergence ("you're 5 min past the Q&A cue").

State file : data/state/runofshow.json
Templates  : data/templates/{name}.json
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from engine.action_log import write_action
from engine.paths import get_data_dir

# Module-level paths — tests can monkeypatch these
RUNOFSHOW_STATE_FILE: Path = get_data_dir() / "state" / "runofshow.json"
TEMPLATES_DIR: Path = get_data_dir() / "templates"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Cue:
    """A single step in the run-of-show sequence."""

    id: str
    label: str
    notes: str = ""
    scene: str = ""           # OBS scene name or Pearl layout name to apply
    lower_third: str = ""     # graphics preset name (optional)
    transition: str = ""      # transition type hint (optional)


@dataclass
class RunOfShow:
    """Ordered list of cues with tracked position."""

    show_id: str
    show_name: str
    cues: list[Cue]
    template: str = ""
    active_cue_index: int = 0
    started_at: str | None = None
    cue_history: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def active_cue(self) -> Cue | None:
        if not self.cues:
            return None
        idx = min(self.active_cue_index, len(self.cues) - 1)
        return self.cues[idx]

    def next_cue(self) -> Cue | None:
        nxt = self.active_cue_index + 1
        if nxt >= len(self.cues):
            return None
        return self.cues[nxt]

    # ------------------------------------------------------------------
    # Mutation helpers (always call _save() after)
    # ------------------------------------------------------------------

    def advance(self) -> Cue | None:
        """
        Move forward one cue.

        Returns the new active cue, or ``None`` if already at the last cue.
        Writes an action log entry on every successful advance.
        """
        if self.active_cue_index + 1 >= len(self.cues):
            return None

        current = self.active_cue()
        self.cue_history.append({
            "cue_id": current.id if current else "",
            "advanced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        self.active_cue_index += 1
        new_cue = self.cues[self.active_cue_index]
        write_action(
            "operator",
            "runofshow_advance",
            {
                "from_cue": current.id if current else "",
                "to_cue": new_cue.id,
                "show_id": self.show_id,
            },
        )
        return new_cue

    def jump(self, cue_id: str) -> Cue | None:
        """
        Jump directly to a cue by id.

        Returns the target cue or ``None`` if the id is not found.
        Writes an action log entry on every successful jump.
        """
        for i, cue in enumerate(self.cues):
            if cue.id == cue_id:
                current = self.active_cue()
                self.cue_history.append({
                    "cue_id": current.id if current else "",
                    "advanced_at": datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                })
                self.active_cue_index = i
                write_action(
                    "operator",
                    "runofshow_jump",
                    {"to_cue": cue_id, "show_id": self.show_id},
                )
                return cue
        return None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def as_dict(self) -> dict:
        d = asdict(self)
        d["active_cue"] = asdict(self.active_cue()) if self.active_cue() else None
        d["next_cue"] = asdict(self.next_cue()) if self.next_cue() else None
        d["progress"] = f"{self.active_cue_index + 1}/{len(self.cues)}"
        d["at_end"] = (self.active_cue_index + 1) >= len(self.cues)
        return d


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _save(show: RunOfShow) -> None:
    RUNOFSHOW_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNOFSHOW_STATE_FILE.write_text(
        json.dumps(show.as_dict()), encoding="utf-8"
    )


def _load_from_dict(d: dict) -> RunOfShow:
    cues = [Cue(**c) for c in d.get("cues", [])]
    return RunOfShow(
        show_id=d.get("show_id", ""),
        show_name=d.get("show_name", ""),
        cues=cues,
        template=d.get("template", ""),
        active_cue_index=d.get("active_cue_index", 0),
        started_at=d.get("started_at"),
        cue_history=d.get("cue_history", []),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_EMPTY_STATE: dict = {
    "show_id": None,
    "show_name": None,
    "cues": [],
    "active_cue_index": 0,
    "active_cue": None,
    "next_cue": None,
    "cue_history": [],
    "progress": "0/0",
    "at_end": False,
}


def get_state() -> dict:
    """Return the current run-of-show state dict.  Returns empty state if none loaded."""
    if not RUNOFSHOW_STATE_FILE.exists():
        return dict(_EMPTY_STATE)
    try:
        return json.loads(RUNOFSHOW_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return dict(_EMPTY_STATE)


def load_template(template_name: str) -> dict:
    """
    Load a named template, reset position to cue 0, persist, return state dict.

    Raises ``FileNotFoundError`` if the template does not exist.
    """
    template_file = TEMPLATES_DIR / f"{template_name}.json"
    if not template_file.exists():
        raise FileNotFoundError(f"Template not found: {template_name}")

    raw = json.loads(template_file.read_text(encoding="utf-8"))
    cues = [Cue(**c) for c in raw.get("cues", [])]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    show = RunOfShow(
        show_id=f"{template_name}_{now[:10].replace('-', '')}",
        show_name=raw.get("name", template_name),
        cues=cues,
        template=template_name,
        active_cue_index=0,
        started_at=now,
    )
    _save(show)
    write_action("operator", "runofshow_load", {"template": template_name})
    return show.as_dict()


def advance() -> dict:
    """Advance one cue forward.  Persists and returns updated state dict."""
    state = get_state()
    if not state.get("show_id"):
        return state
    show = _load_from_dict(state)
    show.advance()
    _save(show)
    return show.as_dict()


def jump_to(cue_id: str) -> dict:
    """Jump to a specific cue by id.  Persists and returns updated state dict."""
    state = get_state()
    if not state.get("show_id"):
        return state
    show = _load_from_dict(state)
    show.jump(cue_id)
    _save(show)
    return show.as_dict()


def list_templates() -> list[dict]:
    """
    Return metadata for every template in ``TEMPLATES_DIR``.

    Each entry: ``{"id": str, "name": str, "description": str, "cue_count": int}``
    """
    if not TEMPLATES_DIR.exists():
        return []
    result = []
    for f in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "id": f.stem,
                "name": raw.get("name", f.stem),
                "description": raw.get("description", ""),
                "cue_count": len(raw.get("cues", [])),
            })
        except Exception:  # noqa: BLE001
            pass
    return result


def get_template(template_name: str) -> dict:
    """Return full template data including cues.  Raises FileNotFoundError if missing."""
    template_file = TEMPLATES_DIR / f"{template_name}.json"
    if not template_file.exists():
        raise FileNotFoundError(f"Template not found: {template_name}")
    return json.loads(template_file.read_text(encoding="utf-8"))
