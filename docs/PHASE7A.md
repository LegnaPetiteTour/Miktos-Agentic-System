# Phase 7a Spec — Post-Session HTML Report

**Branch:** `phase-7a/session-report`
**Objective:** After each session closes, generate a self-contained HTML report
that shows exactly what happened. No server required. Opens in any browser.

This document is the authoritative implementation spec for VS Code.

---

## How It Fits Into the Existing Architecture

The report worker is a new **optional Stage 4 slot** added alongside `notify`
in `PostStreamCoordinator`. It runs after `file_rename` has moved all artifacts
to the `final_folder`. It never raises exceptions. It writes one file.

```text
Stage 1 (parallel):  backup_verify | youtube_en | audio_extract
Stage 2 (parallel):  translate     | transcript
Stage 3 (parallel):  youtube_fr    | file_rename
Stage 4 (optional):  notify        | report          ← NEW
```

---

## Data Available to the Report Worker

The coordinator accumulates results from all prior stages. By Stage 4,
the payload passed to the report worker contains:

```python
# From coordinator Stage 4 payload construction (see coordinator.py):
{
    # Identity
    "event_name":       str,   # e.g. "Council-Meeting"
    "session_date":     str,   # e.g. "2026-04-15"
    "session_id":       str,   # hex e.g. "05b7a3154d20"

    # From backup_verify result
    "file_size_bytes":  int,   # recording size
    "duration_seconds": float, # recording duration

    # From audio_extract result
    "mp3_path":         str,   # path to extracted MP3

    # From youtube_en result
    "video_id_en":      str,   # YouTube EN video ID
    "title_en":         str,   # EN title

    # From translate result
    "title_fr":         str,   # FR title

    # From transcript result
    "transcript_path":  str,   # path to .txt file
    "word_count":       int,
    "detected_languages": list,

    # From youtube_fr result
    "video_id_fr":      str,   # YouTube FR video ID

    # From file_rename result
    "final_folder":     str,   # named session folder path

    # Full slots dict for status/error rendering
    "slots":            dict,  # {slot_name: {success, error, ...}}

    # Pipeline control
    "dry_run":          bool,
}
```

The `slots` dict contains the raw result of every slot:
```python
slots = {
    "backup_verify":  {"success": True/False, "file_size_bytes": ..., "duration_seconds": ..., "error": ...},
    "youtube_en":     {"success": True/False, "video_id": ..., "title": ..., "error": ...},
    "audio_extract":  {"success": True/False, "mp3_path": ..., "error": ...},
    "translate":      {"success": True/False, "title_fr": ..., "description_fr": ..., "error": ...},
    "transcript":     {"success": True/False, "transcript_path": ..., "word_count": ..., "error": ...},
    "youtube_fr":     {"success": True/False, "video_id": ..., "error": ...},
    "file_rename":    {"success": True/False, "final_folder": ..., "error": ...},
    "notify":         {"success": True/False, "skipped": True/False, "error": ...},
}
```

---

## File to Create

```
domains/streamlab_post/workers/report_worker.py
```

One class, one public method. Worker contract is identical to all other workers:
- Never raises exceptions
- Returns `{"success": True/False, "report_path": str, "error": str}`

---

## ReportWorker Contract

```python
class ReportWorker:
    name = "report"

    def run(self, payload: dict) -> dict:
        """
        Generate session_report.html in final_folder.

        Returns:
          {"success": True, "report_path": str}   on success
          {"success": False, "error": str}         on failure
        """
```

### Payload keys used:
- `final_folder` (str) — where to write the HTML file
- `event_name` (str)
- `session_date` (str)
- `duration_seconds` (float)
- `file_size_bytes` (int)
- `video_id_en` (str) — may be empty
- `video_id_fr` (str) — may be empty
- `transcript_path` (str) — may be empty
- `word_count` (int)
- `slots` (dict) — full slot results
- `dry_run` (bool) — if True, return mock result without writing

### Output file:
`{final_folder}/session_report.html`

---

## HTML Report Content Requirements

The report must be **self-contained** (no CDN, no external CSS, no JS libraries).
All styles inline. Opens correctly from the file system in Safari and Chrome.

### Required sections:

**1. Header**
- Event name (large)
- Date and duration (e.g. `2026-04-15 — 6m 32s`)
- Overall status badge: `✅ Complete` or `❌ Partial Failure`

**2. Pipeline Slot Table**

One row per slot in execution order:
```
Slot           Status   Detail
bacup_verify   ✅        165.8 MB, 392s
youtube_en     ✅        Council Meeting (EN) → [link]
audio_extract  ✅        6.2 MB
translate      ✅        Réunion du Conseil (FR)
transcript     ✅        42 words — fr, en
youtube_fr     ✅        Réunion du Conseil → [link]
file_rename    ✅        2026-04-15_Council-Meeting_001
notify         —        skipped
report         ✅        this file
```

For failed slots: show the error message in the Detail column.
For skipped slots: show `— skipped` in Status.
Links to YouTube: `https://youtu.be/{video_id}` — only shown if `video_id` is non-empty.

**3. Files Produced**

List files in `final_folder` with sizes:
```
2026-04-15_Council-Meeting_001_EN.mov    165.8 MB
2026-04-15_Council-Meeting_001.mp3         6.2 MB
2026-04-15_Council-Meeting_001_transcript.txt
2026-04-15_Council-Meeting_001_report.html
```
File sizes formatted as MB if >= 1 MB, KB otherwise.

**4. Transcript Preview** (only if transcript_path exists and is non-empty)

First 200 characters of the transcript file, with a note:
`Full transcript: {filename}`

**5. Footer**
`Generated by Miktos — {ISO timestamp}`

---

## Coordinator Changes

Two changes required in `domains/streamlab_post/coordinator.py`:

### 1. Import the new worker
```python
from domains.streamlab_post.workers.report_worker import ReportWorker
```

### 2. Add report slot to Stage 4

After the existing `notify` slot definition, add:
```python
"report": {
    "worker": ReportWorker(),
    "required": False,
    "payload": {
        "event_name":        event_name,
        "session_date":      session_date,
        "session_id":        session_id,
        "duration_seconds":  backup_result.get("duration_seconds", 0),
        "file_size_bytes":   backup_result.get("file_size_bytes", 0),
        "mp3_path":          audio_result.get("mp3_path", ""),
        "video_id_en":       en_result.get("video_id", ""),
        "title_en":          en_result.get("title", ""),
        "video_id_fr":       stage3_results.get("youtube_fr", {}).get("video_id", ""),
        "title_fr":          translate_result.get("title_fr", ""),
        "transcript_path":   transcript_result.get("transcript_path", ""),
        "word_count":        transcript_result.get("word_count", 0),
        "detected_languages": transcript_result.get("detected_languages", []),
        "final_folder":      rename_result.get("final_folder", str(output_dir)),
        "slots":             all_results,
        "dry_run":           dry_run,
    },
},
```

The Stage 4 dict already has `notify` — add `report` alongside it.

---

## File Naming Convention

The output file name should follow the same session naming convention:
```
{session_name}_report.html
```

Where `session_name` is derived from `final_folder`:
```python
from pathlib import Path
session_name = Path(final_folder).name   # e.g. "2026-04-15_Council-Meeting_001"
report_path = Path(final_folder) / f"{session_name}_report.html"
```

If `final_folder` is the hex-UUID output_dir (file_rename failed), fall back to:
```python
report_path = Path(final_folder) / "session_report.html"
```

---

## Visual Design Requirements

The HTML must look clean and professional. Use these CSS values:

```css
/* Palette */
--bg:          #f8f9fa;
--surface:     #ffffff;
--border:      #dee2e6;
--text:        #212529;
--text-muted:  #6c757d;
--green:       #198754;
--red:         #dc3545;
--blue:        #0d6efd;

/* Typography: system-ui font stack */
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;

/* Layout: max-width 800px, centered, 24px padding */
```

Slot table:
- Status column: `✅` for success, `❌` for fail, `—` for skipped
- Error text: `color: var(--red); font-size: 0.875em`
- Alternating row background for readability

---

## Tests

File: `tests/test_phase_7a_report.py`
Target: ~6 tests

**Required tests:**

1. `test_report_written_to_final_folder(tmp_path)`
   — valid payload with final_folder → HTML file exists at correct path

2. `test_report_contains_all_slots(tmp_path)`
   — all 8 slot names appear in the HTML content

3. `test_report_shows_youtube_links_when_video_ids_present(tmp_path)`
   — `https://youtu.be/` appears for EN and FR when video_ids non-empty

4. `test_report_handles_failed_slot(tmp_path)`
   — failed slot with error message → error text appears in HTML

5. `test_report_dry_run_does_not_write(tmp_path)`
   — `dry_run=True` → returns success, no file written

6. `test_report_worker_never_raises(tmp_path)`
   — invalid/missing final_folder → returns `{"success": False, "error": ...}`,
   does NOT raise an exception

---

## What to Report Back

When complete:
- Test count (82 prior + ~6 new, all passing, 1 permanent skip)
- Contents of `data/sessions/2026-04-15_Miktos-Demo-2026-04-15_005/` after
  running a dry-run test to confirm the file appears in the correct location
- Output of opening `session_report.html` in a browser — screenshot or
  description of what rendered

This conversation audits `report_worker.py`, the coordinator change, and the
test file on disk before sealing. Same protocol as all prior phases.

---

## Architecture Invariants (as always)

- Engine unchanged
- No imports from `engine/graph/` in the new worker
- All prior 82 tests pass unmodified
- `report_worker.py` never raises exceptions
- The coordinator change is additive — `notify` slot is untouched
