"""
report_worker.py — Generate a self-contained HTML session report.

Runs in Stage 4 alongside notify. Never raises exceptions.
Writes {session_name}_report.html to final_folder.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


class ReportWorker:
    name = "report"

    def run(self, payload: dict) -> dict:
        """
        Generate session_report.html in final_folder.

        Returns:
          {"success": True,  "report_path": str}  on success
          {"success": False, "error": str}         on failure
        """
        try:
            return self._run(payload)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self, payload: dict) -> dict:
        dry_run = payload.get("dry_run", False)
        final_folder = payload.get("final_folder", "")

        if not final_folder:
            return {"success": False, "error": "final_folder is required"}

        folder = Path(final_folder)
        session_name = folder.name

        # Determine output path
        if len(session_name) > 12 and "_" in session_name:
            # Named session folder e.g. 2026-04-15_Council-Meeting_001
            report_path = folder / f"{session_name}_report.html"
        else:
            # Hex UUID fallback
            report_path = folder / "session_report.html"

        if dry_run:
            return {"success": True, "report_path": str(report_path)}

        if not folder.exists():
            return {
                "success": False,
                "error": f"final_folder does not exist: {final_folder}",
            }

        html = self._render_html(payload, report_path)
        report_path.write_text(html, encoding="utf-8")
        return {"success": True, "report_path": str(report_path)}

    # ------------------------------------------------------------------
    # HTML generation
    # ------------------------------------------------------------------

    def _render_html(self, payload: dict, report_path: Path) -> str:
        event_name = payload.get("event_name", "")
        session_date = payload.get("session_date", "")
        duration_seconds = float(payload.get("duration_seconds", 0))
        file_size_bytes = int(payload.get("file_size_bytes", 0))
        video_id_en = payload.get("video_id_en", "")
        video_id_fr = payload.get("video_id_fr", "")
        transcript_path = payload.get("transcript_path", "")
        word_count = int(payload.get("word_count", 0))
        detected_languages = payload.get("detected_languages", [])
        slots: dict = payload.get("slots", {})
        final_folder = payload.get("final_folder", "")

        duration_str = _format_duration(duration_seconds)
        overall_ok = all(
            v.get("success", False) or v.get("skipped", False)
            for v in slots.values()
        )
        status_badge = "✅ Complete" if overall_ok else "❌ Partial Failure"
        badge_color = "#198754" if overall_ok else "#dc3545"
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        slot_rows = _render_slot_rows(
            slots, video_id_en, video_id_fr, report_path
        )
        files_rows = _render_files_rows(final_folder)
        transcript_section = _render_transcript_section(
            transcript_path, word_count, detected_languages
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(event_name)} — Session Report</title>
<style>
  :root {{
    --bg:         #f8f9fa;
    --surface:    #ffffff;
    --border:     #dee2e6;
    --text:       #212529;
    --text-muted: #6c757d;
    --green:      #198754;
    --red:        #dc3545;
    --blue:       #0d6efd;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 32px 16px;
  }}
  .container {{ max-width: 800px; margin: 0 auto; }}
  header {{ background: var(--surface); border: 1px solid var(--border);
            border-radius: 8px; padding: 24px; margin-bottom: 24px; }}
  header h1 {{ font-size: 1.75rem; margin-bottom: 6px; }}
  .meta {{ color: var(--text-muted); font-size: 0.95rem; margin-bottom: 12px; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 4px;
            background: {badge_color}; color: #fff; font-weight: 600; font-size: 0.95rem; }}
  section {{ background: var(--surface); border: 1px solid var(--border);
             border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
  section h2 {{ font-size: 1.1rem; margin-bottom: 14px; border-bottom: 1px solid var(--border);
                padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th {{ text-align: left; padding: 8px 10px; background: var(--bg);
        border-bottom: 2px solid var(--border); color: var(--text-muted);
        font-weight: 600; text-transform: uppercase; font-size: 0.78rem; letter-spacing: 0.04em; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:nth-child(odd) td {{ background: #fdfdfe; }}
  a {{ color: var(--blue); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .error {{ color: var(--red); font-size: 0.875em; }}
  .muted {{ color: var(--text-muted); }}
  pre {{ background: var(--bg); border: 1px solid var(--border); border-radius: 4px;
         padding: 12px; font-size: 0.85rem; white-space: pre-wrap; word-break: break-word; }}
  footer {{ text-align: center; color: var(--text-muted); font-size: 0.8rem; margin-top: 24px; }}
</style>
</head>
<body>
<div class="container">

  <header>
    <h1>{_esc(event_name)}</h1>
    <p class="meta">{_esc(session_date)} — {_esc(duration_str)}
      {f"&nbsp;·&nbsp; {_fmt_bytes(file_size_bytes)}" if file_size_bytes else ""}
    </p>
    <span class="badge">{status_badge}</span>
  </header>

  <section>
    <h2>Pipeline</h2>
    <table>
      <thead><tr><th>Slot</th><th>Status</th><th>Detail</th></tr></thead>
      <tbody>
        {slot_rows}
      </tbody>
    </table>
  </section>

  <section>
    <h2>Files Produced</h2>
    <table>
      <thead><tr><th>File</th><th>Size</th></tr></thead>
      <tbody>
        {files_rows}
      </tbody>
    </table>
  </section>

  {transcript_section}

  <footer>Generated by Miktos — {generated_at}</footer>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLOT_ORDER = [
    "backup_verify",
    "youtube_en",
    "audio_extract",
    "translate",
    "transcript",
    "youtube_fr",
    "file_rename",
    "notify",
    "report",
]


def _render_slot_rows(
    slots: dict,
    video_id_en: str,
    video_id_fr: str,
    report_path: Path,
) -> str:
    rows = []
    present = list(slots.keys())
    order = [s for s in _SLOT_ORDER if s in present] + [
        s for s in present if s not in _SLOT_ORDER
    ]

    for slot_name in order:
        result = slots[slot_name]
        success = result.get("success", False)
        skipped = result.get("skipped", False)
        error = result.get("error") or ""

        if skipped:
            status_icon = "—"
            detail = '<span class="muted">skipped</span>'
        elif success:
            status_icon = "✅"
            detail = _slot_detail(slot_name, result, video_id_en, video_id_fr)
        else:
            status_icon = "❌"
            detail = f'<span class="error">{_esc(error or "failed")}</span>'

        rows.append(
            f"<tr><td>{_esc(slot_name)}</td>"
            f"<td>{status_icon}</td>"
            f"<td>{detail}</td></tr>"
        )

    # Add report row (self-referential)
    report_name = report_path.name
    rows.append(
        f"<tr><td>report</td><td>✅</td>"
        f"<td>{_esc(report_name)}</td></tr>"
    )

    return "\n        ".join(rows)


def _slot_detail(
    slot_name: str, result: dict, video_id_en: str, video_id_fr: str
) -> str:
    if slot_name == "backup_verify":
        size = _fmt_bytes(result.get("file_size_bytes", 0))
        dur = result.get("duration_seconds", 0)
        return f"{size}, {int(dur)}s"

    if slot_name == "youtube_en":
        title = _esc(result.get("title", ""))
        vid = video_id_en
        if vid:
            link = f'<a href="https://youtu.be/{_esc(vid)}" target="_blank">youtu.be/{_esc(vid)}</a>'
            return f"{title} → {link}" if title else link
        return title

    if slot_name == "audio_extract":
        mp3 = result.get("mp3_path", "")
        if mp3:
            size = _fmt_bytes(os.path.getsize(mp3)) if os.path.exists(mp3) else ""
            name = Path(mp3).name
            return f"{_esc(name)}{f' ({size})' if size else ''}"
        return ""

    if slot_name == "translate":
        return _esc(result.get("title_fr", ""))

    if slot_name == "transcript":
        wc = result.get("word_count", 0)
        langs = result.get("detected_languages", [])
        lang_str = (", ".join(str(lg) for lg in langs)) if langs else ""
        parts = [f"{wc} word{'s' if wc != 1 else ''}"]
        if lang_str:
            parts.append(lang_str)
        return _esc(" — ".join(parts))

    if slot_name == "youtube_fr":
        vid = video_id_fr
        title_fr = _esc(result.get("title", ""))
        if vid:
            link = f'<a href="https://youtu.be/{_esc(vid)}" target="_blank">youtu.be/{_esc(vid)}</a>'
            return f"{title_fr} → {link}" if title_fr else link
        return title_fr

    if slot_name == "file_rename":
        folder = result.get("final_folder", "")
        return _esc(Path(folder).name) if folder else ""

    if slot_name == "notify":
        return '<span class="muted">sent</span>'

    return ""


def _render_files_rows(final_folder: str) -> str:
    if not final_folder:
        return "<tr><td colspan='2' class='muted'>—</td></tr>"
    folder = Path(final_folder)
    if not folder.exists():
        return "<tr><td colspan='2' class='muted'>folder not found</td></tr>"
    files = sorted(folder.iterdir(), key=lambda f: f.name)
    if not files:
        return "<tr><td colspan='2' class='muted'>no files</td></tr>"
    rows = []
    for f in files:
        if f.is_file():
            size = _fmt_bytes(f.stat().st_size) if f.stat().st_size >= 1024 else ""
            rows.append(
                f"<tr><td>{_esc(f.name)}</td>"
                f"<td class='muted'>{_esc(size)}</td></tr>"
            )
    return "\n        ".join(rows) if rows else "<tr><td colspan='2' class='muted'>—</td></tr>"


def _render_transcript_section(
    transcript_path: str, word_count: int, detected_languages: list
) -> str:
    if not transcript_path:
        return ""
    tp = Path(transcript_path)
    if not tp.exists():
        return ""
    content = tp.read_text(encoding="utf-8").strip()
    if not content:
        return ""
    preview = content[:200]
    ellipsis = "…" if len(content) > 200 else ""
    return f"""  <section>
    <h2>Transcript Preview</h2>
    <pre>{_esc(preview)}{ellipsis}</pre>
    <p class="muted" style="margin-top:8px;font-size:0.85rem;">Full transcript: {_esc(tp.name)}</p>
  </section>"""


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    if total <= 0:
        return "0s"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _fmt_bytes(n: int) -> str:
    if n <= 0:
        return ""
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


def _esc(s: object) -> str:
    """HTML-escape a value."""
    text = str(s) if s is not None else ""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )
