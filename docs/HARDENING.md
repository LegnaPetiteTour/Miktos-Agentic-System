# Operational Hardening Spec

**Branch:** `hardening/operational-scripts`
**Target:** Before the next production stream
**Classification:** Not a numbered phase. Scripts only. No changes to existing
entry points (`main_streamlab.py`, `main_post_stream.py`, `main_preflight.py`).

This document is the authoritative implementation spec for VS Code.
All four scripts live in `scripts/`. All seal criteria must be met before PR.

---

## Constraints That Apply to All Four Scripts

- No changes to any existing file outside `scripts/`
- No new dependencies beyond what is already in `pyproject.toml`
  (`psutil`, `pyyaml`, `python-dotenv` are all available)
- Each script loads `.env` via `load_dotenv()` at startup
- Each script must run cleanly with `--dry-run` producing no side effects
- Each script exits with code `0` on success, `1` on error
- No LLM calls, no external API calls (except `run_session.py` which
  inherits them from `main_preflight.py`)

---

## Script 1 — `scripts/prepare_session.py`

### Purpose
Prompt the operator for the fields that change before every stream and
write them to `session_config.yaml`. Eliminates the manual YAML edit.

### Behaviour

```
python scripts/prepare_session.py [--config PATH]
```

1. Load `domains/streamlab_post/config/session_config.yaml`
   (or `--config PATH` override)
2. Print current values of the three mutable fields:
   - `event_name`
   - `youtube.en.video_id`
   - `youtube.fr.video_id`
3. Prompt: `Event name [{current}]: ` — required, reject empty string
4. Prompt: `YouTube EN video_id [{current}] (Enter to keep): `
   — optional, Enter keeps existing value
5. Prompt: `YouTube FR video_id [{current}] (Enter to keep/leave blank): `
   — optional, Enter keeps existing value (blank is valid — auto-discovery)
6. Show a diff of what will change:
   ```
   Changes:
     event_name:          "Old Event" → "New Event"
     youtube.en.video_id: ""          → "abc123"
   ```
7. Prompt: `Write? [y/N]: ` — default is N (safe)
8. On `y`: write the updated config, print `✅ session_config.yaml updated`
9. On anything else: print `Aborted. No changes made.` and exit 0

### What it must NOT change
Every field in `session_config.yaml` other than `event_name`,
`youtube.en.video_id`, and `youtube.fr.video_id` must be preserved exactly,
including all nested keys, comments are acceptable to lose (YAML round-trip).

### Seal criteria
- Running the script updates only the three target fields
- All other fields in the YAML are preserved
- Entering nothing at the event_name prompt rejects and re-asks
- Pressing Enter on video_id prompts keeps the current value
- `--dry-run` prints what would change but does not write the file
- The written file is valid YAML (`yaml.safe_load` succeeds)

### Tests
~4 tests in `tests/test_hardening_prepare_session.py`:
- valid input writes correct fields
- empty event_name is rejected
- Enter on video_id preserves existing value
- `--dry-run` does not write

---

## Script 2 — `scripts/run_session.py`

### Purpose
Single launcher that replaces the three-terminal workflow. Enforces the
correct startup order. Operator runs one command; system handles the rest.

### Behaviour

```
python scripts/run_session.py [--config PATH] [--poll-interval N]
```

**Step 1 — Pre-flight:**
```python
from domains.streamlab_post.pre_flight.checker import PreFlightChecker
results = PreFlightChecker().run(dry_run=False)
failures = [r for r in results if r["status"] == "fail"]
```
If any failures: print each `❌ {message}` line, print
`Pre-flight failed. Fix the above before streaming.`, `sys.exit(1)`.

**Step 2 — Start post-stream listener:**
```python
import subprocess, sys
post = subprocess.Popen(
    [sys.executable, "main_post_stream.py", "--poll-interval",
     str(poll_interval)],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT
)
```
If `post.poll()` is not None immediately after starting (process died):
print `Failed to start main_post_stream.py`, `sys.exit(1)`.

**Step 3 — Start stream monitor (foreground):**
Print `✅ Post-stream listener started (PID {post.pid})`
Print `Starting stream monitor… (Ctrl+C to stop)`
Then run:
```python
import subprocess, sys
monitor = subprocess.run(
    [sys.executable, "main_streamlab.py", "--handoff"]
)
```
This blocks until the operator stops OBS and the monitor exits naturally,
or until `Ctrl+C`.

**Step 4 — Cleanup:**
In a `finally` block: send `SIGTERM` to `post` if it is still running.
Print `Session ended. Post-stream listener stopped.`

### Important: no output swallowing
The post-stream process stdout/stderr must not be silently discarded.
Use a background thread to forward `post.stdout` to the terminal:
```python
import threading
def _forward(proc):
    for line in proc.stdout:
        print(line.decode(), end="")
threading.Thread(target=_forward, args=(post,), daemon=True).start()
```

### Seal criteria
- With OBS not running: pre-flight fails with `❌ OBS WebSocket — connection
  failed`, script exits 1, neither subprocess is started
- With OBS running and config valid: both processes start, monitor output
  is visible in the terminal
- `Ctrl+C` during monitoring: post-stream process receives SIGTERM and exits
- Post-stream process output (slot results) is visible in the terminal

### Tests
~3 tests in `tests/test_hardening_run_session.py`:
- pre-flight failure exits before starting subprocesses (mock PreFlightChecker)
- both processes start when pre-flight passes (mock subprocess.Popen + run)
- post.poll() not-None triggers failure before monitor starts

---

## Script 3 — `scripts/clear_inbox.py`

### Purpose
Safely clear stale pending messages that block the next session's pre-flight.
Consistent with message bus behavior: moves to `delivered/`, never deletes.

### Behaviour

```
python scripts/clear_inbox.py [--dry-run] [--agent AGENT_ID]
```

Default agent: `post_stream_processor`
Default pending dir: `data/messages/{agent}/pending/`

1. Scan `data/messages/{agent}/pending/` for `*.json` files
2. If none: print `Inbox is empty. Nothing to clear.`, exit 0
3. For each message: read and print summary:
   ```
   [1] 2026-04-13T22:53:14Z  recording_stopped  from: streamlab_monitor
   ```
4. If `--dry-run`: print `Dry run — no changes made.`, exit 0
5. Prompt: `Clear {N} message(s)? [y/N]: ` — default N
6. On `y`:
   - Move each `.json` file to `data/messages/{agent}/delivered/`
   - Append one line to `data/messages/message.log`:
     `{ISO_TIMESTAMP}  CLEARED  {agent} pending inbox ({N} message(s))`
   - Print `✅ Cleared {N} message(s). Logged to message.log.`
7. On anything else: print `Aborted.`, exit 0

### message.log format
Match the existing log format exactly:
```
2026-04-14T12:00:00Z  CLEARED    post_stream_processor pending inbox (2 message(s))
```
Use UTC timestamp. The extra spaces between columns should match the width
pattern already in `message.log` (check existing lines for alignment).

### Seal criteria
- After a failed session: `--dry-run` lists the stale message without moving it
- Running without `--dry-run` + confirming `y`: moves message to `delivered/`,
  `message.log` has a new `CLEARED` line with correct UTC timestamp
- Message files are moved, not deleted — they exist in `delivered/` after the clear
- Aborting at the prompt leaves inbox unchanged

### Tests
~4 tests in `tests/test_hardening_clear_inbox.py`:
- empty inbox prints message and exits cleanly
- `--dry-run` lists messages without moving them
- confirming moves files to `delivered/` and appends to `message.log`
- aborting leaves inbox unchanged

---

## Script 4 — `scripts/clean_sessions.py`

### Purpose
Archive hex-UUID test/dev session folders so that `data/sessions/` only
shows production sessions. At daily frequency, test artifacts accumulate
fast and make the directory useless for review.

### Behaviour

```
python scripts/clean_sessions.py [--dry-run] [--archive] [--days N]
```

**Production session pattern:** `YYYY-MM-DD_*` (starts with a date)
**Test session pattern:** anything else (hex UUIDs, short hashes, etc.)

Default `--days`: 7 (only archive sessions older than 7 days)
`--archive`: archive all matching sessions regardless of age
`--dry-run`: list what would be archived without touching anything

1. Scan `data/sessions/` for subdirectories matching the test pattern
2. Apply age filter (unless `--archive`)
3. Print summary:
   ```
   Found 47 test session(s) to archive (older than 7 days):
     05b7a3154d20   2026-04-09  (5 days old)
     b0d6b6561fa2   2026-04-10  (4 days old)
     ...
   ```
4. If `--dry-run`: print `Dry run — no changes made.`, exit 0
5. If nothing to archive: print `Nothing to archive.`, exit 0
6. Prompt: `Archive {N} session(s) to data/sessions/archive/? [y/N]: `
7. On `y`:
   - `data/sessions/archive/` is created if it does not exist
   - Move each folder with `shutil.move`
   - Print `✅ Archived {N} session(s).`
8. On anything else: print `Aborted.`, exit 0

### Age calculation
Use `datetime.fromtimestamp(os.path.getmtime(session_path))`
compared to `datetime.now()`. Age in days = `(now - mtime).days`.

### Production session guard
Before moving anything, assert that no folder matching `YYYY-MM-DD_*` is
in the move list. If any production session would be moved, print
`Error: would archive production session {name} — aborting.`, exit 1.

### Seal criteria
- `--dry-run` lists test sessions without moving them
- Production sessions (`2026-04-*_Miktos-Demo_*`) never appear in the
  archive list regardless of age
- Confirming `y` moves test sessions to `data/sessions/archive/`
- `data/sessions/archive/` is created if it doesn’t exist
- Running the script twice on the same sessions: second run shows nothing
  to archive (idempotent — already moved)

### Tests
~5 tests in `tests/test_hardening_clean_sessions.py`:
- production sessions excluded from archive list
- `--dry-run` lists without moving
- age filter works correctly (mock mtime)
- confirming moves to archive/
- already-archived sessions not re-listed (idempotent)

---

## gitignore update required

Add to `.gitignore`:
```
data/sessions/archive/
```

---

## What to report back

When complete, report:
- Test count (existing + new, all passing, 1 permanent skip)
- `python scripts/prepare_session.py --dry-run` output
- `python scripts/run_session.py` with OBS not running (pre-flight failure output)
- `python scripts/clean_sessions.py --dry-run` output showing test sessions

This conversation audits all four scripts on disk before sealing.
