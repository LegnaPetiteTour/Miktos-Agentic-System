"""
pearl_client.py — Thin wrapper over the Epiphan Pearl REST API (v2.0)
and the legacy HTTP admin API.

Base URL: http://{PEARL_HOST}:{PEARL_PORT}/api/
Auth:     HTTP Basic Auth — always 'admin', password from PEARL_PASSWORD env var.
Swagger:  http://{PEARL_HOST}/swagger/

Credentials are read from environment variables on every instantiation.
This module never stores credentials beyond the lifetime of the object.
"""

import os
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

_CHUNK_SIZE = 8192


class PearlClient:
    """
    Thin wrapper over Pearl REST API (v2.0) and Legacy HTTP API.
    Auth via HTTP Basic using env vars PEARL_HOST, PEARL_PASSWORD.
    All methods raise requests.RequestException on connection failure.
    """

    def __init__(self) -> None:
        self._host = os.getenv("PEARL_HOST", "192.168.255.250")
        self._port = int(os.getenv("PEARL_PORT", "80"))
        self._password = os.getenv("PEARL_PASSWORD", "")
        self._base = f"http://{self._host}:{self._port}"
        self._auth = HTTPBasicAuth("admin", self._password)

    # ------------------------------------------------------------------
    # System info
    # ------------------------------------------------------------------

    def get_firmware_info(self) -> dict:
        """GET /api/system/firmware → firmware version details."""
        resp = requests.get(
            f"{self._base}/api/system/firmware",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def get_device_identity(self) -> dict:
        """GET /api/system/ident → device name, location, description."""
        resp = requests.get(
            f"{self._base}/api/system/ident",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    def get_channels(self) -> list[dict]:
        """GET /api/channels → list of {id, name} for all channels."""
        resp = requests.get(
            f"{self._base}/api/channels",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])

    def get_channel_publisher_status(self, channel_id: str) -> dict:
        """GET /api/channels/{cid}/publishers/status → streaming state."""
        resp = requests.get(
            f"{self._base}/api/channels/{channel_id}/publishers/status",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def start_streaming(self, channel_id: str) -> None:
        """POST /api/channels/{cid}/publishers/control/start"""
        resp = requests.post(
            f"{self._base}/api/channels/{channel_id}"
            "/publishers/control/start",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()

    def stop_streaming(self, channel_id: str) -> None:
        """POST /api/channels/{cid}/publishers/control/stop"""
        resp = requests.post(
            f"{self._base}/api/channels/{channel_id}"
            "/publishers/control/stop",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()

    def get_layouts(self, channel_id: str) -> list[dict]:
        """GET /api/channels/{cid}/layouts → list of {id, name} for the channel."""
        resp = requests.get(
            f"{self._base}/api/channels/{channel_id}/layouts",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])

    def get_active_layout(self, channel_id: str) -> dict:
        """GET /api/channels/{cid}/layouts/active → currently active layout {id, name}."""
        resp = requests.get(
            f"{self._base}/api/channels/{channel_id}/layouts/active",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {})

    def switch_layout(self, channel_id: str, layout_id: str) -> None:
        """PUT /api/channels/{cid}/layouts/active → activate a layout."""
        resp = requests.put(
            f"{self._base}/api/channels/{channel_id}/layouts/active",
            auth=self._auth,
            json={"id": layout_id},
            timeout=10,
        )
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Recorders
    # ------------------------------------------------------------------

    def get_recorders(self) -> list[dict]:
        """GET /api/recorders → list of recorders with id, name, multisource."""
        resp = requests.get(
            f"{self._base}/api/recorders",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])

    def get_recorder_status(self, recorder_id: str) -> dict:
        """GET /api/recorders/{rid}/status → recording state."""
        resp = requests.get(
            f"{self._base}/api/recorders/{recorder_id}/status",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def get_recorder_files(self, recorder_id: str) -> list[dict]:
        """GET /api/recorders/{rid}/archive/files → list of recording files."""
        resp = requests.get(
            f"{self._base}/api/recorders/{recorder_id}/archive/files",
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])

    def download_recording(
        self, recorder_id: str, file_id: str, dest_path: str
    ) -> str:
        """
        GET /api/recorders/{rid}/archive/files/{fid}

        Downloads the recording file via chunked HTTP GET into dest_path.
        Uses stream=True + iter_content(chunk_size=8192) for large files.
        Returns dest_path (the local path written to).
        """
        url = (
            f"{self._base}/api/recorders/{recorder_id}"
            f"/archive/files/{file_id}"
        )
        with requests.get(
            url, auth=self._auth, stream=True, timeout=30
        ) as resp:
            resp.raise_for_status()
            dest = Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    if chunk:
                        fh.write(chunk)
        return str(dest_path)

    # ------------------------------------------------------------------
    # Legacy HTTP admin API
    # ------------------------------------------------------------------

    def get_legacy_param(self, channel_n: int, key: str) -> str:
        """
        Legacy API fallback.
        GET /admin/channel{N}/get_params.cgi?{key}
        Returns the raw value string (e.g. 'Pearl-2', '4.24.3').
        """
        resp = requests.get(
            f"{self._base}/admin/channel{channel_n}/get_params.cgi",
            params={key: ""},
            auth=self._auth,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.text.strip()
