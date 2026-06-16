#!/usr/bin/env python3
"""Launch Stage C 1M only after a fresh no-active-LAMMPS preflight."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner.stagec_1m import (  # noqa: E402
    FOCUS_RUN_ROOT_DEFAULT,
    build_preflight,
    normalize_repo_path,
    stagec_launch_args,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="launch_stageC_1M_after_focus.py", description=__doc__)
    parser.add_argument("--focus-run-root", default=str(FOCUS_RUN_ROOT_DEFAULT))
    parser.add_argument("--stageC-run-root", required=True)
    parser.add_argument("--config", default=None, help="defaults to <stageC-run-root>/effective_config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="recheck and print launch decision without Popen")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    root = normalize_repo_path(args.stageC_run_root)
    config = normalize_repo_path(args.config) if args.config else root / "effective_config.yaml"
    preflight = build_preflight(config, root, args.focus_run_root)
    write_json(root / "stageC_1M_launch_recheck.json", preflight)

    if not preflight["allowed_to_launch_now"]:
        result = {
            "launched": False,
            "reason": "preflight_blocked",
            "blocked_by": preflight["blocked_by"],
            "queue_ready": preflight["queue_ready"],
            "stageC_run_root": str(root),
        }
        write_json(root / "stageC_1M_launch_refusal.json", result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2

    launch_args = stagec_launch_args(config, root)
    if args.dry_run:
        result = {
            "launched": False,
            "reason": "dry_run",
            "blocked_by": [],
            "command": launch_args,
            "stageC_run_root": str(root),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    proc = subprocess.Popen(launch_args, cwd=REPO_ROOT)
    result = {
        "launched": True,
        "pid": proc.pid,
        "command": launch_args,
        "stageC_run_root": str(root),
    }
    write_json(root / "stageC_1M_launch_record.json", result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
