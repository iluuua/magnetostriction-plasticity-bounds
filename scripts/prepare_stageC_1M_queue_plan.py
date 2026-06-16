#!/usr/bin/env python3
"""Prepare Stage C 1M-class queue artifacts without launching MD."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner.stagec_1m import (  # noqa: E402
    FOCUS_RUN_ROOT_DEFAULT,
    STAGEC_CONFIG_TEMPLATE,
    prepare_stagec_queue,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prepare_stageC_1M_queue_plan.py", description=__doc__)
    parser.add_argument("--config-template", default=str(STAGEC_CONFIG_TEMPLATE))
    parser.add_argument("--focus-run-root", default=str(FOCUS_RUN_ROOT_DEFAULT))
    parser.add_argument("--stageC-run-root", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    result = prepare_stagec_queue(
        config_template=args.config_template,
        run_root=args.stageC_run_root,
        focus_root=args.focus_run_root,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
