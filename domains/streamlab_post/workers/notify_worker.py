"""
NotificationWorker — Phase 5 post-stream closure.

Sends the transcript notification via Teams webhook and/or email
via the Microsoft Graph API. Both channels are optional — if neither
is configured the slot succeeds silently.

This is the optional Stage 4 slot. Its failure never blocks the session.
"""

import base64
import os
from pathlib import Path

import requests


_MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024  # 3 MB Graph API safe limit


class NotificationWorker:
    """
    Send transcript notification via Teams webhook and/or email.

    Teams:  POST adaptive card to TEAMS_WEBHOOK_URL.
    Email:  POST /v1.0/users/{from_email}/sendMail via Microsoft Graph API.
            Uses MSAL ConfidentialClientApplication for auth.

    If no notification channels configured, returns success: True,
    notes: "no notification channels configured — skipped".

    Never raises — optional slot that never blocks the session.
    """

    name = "notification_worker"
    _GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
    _GRAPH_SEND_URL = (
        "https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
    )

    def run(self, payload: dict) -> dict:
        """
        Send notification via Teams and/or email.

        Payload keys:
          transcript_path (str)       — path to transcript file
          final_folder (str)          — session folder path
          event_name (str)            — event name for subject/body
          duration_seconds (float)    — session duration
          date (str)                  — session date YYYY-MM-DD
          recipients_email (list)     — email addresses to notify
          recipients_teams (str)      — Teams webhook URL (single URL)
          subject_template (str)      — subject format string
          body_template (str)         — body format string
          dry_run (bool)              — if True, simulate sending

        Returns:
          {success, sent_via, recipient_count, notes}
        """
        transcript_path = payload.get("transcript_path", "")
        final_folder = payload.get("final_folder", "")
        event_name = payload.get("event_name", "Stream")
        duration_seconds = payload.get("duration_seconds", 0)
        session_date = payload.get("date", "")
        recipients_email: list[str] = payload.get("recipients_email", [])
        recipients_teams: str = payload.get("recipients_teams", "")
        subject_template = payload.get(
            "subject_template", "Transcript — {event_name} ({date})"
        )
        body_template = payload.get(
            "body_template",
            (
                "The transcript for {event_name} ({date}) is ready.\n"
                "Session folder: {final_folder}\n"
                "Transcript: {transcript_path}\n"
                "Duration: {duration}s"
            ),
        )
        dry_run = payload.get("dry_run", False)

        teams_url = recipients_teams or os.environ.get("TEAMS_WEBHOOK_URL", "")
        email_recipients = [r for r in recipients_email if r]

        if not teams_url and not email_recipients:
            return {
                "success": True,
                "sent_via": [],
                "recipient_count": 0,
                "notes": "no notification channels configured — skipped",
            }

        template_vars = {
            "event_name": event_name,
            "date": session_date,
            "final_folder": final_folder,
            "transcript_path": transcript_path,
            "duration": int(duration_seconds),
        }
        try:
            subject = subject_template.format(**template_vars)
            body = body_template.format(**template_vars)
        except KeyError:
            subject = f"Transcript — {event_name}"
            body = f"Session complete.\nFolder: {final_folder}"

        sent_via: list[str] = []
        recipient_count = 0
        notes_parts: list[str] = []

        if dry_run:
            if teams_url:
                sent_via.append("teams")
            if email_recipients:
                sent_via.append("email")
                recipient_count = len(email_recipients)
            return {
                "success": True,
                "dry_run": True,
                "sent_via": sent_via,
                "recipient_count": recipient_count,
                "notes": "dry_run — no messages actually sent",
            }

        # Teams webhook
        if teams_url:
            teams_result = self._send_teams(teams_url, body)
            if teams_result:
                sent_via.append("teams")
            else:
                notes_parts.append("Teams delivery failed")

        # Email via Microsoft Graph
        if email_recipients:
            email_result = self._send_email(
                recipients=email_recipients,
                subject=subject,
                body=body,
                transcript_path=transcript_path,
            )
            if email_result["sent"]:
                sent_via.append("email")
                recipient_count = len(email_recipients)
            else:
                notes_parts.append(f"Email delivery failed: {email_result['error']}")

        return {
            "success": True,  # optional slot — never fails the session
            "sent_via": sent_via,
            "recipient_count": recipient_count,
            "notes": "; ".join(notes_parts) if notes_parts else "ok",
        }

    def _send_teams(self, webhook_url: str, message: str) -> bool:
        """Send adaptive card to Teams webhook. Returns True on success."""
        body = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "type": "AdaptiveCard",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": message,
                                "wrap": True,
                            }
                        ],
                        "$schema": (
                            "http://adaptivecards.io/schemas/adaptive-card.json"
                        ),
                        "version": "1.2",
                    },
                }
            ],
        }
        try:
            resp = requests.post(webhook_url, json=body, timeout=15)
            return resp.status_code in (200, 202)
        except requests.RequestException:
            return False

    def _send_email(
        self,
        recipients: list[str],
        subject: str,
        body: str,
        transcript_path: str,
    ) -> dict:
        """Send email via Microsoft Graph API. Returns {sent, error}."""
        client_id = os.environ.get("OUTLOOK_CLIENT_ID", "")
        client_secret = os.environ.get("OUTLOOK_CLIENT_SECRET", "")
        tenant_id = os.environ.get("OUTLOOK_TENANT_ID", "")
        from_email = os.environ.get("NOTIFICATION_FROM_EMAIL", "")

        if not client_id:
            return {"sent": False, "error": "OUTLOOK_CLIENT_ID not configured"}

        try:
            import msal
        except ImportError:
            return {
                "sent": False,
                "error": "msal not installed — run: pip install msal",
            }

        try:
            app = msal.ConfidentialClientApplication(
                client_id=client_id,
                client_credential=client_secret,
                authority=f"https://login.microsoftonline.com/{tenant_id}",
            )
            token_result = app.acquire_token_for_client(
                scopes=self._GRAPH_SCOPE
            )
        except Exception as exc:
            return {"sent": False, "error": f"MSAL auth failed: {exc}"}

        if not token_result or "access_token" not in token_result:
            error = (token_result or {}).get(
                "error_description", "token acquisition failed"
            )
            return {"sent": False, "error": error}

        access_token = token_result["access_token"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        to_recipients = [
            {"emailAddress": {"address": r}} for r in recipients
        ]

        message_body: dict = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": to_recipients,
            }
        }

        # Attach transcript if it exists and is within size limit
        transcript_file = Path(transcript_path)
        if transcript_file.exists():
            file_bytes = transcript_file.read_bytes()
            if len(file_bytes) <= _MAX_ATTACHMENT_BYTES:
                message_body["message"]["attachments"] = [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": transcript_file.name,
                        "contentBytes": base64.b64encode(file_bytes).decode(),
                    }
                ]
            else:
                # File too large — mention path in body instead
                message_body["message"]["body"]["content"] += (
                    f"\n\nTranscript file (too large to attach): {transcript_path}"
                )

        try:
            resp = requests.post(
                self._GRAPH_SEND_URL.format(from_email=from_email),
                headers=headers,
                json=message_body,
                timeout=30,
            )
            if resp.status_code in (200, 202):
                return {"sent": True, "error": ""}
            return {
                "sent": False,
                "error": f"Graph API {resp.status_code}: {resp.text[:200]}",
            }
        except requests.RequestException as exc:
            return {"sent": False, "error": f"Graph request failed: {exc}"}
