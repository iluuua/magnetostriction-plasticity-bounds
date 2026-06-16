#!/usr/bin/env python3
"""CLI for the A0 / A1-small autopilot stage sweep.

Usage (from the repo root, with the OVITO venv python):

  .venv\\Scripts\\python.exe scripts\\run_stage_sweep.py --config configs\\stage_sweep_A0_A1_production.yaml --plan-only
  .venv\\Scripts\\python.exe scripts\\run_stage_sweep.py --config configs\\stage_sweep_A0_A1_production.yaml --check-env
  .venv\\Scripts\\python.exe scripts\\run_stage_sweep.py --config configs\\stage_sweep_A0_A1_production.yaml --run-a0-smoke
  .venv\\Scripts\\python.exe scripts\\run_stage_sweep.py --config configs\\stage_sweep_A0_A1_production.yaml --run-a0-production
  .venv\\Scripts\\python.exe scripts\\run_stage_sweep.py --config configs\\stage_sweep_A0_A1_production.yaml --run-a1-smoke
  .venv\\Scripts\\python.exe scripts\\run_stage_sweep.py --config configs\\stage_sweep_A0_A1_production.yaml --run-a1-production
  .venv\\Scripts\\python.exe scripts\\run_stage_sweep.py --config configs\\stage_sweep_A0_A1_production.yaml --autopilot-A0-A1-production
  .venv\\Scripts\\python.exe scripts\\run_stage_sweep.py --config configs\\stage_sweep_A0_A1_production.yaml --analyze-only

Add --run-dir runs\\stage_sweep_A0_A1_production\\<timestamp> to resume an
interrupted run (completed steps are skipped via state.json).

Without an execution flag the script prints this help and exits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner import autopilot as ap  # noqa: E402
from stage_runner import gpu_grid  # noqa: E402
from stage_runner import paths  # noqa: E402
from stage_runner.config import ConfigError, load_config  # noqa: E402

EXECUTION_FLAGS = [
    ("plan_only", "plan"),
    ("check_env", None),
    ("run_a0_smoke", "a0_smoke"),
    ("run_a0_production", "a0_analysis"),  # production gate includes analysis + CSV
    ("run_a1_smoke", "a1_smoke"),
    ("run_a1_production", "a1_analysis"),
    ("autopilot_A0_A1_production", "final_report"),
    ("analyze_only", None),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_stage_sweep.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", required=True, help="YAML config path")
    parser.add_argument("--run-dir", default=None,
                        help="existing run directory to resume / analyze")
    parser.add_argument("--plan-only", action="store_true",
                        help="validate config + inputs, print the plan, run nothing")
    parser.add_argument("--check-env", action="store_true",
                        help="detect LAMMPS/MPI/python/resources, run nothing")
    parser.add_argument("--run-a0-smoke", action="store_true",
                        help="run A0 smoke (plus prerequisites) and stop")
    parser.add_argument("--run-a0-production", action="store_true",
                        help="run through A0 production + analysis and stop")
    parser.add_argument("--run-a1-smoke", action="store_true",
                        help="run through A1-small build + smoke and stop")
    parser.add_argument("--run-a1-production", action="store_true",
                        help="run through the gate, A1 production + analysis, and stop")
    parser.add_argument("--autopilot-A0-A1-production", action="store_true",
                        help="full autopilot: A0 smoke -> ... -> A1 production -> final report")
    parser.add_argument("--run-stage", default=None,
                        help="GPU grid stage name, e.g. A0_24k, A1_small, A1_medium, A2_large")
    parser.add_argument("--gpu", action="store_true",
                        help="confirm GPU execution for --run-stage in the GPU grid runner")
    parser.add_argument("--autopilot-gpu-grid", action="store_true",
                        help="full gated GPU grid autopilot from the YAML config")
    parser.add_argument("--resume", action="store_true",
                        help="resume the latest GPU grid run, or --run-dir if supplied")
    parser.add_argument("--force-rerun", default=None,
                        help="rerun one completed GPU grid case_id instead of skipping it")
    parser.add_argument("--smoke-only", action="store_true",
                        help="for GPU grid Stage B runs: stop after all smoke cases pass")
    parser.add_argument("--analyze-only", action="store_true",
                        help="re-run OVITO analysis on existing final dumps in --run-dir")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)

    if gpu_grid.is_grid_config_file(args.config):
        selected = []
        for flag_name in ("plan_only", "check_env", "autopilot_gpu_grid", "resume", "analyze_only"):
            if getattr(args, flag_name):
                selected.append(flag_name)
        if args.run_stage:
            selected.append("run_stage")
        if args.force_rerun and not (args.run_stage or args.autopilot_gpu_grid):
            selected.append("force_rerun")
        if not selected:
            parser.print_help()
            return 0
        if len(selected) > 1 and not (
            args.force_rerun and selected in (["run_stage", "force_rerun"], ["autopilot_gpu_grid", "force_rerun"])
        ):
            parser.error(f"choose exactly one GPU grid execution flag, got: {selected}")
        return gpu_grid.main_from_args(args)

    selected = [name for name, _ in EXECUTION_FLAGS if getattr(args, name)]
    if not selected:
        parser.print_help()
        return 0
    if len(selected) > 1:
        parser.error(f"choose exactly one execution flag, got: {selected}")

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 1

    flag = selected[0]

    if flag == "plan_only":
        ok, lines = ap.validate_plan(cfg)
        print("\n".join(lines))
        print(f"\nplan-only result: {'OK' if ok else 'FAIL'}")
        print(f"(a new run would be created under {paths.RUNS_ROOT})")
        return 0 if ok else 1

    if flag == "check_env":
        ok, _env, lines = ap.check_env(cfg)
        print("\n".join(lines))
        print(f"\ncheck-env result: {'OK' if ok else 'FAIL'}")
        return 0 if ok else 1

    run_dir = Path(args.run_dir) if args.run_dir else None
    if flag == "analyze_only" and run_dir is None:
        run_dir = paths.find_latest_run_dir()
        if run_dir is None:
            print("ERROR: --analyze-only needs --run-dir (no runs found)", file=sys.stderr)
            return 1

    try:
        pilot = ap.Autopilot(cfg, run_dir=run_dir)
    except ap.StopPipeline as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if flag == "analyze_only":
        return 0 if pilot.analyze_only() else 1

    target = dict(EXECUTION_FLAGS)[flag]
    ok = pilot.run_until(target)
    print(f"\nrun directory: {pilot.run_dir}")
    print(f"result: {'OK' if ok else 'STOPPED (see summaries/stop_report.md)'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
