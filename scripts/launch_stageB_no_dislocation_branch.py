#!/usr/bin/env python3
"""Gated no-dislocation branch proposal launcher.

The default --dry-run prints the proposal order and never starts MD. Launch
modes are blocked until the corresponding builder/runtime support exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner.stageb_postrun import (  # noqa: E402
    load_postrun_decision,
    no_dislocation_plan_markdown,
    no_dislocation_proposals,
    validate_no_dislocation_gate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="launch_stageB_no_dislocation_branch.py",
        description=__doc__,
    )
    parser.add_argument("--run-root", required=True, help="source Stage B 100k run root")
    parser.add_argument("--decision-path", default=None, help="override postrun_decision.json path")
    parser.add_argument("--output-plan", default=None, help="optional markdown plan output")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--launch-positive-control", action="store_true")
    mode.add_argument("--launch-seeded", action="store_true")
    mode.add_argument("--launch-cyclic", action="store_true")
    mode.add_argument("--launch-platelet", action="store_true")
    return parser


def selected_mode(args: argparse.Namespace) -> str:
    for name in ("launch_positive_control", "launch_seeded", "launch_cyclic", "launch_platelet"):
        if getattr(args, name):
            return name.replace("_", "-")
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
    gate = validate_no_dislocation_gate(args.run_root, mode=mode, decision_path=args.decision_path)
    decision, _path = load_postrun_decision(args.run_root, args.decision_path)
    payload = gate.as_dict()
    payload["proposals"] = no_dislocation_proposals()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if args.output_plan:
        p = Path(args.output_plan)
        if not p.is_absolute():
            p = REPO_ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(no_dislocation_plan_markdown(decision), encoding="utf-8")
        print(f"plan_written={p}")
    if not gate.allowed:
        print("REFUSED: no-dislocation branch gate is closed.", file=sys.stderr)
        return 1
    print("No MD launched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

