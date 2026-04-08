"""
Filesystem tools — backwards-compatible re-export shim.

FileScannerTool and FileHashTool now live in engine/tools/shared_tools.py
because they are domain-agnostic and shared across all domains.

This module re-exports them so that existing imports from
domains.file_analyzer.tools.fs_tools continue to work without change.
"""

from engine.tools.shared_tools import FileScannerTool, FileHashTool

__all__ = ["FileScannerTool", "FileHashTool"]
