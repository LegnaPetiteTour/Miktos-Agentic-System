# Phase 14 Spec — Live Production Panel

**Branch:** `phase-14/live-production-panel`
**Depends on:** Phase 13 sealed (`937c9ea`)
**Core principle:** Surface what Pearl and OBS already know.
Miktos does not encode, composite, or render. It switches, monitors,
and captions — all through existing APIs.

---

## Objective

Transform the Miktos cockpit from a monitoring surface into an active
production control panel. The operator stays in Miktos during the
entire live event. Four capabilities:

1. **Live switching** — punch layouts/scenes with one click
2. **Stream health** — encoding quality, internet stability per channel
3. **Audio meters** — VU levels per channel, mute controls
4. **Live captions** — real-time STT in cockpit + push to YouTube

---

## Feature 1 — Live Switching Panel

### What it shows

Two columns side by side: EN channel (Pearl recorder 2 / OBS) and FR
channel (Pearl recorder 3). Each column shows:

- Current active layout/scene name (highlighted)
- All available layouts/scenes as clickable buttons
- Transition indicator when a switch is in progress
- Last switch timestamp

### How it works

**Pearl:** wraps the existing `pearl_control.py` API

- `GET /api/pearl/layouts/{channel_id}` — already exists (Phase 10a)
- `POST /api/pearl/switch` — already exists (Phase 10a)
- Auto-refresh every 4 seconds via existing SSE stream

**OBS:** new integration

- `GET /api/obs/scenes` — new endpoint, calls OBS WebSocket `GetSceneList`
- `POST /api/obs/switch` — new endpoint, calls OBS WebSocket `SetCurrentProgramScene`
- `GET /api/obs/current` — new endpoint, calls `GetCurrentProgramScene`

### New file: `web/api/switcher.py`

```python
# Endpoints:
# GET  /api/switcher/pearl/layouts/{channel}  — list layouts
# POST /api/switcher/pearl/switch              — switch Pearl layout
# GET  /api/switcher/obs/scenes               — list OBS scenes
# POST /api/switcher/obs/switch               — switch OBS scene
# GET  /api/switcher/obs/current              — current OBS scene
```

The Pearl half already exists in `web/api/pearl.py` — `switcher.py`
extends it with OBS equivalents and adds a unified endpoint:

```text
GET  /api/switcher/state
     → {pearl: {ch2: {active: str, layouts: [...]},
                ch3: {active: str, layouts: [...]}},
        obs: {active: str, scenes: [...]}}
```

The SSE stream in `status.py` adds `switcher_state` to its payload.

---

## Feature 2 — Stream Health Dashboard

### Health Metrics

Per-channel health panel:

| Metric | Source | Update rate |
| --- | --- | --- |
| Upload speed (Mbps) | macOS `networkQuality` CLI | Every 30s |
| Pearl streaming bitrate | Pearl `GET /api/channels/{id}/publishers` | Every 5s |
| Pearl stream state | Pearl API | Every 5s |
| OBS streaming bitrate | OBS WebSocket `GetStreamStatus` | Every 5s |
| OBS dropped frames | OBS WebSocket `GetStreamStatus` | Every 5s |
| OBS output state | OBS WebSocket `GetOutputStatus` | Every 5s |

Visual encoding quality indicator per channel:

- 🟢 Green: bitrate > 80% of target, dropped frames < 0.5%
- 🟡 Yellow: bitrate 50–80%, dropped frames 0.5–2%
- 🔴 Red: bitrate < 50%, dropped frames > 2%

### New endpoint: `GET /api/health/stream`

Reads Pearl and OBS streaming stats, returns unified JSON.
Added to SSE `status.py` payload as `stream_health`.

### Internet speed

Uses macOS built-in `networkQuality` CLI (no dependencies):

```python
import subprocess, json
result = subprocess.run(
    ['networkQuality', '-s', '-c'],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout)
upload_mbps = data['ul_throughput'] / 1_000_000
```

Run every 30 seconds in background thread, cache the result.

---

## Feature 3 — Audio Level Meters

### Reality check

Neither Pearl REST API nor OBS WebSocket exposes real-time audio
level data (VU meter values). The Pearl REST API returns channel
configuration and streaming status, not sample-level audio data.
OBS WebSocket has `GetInputVolume` but not live VU levels.

**What IS achievable:**

- **Volume controls:** Pearl channel volume is configurable via API
  (`PATCH /api/channels/{id}/audio`). Miktos can expose a fader.
- **Mute controls:** Pearl and OBS both support mute via API.
- **VU meters:** Require audio tap from the system.
  Achievable via BlackHole virtual audio + Python audio processing,
  but adds a significant dependency (BlackHole install, audio routing).

**Phase 14 delivers:**

- Volume faders per channel (Pearl audio level via API)
- Mute/unmute per channel (Pearl + OBS)
- Visual indicator: muted / active / unknown

**Phase 15 (deferred):**

- Live VU meter visualization (requires BlackHole or similar audio tap)

### New endpoint: `POST /api/audio/mute`

```text
POST /api/audio/mute
     Body: {channel: "pearl_en" | "pearl_fr" | "obs", mute: bool}
     → Calls Pearl PATCH /api/channels/{id}/audio or OBS SetInputMute
```

---

## Feature 4 — Live Captions

### Overview

Live captions have two parts:

1. **Caption monitor** — real-time transcript visible in Miktos cockpit
2. **YouTube caption push** — captions delivered to YouTube viewers

### Architecture

```text
Audio source (BlackHole virtual device)
    │
    ▼
faster-whisper (local, free, runs on M1/M2 Mac)
    │
    ├──► Caption monitor panel (WebSocket to browser)
    │
    └──► YouTube caption ingestion URL (HTTP POST)
```

### Audio source

Operator installs BlackHole (free, open source virtual audio device).
In macOS Sound settings, they create a Multi-Output Device that sends
audio to both speakers AND BlackHole simultaneously.
Miktos captures audio from BlackHole.

Install command (one-time, shown in Miktos setup):

```bash
brew install blackhole-2ch
```

### Speech-to-text: faster-whisper (local)

`faster-whisper` is a Python binding for Whisper optimized for Apple Silicon.
No API key, no ongoing cost. Models download once (~150 MB for small model).

```python
from faster_whisper import WhisperModel
model = WhisperModel("small", device="cpu", compute_type="int8")
# Process 3-second audio chunks
segments, _ = model.transcribe(audio_chunk, language="en")
```

For bilingual:

- EN channel caption worker: `language="en"`
- FR channel caption worker: `language="fr"`

Latency: ~1-2s for 3-second chunks on M1 Mac.

### YouTube caption ingestion

YouTube provides a unique HTTP POST URL for each live broadcast.
Captions are delivered via simple HTTP POST with text and timestamp.

```python
import requests
from datetime import datetime, timezone

def push_caption(ingestion_url: str, text: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    payload = f"{timestamp}\n{text}"
    requests.post(
        ingestion_url,
        data=payload.encode('utf-8'),
        headers={'Content-Type': 'text/plain; charset=utf-8'},
        timeout=5,
    )
```

The ingestion URL is retrieved from YouTube via:

```text
GET /youtube/v3/liveBroadcasts?part=contentDetails&id={video_id}
    → contentDetails.monitorStream.embedHtml contains ingestion URL
```

Or more directly: the operator copies it from YouTube Studio and
pastes it into the Miktos session setup form. This avoids OAuth
scope complexity for the first implementation.

### New file: `domains/captioning/caption_worker.py`

Follows the same domain adapter pattern as `epiphan/` and `streamlab/`:

```python
class CaptionWorker:
    """Real-time speech-to-text and caption delivery.
    
    Runs in a background thread. Captures audio from a named
    audio device, transcribes via faster-whisper, and both:
    - Publishes captions to the web cockpit via WebSocket
    - POSTs captions to YouTube caption ingestion URL
    """
    def start(self, audio_device: str, language: str,
              ingestion_url: str | None = None) -> None: ...
    def stop(self) -> None: ...
    def get_recent(self, n: int = 5) -> list[str]: ...
```

### New endpoints: `web/api/captions.py`

```text
POST /api/captions/start
     Body: {channel: "en"|"fr", audio_device: str,
            ingestion_url: str|None}
     → Starts caption worker for channel

POST /api/captions/stop
     Body: {channel: "en"|"fr"}
     → Stops caption worker

GET  /api/captions/stream    (SSE)
     → Pushes caption lines as they arrive, tagged with channel

GET  /api/captions/status
     → {en: {active: bool, words_captured: int},
        fr: {active: bool, words_captured: int}}
```

### Session config extension

```yaml
captions:
  en:
    audio_device: "BlackHole 2ch"
    language: "en"
    youtube_ingestion_url: ""  # paste from YouTube Studio
  fr:
    audio_device: "BlackHole 2ch"
    language: "fr"
    youtube_ingestion_url: ""  # paste from YouTube Studio
```

Added to `/setup` form and `/onboarding` wizard (new step: Captions).

---

## New Files Summary

```text
domains/captioning/
  __init__.py
  caption_worker.py      ← audio capture + STT + YouTube push

web/api/
  switcher.py            ← Pearl + OBS scene/layout switching
  health.py              ← stream health stats
  audio_control.py       ← mute/volume controls
  captions.py            ← caption control + SSE stream

web/templates/
  panel_switcher.html    ← HTMX partial for switching panel
  panel_health.html      ← HTMX partial for health panel
  panel_audio.html       ← HTMX partial for audio panel
  panel_captions.html    ← HTMX partial for captions panel

web/server.py            ← MODIFIED: include 4 new routers
web/api/status.py        ← MODIFIED: SSE payload extended
web/templates/index.html ← MODIFIED: 4 new panels in cockpit
```

---

## Cockpit Layout After Phase 14

```text
┌──────────────────────────────────────────────────┐
│ HARDWARE  [epiphan]   SESSION [Start] [Stop]          │
├──────────────────────────────────────────────────┤
│ SWITCHING                                              │
│  EN Channel          FR Channel                       │
│  [Speaker View ●]   [Interpreter View ●]             │
│  [Slides View   ]   [Slides View     ]               │
│  [Wide Shot     ]   [Wide Shot       ]               │
├──────────────────────────────────────────────────┤
│ STREAM HEALTH                                          │
│  EN 🟢 4.2 Mbps  FR 🟢 3.8 Mbps   Upload 🟢 12.4 Mbps  │
├──────────────────────────────────────────────────┤
│ AUDIO                                                  │
│  EN [====|    ]  🔊  FR [===|     ]  🔇 MUTED        │
├──────────────────────────────────────────────────┤
│ LIVE CAPTIONS                      [EN] [FR] [Both]   │
│  EN: “We are pleased to announce the new policy...”    │
│  FR: “Nous sommes heureux d’annoncer la nouvelle...”   │
│  🟠 Pushing to YouTube • 2,847 words captured           │
├──────────────────────────────────────────────────┤
│ STREAM  ● LIVE  00:42:17     HEALTH  │ PIPELINE ▤    │
└──────────────────────────────────────────────────┘
```

---

## New Dependencies

```text
faster-whisper>=1.0    ← local STT (no API key, free)
sounddevice>=0.4       ← audio capture from virtual device
obsws-python>=1.7      ← already in project (Phase 3)
numpy>=1.24            ← audio processing
```

BlackHole: operator installs once via Homebrew.
faster-whisper model: downloads on first caption use (~150 MB for small).

---

## Tests (`tests/test_phase_14_production.py`)

~12 tests, mocked hardware, no live Pearl/OBS/audio required:

**Switcher:**

1. `test_pearl_layouts_endpoint` — returns layout list per channel
2. `test_pearl_switch_endpoint` — calls switch and returns success
3. `test_obs_scenes_endpoint` — returns scene list (mocked WS)
4. `test_obs_switch_endpoint` — switches scene (mocked WS)

**Health:**
5. `test_stream_health_endpoint` — returns unified health JSON
6. `test_quality_indicator_green` — high bitrate → green status
7. `test_quality_indicator_red` — low bitrate → red status

**Audio control:**
8. `test_mute_pearl_channel` — sends mute to Pearl API
9. `test_unmute_obs` — sends unmute to OBS WebSocket

**Captions:**
10. `test_caption_start_endpoint` — starts worker, returns 200
11. `test_caption_stop_endpoint` — stops worker cleanly
12. `test_youtube_caption_push` — mocked HTTP POST to ingestion URL

**Target: 140 + ~12 = ~152 passed, 1 skip.**

---

## What Does Not Change

- Engine, coordinator, workers — not touched
- Post-stream pipeline — not touched
- All Phase 12/13 paths — not touched
- `run_session.py` terminal path — preserved
- Architecture invariant — additive only

---

## Seal Criteria

- All 12 new tests pass, 140 prior tests unmodified
- Live switching panel shows Pearl layouts and switches correctly
- OBS scene list appears and scene switching works
- Stream health panel shows green/yellow/red per channel
- Audio mute/unmute works for both Pearl and OBS
- Caption monitor displays real-time text during a live session
- YouTube caption push delivers text to a test stream (manual validation)

---

## Phase 15 Preview (not in this phase)

- Lower thirds editor (push graphic name to Pearl overlay or OBS source)
- Transition type selector (cut / fade / wipe per channel)
- Intro/outro trigger buttons
- Live VU meter visualization (requires audio tap established in Phase 14)

---

*Spec written 2026-05-02.*
*Branch: `phase-14/live-production-panel` from `main` at `937c9ea`.*
*Research basis: docs/research/RQ-002-live-production-ecosystem.md*
