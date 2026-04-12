"""
Phase 4a benchmark — Sequential vs Parallel on Kosmos EXIF extraction.

Generates N synthetic JPEG images with embedded EXIF camera metadata,
runs the full Kosmos engine graph in sequential mode then parallel mode
against the same folder, and prints a timing comparison.

Usage:
  python engine/benchmarks/parallel_benchmark.py --count 200
  python engine/benchmarks/parallel_benchmark.py --count 200 --workers 8
  python engine/benchmarks/parallel_benchmark.py --path ~/Pictures
  python engine/benchmarks/parallel_benchmark.py --path ~/Pictures --workers 8

If --path is provided, uses real media files instead of generating synthetic ones.
Synthetic images are written to a temp directory and deleted after the benchmark.
"""

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import cast

# Ensure repo root is on the path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.graph.graph_builder import build_graph  # noqa: E402
from engine.graph.state import RunState  # noqa: E402
from engine.services.state_store import generate_run_id  # noqa: E402
from engine.tools.shared_tools import FileScannerTool  # noqa: E402
from domains.kosmos.tools.media_classifier import classify_media_file  # noqa: E402


def _require_piexif():
    try:
        import piexif  # noqa: F401
    except ImportError:
        print("ERROR: piexif is required for synthetic image generation.")
        print("  pip install piexif pillow")
        sys.exit(1)


def _generate_synthetic_images(count: int, out_dir: Path) -> None:
    """Generate count synthetic JPEGs (80%) and PNGs (20%) in out_dir."""
    import piexif
    from PIL import Image

    jpeg_count = int(count * 0.8)
    png_count = count - jpeg_count

    exif_bytes = piexif.dump({
        "0th": {
            piexif.ImageIFD.Make: b"BenchmarkCam",
            piexif.ImageIFD.Model: b"M1",
        }
    })

    for i in range(jpeg_count):
        img = Image.new("RGB", (1920, 1080), color=(i % 256, 128, 64))
        path = out_dir / f"bench_{i:05d}.jpg"
        img.save(str(path), "JPEG", exif=exif_bytes)

    for i in range(png_count):
        img = Image.new("RGB", (1920, 1080), color=(64, i % 256, 128))
        path = out_dir / f"bench_png_{i:05d}.png"
        img.save(str(path), "PNG")


def _build_state(root_path: str, parallel: bool, workers: int) -> RunState:
    return {
        "run_id": generate_run_id(),
        "domain": "kosmos",
        "goal": f"Benchmark: {root_path}",
        "mode": "dry_run",
        "current_step": "init",
        "pending_tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "skipped_tasks": [],
        "exhausted_tasks": [],
        "review_queue": [],
        "proposed_actions": [],
        "applied_actions": [],
        "artifacts": [],
        "errors": [],
        "logs": [],
        "retries": 0,
        "max_retries": 3,
        "replans": 0,
        "max_replans": 2,
        "done": False,
        "exit_reason": None,
        "agent_id": "kosmos",
        "inbox_messages": [],
        "context": {
            "root_path": root_path,
            "batch_size": 500,  # large batch to minimise loop overhead
            "execution_mode": "parallel" if parallel else "sequential",
            "parallel_workers": workers,
            "thresholds": {
                "auto_approve": 0.90,
                "review_queue": 0.60,
            },
            "exhausted_threshold": 0.20,
            "tools": {
                "scanner": FileScannerTool(),
                "classifier": classify_media_file,
            },
        },
    }


def _run_and_time(root_path: str, parallel: bool, workers: int):
    """Run the graph and return (elapsed_seconds, final_state)."""
    graph = build_graph()
    state = _build_state(root_path, parallel=parallel, workers=workers)
    t0 = time.perf_counter()
    final = cast(RunState, graph.invoke(state))
    elapsed = time.perf_counter() - t0
    return elapsed, final


def _actions_signature(state: RunState) -> list:
    """Sorted list of (file_path, category, confidence) for correctness check."""
    actions = state.get("proposed_actions", [])
    return sorted(
        [(a["file_path"], a["category"], a["confidence"]) for a in actions],
        key=lambda x: x[0],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Phase 4a benchmark — Sequential vs Parallel"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--count",
        type=int,
        default=200,
        help="Number of synthetic images to generate (default: 200)",
    )
    group.add_argument(
        "--path",
        type=str,
        help="Path to a real media folder (uses real files instead of synthetic)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of parallel workers (default: 8)",
    )
    args = parser.parse_args()

    tmp_dir = None
    if args.path:
        root_path = str(Path(args.path).expanduser().resolve())
        if not Path(root_path).exists():
            print(f"ERROR: Path does not exist: {root_path}")
            sys.exit(1)
        file_count = len(list(Path(root_path).rglob("*")))
        print(f"\nUsing real media folder: {root_path}")
        print(f"Files found            : {file_count}")
    else:
        _require_piexif()
        tmp_dir = tempfile.mkdtemp(prefix="miktos_bench_")
        root_path = tmp_dir
        print(f"\nGenerating {args.count} synthetic images...", end=" ", flush=True)
        _generate_synthetic_images(args.count, Path(tmp_dir))
        print("done.")

    try:
        print("Running sequential...", end=" ", flush=True)
        seq_elapsed, seq_state = _run_and_time(
            root_path, parallel=False, workers=args.workers
        )
        seq_actions = len(seq_state.get("proposed_actions", []))
        print(f"done ({seq_elapsed:.2f}s)")

        print("Running parallel...  ", end=" ", flush=True)
        par_elapsed, par_state = _run_and_time(
            root_path, parallel=True, workers=args.workers
        )
        par_actions = len(par_state.get("proposed_actions", []))
        print(f"done ({par_elapsed:.2f}s)")

        # Correctness check
        seq_sig = _actions_signature(seq_state)
        par_sig = _actions_signature(par_state)
        correctness = "PASS" if seq_sig == par_sig else "FAIL"
        match_count = sum(
            1 for s, p in zip(seq_sig, par_sig) if s == p
        )

        speedup = seq_elapsed / par_elapsed if par_elapsed > 0 else float("inf")
        seq_rate = seq_actions / seq_elapsed if seq_elapsed > 0 else 0.0
        par_rate = par_actions / par_elapsed if par_elapsed > 0 else 0.0

        print()
        print("Phase 4a \u2014 Parallel Execution Benchmark")
        print("=" * 44)
        print(f"Files       : {seq_actions}")
        print(f"Sequential  : {seq_elapsed:.2f}s  ({seq_rate:.1f} files/sec)")
        print(
            f"Parallel    : {par_elapsed:.2f}s  ({par_rate:.1f} files/sec)"
            f"  [{args.workers} workers]"
        )
        print(f"Speedup     : {speedup:.1f}x")
        print(
            f"Correctness : {correctness}"
            f" ({match_count}/{seq_actions} actions match)"
        )
        print("=" * 44)

        if correctness == "FAIL":
            print("\nCORRECTNESS FAILURE — results differ between modes.")
            sys.exit(1)

    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
