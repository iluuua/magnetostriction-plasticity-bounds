#!/usr/bin/env python3
"""Gated Stage B 500k winner-case confirmation launcher.

The default mode is --dry-run. Dry-run/validate modes never launch MD. --launch
requires a completed post-run decision with confirmed DXA signal and explicit
manual approval.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner import paths  # noqa: E402
from stage_runner.stageb_postrun import (  # noqa: E402
    timestamp_dir,
    validate_500k_gate,
    write_500k_preflight_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="launch_stageB_500k_confirmation.py",
        description=__doc__,
    )
    parser.add_argument("--run-root", required=True, help="source Stage B 100k run root")
    parser.add_argument("--decision-path", default=None, help="override postrun_decision.json path")
    parser.add_argument("--output-run-root", default=None, help="where to write launch artifacts")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preflight only; write nothing")
    mode.add_argument("--validate-only", action="store_true", help="preflight and write launch artifacts if allowed")
    mode.add_argument("--launch", action="store_true", help="run after all gates and manual approval")
    parser.add_argument("--approve-500k-confirmation", action="store_true", help="explicit manual approval for --launch")
    return parser


def selected_mode(args: argparse.Namespace) -> str:
    if args.launch:
        return "launch"
    if args.validate_only:
        return "validate-only"
    return "dry-run"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    mode = selected_mode(args)
    gate = validate_500k_gate(
        args.run_root,
        mode=mode,
        decision_path=args.decision_path,
        approve_cli=bool(args.approve_500k_confirmation),
    )
    print(json.dumps(gate.as_dict(), indent=2, ensure_ascii=False))
    if not gate.allowed:
        print("REFUSED: 500k confirmation gate is closed.", file=sys.stderr)
        return 1
    output_root = Path(args.output_run_root) if args.output_run_root else (
        paths.REPO_ROOT / "runs" / "stageB_500k_confirmation" / timestamp_dir()
    )
    if not output_root.is_absolute():
        output_root = (paths.REPO_ROOT / output_root).resolve()
    if mode == "dry-run":
        print("DRY-RUN: preflight passed; no files written and no MD launched.")
        return 0
    written = write_500k_preflight_artifacts(output_root, gate)
    print("written:")
    for path in written:
        print(f"  {path}")
    if mode == "validate-only":
        print("VALIDATE-ONLY: artifacts written; no MD launched.")
        return 0
    command_path = output_root / "command.txt"
    cmd = command_path.read_text(encoding="utf-8").strip().split()
    print("LAUNCH: starting gated 500k confirmation command.")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())

