"""
reset_layout_log.py — Remove stale layout entries from layout_log.jsonl.

Strips entries whose layout no longer exists on Pearl (identified by name or
layout_id) and rewrites the file in-place.  A backup is written alongside the
original before any changes are made.

Usage:
    # Preview what would be removed (no changes written)
    python scripts/reset_layout_log.py --dry-run

    # Remove all entries for layout_name "Interpreter View"
    python scripts/reset_layout_log.py --stale-name "Interpreter View"

    # Remove all entries for layout_id 2
    python scripts/reset_layout_log.py --stale-id 2

    # Remove by name AND truncate everything before a given date
    python scripts/reset_layout_log.py --stale-name "Interpreter View" --before 2026-05-05

    # Nuke the whole file (fresh start)
    python scripts/reset_layout_log.py --clear-all
"""

import argparse
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAYOUT_LOG = REPO_ROOT / "data" / "logs" / "layout_log.jsonl"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Clean stale entries from layout_log.jsonl")
    p.add_argument("--stale-name", metavar="NAME", action="append", default=[],
                   help="Remove entries where layout_name matches NAME (repeatable)")
    p.add_argument("--stale-id", metavar="ID", action="append", default=[],
                   help="Remove entries where layout_id matches ID (repeatable)")
    p.add_argument("--before", metavar="YYYY-MM-DD",
                   help="Remove entries with ts strictly before this date")
    p.add_argument("--clear-all", action="store_true",
                   help="Remove ALL entries (empty the log)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be removed without writing anything")
    return p.parse_args()


def _is_stale(entry: dict, stale_names: list[str], stale_ids: list[str],
              before_date: date | None) -> bool:
    if stale_names and entry.get("layout_name") in stale_names:
        return True
    if stale_ids and str(entry.get("layout_id", "")) in [str(i) for i in stale_ids]:
        return True
    if before_date:
        raw_ts = entry.get("ts", "")
        try:
            entry_date = datetime.fromisoformat(raw_ts.rstrip("Z")).date()
            if entry_date < before_date:
                return True
        except ValueError:
            pass
    return False


def main() -> None:
    args = _parse_args()

    if not LAYOUT_LOG.exists():
        print(f"Nothing to do — {LAYOUT_LOG} does not exist.")
        sys.exit(0)

    if args.clear_all:
        if args.dry_run:
            lines = LAYOUT_LOG.read_text().splitlines()
            print(f"[dry-run] Would remove ALL {len(lines)} entries and empty the file.")
        else:
            backup = LAYOUT_LOG.with_suffix(".jsonl.bak")
            shutil.copy2(LAYOUT_LOG, backup)
            print(f"Backup written to {backup}")
            LAYOUT_LOG.write_text("")
            print("layout_log.jsonl cleared.")
        return

    before_date: date | None = None
    if args.before:
        try:
            before_date = date.fromisoformat(args.before)
        except ValueError:
            print(f"ERROR: --before value '{args.before}' is not a valid YYYY-MM-DD date.")
            sys.exit(1)

    raw_lines = LAYOUT_LOG.read_text().splitlines()
    kept: list[str] = []
    removed: list[str] = []

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)  # keep malformed lines untouched
            continue

        if _is_stale(entry, args.stale_name, args.stale_id, before_date):
            removed.append(line)
        else:
            kept.append(line)

    print(f"Entries total  : {len(raw_lines)}")
    print(f"Entries removed: {len(removed)}")
    print(f"Entries kept   : {len(kept)}")

    if removed:
        print("\nRemoved:")
        for r in removed:
            print(f"  {r}")

    if args.dry_run:
        print("\n[dry-run] No changes written.")
        return

    if not removed:
        print("Nothing to remove.")
        return

    backup = LAYOUT_LOG.with_suffix(".jsonl.bak")
    shutil.copy2(LAYOUT_LOG, backup)
    print(f"\nBackup written to {backup}")

    LAYOUT_LOG.write_text("\n".join(kept) + ("\n" if kept else ""))
    print(f"layout_log.jsonl rewritten ({len(kept)} entries kept).")


if __name__ == "__main__":
    main()
