# Phase 8 Spec — Epiphan Pearl Domain Adapter

**Branch:** `phase-8/epiphan-pearl`
**Vision:** Miktos as the operations hub above the stack — not replacing Pearl,
but extracting its full power through a unified workflow.

This spec governs two sub-phases with a gate between them.

---

## Context: What Phase 8 Proves

Phase 5 proved the post-stream pipeline works for one hardware backend (OBS).
Phase 8 proves the engine is genuinely multi-domain: a second hardware backend
(Epiphan Pearl) plugs into the same engine, uses the same post-stream workers,
and the engine requires zero changes.

Phase 8b then proves the second dimension of the vision: Miktos can issue
commands to hardware during a live stream, not just react after it ends.

---

## Pearl API Surface (confirmed from live device at 192.168.2.45)

**Device confirmed:** Pearl-2, firmware 4.24.3
**Swagger UI:** `http://192.168.2.45/swagger/` (REST API v2.0, OAS 3.0)

Pearl-2 exposes two API layers:

### Modern REST API (v2.0) — preferred
- Base URL: `http://{pearl_ip}/api/`
- Auth: HTTP Basic Auth (`admin:{password}`)
- JSON responses
- Swagger spec: `http://{pearl_ip}/api/v2.0/openapi.yml`

**Confirmed working endpoints (verified on live device):**

```
GET  /api/channels
     → Returns list of channels with id and name
     → Confirmed response:
       {"status":"ok","result":[
         {"id":"1","name":"Master-EN"},
         {"id":"4","name":"Master-FR"},
         {"id":"8","name":"OPH Standard EN"},
         {"id":"9","name":"OPH Standard FR"},
         {"id":"13","name":"A DAY FR"},
         {"id":"14","name":"ADay EN"},
         {"id":"19","name":"BACKUP EN"},
         {"id":"20","name":"BACKUP FR"},
         ...
       ]}

GET  /api/system/firmware
     → Returns firmware version details

GET  /api/system/ident
     → Returns device name, location, description

GET  /api/recorders
     → Returns list of recorders with properties

GET  /api/recorders/status
     → Returns status information for all recorders

GET  /api/recorders/{rid}/archive/files
     → Lists recording files for a recorder

GET  /api/recorders/{rid}/archive/files/{fid}
     → Downloads the specified recording file

PUT  /api/channels/{cid}/layouts/active
     → Activates the specified layout in a channel (layout switching)

POST /api/channels/{cid}/publishers/control/start
     → Start all publishers (streaming) for a channel

POST /api/channels/{cid}/publishers/control/stop
     → Stop all publishers (streaming) for a channel

GET  /api/channels/{cid}/publishers/status
     → Get streaming status for a channel

GET  /api/inputs
     → Returns all available video/audio inputs (NDI sources, HDMI, etc.)
```

**Critical note on channel IDs:**
Pearl-2 assigns channel IDs when channels are created — they are NOT sequential.
The `pearl_config.yaml` must specify actual channel IDs, not assumed numbers.
From the live device: EN channel = `"1"` (Master-EN), FR channel = `"4"` (Master-FR).

### Legacy HTTP API — used for configuration reads
- Base URL: `http://{pearl_ip}/admin/`
- Pattern: `/admin/channel{N}/get_params.cgi?key`
- Confirmed working: returns `product_name`, `firmware_version`, `rec_enabled`,
  `publish_type`, `framesize`, `title`

**Auth pattern for all REST calls:**
```python
import os
import requests
from requests.auth import HTTPBasicAuth

auth = HTTPBasicAuth('admin', os.getenv('PEARL_PASSWORD', ''))
response = requests.get(
    f'http://{os.getenv("PEARL_HOST")}/api/channels',
    auth=auth,
    timeout=10
)
```

**Environment variables:**
```
PEARL_HOST      # Pearl-2 IP address (e.g. 192.168.2.45)
PEARL_PORT      # default: 80
PEARL_PASSWORD  # admin password (empty string if not set)
```

**Model support:** Pearl-2, Mini, Nano, Nexus all use the same REST API surface.
Handled via a `pearl_model` config field that sets capability constraints
(Nano: single channel only; others: multi-channel).

---

## Phase 8a — Pearl Monitor + Post-Stream Automation

### Objective

Same pattern as the OBS domain. New domain, engine unchanged. All existing
post-stream workers reused. The one new worker (`RecordingDownloadWorker`)
pulls the recording from Pearl via REST API to a local path, after which
the pipeline continues identically to the OBS workflow.

### New File Structure

```
domains/epiphan/
  __init__.py
  config/
    thresholds.yaml           ← Pearl health thresholds
    pearl_config.example.yaml ← connection + channel config reference
  tools/
    __init__.py
    pearl_client.py           ← REST + legacy HTTP client, auth, requests
    pearl_monitor.py          ← EpiphanMonitorTool (health → alert items)

domains/streamlab_post/workers/
  recording_download_worker.py  ← HTTP pull from Pearl + local path output

main_epiphan.py               ← entry point (same pattern as main_streamlab.py)
tests/test_phase_8a_epiphan.py  ← ~8 tests
```

---

### `domains/epiphan/tools/pearl_client.py`

```python
class PearlClient:
    """
    Thin wrapper over Pearl REST API (v2.0) and Legacy HTTP API.
    Auth via HTTP Basic using env vars PEARL_HOST, PEARL_PASSWORD.
    All methods raise on connection failure so the monitor can handle it.

    Base URL: http://{PEARL_HOST}:{PEARL_PORT}/api/
    Swagger:  http://{PEARL_HOST}/swagger/
    """

    def __init__(self) -> None:
        self._host = os.getenv('PEARL_HOST', '192.168.255.250')
        self._port = int(os.getenv('PEARL_PORT', '80'))
        self._password = os.getenv('PEARL_PASSWORD', '')
        self._base = f'http://{self._host}:{self._port}'
        self._auth = HTTPBasicAuth('admin', self._password)

    def get_firmware_info(self) -> dict:
        """GET /api/system/firmware — returns firmware version details."""

    def get_device_identity(self) -> dict:
        """GET /api/system/ident — returns device name, location, description."""

    def get_channels(self) -> list[dict]:
        """GET /api/channels — returns list of {id, name} for all channels."""

    def get_channel_publisher_status(self, channel_id: str) -> dict:
        """GET /api/channels/{cid}/publishers/status — streaming state."""

    def get_recorders(self) -> list[dict]:
        """GET /api/recorders — returns list of recorders with properties."""

    def get_recorder_status(self, recorder_id: str) -> dict:
        """GET /api/recorders/{rid}/status — recording state."""

    def get_recorder_files(self, recorder_id: str) -> list[dict]:
        """GET /api/recorders/{rid}/archive/files — list of recording files."""

    def download_recording(self, recorder_id: str, file_id: str,
                           dest_path: str) -> str:
        """
        GET /api/recorders/{rid}/archive/files/{fid}
        Downloads recording file via chunked HTTP GET to dest_path.
        Returns local path of the downloaded file.
        """

    def switch_layout(self, channel_id: str, layout_id: str) -> None:
        """PUT /api/channels/{cid}/layouts/active — activate a layout."""

    def start_streaming(self, channel_id: str) -> None:
        """POST /api/channels/{cid}/publishers/control/start"""

    def stop_streaming(self, channel_id: str) -> None:
        """POST /api/channels/{cid}/publishers/control/stop"""

    def get_legacy_param(self, channel_n: int, key: str) -> str:
        """
        Legacy API: GET /admin/channel{N}/get_params.cgi?{key}
        Used for fallback status reads.
        Returns the raw value string.
        """
```

---

### `domains/epiphan/tools/pearl_monitor.py` — EpiphanMonitorTool

Same pattern as `OBSMonitorTool`. Returns `{"files": [alert_items], "count": N}`
with the same alert item shape. The engine's planner sees no difference.

**Health checks (polls `PearlClient` on each tick):**

| Alert type | API source | Severity |
|---|---|---|
| `recording_stopped` | recorder status = not recording | hard fail |
| `streaming_stopped` | channel publisher status = stopped | hard fail |
| `disk_low` | recorder storage < threshold | warning |

Note: Pearl-2 does not expose CPU/memory via the REST API in the same way
OBS WebSocket does. Health monitoring focuses on recording and streaming state.
If additional system stats are needed, the legacy API `get_params.cgi` can
be used for available metrics.

**Edge-triggered handoff:** Same pattern as `main_streamlab.py`.
The monitor watches for `recording_stopped` and publishes the
`recording_stopped` event to the bus when the recording transitions
from active → stopped.

**`thresholds.yaml`:**
```yaml
poll_interval_seconds: 5
stream:
  disk_space_warning_gb: 10
```

---

### `domains/streamlab_post/workers/recording_download_worker.py`

New **pre-Stage 1 worker** — downloads the Pearl recording to a local path
so the rest of the pipeline can proceed identically.

```python
class RecordingDownloadWorker:
    name = "recording_download"

    def run(self, payload: dict) -> dict:
        """
        Pull the most recently completed recording from Pearl.

        Payload keys:
          pearl_host       str   Pearl IP address
          pearl_recorder_id str  which recorder to pull from (from config)
          download_dir     str   local directory to save to
          dry_run          bool

        Returns:
          {"success": True, "file_path": str, "file_size_bytes": int}
          {"success": False, "error": str}
        """
```

**How it finds the file:** After `recording_stopped` fires, the worker calls
`PearlClient.get_recorder_files(recorder_id)`, finds the most recently
completed file (not currently recording), and downloads it via chunked
HTTP GET to `download_dir`. Returns the local file path.

**Coordinator integration:** When `session_config.yaml` has `hardware: epiphan`,
the coordinator runs `RecordingDownloadWorker` before Stage 1 and passes
the downloaded local path as `file_path` to all subsequent workers.
`backup_verify`, `audio_extract`, and `file_rename` see a local path and
require zero changes.

---

### `pearl_config.example.yaml`

```yaml
# Pearl connection
pearl:
  host: ""                     # Pearl-2 IP address (e.g. 192.168.2.45)
  port: 80
  model: "pearl-2"             # pearl-2 | pearl-mini | pearl-nano | pearl-nexus
  channel_en: ""               # Pearl channel ID for EN stream (e.g. "1")
  channel_fr: ""               # Pearl channel ID for FR stream (e.g. "4")
  recorder_id: ""              # Pearl recorder ID to pull recording from
  download_dir: "~/Downloads/pearl-recordings"

# NOTE: Channel IDs are NOT sequential — check your Pearl's channel list:
# curl -u admin: 'http://{pearl_ip}/api/channels'
# On the reference device:
#   "1"  = Master-EN
#   "4"  = Master-FR
#   "8"  = OPH Standard EN
#   "9"  = OPH Standard FR

# Session identity (same fields as OBS workflow)
event_name: ""
stream_date: ""

# YouTube (same as OBS workflow — workers unchanged)
youtube:
  en:
    channel_id: ""
    video_id: ""
    playlist_id: ""
  fr:
    channel_id: ""
    video_id: ""
    playlist_id: ""
```

---

### `main_epiphan.py` — entry point

Same outer loop pattern as `main_streamlab.py`:
- Loads `pearl_config.yaml` + thresholds
- Instantiates `EpiphanMonitorTool` with `PearlClient`
- Builds and invokes the engine graph on each tick
- With `--handoff`: publishes `recording_stopped` on active→stopped transition
- With `--recorder`: specifies which Pearl recorder ID to pull from

```bash
python main_epiphan.py --handoff --recorder 1
```

---

### `session_config.yaml` extension

Add a `hardware` discriminator field:
```yaml
hardware: "epiphan"   # or "obs" (default)
```

`run_session.py` reads this field to start `main_epiphan.py` instead of
`main_streamlab.py`. `PostStreamCoordinator` reads it to insert
`RecordingDownloadWorker` before Stage 1.

All other coordinator behavior, workers, and post-stream pipeline unchanged.

---

### `prepare_session.py` extension

Add hardware selector at the start of the prompt flow:
```
Hardware backend [obs/epiphan] (obs): epiphan
```

When `epiphan` selected, additionally prompt:
```
Pearl EN channel ID [{current}]: 
Pearl FR channel ID [{current}]: 
Pearl recorder ID [{current}]: 
```

---

### Phase 8a Tests (`tests/test_phase_8a_epiphan.py`)

~8 tests, all mocked (no live Pearl required):

1. `test_pearl_client_get_channels` — mock GET /api/channels → returns list
2. `test_pearl_client_get_recorder_files` — mock recorder file list response
3. `test_pearl_client_download_recording` — mock chunked download → file written to tmp_path
4. `test_epiphan_monitor_healthy_stream` — all recorders active → zero alert items
5. `test_epiphan_monitor_recording_stopped` — recorder inactive → alert item
6. `test_recording_download_worker_success` — mock PearlClient → local file path returned
7. `test_recording_download_worker_dry_run` — dry_run=True → returns mock success, no download
8. `test_recording_download_worker_never_raises` — bad host → returns failure dict, no exception

### Phase 8a Seal Criteria

- All tests pass, prior 94 tests unmodified, 1 permanent skip
- `python main_epiphan.py --dry-run` exits cleanly
- `python scripts/prepare_session.py` with `hardware: epiphan` updates config correctly
- Live test: `curl -u admin: 'http://192.168.2.45/api/recorders'` returns recorder list
- Live test: `PearlClient.get_channels()` returns the 10 known channels
- Engine unchanged: `grep -r 'from engine.graph' domains/epiphan/` returns nothing

**Gate to Phase 8b:** 3 clean Pearl sessions using the Phase 8a workflow.

---

## Phase 8b — Live Layout Control

### Objective

Miktos issues layout switch commands to Pearl during a live stream.
The operator uses `pearl_control.py` to control which Zoom participant feed
goes to which YouTube channel in real time. This is Stage 2 in the vision:
Miktos moves from observer to coordinator.

### What Layout Switching Means for This Workflow

Your Zoom session feeds Pearl via NDI. Pearl has multiple layouts per channel,
each configured to show a different combination of Zoom participants:
- `speaker-en` — active speaker feed, EN channel
- `interpreter-fr` — French interpreter feed, FR channel
- `sign-language` — sign language interpreter
- `presentation` — screen share / presentation source
- `split-en-fr` — side-by-side (EN + FR)

These layouts are pre-configured in Pearl's Admin UI. Miktos switches
between pre-existing layouts only — it does not create them.

### API endpoint for layout switching (confirmed from Swagger)

```
PUT /api/channels/{cid}/layouts/active
```

Body: `{"id": "{layout_id}"}` — the layout ID integer from Pearl's layout list.

### New File

```
scripts/pearl_control.py
```

### CLI Interface

```bash
# List available layouts for a channel
python scripts/pearl_control.py layouts --channel 1

# Switch to a layout by name (fuzzy-matched against Pearl's layout names)
python scripts/pearl_control.py switch --channel 1 --layout speaker
python scripts/pearl_control.py switch --channel 4 --layout interpreter-fr

# Show current live layout on each configured channel
python scripts/pearl_control.py status
```

Note: use the actual Pearl channel ID (e.g. `1` for Master-EN, `4` for Master-FR).

### Console output

```
  Pearl Layout Control
  ──────────────────────────────────────────
  Channel 1 (Master-EN): speaker-fr  → interpreter-fr  ✅
  Channel 4 (Master-FR): (unchanged)
```

### Phase 8b Tests (`tests/test_phase_8b_layout_control.py`)

~4 tests:

1. `test_layout_list_parsed` — mock REST response → list of layout names returned
2. `test_layout_fuzzy_match` — "speaker" matches "speaker-fr" layout name
3. `test_layout_switch_calls_api` — switch command calls PUT /api/channels/{cid}/layouts/active
4. `test_status_shows_current_layout` — after switch, status shows new layout name

### Phase 8b Seal Criteria

- Tests pass, prior tests unmodified
- `python scripts/pearl_control.py layouts --channel 1` returns layout names from live Pearl-2
- `python scripts/pearl_control.py switch --channel 1 --layout speaker` switches active layout
  (verified on Pearl-2 touch screen — layout indicator changes)
- No disruption to recording or streaming during layout switch

---

## What Phase 9 Becomes

With Phase 8a and 8b complete, the system has:
- OBS domain: post-stream automation (reactive)
- Pearl domain: post-stream automation + live layout control (active)
- Two proven patterns: reactive and active

Phase 9 is the first version of the production cockpit — the `rich` terminal
interface from Phase 7b extended into a unified panel that:
- Shows active hardware (OBS or Pearl)
- Displays real-time health for the active domain
- Shows current layout per channel (Pearl)
- Allows layout switching via keypress
- Shows post-stream stage progress after stream ends

The web GUI (Stage 3 of the vision) comes after Phase 9 is validated in production.

---

## Architecture Invariants

- Engine unchanged across both sub-phases
- No imports from `engine/graph/` in any new domain file
- All 94 prior tests pass unmodified
- `PearlClient` never stores credentials — reads from env vars only
- `RecordingDownloadWorker` never raises exceptions (same contract as all workers)
- Layout switching is additive — no changes to `PostStreamCoordinator` or
  any existing worker

---

## Pre-Implementation Gate: MET ✅

Confirmed on live Pearl-2 (192.168.2.45, firmware 4.24.3):

```
GET /api/channels → 200 OK, 10 channels confirmed
GET /admin/channel1/get_params.cgi?firmware_version → 4.24.3
GET /admin/channel1/get_params.cgi?product_name → Pearl-2
Swagger UI accessible at http://192.168.2.45/swagger/
REST API v2.0 confirmed (OAS 3.0)
```

Correct API base path: `/api/` (not `/api/1.0/`)
Recordings API: `/api/recorders/{rid}/archive/files` (not `/api/channels/{cid}/recordings`)
Layout switch: `PUT /api/channels/{cid}/layouts/active`

**VS Code can begin Phase 8a implementation.**

---

*Spec written: 2026-04-15. API paths corrected from live device responses: 2026-04-16.*
