"""
engine/adapters/registry.py — Adapter registry (ADR-009).

Returns the correct platform adapter based on the ``HARDWARE_ADAPTER``
environment variable (or its alias ``HARDWARE_PLATFORM``).

Supported values (case-insensitive):
    ``epiphan`` / ``pearl``  →  PearlAdapter
    ``obs``  (default)       →  OBSAdapter

Adding a new platform:
    1. Create ``domains/{platform}/adapter.py`` implementing ``DeviceAdapter``
    2. Add a branch in ``get_adapter()``
    3. Register tests in ``tests/test_{platform}_adapter.py``
"""

from __future__ import annotations

import os


def get_adapter():
    """
    Return an instantiated adapter for the configured hardware platform.

    The adapter is freshly instantiated on every call — callers that need
    a persistent connection should hold the returned object themselves.
    """
    platform = (
        os.getenv("HARDWARE_ADAPTER", "")
        or os.getenv("HARDWARE_PLATFORM", "obs")
    ).lower()

    if platform in ("epiphan", "pearl"):
        from engine.adapters.pearl_adapter import PearlAdapter  # noqa: PLC0415

        return PearlAdapter()

    # Default → OBS Studio
    from engine.adapters.obs_adapter import OBSAdapter  # noqa: PLC0415

    return OBSAdapter()
