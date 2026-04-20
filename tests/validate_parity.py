#!/usr/bin/env python3
"""
Compare direct CodeCarbon tracking vs pygreensense tracking on the same window.

Both methods measure the same workload:
    tracker.start() -> subprocess.run(target_file) -> tracker.stop()
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from codecarbon import EmissionsTracker

# Allow importing src package when script is run from tests/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.green_code_smell.cli import run_entry_point_with_carbon  # noqa: E402


def run_direct_codecarbon(target_file: Path, iterations: int, timeout: int) -> List[float]:
    """Run direct CodeCarbon measurements around subprocess execution."""
    emissions = []
    for i in range(1, iterations + 1):
        tracker = EmissionsTracker(
            log_level="critical",
            save_to_file=False,
            save_to_api=False,
            allow_multiple_runs=True,
            project_name=f"parity_direct_{target_file.stem}",
        )
        tracker.start()
        subprocess.run(
            [sys.executable, str(target_file)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        value = tracker.stop()
        emissions.append(value or 0.0)
        print(f"[direct] run {i}/{iterations}: {emissions[-1]:.12e} kgCO2eq")
    return emissions


def summarize(values: List[float]) -> Dict[str, float]:
    diffs = [values[i] - values[i - 1] for i in range(1, len(values))]
    return {
        "count": float(len(values)),
        "avg": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "avg_diff_signed": statistics.mean(diffs) if diffs else 0.0,
        "avg_diff_abs": statistics.mean(abs(d) for d in diffs) if diffs else 0.0,
    }


def print_stats(label: str, stats: Dict[str, float]) -> None:
    print(f"\n{label}")
    print(f"  count: {int(stats['count'])}")
    print(f"  avg: {stats['avg']:.12e} kgCO2eq")
    print(f"  min: {stats['min']:.12e} kgCO2eq")
    print(f"  max: {stats['max']:.12e} kgCO2eq")
    print(f"  avg diff signed: {stats['avg_diff_signed']:.12e} kgCO2eq")
    print(f"  avg diff abs: {stats['avg_diff_abs']:.12e} kgCO2eq")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate pygreensense carbon parity vs CodeCarbon.")
    parser.add_argument(
        "--target",
        default="after.py",
        help="Target Python file to execute (default: after.py in current directory).",
    )
    parser.add_argument("--iterations", type=int, default=10, help="Number of runs for each method.")
    parser.add_argument("--timeout", type=int, default=30, help="Per-run timeout in seconds.")
    args = parser.parse_args()

    target_file = Path(args.target).resolve()
    if not target_file.exists():
        print(f"Target file not found: {target_file}")
        return 1

    print(f"Target: {target_file}")
    print(f"Iterations: {args.iterations}\n")

    direct = run_direct_codecarbon(target_file, args.iterations, args.timeout)
    lib_runs, _, _ = run_entry_point_with_carbon(target_file, iterations=args.iterations, timeout=args.timeout)
    lib = [r["emission"] for r in lib_runs]
    for i, value in enumerate(lib, 1):
        print(f"[lib]    run {i}/{len(lib)}: {value:.12e} kgCO2eq")

    if not direct or not lib:
        print("Could not collect enough runs for one of the methods.")
        return 1

    direct_stats = summarize(direct)
    lib_stats = summarize(lib)
    print_stats("Direct CodeCarbon (subprocess window)", direct_stats)
    print_stats("pygreensense run_entry_point_with_carbon", lib_stats)

    pct_diff_avg = abs(lib_stats["avg"] - direct_stats["avg"]) / direct_stats["avg"] * 100 if direct_stats["avg"] else 0.0
    ratio = lib_stats["avg"] / direct_stats["avg"] if direct_stats["avg"] else 0.0
    print("\nComparison")
    print(f"  mean absolute percentage difference: {pct_diff_avg:.2f}%")
    print(f"  mean ratio (lib/direct): {ratio:.4f}x")
    print("  note: for short tasks, 30-50%+ drift can happen due to noise and startup overhead.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
