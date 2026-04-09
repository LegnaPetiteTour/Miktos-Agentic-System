"""
SessionCoordinator — Phase 4c coordinator agent.

Receives a recording_ready message, dispatches three workers in parallel,
aggregates their results into a session artifact, and posts session_complete
back to the originating agent.

Architecture contract:
  - Coordinator decomposes the goal into named subtask slots
  - Each slot maps to exactly one worker
  - Workers run in parallel via ThreadPoolExecutor(max_workers=3)
  - Aggregation fills slots with worker results — deterministic, no inference
  - If a required slot fails after max_worker_retries: exit_reason = "partial_failure"
  - If an optional slot fails: session continues, gap noted in artifact
  - Coordinator never executes domain logic itself
  - Coordinator always posts a completion message (success or partial_failure)

Slot definitions:
  organize   (required)  KosmosWorker    — classify and propose file path
  thumbnail  (optional)  ThumbnailWorker — extract first-frame JPEG
  metadata   (required)  MetadataWorker  — write session.json

Message lifecycle:
  pending → dispatched → acknowledged → completed
                      ↘ failed → retrying → completed
                                          ↘ exhausted
"""

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from engine.coordinator.workers import KosmosWorker, MetadataWorker, ThumbnailWorker
from engine.messaging.bus import MessageBus
from engine.messaging.models import AgentMessage


class SessionCoordinator:
    """
    Coordinator for organizing a single recording session.

    Dispatches three workers in parallel, aggregates results,
    and posts session_complete back to the originating agent.
    """

    def __init__(
        self,
        bus: MessageBus,
        sessions_dir: str | Path = "data/sessions",
        max_worker_retries: int = 2,
        agent_id: str = "session_coordinator",
    ) -> None:
        self.bus = bus
        self.sessions_dir = Path(sessions_dir)
        self.max_worker_retries = max_worker_retries
        self.agent_id = agent_id

    def handle(self, message: AgentMessage) -> dict[str, Any]:
        """
        Process one recording_ready message.
        Returns the session artifact dict.
        """
        payload = message.payload
        file_path = payload.get("file_path") or payload.get("recordings_path", "")
        scene = payload.get("scene", "")
        trigger_run_id = payload.get("trigger_run_id", message.run_id)

        session_id = uuid.uuid4().hex[:12]
        output_dir = self.sessions_dir / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------------------------
        # Define subtask slots
        # ------------------------------------------------------------------
        slots: dict[str, dict[str, Any]] = {
            "organize": {
                "worker": KosmosWorker(),
                "required": True,
                "payload": {
                    "file_path": file_path,
                    "output_dir": str(output_dir),
                },
            },
            "thumbnail": {
                "worker": ThumbnailWorker(),
                "required": False,
                "payload": {
                    "file_path": file_path,
                    "output_dir": str(output_dir),
                },
            },
            "metadata": {
                "worker": MetadataWorker(),
                "required": True,
                "payload": {
                    "file_path": file_path,
                    "output_dir": str(output_dir),
                    "session_id": session_id,
                    "scene": scene,
                    "trigger_run_id": trigger_run_id,
                    "thumbnail_path": str(output_dir / "thumbnail.jpg"),
                    "category": "",  # filled after organize completes
                },
            },
        }

        # ------------------------------------------------------------------
        # Dispatch all slots in parallel with retry for required slots
        # ------------------------------------------------------------------
        results: dict[str, dict[str, Any]] = {}

        def _run_with_retry(
            slot_name: str, slot: dict[str, Any]
        ) -> tuple[str, dict[str, Any]]:
            worker = slot["worker"]
            slot_payload = slot["payload"]
            required = slot["required"]
            last_result: dict[str, Any] = {}

            for attempt in range(1 + self.max_worker_retries):
                self.bus.append_log(
                    event="DISPATCHED" if attempt == 0 else "RETRYING",
                    from_agent=self.agent_id,
                    to_agent=worker.name,
                    message_type=slot_name,
                    message_id=session_id,
                    notes=f"attempt {attempt + 1}",
                )
                last_result = worker.run(slot_payload)
                if last_result.get("success"):
                    self.bus.append_log(
                        event="COMPLETED",
                        from_agent=worker.name,
                        to_agent=self.agent_id,
                        message_type=slot_name,
                        message_id=session_id,
                    )
                    return slot_name, last_result
                else:
                    self.bus.append_log(
                        event="FAILED",
                        from_agent=worker.name,
                        to_agent=self.agent_id,
                        message_type=slot_name,
                        message_id=session_id,
                        notes=last_result.get("error", "unknown error"),
                    )
                    if not required:
                        break  # optional: don't retry

            return slot_name, last_result

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(_run_with_retry, name, slot): name
                for name, slot in slots.items()
            }
            for future in as_completed(futures):
                slot_name, result = future.result()
                results[slot_name] = result

        # ------------------------------------------------------------------
        # Patch metadata payload with organize result (category)
        # ------------------------------------------------------------------
        organize_result = results.get("organize", {})
        if organize_result.get("success") and organize_result.get("category"):
            # Re-run metadata with category filled in — run synchronously post-collect
            meta_slot = slots["metadata"]
            meta_slot["payload"]["category"] = organize_result["category"]
            _, meta_result = _run_with_retry("metadata", meta_slot)
            results["metadata"] = meta_result

        # ------------------------------------------------------------------
        # Determine exit_reason
        # ------------------------------------------------------------------
        failed_required: list[str] = []
        for slot_name, slot in slots.items():
            if slot["required"] and not results.get(slot_name, {}).get("success"):
                failed_required.append(slot_name)

        exit_reason = "partial_failure" if failed_required else "success"

        # ------------------------------------------------------------------
        # Build session artifact
        # ------------------------------------------------------------------
        artifact: dict[str, Any] = {
            "session_id": session_id,
            "output_dir": str(output_dir),
            "file_path": file_path,
            "scene": scene,
            "trigger_run_id": trigger_run_id,
            "exit_reason": exit_reason,
            "failed_slots": failed_required,
            "slots": {
                name: {
                    "success": results.get(name, {}).get("success", False),
                    "required": slots[name]["required"],
                    **{
                        k: v
                        for k, v in results.get(name, {}).items()
                        if k != "success"
                    },
                }
                for name in slots
            },
        }

        # ------------------------------------------------------------------
        # Post session_complete back to originating agent
        # ------------------------------------------------------------------
        reply = self.bus.post(
            from_agent=self.agent_id,
            to_agent=message.from_agent,
            message_type="session_complete",
            payload=artifact,
            run_id=trigger_run_id,
        )
        self.bus.append_log(
            event="POSTED",
            from_agent=self.agent_id,
            to_agent=message.from_agent,
            message_type="session_complete",
            message_id=reply.message_id,
            notes=exit_reason,
        )

        return artifact
