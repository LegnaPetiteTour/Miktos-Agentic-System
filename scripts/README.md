# Scripts

Operator scripts for daily stream workflow. Run from the repo root with `.venv/bin/python`.

| Script | Purpose |
| --- | --- |
| `prepare_session.py` | Prompt for event name + YouTube video IDs; writes `session_config.yaml`. Run before every stream. |
| `run_session.py` | Single launcher: pre-flight → post-stream listener → stream monitor. Enforces correct startup order. |
| `clear_inbox.py` | Safely moves stale pending messages to `delivered/`. Run if a previous session ended uncleanly. |
| `clean_sessions.py` | Archives hex-UUID test session folders; leaves dated production sessions untouched. |
| `pearl_control.py` | Live layout switching CLI for Epiphan Pearl (`layouts`, `switch`, `status` subcommands). |
| `youtube_auth.py` | One-time OAuth2 refresh token setup for YouTube Data API v3 (EN + FR channels). |

## Standard workflow

```bash
python scripts/prepare_session.py   # set event_name + video_ids
python scripts/run_session.py       # start everything, monitor stream
# Stop recording when done — session closes automatically
```

## Pearl workflow

```bash
python scripts/prepare_session.py   # select hardware: epiphan
python scripts/run_session.py       # start on Pearl, monitor until recording stops
python scripts/pearl_control.py layouts --channel 2   # inspect layouts
python scripts/pearl_control.py switch  --channel 2 --layout speaker
```
