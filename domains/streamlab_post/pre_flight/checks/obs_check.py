"""
obs_check — Pre-flight Check 1 (hard failure).

Attempts to connect to OBS WebSocket. If the connection is refused
or times out the stream cannot be monitored and the preflight fails.

Environment variables read (same as obs_client.py):
  OBS_HOST      default: localhost
  OBS_PORT      default: 4455
  OBS_PASSWORD  required for authenticated WS servers
"""

import os


def run(dry_run: bool = False) -> dict:
    """
    Ping. OBS WebSocket.

    Returns:
        {"name": "obs_connection", "status": "ok"|"fail", "message": str}
    """
    if dry_run:
        return {
            "name": "obs_connection",
            "status": "ok",
            "message": "OBS WebSocket — reachable (dry-run)",
        }

    host = os.getenv("OBS_HOST", "localhost")
    port = int(os.getenv("OBS_PORT", "4455"))
    password = os.getenv("OBS_PASSWORD", "")

    try:
        import obsws_python as obs  # type: ignore[import]

        client = obs.ReqClient(host=host, port=port, password=password, timeout=5)
        client.disconnect()
        return {
            "name": "obs_connection",
            "status": "ok",
            "message": f"OBS WebSocket — reachable at {host}:{port}",
        }
    except Exception as exc:
        return {
            "name": "obs_connection",
            "status": "fail",
            "message": f"OBS WebSocket — connection failed ({host}:{port}): {exc}",
        }
