# Phase 11 Spec — Dual-Channel Bilingual Pipeline

**Branch:** `phase-11/dual-channel`
**Depends on:** Phase 10b sealed (`35201ae`)
**Core principle:** Extend the coordinator to process both Pearl channels in a
single session. One stream event → two recordings → two audio files → two
transcripts → one session folder. Engine unchanged.

---

## Why This Phase Exists

All prior sessions only processed channel 2 (EN). Channel 3 (FR) was streamed
to YouTube by Pearl natively, and Miktos updated the FR YouTube metadata via
translation — but never downloaded or processed the FR recording.

For legal, editorial, and archival purposes:
- The FR recording on Pearl recorder 3 is proof of what was streamed on the
  French channel
- The FR transcript is the authoritative record of what the interpreter said
- Both are required for media accountability

Pearl records both channels simultaneously and independently. Both recordings
exist on Pearl’s internal storage after every bilingual session.

---

## What Changes

### Session folder output (before → after)

**Before (EN only):**
```
YYYY-MM-DD_EventName_NNN_001/
  YYYY-MM-DD_EventName_NNN_001_EN          ← EN recording
  YYYY-MM-DD_EventName_NNN_001.mp3         ← EN audio
  YYYY-MM-DD_EventName_NNN_001_transcript.txt
  YYYY-MM-DD_EventName_NNN_001_report.html
```

**After (dual-channel):**
```
YYYY-MM-DD_EventName_NNN_001/
  YYYY-MM-DD_EventName_NNN_001_EN          ← EN recording (Pearl recorder channel_en)
  YYYY-MM-DD_EventName_NNN_001_FR          ← FR recording (Pearl recorder channel_fr)
  YYYY-MM-DD_EventName_NNN_001.mp3         ← EN audio
  YYYY-MM-DD_EventName_NNN_001_FR.mp3      ← FR audio
  YYYY-MM-DD_EventName_NNN_001_transcript.txt    ← EN transcript
  YYYY-MM-DD_EventName_NNN_001_FR_transcript.txt ← FR transcript
  YYYY-MM-DD_EventName_NNN_001_report.html
```

---

## Pipeline Changes

### Pre-Stage 1 (currently: download EN only)

**Add:** download FR recording from Pearl recorder `channel_fr`

```python
# Existing
dl_en = RecordingDownloadWorker().run({
    "pearl_recorder_id": str(pearl_cfg.get("channel_en", "1")),
    ...
})

# New (parallel with EN or sequential)
dl_fr = RecordingDownloadWorker().run({
    "pearl_recorder_id": str(pearl_cfg.get("channel_fr", "3")),
    ...
})
```

Both downloads run before Stage 1. FR download failure is non-fatal — it
logs the error and proceeds with EN-only processing. The session is never
blocked by a missing FR recording.

### Stage 1 (currently: backup_verify, youtube_en, audio_extract for EN)

**Add:** `audio_extract_fr` slot — extracts MP3 from FR recording

```python
"audio_extract_fr": {
    "worker": AudioExtractWorker(),
    "required": False,   # FR is additive — never blocks the session
    "payload": {
        "file_path": fr_file_path,
        "output_dir": str(output_dir),
        "output_suffix": "_FR",   # produces session_FR.mp3
        "dry_run": dry_run,
    },
}
```

**Note:** `AudioExtractWorker` needs a new `output_suffix` parameter to name
the FR audio file distinctly. Default suffix is `""` (EN, current behaviour).

### Stage 2 (currently: translate, transcript for EN)

**Add:** `transcript_fr` slot — transcribes FR audio via ElevenLabs

```python
"transcript_fr": {
    "worker": TranscriptWorker(),
    "required": False,
    "payload": {
        "mp3_path": fr_audio_result.get("mp3_path", ""),
        "output_dir": str(output_dir),
        "output_suffix": "_FR",   # produces transcript_FR.txt
        "language_code": "fr",   # always FR for this slot
        "dry_run": dry_run,
    },
}
```

**Note:** `TranscriptWorker` needs a new `output_suffix` parameter too.
Default `""` (EN). FR always uses `language_code: "fr"` regardless of config.

### Stage 3 — file_rename

**Extend payload** to include FR paths:

```python
"fr_recording_path": fr_file_path,
"fr_mp3_path": fr_audio_result.get("mp3_path", ""),
"fr_transcript_path": fr_transcript_result.get("transcript_path", ""),
```

`FileRenameWorker` already renames whatever paths it receives. Adding FR
paths extends the rename to include the FR files with `_FR` suffix.
`FileRenameWorker.run()` must be updated to accept and rename these
optional FR paths.

### Stage 4 — report

**Extend payload** to include FR transcript path and FR transcript stats:
```python
"fr_transcript_path": fr_transcript_result.get("transcript_path", ""),
"fr_word_count":      fr_transcript_result.get("word_count", 0),
```

`ReportWorker` should show FR audio, FR transcript, and both word counts
in the session report. FR slots appear as additional rows in the pipeline table.

---

## Worker Changes Required

### `audio_worker.py`

Add `output_suffix: str = ""` to payload.

Currently the output file is always named `audio.mp3` (later renamed).
With suffix: EN produces `audio.mp3`, FR produces `audio_FR.mp3`.

### `transcript_worker.py`

Add `output_suffix: str = ""` to payload.

Currently the output file is always named `transcript.txt`.
With suffix: EN produces `transcript.txt`, FR produces `transcript_FR.txt`.

### `rename_worker.py`

Accept optional `fr_recording_path`, `fr_mp3_path`, `fr_transcript_path`.
Rename each to the session-named equivalent with `_FR` suffix where
applicable.

### `report_worker.py`

Accept optional `fr_transcript_path`, `fr_word_count`.
Show FR file sizes and transcript stats in the report.

---

## Failure Modes

| Failure | Behaviour |
|---|---|
| FR download fails | Log error, proceed EN-only. Session not blocked. |
| FR audio extract fails | Log error, no FR MP3. Session not blocked. |
| FR transcript fails | Log error, no FR transcript. Session not blocked. |
| EN download fails | `partial_failure` as today. Session stops. |

All FR slots are `required: False`. The session is never blocked by a
missing or failed FR path. EN remains the primary required path.

---

## session_config.yaml

No new fields needed. `pearl.channel_fr` already exists and is set to `3`.
The coordinator reads it at Pre-Stage 1 time.

---

## OBS Sessions

No change. When `hardware: obs`, Pre-Stage 1 runs the OBS path (no download).
The dual-channel extension only fires when `hardware: epiphan` and
`pearl.channel_fr` is set and non-zero.

---

## Tests (`tests/test_phase_11_dual_channel.py`)

~8 tests, mocked workers, no live Pearl required:

1. `test_fr_download_called_when_epiphan` — coordinator calls RecordingDownloadWorker twice
2. `test_fr_download_failure_non_fatal` — FR download fails, EN pipeline continues
3. `test_audio_extract_fr_suffix` — AudioExtractWorker called with `output_suffix="_FR"`
4. `test_transcript_fr_suffix` — TranscriptWorker called with FR suffix and `language_code="fr"`
5. `test_rename_includes_fr_paths` — FileRenameWorker receives fr_recording_path etc.
6. `test_obs_no_fr_download` — OBS sessions do not call FR download
7. `test_audio_suffix_default_en` — EN audio has no suffix (backwards compat)
8. `test_report_includes_fr_fields` — ReportWorker payload includes fr_transcript_path

**Prior tests unmodified. Target: 122 + ~8 = ~130 passed, 1 skip.**

---

## Seal Criteria

- All tests pass, 122 prior tests unmodified
- One real bilingual session run: EN + FR channels recording simultaneously
- Session folder contains 7 files: EN recording, FR recording, EN MP3, FR MP3,
  EN transcript, FR transcript, report
- FR download failure tested: stop channel 3 recording early, confirm EN
  pipeline completes normally
- OBS sessions unchanged

---

## What Does Not Change

- Engine, message bus, monitor loop — not touched
- `main_epiphan.py` — still monitors EN channel only for `recording_stopped`
- `session_config.yaml` schema — no new fields
- Web cockpit — no changes needed (reads session folder, shows all files)
- `youtube_fr` slot — unchanged (already updates FR YouTube metadata)
- All OBS-path behaviour — unchanged
- Architecture invariant — additive only

---

*Spec written 2026-04-19.*
*Branch: `phase-11/dual-channel` from `main` at `169a0ce`.*
