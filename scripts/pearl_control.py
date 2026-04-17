"""
pearl_control.py — CLI for live layout switching on Epiphan Pearl.

Lets the operator switch which layout is active on a Pearl channel in
real time during a stream, without touching the Pearl touch screen.

Credentials are read from environment variables (PEARL_HOST, PEARL_PORT,
PEARL_PASSWORD) via PearlClient — never stored in this file.

Usage
─────
  python scripts/pearl_control.py layouts --channel 2
  python scripts/pearl_control.py switch  --channel 2 --layout speaker
  python scripts/pearl_control.py switch  --channel 2 --layout 3
  python scripts/pearl_control.py status
  python scripts/pearl_control.py status  --channel 2

Subcommands
───────────
  layouts   List available layouts for a channel.
  switch    Activate a layout by name (fuzzy) or exact ID.
            Name matching is case-insensitive substring match.
            Exact ID wins over name match if both are possible.
  status    Show the currently active layout for one or all channels.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_REPO_ROOT / ".env")

# Layout switch log — read by the cockpit display to show active layouts per channel.
_LAYOUT_LOG = _REPO_ROOT / "data" / "logs" / "layout_log.jsonl"

# Must import after load_dotenv so PearlClient picks up env vars.
from domains.epiphan.tools.pearl_client import PearlClient  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_layout(
    layouts: list[dict], query: str
) -> dict | None:
    """
    Resolve a layout name or ID from a list of layout dicts.

    Resolution order:
      1. Exact ID match (case-sensitive)
      2. Exact name match (case-insensitive)
      3. First substring name match (case-insensitive)

    Returns the matching layout dict, or None if no match.
    """
    q_lower = query.lower()

    # Exact ID
    for layout in layouts:
        if layout.get("id") == query:
            return layout

    # Exact name (case-insensitive)
    for layout in layouts:
        if layout.get("name", "").lower() == q_lower:
            return layout

    # Substring
    for layout in layouts:
        if q_lower in layout.get("name", "").lower():
            return layout

    return None


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_layouts(args: argparse.Namespace, client: PearlClient) -> int:
    """List available layouts for a channel."""
    layouts = client.get_layouts(str(args.channel))
    if not layouts:
        print(f"No layouts found for channel {args.channel}.")
        return 1
    active = client.get_active_layout(str(args.channel))
    active_id = active.get("id", "")
    print(f"Layouts for channel {args.channel}:")
    for layout in layouts:
        lid = layout.get("id", "")
        name = layout.get("name", lid)
        marker = " ← active" if lid == active_id else ""
        print(f"  {lid:<12}  {name}{marker}")
    return 0


def cmd_switch(args: argparse.Namespace, client: PearlClient) -> int:
    """Switch the active layout on a channel."""
    layouts = client.get_layouts(str(args.channel))
    if not layouts:
        print(
            f"No layouts found for channel {args.channel}.",
            file=sys.stderr,
        )
        return 1

    matched = _resolve_layout(layouts, args.layout)
    if matched is None:
        names = ", ".join(
            f'"{lay.get("name", lay.get("id"))}"' for lay in layouts
        )
        print(
            f'Layout {args.layout!r} not found on channel {args.channel}.\n'
            f"Available: {names}",
            file=sys.stderr,
        )
        return 1

    layout_id = matched["id"]
    layout_name = matched.get("name", layout_id)
    client.switch_layout(str(args.channel), layout_id)
    print(f"✅  Channel {args.channel} → layout '{layout_name}' (id={layout_id})")

    # Log the switch so the cockpit display can show the active layout.
    _LAYOUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_LAYOUT_LOG, "a") as _lf:
        _lf.write(
            json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "channel": str(args.channel),
                "layout_id": layout_id,
                "layout_name": layout_name,
            }) + "\n"
        )

    return 0


def cmd_status(args: argparse.Namespace, client: PearlClient) -> int:
    """Show the active layout for one or all channels."""
    if args.channel:
        channels = [{"id": str(args.channel)}]
    else:
        channels = client.get_channels()

    for ch in channels:
        cid = str(ch.get("id", ""))
        cname = ch.get("name", cid)
        try:
            active = client.get_active_layout(cid)
            lid = active.get("id", "—")
            lname = active.get("name", lid)
            print(f"  Channel {cid} ({cname}): layout '{lname}' (id={lid})")
        except Exception as exc:
            print(f"  Channel {cid} ({cname}): error — {exc}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pearl_control.py",
        description="Live layout control for Epiphan Pearl.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # layouts
    p_layouts = sub.add_parser("layouts", help="List layouts for a channel.")
    p_layouts.add_argument(
        "--channel", required=True, metavar="ID",
        help="Pearl channel ID (e.g. 2 for EN, 3 for FR).",
    )

    # switch
    p_switch = sub.add_parser("switch", help="Activate a layout.")
    p_switch.add_argument(
        "--channel", required=True, metavar="ID",
        help="Pearl channel ID.",
    )
    p_switch.add_argument(
        "--layout", required=True, metavar="NAME_OR_ID",
        help="Layout name (fuzzy) or exact ID.",
    )

    # status
    p_status = sub.add_parser(
        "status", help="Show active layout (all channels or one)."
    )
    p_status.add_argument(
        "--channel", default=None, metavar="ID",
        help="Limit to one channel (omit for all).",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    client = PearlClient()
    handlers = {
        "layouts": cmd_layouts,
        "switch": cmd_switch,
        "status": cmd_status,
    }
    sys.exit(handlers[args.command](args, client))


if __name__ == "__main__":
    main()
