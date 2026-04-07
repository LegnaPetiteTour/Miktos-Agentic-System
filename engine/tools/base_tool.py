"""
Base tool interface for the Miktos engine.

All domain tools must implement this interface.
This ensures the execution layer can call any tool uniformly.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """All Miktos tools inherit from this."""

    name: str
    description: str

    @abstractmethod
    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool and return a structured result."""
        raise NotImplementedError

    def safe_run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Wraps run() with error handling. Always returns a result dict."""
        try:
            result = self.run(input)
            return {"success": True, "result": result, "error": None}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
