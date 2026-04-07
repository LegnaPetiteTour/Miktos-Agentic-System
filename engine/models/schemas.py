"""
Shared Pydantic schemas for the Miktos engine.

These are domain-agnostic data structures used across all domains.
"""

from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum


class DecisionOutcome(str, Enum):
    CONTINUE = "continue"
    RETRY = "retry"
    REPLAN = "replan"
    ESCALATE = "escalate"
    STOP = "stop"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    REVIEW = "review"


class Task(BaseModel):
    task_id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 1
    retries: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: dict = {}


class ReviewResult(BaseModel):
    task_id: str
    passed: bool
    confidence: float  # 0.0 to 1.0
    issues: list[str] = []
    recommendation: DecisionOutcome
    notes: str = ""


class ActionRecord(BaseModel):
    action_id: str
    task_id: str
    action_type: str
    target: str
    proposed: dict
    applied: bool = False
    dry_run: bool = True
    result: Optional[str] = None
