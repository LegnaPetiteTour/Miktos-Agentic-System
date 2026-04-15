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

## Pearl API Surface (confirmed from documentation)

Pearl-2 exposes two API layers:

**Modern REST API** (preferred)
- Base URL: `http://{pearl_ip}/api/1.0/`
- Auth: HTTP Basic Auth (`admin:{password}`)
- JSON responses
- Endpoints: system info, channel status, recording control, file management,
  streaming control, layout management

**Legacy HTTP API** (fallback / config control)
- Base URL: `http://{pearl_ip}/admin/`
- Pattern: `/admin/channel{N}/get_params.cgi?key` and `set_params.cgi?key=value`
- Auth: HTTP Basic Auth
- Used for: configuration keys, layout switching, stream parameters

**Confirmed API capabilities:**
- `GET  /api/1.0/system`                    ← device info, firmware, model
- `GET  /api/1.0/channels`                  ← list all channels with status
- `GET  /api/1.0/channels/{id}`             ← channel detail, streaming state
- `POST /api/1.0/channels/{id}/recording/control` ← start/stop recording
- `GET  /api/1.0/channels/{id}/recordings`  ← list recordings (name, size, date)
- `GET  /api/1.0/channels/{id}/recordings/{filename}` ← download recording file
- `GET  /admin/channel{N}/get_params.cgi?{key}` ← read config/status
- `http://{ip}/admin/channel{N}/set_params.cgi?layout={id}` ← switch layout
- `GET  /admin/channel{N}/get_params.cgi?rec_enabled` ← recording state

**Auth pattern for all calls:**
```python
import requests
from requests.auth import HTTPBasicAuth

auth = HTTPBasicAuth('admin', os.getenv('PEARL_PASSWORD'))
response = requests.get(f'http://{ip}/api/1.0/system', auth=auth, timeout=10)
```

**Environment variables:**
```
PEARL_HOST      # Pearl-2 IP address (default: 192.168.255.250)
PEARL_PORT      # default: 80
PEARL_PASSWORD  # admin password
```

**Model support:** Pearl-2, Mini, Nano, Nexus all use the same REST API surface.
Differences are in capability (Nano: single channel only; others: multi-channel).
Handled via a `pearl_model` config field that sets capability constraints.

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
    Thin wrapper over Pearl REST + Legacy HTTP APIs.
    Auth via HTTP Basic using env vars PEARL_HOST, PEARL_PASSWORD.
    All methods raise on connection failure so the monitor can handle it.
    """

    def __init__(self) -> None:
        self._host = os.getenv('PEARL_HOST', '192.168.255.250')
        self._port = int(os.getenv('PEARL_PORT', '80'))
        self._password = os.getenv('PEARL_PASSWORD', '')
        self._base = f'http://{self._host}:{self._port}'
        self._auth = HTTPBasicAuth('admin', self._password)

    def get_system_info(self) -> dict:
        """GET /api/1.0/system — returns firmware, model, uptime."""

    def get_channels(self) -> list[dict]:
        """GET /api/1.0/channels — returns all channels with streaming state."""

    def get_channel_status(self, channel_id: str) -> dict:
        """GET /api/1.0/channels/{channel_id} — streaming + recording state."""

    def get_recordings(self, channel_id: str) -> list[dict]:
        """GET /api/1.0/channels/{channel_id}/recordings — list of recording files."""

    def download_recording(self, channel_id: str, filename: str,
                           dest_path: str) -> str:
        """
        Download recording file to dest_path via streaming HTTP GET.
        Returns local path of the downloaded file.
        Uses chunked download to handle large files (165MB+).
        """

    def switch_layout(self, channel_id: str, layout_id: str) -> None:
        """Legacy API: set active layout for a channel."""

    def start_streaming(self, channel_id: str) -> None:
        """REST API: start streaming on a channel."""

    def stop_streaming(self, channel_id: str) -> None:
        """REST API: stop streaming on a channel."""

    def get_stats(self) -> dict:
        """GET /api/1.0/system — CPU, memory, uptime for health monitoring."""
```

---

### `domains/epiphan/tools/pearl_monitor.py` — EpiphanMonitorTool

Same pattern as `OBSMonitorTool`. Returns `{"files": [alert_items], "count": N}`
with the same alert item shape. The engine’s planner sees no difference.

**Health checks (polls via `PearlClient`):**

| Alert type | Source | Hard fail / warning |
|---|---|---|
| `streaming_stopped` | channel streaming state = inactive | hard fail |
| `recording_stopped` | channel recording state = inactive | hard fail |
| `stream_down` | all channels have no active output | hard fail |
| `cpu_overload` | system CPU > threshold | warning |
| `memory_pressure` | system memory > threshold | warning |
| `disk_low` | internal storage < threshold | warning |

**Edge-triggered handoff:** Same pattern as `main_streamlab.py`. The monitor
watches for `recording_stopped` and publishes the `recording_stopped` event
to the bus when the recording transitions from active → stopped.

**`thresholds.yaml`:**
```yaml
poll_interval_seconds: 5
stream:
  cpu_usage_warning: 70
  cpu_usage_critical: 90
  memory_usage_warning: 80
  disk_space_warning_gb: 10
  dropped_frames_pct_warning: 2.0
  dropped_frames_pct_critical: 5.0
```

---

### `domains/streamlab_post/workers/recording_download_worker.py`

New **Stage 0 worker** — runs before Stage 1, downloads the Pearl recording
to a local temp path so the rest of the pipeline can proceed identically.

```python
class RecordingDownloadWorker:
    name = "recording_download"

    def run(self, payload: dict) -> dict:
        """
        Pull the most recent completed recording from Pearl.

        Payload keys:
          pearl_host       str   Pearl IP address
          pearl_channel_id str   which channel to pull from
          download_dir     str   local directory to save to
          dry_run          bool

        Returns:
          {"success": True, "file_path": str, "file_size_bytes": int}
          {"success": False, "error": str}
        """
```

**How it finds the file:** After the `recording_stopped` event fires, the
worker calls `PearlClient.get_recordings(channel_id)`, finds the most recently
completed file (not currently recording), and downloads it via chunked HTTP GET
to `download_dir`. Returns the local file path.

**Coordinator integration:** When `session_config.yaml` has `hardware: epiphan`,
the coordinator inserts `recording_download` before Stage 1 and uses the
downloaded local path as `file_path` for all subsequent workers. The
`backup_verify`, `audio_extract`, and `file_rename` workers see a local file
path and require zero changes.

---

### `pearl_config.example.yaml`

```yaml
# Pearl connection
pearl:
  host: "192.168.255.250"      # Pearl-2 IP address
  port: 80
  model: "pearl-2"             # pearl-2 | pearl-mini | pearl-nano | pearl-nexus
  channel_en: "1"              # Pearl channel ID for EN stream
  channel_fr: "2"              # Pearl channel ID for FR stream
  download_dir: "~/Downloads/pearl-recordings"

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
- With `--recordings-channel`: specifies which Pearl channel to pull recording from

```bash
python main_epiphan.py --handoff --recordings-channel 1
```

---

### `session_config.yaml` extension

Add a `hardware` discriminator field:
```yaml
hardware: "epiphan"   # or "obs" (default)
```

`run_session.py` and `PostStreamCoordinator` read this field to:
1. Start `main_epiphan.py` instead of `main_streamlab.py`
2. Insert `recording_download` before Stage 1 when `hardware: epiphan`

All other coordinator behavior, workers, and post-stream pipeline unchanged.

---

### `prepare_session.py` extension

Add hardware selector at the start of the prompt flow:
```
Hardware backend [obs/epiphan] (obs): epiphan
```

When `epiphan` selected, additionally prompt:
```
Pearl EN channel ID [1]: 
Pearl FR channel ID [2]: 
Download directory [~/Downloads/pearl-recordings]: 
```

---

### Phase 8a Tests (`tests/test_phase_8a_epiphan.py`)

~8 tests, all mocked (no live Pearl required):

1. `test_pearl_client_get_system_info` — mock GET /api/1.0/system → returns dict
2. `test_pearl_client_get_recordings` — mock recording list response
3. `test_pearl_client_download_recording` — mock chunked download → file written to tmp_path
4. `test_epiphan_monitor_healthy_stream` — all channels active → zero alert items
5. `test_epiphan_monitor_recording_stopped` — channel recording inactive → alert item
6. `test_recording_download_worker_success` — mock PearlClient → local file path returned
7. `test_recording_download_worker_dry_run` — dry_run=True → returns mock success, no download
8. `test_recording_download_worker_never_raises` — bad host → returns failure dict, no exception

### Phase 8a Seal Criteria

- All tests pass, prior 94 tests unmodified, 1 permanent skip
- `python main_epiphan.py --dry-run` exits cleanly
- `python scripts/prepare_session.py` with `hardware: epiphan` updates config correctly
- Live test with Pearl-2: `PearlClient.get_system_info()` returns device info
- Live test: `PearlClient.get_recordings('1')` returns list of files
- Engine unchanged: `grep -r 'from engine.graph' domains/epiphan/` returns nothing

**Gate to Phase 8b:** 3 clean Pearl sessions using the Phase 8a workflow.

---

## Phase 8b — Live Layout Control

### Objective

Miktos issues commands to Pearl during a live stream. The operator uses
`pearl_control.py` to switch which Zoom participant feed goes to which
YouTube channel, in real time. This is Stage 2 in the vision: Miktos moves
from observer to coordinator.

### What Layout Switching Means for This Workflow

Your Zoom session feeds Pearl via NDI. Pearl has multiple layouts per channel,
each layout configured to show a different combination of Zoom participants:
- `speaker-en` — active speaker feed, EN channel
- `interpreter-fr` — French interpreter feed, FR channel
- `sign-language` — sign language interpreter
- `presentation` — screen share / presentation source
- `split-en-fr` — side-by-side (EN + FR)

These layouts are pre-configured in Pearl’s Admin UI. Miktos does not create
layouts — it only switches between pre-existing ones.

### New File

```
scripts/pearl_control.py
```

### CLI Interface

```bash
# List available layouts for a channel
python scripts/pearl_control.py layouts --channel 1

# Switch to a layout by name (fuzzy-matched against Pearl’s layout names)
python scripts/pearl_control.py switch --channel 1 --layout speaker
python scripts/pearl_control.py switch --channel 2 --layout interpreter-fr

# Switch both channels simultaneously
python scripts/pearl_control.py switch --channel 1 --layout speaker \
                                        --channel 2 --layout interpreter-fr

# Show current live layout on each channel
python scripts/pearl_control.py status
```

### Implementation

`pearl_control.py` uses `PearlClient.switch_layout(channel_id, layout_id)`
(already built in Phase 8a) to issue the layout switch via the Legacy HTTP API:

```
http://{pearl_ip}/admin/channel{N}/set_params.cgi?layout={layout_id}
```

The layout ID is an integer. `pearl_control.py` first fetches the layout list
via the REST API, fuzzy-matches the operator’s text input to a layout name,
then sends the switch command.

**Console output:**
```
  Pearl Layout Control
  ──────────────────────────────
  Channel 1: speaker-fr  → interpreter-fr  ✅
  Channel 2: (unchanged)
```

**Integration with `run_session.py` status display:**
When a layout switch occurs, `pearl_control.py` can write a marker to
`data/sessions/current/layout_log.jsonl` (one line per switch, with timestamp,
channel, and layout name). The `StatusDisplay` in `run_session.py` reads this
file and shows the current active layout per channel in the status panel.

### Phase 8b Tests (`tests/test_phase_8b_layout_control.py`)

~4 tests:

1. `test_layout_list_parsed` — mock REST response → list of layout names returned
2. `test_layout_fuzzy_match` — “speaker” matches “speaker-fr” layout name
3. `test_layout_switch_calls_client` — switch command calls PearlClient.switch_layout
4. `test_status_shows_current_layout` — after switch, status endpoint returns new layout

### Phase 8b Seal Criteria

- Tests pass, prior tests unmodified
- `python scripts/pearl_control.py layouts --channel 1` returns layout names
  from a live Pearl-2
- `python scripts/pearl_control.py switch --channel 1 --layout speaker`
  switches the active layout on the live device (verified on touch screen)
- No disruption to recording or streaming during layout switch

---

## What Phase 9 Becomes

With Phase 8a and 8b complete, the system has:
- OBS domain: post-stream automation, reactive
- Pearl domain: post-stream automation + live layout control
- Two proven patterns: reactive (post-stream) and active (live control)

Phase 9 is the first version of the production cockpit — the `rich` terminal
interface from Phase 7b extended into a unified panel that:
- Shows the active hardware (OBS or Pearl)
- Displays real-time health for the active domain
- Shows current layout per channel (Pearl)
- Allows layout switching via keypress (Pearl)
- Shows post-stream stage progress after stream ends

This is Stage 2 → Stage 3 in the vision. The web GUI (Stage 3 fully realized)
comes after Phase 9 is validated in production.

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

## Pre-Implementation Gate

Before VS Code writes any code, confirm on the live Pearl-2:

```bash
# Should return JSON with device info
curl -u admin:{password} http://{pearl_ip}/api/1.0/system

# Should return list of channels
curl -u admin:{password} http://{pearl_ip}/api/1.0/channels

# Should return list of recordings for channel 1
curl -u admin:{password} http://{pearl_ip}/api/1.0/channels/1/recordings
```

If these three calls work, Phase 8a implementation can begin.
Report the JSON response from `/api/1.0/system` so the spec can be
refined with the actual field names from your device.

---

*Spec written: 2026-04-15.*
*API surface confirmed from Epiphan documentation and REST API guide.*
*Implementation begins after pre-implementation gate is met.*
