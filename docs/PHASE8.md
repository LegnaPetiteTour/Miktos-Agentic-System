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
- Swagger spec at: `http://{pearl_ip}/api/v2.0/openapi.yml`

### Confirmed working endpoints (verified on live device)

```
GET  /api/channels
     → {"status":"ok","result":[{"id":"1","name":"Master-EN"}, ...]}

GET  /api/recorders
     → {"status":"ok","result":[
         {"id":"1",  "name":"Master-EN",             "multisource":false},
         {"id":"4",  "name":"Master-FR",             "multisource":false},
         {"id":"8",  "name":"OPH Standard EN",       "multisource":false},
         {"id":"9",  "name":"OPH Standard FR",       "multisource":false},
         {"id":"13", "name":"A DAY FR",              "multisource":false},
         {"id":"14", "name":"ADay EN",               "multisource":false},
         {"id":"17", "name":"OPL Book Awards Oct 11","multisource":false},
         {"id":"18", "name":"TEST - JJ",             "multisource":false},
         {"id":"19", "name":"BACKUP EN",             "multisource":false},
         {"id":"20", "name":"BACKUP FR",             "multisource":false},
         {"id":"m1", "name":"Recorder 1",            "multisource":true}
       ]}

GET  /api/recorders/status
     → Returns status information for all recorders

GET  /api/recorders/{rid}/archive/files
     → Lists recording files for a recorder

GET  /api/recorders/{rid}/archive/files/{fid}
     → Downloads the specified recording file

GET  /api/system/firmware
     → Returns firmware version details

GET  /api/system/ident
     → Returns device name, location, description

GET  /api/channels/{cid}/publishers/status
     → Get streaming status for a channel

POST /api/channels/{cid}/publishers/control/start
     → Start streaming on a channel

POST /api/channels/{cid}/publishers/control/stop
     → Stop streaming on a channel

PUT  /api/channels/{cid}/layouts/active
     → Activate a layout in the channel (layout switching)

GET  /api/inputs
     → Returns all available video/audio inputs (NDI sources, HDMI, etc.)
```

### Key architectural insight: channels and recorders share IDs

Recorder IDs mirror channel IDs exactly on this device:
- Recorder `"1"` = Master-EN (same as Channel `"1"`)
- Recorder `"4"` = Master-FR (same as Channel `"4"`)

**`channel_en` and `recorder_en` are the same value.** No separate lookup needed.

There is also one multitrack recorder: `{"id":"m1","name":"Recorder 1","multisource":true}`.
This captures multiple sources simultaneously. Not used in Phase 8a but noted for future.

### Critical note on channel IDs

Channel IDs are NOT sequential — they are assigned at creation time.
`pearl_config.yaml` must specify actual IDs. From the live device:
- `"1"` = Master-EN  →  the default EN streaming channel
- `"4"` = Master-FR  →  the default FR streaming channel

### Legacy HTTP API — used for fallback reads

- Base URL: `http://{pearl_ip}/admin/`
- Pattern: `/admin/channel{N}/get_params.cgi?key`
- Confirmed working: `product_name`, `firmware_version`, `rec_enabled`,
  `publish_type`, `framesize`, `title`

### Auth pattern for all REST calls

```python
import os
import requests
from requests.auth import HTTPBasicAuth

auth = HTTPBasicAuth('admin', os.getenv('PEARL_PASSWORD', ''))
resp = requests.get(
    f'http://{os.getenv("PEARL_HOST")}/api/channels',
    auth=auth,
    timeout=10
)
data = resp.json()   # {"status": "ok", "result": [...]}
```

### Environment variables

```
PEARL_HOST      # Pearl-2 IP address (e.g. 192.168.2.45)
PEARL_PORT      # default: 80
PEARL_PASSWORD  # admin password (empty string if not set)
```

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
        """GET /api/system/firmware → firmware version details."""

    def get_device_identity(self) -> dict:
        """GET /api/system/ident → device name, location, description."""

    def get_channels(self) -> list[dict]:
        """GET /api/channels → list of {id, name} for all channels."""

    def get_channel_publisher_status(self, channel_id: str) -> dict:
        """GET /api/channels/{cid}/publishers/status → streaming state."""

    def get_recorders(self) -> list[dict]:
        """GET /api/recorders → list of recorders with id, name, multisource."""

    def get_recorder_status(self, recorder_id: str) -> dict:
        """GET /api/recorders/{rid}/status → recording state."""

    def get_recorder_files(self, recorder_id: str) -> list[dict]:
        """GET /api/recorders/{rid}/archive/files → list of recording files."""

    def download_recording(self, recorder_id: str, file_id: str,
                           dest_path: str) -> str:
        """
        GET /api/recorders/{rid}/archive/files/{fid}
        Downloads recording file via chunked HTTP GET to dest_path.
        Returns local path of the downloaded file.
        Uses stream=True + iter_content(chunk_size=8192) for large files.
        """

    def switch_layout(self, channel_id: str, layout_id: str) -> None:
        """PUT /api/channels/{cid}/layouts/active → activate a layout."""

    def start_streaming(self, channel_id: str) -> None:
        """POST /api/channels/{cid}/publishers/control/start"""

    def stop_streaming(self, channel_id: str) -> None:
        """POST /api/channels/{cid}/publishers/control/stop"""

    def get_legacy_param(self, channel_n: int, key: str) -> str:
        """
        Legacy API fallback.
        GET /admin/channel{N}/get_params.cgi?{key}
        Returns the raw value string (e.g. "Pearl-2", "4.24.3").
        """
```

All methods must raise `requests.RequestException` on failure so
`EpiphanMonitorTool` can catch and convert to alert items.

---

### `domains/epiphan/tools/pearl_monitor.py` — EpiphanMonitorTool

Same pattern as `OBSMonitorTool`. Returns `{"files": [alert_items], "count": N}`
with the same alert item shape. The engine's planner sees no difference.

**Health checks (polls `PearlClient` on each tick):**

| Alert type | API source | Severity |
|---|---|---|
| `recording_stopped` | recorder status = not recording | hard fail |
| `streaming_stopped` | channel publisher status = stopped | hard fail |
| `disk_low` | Pearl storage < threshold | warning |

Note: Pearl-2 does not expose CPU/memory stats via REST the same way OBS
WebSocket does. Health monitoring focuses on recording and streaming state.

**Edge-triggered handoff:** Same pattern as `main_streamlab.py`.
Watches for `recording_stopped` transition (active → stopped) and publishes
the `recording_stopped` event to the message bus exactly once.

**`thresholds.yaml`:**
```yaml
poll_interval_seconds: 5
stream:
  disk_space_warning_gb: 10
```

---

### `domains/streamlab_post/workers/recording_download_worker.py`

New **pre-Stage 1 worker** — downloads the Pearl recording to a local path
so the rest of the pipeline can continue identically to the OBS workflow.

```python
class RecordingDownloadWorker:
    name = "recording_download"

    def run(self, payload: dict) -> dict:
        """
        Pull the most recently completed recording from Pearl.

        Payload keys:
          pearl_host       str   Pearl IP (from PEARL_HOST env var fallback)
          pearl_recorder_id str  recorder ID — same as channel_en/fr ID
          download_dir     str   local directory to save to (created if absent)
          dry_run          bool

        Returns:
          {"success": True, "file_path": str, "file_size_bytes": int}
          {"success": False, "error": str}

        Never raises.
        """
```

**How it finds the file:** Calls `PearlClient.get_recorder_files(recorder_id)`,
finds the most recently completed file (status = not currently recording),
downloads via chunked HTTP GET to `download_dir`, returns the local path.

**Coordinator integration:** When `session_config.yaml` has `hardware: epiphan`,
the coordinator runs `RecordingDownloadWorker` before Stage 1 and passes the
downloaded local path as `file_path` to all subsequent workers.
`backup_verify`, `audio_extract`, and `file_rename` see a local path and
require zero changes.

---

### `pearl_config.example.yaml`

```yaml
# Pearl connection
pearl:
  host: ""              # Pearl-2 IP address (e.g. 192.168.2.45)
  port: 80
  model: "pearl-2"      # pearl-2 | pearl-mini | pearl-nano | pearl-nexus
  channel_en: ""        # Pearl channel ID for EN stream
  channel_fr: ""        # Pearl channel ID for FR stream
  download_dir: "~/Downloads/pearl-recordings"

# NOTE: Channel and recorder IDs are identical on Pearl-2.
# channel_en is also the recorder ID for EN recordings.
# IDs are NOT sequential — verify with:
#   curl -u admin: 'http://{pearl_ip}/api/channels'
#   curl -u admin: 'http://{pearl_ip}/api/recorders'
#
# Reference device (192.168.2.45):
#   "1"  = Master-EN          "4"  = Master-FR
#   "8"  = OPH Standard EN    "9"  = OPH Standard FR
#   "13" = A DAY FR           "14" = ADay EN
#   "19" = BACKUP EN          "20" = BACKUP FR
#   "m1" = Recorder 1 (multitrack, multisource:true)

# Session identity (same fields as OBS workflow)
hardware: "epiphan"
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
- `--recorder` flag specifies which Pearl recorder ID to monitor and pull from

```bash
python main_epiphan.py --handoff --recorder 1
```

---

### `session_config.yaml` + `run_session.py` extension

Add `hardware` discriminator:
```yaml
hardware: "epiphan"   # or "obs" (default when absent)
```

`run_session.py` reads this field to start `main_epiphan.py` instead of
`main_streamlab.py`. `PostStreamCoordinator` reads it to insert
`RecordingDownloadWorker` before Stage 1.

All other coordinator behavior, workers, and post-stream pipeline unchanged.

---

### `prepare_session.py` extension

Add hardware selector at the top of the prompt flow:
```
Hardware backend [obs/epiphan] (obs): epiphan
```

When `epiphan` is selected, additionally prompt:
```
Pearl EN channel ID [{current}]:
Pearl FR channel ID [{current}]:
```
(Recorder ID is derived from channel_en — no separate prompt needed.)

---

### Phase 8a Tests (`tests/test_phase_8a_epiphan.py`)

~8 tests, all mocked (no live Pearl required):

1. `test_pearl_client_get_channels` — mock GET /api/channels → list returned
2. `test_pearl_client_get_recorders` — mock GET /api/recorders → list with m1 included
3. `test_pearl_client_download_recording` — mock chunked download → file written to tmp_path
4. `test_epiphan_monitor_healthy` — all recorders active → zero alert items
5. `test_epiphan_monitor_recording_stopped` — recorder inactive → alert item returned
6. `test_recording_download_worker_success` — mock PearlClient → local file path returned
7. `test_recording_download_worker_dry_run` — dry_run=True → success, no file written
8. `test_recording_download_worker_never_raises` — bad host → failure dict, no exception

### Phase 8a Seal Criteria

- All tests pass, prior 94 tests unmodified, 1 permanent skip
- `python main_epiphan.py --dry-run` exits cleanly
- `python scripts/prepare_session.py` with `hardware: epiphan` updates config
- Live: `PearlClient.get_channels()` returns all 10 channels
- Live: `PearlClient.get_recorders()` returns all 11 recorders including `m1`
- Engine unchanged: `grep -r 'from engine.graph' domains/epiphan/` returns nothing

**Gate to Phase 8b:** 3 clean Pearl sessions.

---

## Phase 8b — Live Layout Control

### Objective

Miktos issues layout switch commands to Pearl during a live stream.
The operator uses `pearl_control.py` to control which Zoom participant feed
goes to which YouTube channel in real time. Stage 2 of the vision: Miktos
moves from observer to coordinator.

### Layout concept on this Pearl-2

Zoom feeds Pearl via NDI. Pearl has multiple layouts per channel, each
configured to show a different Zoom participant combination. These layouts
are pre-configured in Pearl's Admin UI — Miktos switches between them only.

Example layouts for `Master-EN` (channel 1):
- Speaker view
- Interpreter view
- Sign language view
- Presentation / screen share

### API endpoint for layout switching (confirmed from Swagger)

```
PUT /api/channels/{cid}/layouts/active
Body: {"id": "{layout_id}"}
```

The layout ID is a string from Pearl's layout list for that channel.

### New File

```
scripts/pearl_control.py
```

### CLI Interface

```bash
# List available layouts for a channel
python scripts/pearl_control.py layouts --channel 1

# Switch active layout (fuzzy name match)
python scripts/pearl_control.py switch --channel 1 --layout speaker
python scripts/pearl_control.py switch --channel 4 --layout interpreter

# Show current active layout for each configured channel
python scripts/pearl_control.py status
```

Use actual Pearl channel IDs: `1` = Master-EN, `4` = Master-FR.

### Console output

```
  Pearl Layout Control
  ──────────────────────────────────────────
  Channel 1 (Master-EN): speaker  →  interpreter  ✅
  Channel 4 (Master-FR): (unchanged)
```

### Phase 8b Tests (`tests/test_phase_8b_layout_control.py`)

~4 tests:

1. `test_layout_list_parsed` — mock response → list of layout names returned
2. `test_layout_fuzzy_match` — "speaker" matches "Speaker view" layout name
3. `test_layout_switch_calls_api` — PUT /api/channels/{cid}/layouts/active called
4. `test_status_shows_current_layout` — after switch, status reflects new layout

### Phase 8b Seal Criteria

- Tests pass, prior tests unmodified
- `python scripts/pearl_control.py layouts --channel 1` returns layout names from live Pearl-2
- `python scripts/pearl_control.py switch --channel 1 --layout speaker` switches layout
  (verified on Pearl-2 touch screen)
- No disruption to recording or streaming during switch

---

## What Phase 9 Becomes

With Phase 8 complete:
- OBS domain: post-stream automation (reactive)
- Pearl domain: post-stream automation + live layout control (active)

Phase 9: unified `rich` terminal cockpit showing active hardware, live health,
current layout per Pearl channel, layout switching via keypress, post-stream
stage progress. Terminal-first. Web GUI comes after Phase 9 is validated.

---

## Architecture Invariants

- Engine unchanged across both sub-phases
- No imports from `engine/graph/` in any new domain file
- All 94 prior tests pass unmodified
- `PearlClient` never stores credentials — reads from env vars only
- `RecordingDownloadWorker` never raises exceptions
- Layout switching additive — no changes to `PostStreamCoordinator` or
  any existing worker

---

## Pre-Implementation Gate: MET ✅

Confirmed on live Pearl-2 (192.168.2.45, firmware 4.24.3, 2026-04-16):

```
GET /api/channels  → 200 OK, 10 channels
GET /api/recorders → 200 OK, 11 recorders (10 single + 1 multitrack "m1")
GET /admin/channel1/get_params.cgi?firmware_version → 4.24.3
GET /admin/channel1/get_params.cgi?product_name → Pearl-2
Swagger UI: http://192.168.2.45/swagger/ (REST API v2.0, OAS 3.0)
```

Confirmed API paths:
- Base: `/api/`
- Recordings: `/api/recorders/{rid}/archive/files`
- Layout switch: `PUT /api/channels/{cid}/layouts/active`
- Channel IDs and recorder IDs share the same namespace and values

**VS Code can begin Phase 8a implementation on branch `phase-8/epiphan-pearl`.**

---

*Spec written 2026-04-15. API paths corrected from live device 2026-04-16.*
*Recorder IDs confirmed identical to channel IDs — no separate recorder_id config needed.*
