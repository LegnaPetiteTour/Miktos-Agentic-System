"""
Core state schema for the Miktos engine.

This is the spine of the system.
Every node reads from and writes to this state.

State must always answer:
  - Where is the system right now?
  - What has already succeeded?
  - What has failed?
  - What is pending?
  - What changed since last loop?
  - What are the bounds?
"""

from typing import Any, Optional
from typing_extensions import TypedDict


class RunState(TypedDict):
    # Identity
    run_id: str
    domain: str  # e.g. 'file_analyzer', 'kosmos', 'streamlab'

    # Goal
    goal: str
    mode: str  # 'dry_run' | 'live'

    # Progress tracking
    current_step: str
    pending_tasks: list[dict]
    completed_tasks: list[dict]
    failed_tasks: list[dict]
    skipped_tasks: list[dict]   # low-confidence, not attempted
    exhausted_tasks: list[dict]  # attempted max_retries times, unresolved

    # Review queue (items requiring human review)
    review_queue: list[dict]

    # Outputs
    proposed_actions: list[dict]
    applied_actions: list[dict]
    artifacts: list[dict]

    # Errors and logs
    errors: list[dict]
    logs: list[str]

    # Loop control
    retries: int
    max_retries: int
    replans: int
    max_replans: int
    done: bool
    # 'success' | 'retry' | 'replan' | 'escalate' | 'stop'
    exit_reason: Optional[str]

    # Agent identity (Phase 4b)
    # agent_id defaults to domain for backward compatibility.
    # inbox_messages is populated by message_trigger_node when enable_messaging=True.
    agent_id: str
    inbox_messages: list[dict]

    # Domain-specific context (each domain extends this)
    context: dict[str, Any]
