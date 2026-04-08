"""
OBS WebSocket client wrapper for the StreamLab domain.

Thin connection manager. Credentials are read exclusively from environment
variables loaded via python-dotenv — never hardcoded.

Environment variables:
  OBS_HOST      hostname of the OBS WebSocket server (default: localhost)
  OBS_PORT      port number (default: 4455)
  OBS_PASSWORD  WebSocket server password (required)
"""

import os

import obsws_python as obs  # type: ignore[import]

from engine.tools.base_tool import BaseTool


class OBSClientTool(BaseTool):
    """Manages a connection to the OBS WebSocket server."""

    name = "obs_client"
    description = "Manages connection to OBS WebSocket server."

    def __init__(self) -> None:
        self._client: obs.ReqClient | None = None

    def connect(self) -> obs.ReqClient:
        """Open a new connection using environment variables."""
        host = os.getenv("OBS_HOST", "localhost")
        port = int(os.getenv("OBS_PORT", "4455"))
        password = os.getenv("OBS_PASSWORD", "")

        self._client = obs.ReqClient(
            host=host,
            port=port,
            password=password,
            timeout=5,
        )
        return self._client

    def disconnect(self) -> None:
        """Close the connection gracefully."""
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

    def run(self, input: dict) -> dict:
        """BaseTool implementation — returns current connection status."""
        return {"connected": self._client is not None}
