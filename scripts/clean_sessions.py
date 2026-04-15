"""
clean_sessions.py — Archive hex-UUID test session folders from data/sessions/.

Production sessions (YYYY-MM-DD_*) are never touched.

Usage:
    python scripts/clean_sessions.py [--dry-run] [--archive] [--days N]
"""

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = REPO_ROOT / "data/sessions"
ARCHIVE_DIR = SESSIONS_DIR / "archive"

_PRODUCTION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_")


def _is_production(name: str) -> bool:
    return bool(_PRODUCTION_RE.match(name))


def _age_days(path: Path) -> int:
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return (datetime.now() - mtime).days


def run(dry_run: bool, archive_all: bool, days: int) -> int:
    if not SESSIONS_DIR.exists():
        print("data/sessions/ not found. Nothing to do.")
        return 0

    candidates = [
        p for p in SESSIONS_DIR.iterdir()
        if p.is_dir() and p.name != "archive" and not _is_production(p.name)
    ]

    if archive_all:
        to_archive = candidates
    else:
        to_archive = [p for p in candidates if _age_days(p) >= days]

    if not to_archive:
        print("Nothing to archive.")
        return 0

    # Production guard — should never trigger given the filter above,
    # but abort explicitly if somehow a production session snuck in.
    for p in to_archive:
        if _is_production(p.name):
            print(
                f"Error: would archive production session {p.name} — aborting.",
                file=sys.stderr,
            )
            return 1

    age_label = "all ages" if archive_all else f"older than {days} days"
    print(f"Found {len(to_archive)} test session(s) to archive ({age_label}):\n")
    for p in sorted(to_archive, key=lambda x: x.stat().st_mtime):
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        age = _age_days(p)
        print(f"  {p.name}   {mtime.strftime('%Y-%m-%d')}  ({age} day(s) old)")

    print()

    if dry_run:
        print("Dry run — no changes made.")
        return 0

    answer = input(
        f"Archive {len(to_archive)} session(s) to data/sessions/archive/? [y/N]: "
    ).strip().lower()
    if answer != "y":
        print("Aborted.")
        return 0

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for p in to_archive:
        shutil.move(str(p), str(ARCHIVE_DIR / p.name))

    print(f"✅  Archived {len(to_archive)} session(s).")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive test session folders from data/sessions/."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--archive", action="store_true",
        help="Archive all matching sessions regardless of age."
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Only archive sessions older than N days (default: 7)."
    )
    args = parser.parse_args()
    sys.exit(run(args.dry_run, args.archive, args.days))


if __name__ == "__main__":
    main()
