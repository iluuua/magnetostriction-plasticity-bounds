#!/usr/bin/env python3
"""Write an event-window dry-run plan from event_timeline.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from event_pipeline.window import EventWindowPolicy, write_event_window_outputs  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plan_event_window.py", description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--timeline-json", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--pre-steps", type=int, default=10000)
    parser.add_argument("--post-steps", type=int, default=10000)
    parser.add_argument("--dump-every", type=int, default=100)
    parser.add_argument("--analysis-every", type=int, default=100)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    policy = EventWindowPolicy(
        pre_steps=args.pre_steps,
        post_steps=args.post_steps,
        dump_every=args.dump_every,
        analysis_every=args.analysis_every,
    )
    result = write_event_window_outputs(args.run_root, args.timeline_json, args.output_dir, policy)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
