"""
Global configuration for the Miktos engine.
"""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
STATE_DIR = DATA_DIR / "state"
LOGS_DIR = DATA_DIR / "logs"
REVIEW_QUEUE_DIR = DATA_DIR / "review_queue"

# Engine defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_REPLANS = 2
DEFAULT_MODE = "dry_run"  # 'dry_run' | 'live'

# LLM (optional, narrow use only)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL = "claude-sonnet-4-20250514"
