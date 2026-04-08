# StreamLab Test Fixtures

No file fixtures are needed for the StreamLab domain.

StreamLab tests operate in two modes:

| Test | Data source |
|---|---|
| `test_obs_connection_live` | Live OBS WebSocket (skipped if OBS not running) |
| `test_alert_classifier_stream_down` | Inline dict literal in test file |
| `test_alert_classifier_warning_routes_to_review_queue` | Inline dict literal + `MockOBSMonitorTool` |
| `test_streamlab_full_loop_engine_unchanged` | `MockOBSMonitorTool` with injected stream_down item |

Unlike the `file_analyzer` (file stubs) and `kosmos` (real JPEG/PNG with EXIF)
domains, StreamLab uses no file system fixtures because its inputs — OBS metric
snapshots — are either fetched live from OBS or constructed inline as dicts.

The `MockOBSMonitorTool` (defined in `test_streamlab_domain.py`) is the
equivalent of the media fixture folder: it provides deterministic, repeatable
input to the engine without requiring network access.
