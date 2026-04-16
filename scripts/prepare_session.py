"""
prepare_session.py — Update per-stream fields in session_config.yaml.

Usage:
    python scripts/prepare_session.py [--config PATH] [--dry-run]
"""

import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CONFIG = (
    Path(__file__).resolve().parent.parent
    / "domains/streamlab_post/config/session_config.yaml"
)

MUTABLE_FIELDS = [
    ("event_name", None),
    ("youtube.en.video_id", ("youtube", "en", "video_id")),
    ("youtube.fr.video_id", ("youtube", "fr", "video_id")),
]


def _get_nested(data: dict, keys: tuple) -> str:
    val = data
    for k in keys:
        val = val.get(k, {}) if isinstance(val, dict) else {}
    return val if isinstance(val, str) else ""


def _set_nested(data: dict, keys: tuple, value: str) -> None:
    d = data
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def _prompt(label: str, current: str, required: bool) -> str:
    hint = f"[{current}]" if current else "[empty]"
    suffix = " (Enter to keep)" if not required else ""
    while True:
        answer = input(f"{label} {hint}{suffix}: ").strip()
        if answer:
            return answer
        if required:
            print("  This field is required — please enter a value.")
        else:
            return current


def run(config_path: Path, dry_run: bool) -> int:
    if not config_path.exists():
        print(f"Error: config not found at {config_path}", file=sys.stderr)
        return 1

    with open(config_path) as fh:
        data = yaml.safe_load(fh)

    # Read current values
    event_name_current = data.get("event_name", "")
    en_vid_current = _get_nested(data, ("youtube", "en", "video_id"))
    fr_vid_current = _get_nested(data, ("youtube", "fr", "video_id"))
    hardware_current = data.get("hardware", "obs")
    _pearl_cfg = data.get("pearl", {}) if isinstance(data.get("pearl"), dict) else {}
    pearl_en_current = str(_pearl_cfg.get("channel_en", ""))
    pearl_fr_current = str(_pearl_cfg.get("channel_fr", ""))

    print("\nCurrent values:")
    print(f"  hardware:            {hardware_current!r}")
    print(f"  event_name:          {event_name_current!r}")
    print(f"  youtube.en.video_id: {en_vid_current!r}")
    print(f"  youtube.fr.video_id: {fr_vid_current!r}")
    if hardware_current == "epiphan":
        print(f"  pearl.channel_en:    {pearl_en_current!r}")
        print(f"  pearl.channel_fr:    {pearl_fr_current!r}")
    print()

    if dry_run:
        print("Dry run — showing current values only. No changes made.")
        return 0

    new_hardware = (
        _prompt(
            "Hardware backend [obs/epiphan]",
            hardware_current,
            required=False,
        )
        or hardware_current
    )
    new_event = _prompt("Event name", event_name_current, required=True)
    new_en_vid = _prompt("YouTube EN video_id", en_vid_current, required=False)
    new_fr_vid = _prompt(
        "YouTube FR video_id", fr_vid_current, required=False
    )
    new_pearl_en = pearl_en_current
    new_pearl_fr = pearl_fr_current
    if new_hardware == "epiphan":
        new_pearl_en = (
            _prompt(
                "Pearl channel_en (EN recorder ID)",
                pearl_en_current,
                required=False,
            )
            or pearl_en_current
        )
        new_pearl_fr = (
            _prompt(
                "Pearl channel_fr (FR recorder ID)",
                pearl_fr_current,
                required=False,
            )
            or pearl_fr_current
        )

    # Build diff
    changes = {}
    if new_hardware != hardware_current:
        changes["hardware"] = (hardware_current, new_hardware)
    if new_event != event_name_current:
        changes["event_name"] = (event_name_current, new_event)
    if new_en_vid != en_vid_current:
        changes["youtube.en.video_id"] = (en_vid_current, new_en_vid)
    if new_fr_vid != fr_vid_current:
        changes["youtube.fr.video_id"] = (fr_vid_current, new_fr_vid)
    if new_pearl_en != pearl_en_current:
        changes["pearl.channel_en"] = (pearl_en_current, new_pearl_en)
    if new_pearl_fr != pearl_fr_current:
        changes["pearl.channel_fr"] = (pearl_fr_current, new_pearl_fr)

    if not changes:
        print("\nNo changes.")
        return 0

    print("\nChanges:")
    for field, (old, new) in changes.items():
        print(f"  {field}: {old!r} → {new!r}")

    answer = input("\nWrite? [y/N]: ").strip().lower()
    if answer != "y":
        print("Aborted. No changes made.")
        return 0

    # Apply
    data["hardware"] = new_hardware
    data["event_name"] = new_event
    _set_nested(data, ("youtube", "en", "video_id"), new_en_vid)
    _set_nested(data, ("youtube", "fr", "video_id"), new_fr_vid)
    if new_hardware == "epiphan":
        pearl_block = data.setdefault("pearl", {})
        try:
            pearl_block["channel_en"] = int(new_pearl_en)
        except (ValueError, TypeError):
            pearl_block["channel_en"] = new_pearl_en
        try:
            pearl_block["channel_fr"] = int(new_pearl_fr)
        except (ValueError, TypeError):
            pearl_block["channel_fr"] = new_pearl_fr

    with open(config_path, "w") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)

    print("✅ session_config.yaml updated")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare session config.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(run(args.config, args.dry_run))


if __name__ == "__main__":
    main()
