"""
PostStreamCoordinator — Phase 5 post-stream closure engine.

Multi-stage execution with inter-stage payload enrichment:

  Stage 1 (parallel):  backup_verify   youtube_en    audio_extract
                            ↓               ↓               ↓
  Stage 2 (parallel):  translate       transcript
     (translate  ← youtube_en title + description)
     (transcript ← audio_extract mp3_path)
                            ↓               ↓
  Stage 3 (parallel):  youtube_fr      file_rename
     (youtube_fr  ← translate title_fr + description_fr)
     (file_rename ← all prior paths + event_name)
                            ↓
  Stage 4 (optional):  notify
     (notify ← transcript_path + final_folder + session metadata)

Rules:
  - If any required slot in Stage 1 fails: stop immediately → partial_failure.
  - Optional slots (notify) never block the session.
  - Each stage receives the merged results of all prior stages as payload enrichment.
  - Workers are independent: they receive only the keys they need.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

from domains.streamlab_post.workers.audio_worker import AudioExtractWorker
from domains.streamlab_post.workers.backup_worker import BackupVerificationWorker
from domains.streamlab_post.workers.notify_worker import NotificationWorker
from domains.streamlab_post.workers.rename_worker import FileRenameWorker
from domains.streamlab_post.workers.report_worker import ReportWorker
from domains.streamlab_post.workers.transcript_worker import TranscriptWorker
from domains.streamlab_post.workers.translation_worker import TranslationWorker
from domains.streamlab_post.workers.youtube_worker import YouTubeWorker


class PostStreamCoordinator:
    """
    Coordinator for post-stream closure.

    Runs four sequential stages with intra-stage parallelism.
    Enriches payload between stages using prior stage results.
    """

    def __init__(
        self,
        sessions_dir: str | Path = "data/sessions",
        max_workers: int = 4,
        agent_id: str = "post_stream_processor",
    ) -> None:
        self.sessions_dir = Path(sessions_dir)
        self.max_workers = max_workers
        self.agent_id = agent_id

    def run(
        self, payload: dict[str, Any], session_config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute the full four-stage post-stream closure.

        Args:
          payload:        Message payload from the recording_stopped event.
          session_config: Parsed session_config.yaml content.

        Returns a session artifact dict with all slot results, timing,
        exit_reason ("success" | "partial_failure"), and final paths.
        """
        session_id = uuid.uuid4().hex[:12]
        output_dir = self.sessions_dir / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        event_name = session_config.get("event_name", "Event")
        session_date = (
            session_config.get("stream_date", "") or date.today().isoformat()
        )
        recording_cfg = session_config.get("recording", {})
        youtube_cfg = session_config.get("youtube", {})
        elevenlabs_cfg = session_config.get("elevenlabs", {})
        notification_cfg = session_config.get("notification", {})

        file_path = payload.get("file_path", "")
        if not file_path:
            # recordings_path may be a folder — find the most recent recording
            recordings_path = Path(payload.get("recordings_path", ""))
            if recordings_path.is_dir():
                candidates = sorted(
                    [
                        f for f in recordings_path.iterdir()
                        if f.suffix.lower() in (".mkv", ".mov", ".mp4", ".flv")
                    ],
                    key=lambda f: f.stat().st_mtime,
                    reverse=True,
                )
                file_path = str(candidates[0]) if candidates else ""
            else:
                file_path = str(recordings_path)
        dry_run = payload.get("dry_run", False)

        # Accumulated results — enriched after each stage
        accumulated: dict[str, Any] = {}
        all_results: dict[str, dict[str, Any]] = {}

        # ──────────────────────────────────────────────────────────────
        # Stage 1 — Parallel: backup_verify, youtube_en, audio_extract
        # ──────────────────────────────────────────────────────────────
        stage1_slots = {
            "backup_verify": {
                "worker": BackupVerificationWorker(),
                "required": True,
                "payload": {
                    "file_path": file_path,
                    "min_size_bytes": recording_cfg.get("min_size_bytes", 1_048_576),
                    "dry_run": dry_run,
                },
            },
            "youtube_en": {
                "worker": YouTubeWorker(),
                "required": True,
                "payload": {
                    "language": "en",
                    "channel_id": youtube_cfg.get("en", {}).get("channel_id", ""),
                    "video_id": youtube_cfg.get("en", {}).get("video_id", ""),
                    "title": youtube_cfg.get("en", {}).get("title", ""),
                    "description": youtube_cfg.get("en", {}).get("description", ""),
                    "playlist_id": youtube_cfg.get("en", {}).get("playlist_id", ""),
                    "visibility": youtube_cfg.get("en", {}).get("visibility", "public"),
                    "dry_run": dry_run,
                },
            },
            "audio_extract": {
                "worker": AudioExtractWorker(),
                "required": True,
                "payload": {
                    "file_path": file_path,
                    "output_dir": str(output_dir),
                    "dry_run": dry_run,
                },
            },
        }

        stage1_results = self._run_stage("Stage 1", stage1_slots, session_id)
        all_results.update(stage1_results)
        accumulated.update(
            {k: v for result in stage1_results.values() for k, v in result.items()}
        )

        # Check Stage 1 required failures
        stage1_failures = [
            name
            for name, slot in stage1_slots.items()
            if slot["required"] and not stage1_results.get(name, {}).get("success")
        ]
        if stage1_failures:
            return self._build_artifact(
                session_id=session_id,
                output_dir=output_dir,
                event_name=event_name,
                session_date=session_date,
                all_results=all_results,
                exit_reason="partial_failure",
                failure_reason=(
                    f"Stage 1 required slots failed: {', '.join(stage1_failures)}"
                ),
            )

        # ──────────────────────────────────────────────────────────────
        # Stage 2 — Parallel: translate, transcript
        # ──────────────────────────────────────────────────────────────
        en_result = stage1_results.get("youtube_en", {})
        audio_result = stage1_results.get("audio_extract", {})

        stage2_slots = {
            "translate": {
                "worker": TranslationWorker(),
                "required": False,
                "payload": {
                    "title_en": en_result.get("title", ""),
                    "description_en": en_result.get("description", ""),
                    "dry_run": dry_run,
                },
            },
            "transcript": {
                "worker": TranscriptWorker(),
                "required": False,
                "payload": {
                    "mp3_path": audio_result.get("mp3_path", ""),
                    "output_dir": str(output_dir),
                    "language_code": elevenlabs_cfg.get("language_code", "fr"),
                    "dry_run": dry_run,
                },
            },
        }

        stage2_results = self._run_stage("Stage 2", stage2_slots, session_id)
        all_results.update(stage2_results)
        accumulated.update(
            {k: v for result in stage2_results.values() for k, v in result.items()}
        )

        # ──────────────────────────────────────────────────────────────
        # Stage 3 — Parallel: youtube_fr, file_rename
        # ──────────────────────────────────────────────────────────────
        translate_result = stage2_results.get("translate", {})
        transcript_result = stage2_results.get("transcript", {})

        stage3_slots = {
            "youtube_fr": {
                "worker": YouTubeWorker(),
                "required": False,
                "payload": {
                    "language": "fr",
                    "channel_id": youtube_cfg.get("fr", {}).get("channel_id", ""),
                    "video_id": youtube_cfg.get("fr", {}).get("video_id", ""),
                    "title": translate_result.get("title_fr", ""),
                    "description": translate_result.get("description_fr", ""),
                    "playlist_id": youtube_cfg.get("fr", {}).get("playlist_id", ""),
                    "visibility": youtube_cfg.get("fr", {}).get("visibility", "public"),
                    "dry_run": dry_run,
                },
            },
            "file_rename": {
                "worker": FileRenameWorker(),
                "required": False,
                "payload": {
                    "recording_path": file_path,
                    "mp3_path": audio_result.get("mp3_path", ""),
                    "transcript_path": transcript_result.get("transcript_path", ""),
                    "thumbnail_path": str(output_dir / "thumbnail.jpg"),
                    "event_name": event_name,
                    "session_date": session_date,
                    "sessions_dir": str(self.sessions_dir),
                    "dry_run": dry_run,
                },
            },
        }

        stage3_results = self._run_stage("Stage 3", stage3_slots, session_id)
        all_results.update(stage3_results)
        accumulated.update(
            {k: v for result in stage3_results.values() for k, v in result.items()}
        )

        # ──────────────────────────────────────────────────────────────
        # Stage 4 (optional) — notify
        # ──────────────────────────────────────────────────────────────
        rename_result = stage3_results.get("file_rename", {})
        backup_result = stage1_results.get("backup_verify", {})

        stage4_slots = {
            "notify": {
                "worker": NotificationWorker(),
                "required": False,
                "payload": {
                    "transcript_path": transcript_result.get("transcript_path", ""),
                    "final_folder": rename_result.get("final_folder", str(output_dir)),
                    "event_name": event_name,
                    "duration_seconds": backup_result.get("duration_seconds", 0),
                    "date": session_date,
                    "recipients_email": notification_cfg.get(
                        "recipients_email", []
                    ),
                    "recipients_teams": notification_cfg.get(
                        "recipients_teams", ""
                    ),
                    "subject_template": notification_cfg.get(
                        "subject_template",
                        "Transcript — {event_name} ({date})",
                    ),
                    "body_template": notification_cfg.get("body_template", ""),
                    "dry_run": dry_run,
                },
            },
            "report": {
                "worker": ReportWorker(),
                "required": False,
                "payload": {
                    "event_name":          event_name,
                    "session_date":        session_date,
                    "session_id":          session_id,
                    "duration_seconds":    backup_result.get("duration_seconds", 0),
                    "file_size_bytes":     backup_result.get("file_size_bytes", 0),
                    "mp3_path":            audio_result.get("mp3_path", ""),
                    "video_id_en":         en_result.get("video_id", ""),
                    "title_en":            en_result.get("title", ""),
                    "video_id_fr":         stage3_results.get("youtube_fr", {}).get("video_id", ""),
                    "title_fr":            translate_result.get("title_fr", ""),
                    "transcript_path":     transcript_result.get("transcript_path", ""),
                    "word_count":          transcript_result.get("word_count", 0),
                    "detected_languages":  transcript_result.get("detected_languages", []),
                    "final_folder":        rename_result.get("final_folder", str(output_dir)),
                    "slots":               all_results,
                    "dry_run":             dry_run,
                },
            },
        }

        stage4_results = self._run_stage("Stage 4", stage4_slots, session_id)
        all_results.update(stage4_results)

        return self._build_artifact(
            session_id=session_id,
            output_dir=output_dir,
            event_name=event_name,
            session_date=session_date,
            all_results=all_results,
            exit_reason="success",
            failure_reason="",
        )

    def _run_stage(
        self,
        stage_name: str,
        slots: dict[str, dict[str, Any]],
        session_id: str,
    ) -> dict[str, dict[str, Any]]:
        """
        Run all slots in this stage in parallel.
        Returns results dict {slot_name: result_dict}.
        """
        results: dict[str, dict[str, Any]] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    slot["worker"].run, slot["payload"]
                ): slot_name
                for slot_name, slot in slots.items()
            }
            for future in as_completed(futures):
                slot_name = futures[future]
                try:
                    results[slot_name] = future.result()
                except Exception as exc:
                    results[slot_name] = {
                        "success": False,
                        "error": f"Unhandled exception in {slot_name}: {exc}",
                    }

        return results

    def _build_artifact(
        self,
        session_id: str,
        output_dir: Path,
        event_name: str,
        session_date: str,
        all_results: dict[str, dict[str, Any]],
        exit_reason: str,
        failure_reason: str,
    ) -> dict[str, Any]:
        """Build and return the final session artifact."""
        rename_result = all_results.get("file_rename", {})
        backup_result = all_results.get("backup_verify", {})
        transcript_result = all_results.get("transcript", {})

        return {
            "session_id": session_id,
            "event_name": event_name,
            "session_date": session_date,
            "exit_reason": exit_reason,
            "failure_reason": failure_reason,
            "output_dir": str(output_dir),
            "final_folder": rename_result.get("final_folder", str(output_dir)),
            "duration_seconds": backup_result.get("duration_seconds", 0),
            "transcript_path": transcript_result.get("transcript_path", ""),
            "slots": all_results,
        }
