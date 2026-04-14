"""
main_preflight.py — Miktos Pre-Flight Check entry point.

Run this before every stream to catch problems before they cause
post-stream failures.

Usage:
    python main_preflight.py            # live check (requires OBS running)
    python main_preflight.py --dry-run  # mock check (no live connections)

Exit codes:
    0 — READY TO STREAM (no failures; warnings are listed but non-blocking)
    1 — NOT READY (one or more hard failures detected)
"""

import argparse
import sys

from dotenv import load_dotenv

from domains.streamlab_post.pre_flight.checker import PreFlightChecker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Miktos Pre-Flight Check — verify system readiness before streaming.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Skip live connections and API calls. "
            "Returns mock ok for all checks. "
            "Use to verify the command runs on this machine."
        ),
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    checker = PreFlightChecker()
    results = checker.run(dry_run=args.dry_run)

    dry_label = "  [DRY RUN]" if args.dry_run else ""
    print(f"\n  Miktos Pre-Flight Check{dry_label}")
    print("  " + "─" * 39)

    for r in results:
        status = r["status"]
        if status == "ok":
            icon = "✅"
        elif status == "warn":
            icon = "⚠️ "
        else:
            icon = "❌"
        print(f"  {icon}  {r['message']}")

    print("  " + "─" * 39)

    failures = [r for r in results if r["status"] == "fail"]
    warnings = [r for r in results if r["status"] == "warn"]

    if failures:
        print(f"  NOT READY  ({len(failures)} error(s), {len(warnings)} warning(s))\n")
        sys.exit(1)
    else:
        print(f"  READY TO STREAM  ({len(warnings)} warning(s), 0 errors)\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
