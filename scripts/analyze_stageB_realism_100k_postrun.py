#!/usr/bin/env python3
"""Post-run decision gate for the Stage B realism 100k run.

Reads state.json, small CSV/JSON analysis outputs, and writes the post-run
verdict only after the source run is complete unless --write-incomplete is
explicitly supplied. This script never launches MD.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner.stageb_postrun import analyze_run_root  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analyze_stageB_realism_100k_postrun.py",
        description=__doc__,
    )
    parser.add_argument("--run-root", required=True, help="Stage B realism 100k run root")
    parser.add_argument("--dry-run", action="store_true", help="compute and print decision; write nothing")
    parser.add_argument(
        "--write-incomplete",
        action="store_true",
        help="allow writing an incomplete verdict; normally blocked by run-root safety rules",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    decision = analyze_run_root(
        args.run_root,
        dry_run=bool(args.dry_run),
        write_incomplete=bool(args.write_incomplete),
    )
    print(
        "status={status} branch={branch} winner_case={winner}".format(
            status=decision["status"],
            branch=decision["branch"],
            winner=decision.get("winner_case"),
        )
    )
    if decision.get("write_skipped_reason"):
        print(f"write_skipped_reason={decision['write_skipped_reason']}")
    if decision.get("writes"):
        print("writes:")
        for path in decision["writes"]:
            print(f"  {path}")
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

