#!/usr/bin/env python3
"""Prepare the safe Stage B focus 5-6 transition without launching MD."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner.focus_transition import (  # noqa: E402
    FOCUS_OUTPUT_ROOT,
    OLD_RUN_ROOT_DEFAULT,
    SNAPSHOT_DIRNAME,
    copy_partial_event_outputs_to_completed_aliases,
    normalize_repo_path,
    timestamp_dir,
    write_completed_cases_snapshot,
    write_focus_run_setup,
    write_safe_stop_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prepare_focus_5_6_transition.py", description=__doc__)
    parser.add_argument("--old-run-root", default=str(OLD_RUN_ROOT_DEFAULT))
    parser.add_argument(
        "--focus-run-root",
        default=None,
        help="new run root; defaults to runs/stageB_nearGB_vacancies_focus_100k/<timestamp>",
    )
    parser.add_argument(
        "--focus-config-template",
        default="configs/stageB_nearGB_vacancies_focus_100k.template.yaml",
    )
    parser.add_argument("--snapshot-dir", default=None)
    parser.add_argument(
        "--partial-event-output-dir",
        default=None,
        help="if supplied, write completed-case alias names for existing event dry-run outputs in this directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)

    old_root = normalize_repo_path(args.old_run_root)
    if args.focus_run_root:
        focus_root = normalize_repo_path(args.focus_run_root)
    else:
        focus_root = normalize_repo_path(Path("runs") / FOCUS_OUTPUT_ROOT / timestamp_dir())
    snapshot_dir = normalize_repo_path(args.snapshot_dir) if args.snapshot_dir else old_root / SNAPSHOT_DIRNAME

    manifest = write_completed_cases_snapshot(old_root, snapshot_dir)
    safe_stop_plan = write_safe_stop_plan(old_root, snapshot_dir)
    focus_setup = write_focus_run_setup(
        args.focus_config_template,
        focus_root,
        old_run_root=old_root,
        snapshot_dir=snapshot_dir,
    )
    alias_writes = []
    if args.partial_event_output_dir:
        alias_writes = [str(p) for p in copy_partial_event_outputs_to_completed_aliases(args.partial_event_output_dir)]

    result = {
        "old_run_root": str(old_root),
        "snapshot_manifest": str(snapshot_dir / "completed_cases_manifest.json"),
        "snapshot_summary": str(snapshot_dir / "completed_cases_summary.md"),
        "completed_cases": manifest["completed_cases"],
        "running_cases": manifest["running_cases"],
        "safe_stop_plan": str(safe_stop_plan),
        "focus_run_root": focus_setup["focus_run_root"],
        "effective_config": focus_setup["effective_config"],
        "focus_run_command": str(focus_root / "focus_run_command.txt"),
        "preflight_json": str(focus_root / "focus_run_preflight.json"),
        "preflight_md": str(focus_root / "focus_run_preflight.md"),
        "allowed_to_launch": focus_setup["preflight"]["allowed_to_launch"],
        "blockers": focus_setup["preflight"]["blockers"],
        "partial_event_alias_writes": alias_writes,
        "external_execution": "not_run",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
