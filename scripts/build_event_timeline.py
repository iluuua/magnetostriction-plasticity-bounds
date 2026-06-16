#!/usr/bin/env python3
"""Build event_timeline CSV/JSON from existing analysis artifacts.

This script reads existing run files only. It does not launch MD.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from event_pipeline.timeline import build_event_timeline, write_event_timeline_outputs  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build_event_timeline.py", description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--dry-run", action="store_true", help="print summary without writing files")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="accepted for explicit partial-run workflows; missing/running cases are skipped",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    if args.dry_run:
        rows = build_event_timeline(args.run_root)
        print(json.dumps({"frame_count": len(rows), "frames": rows}, indent=2, ensure_ascii=False))
        return 0
    result = write_event_timeline_outputs(args.run_root, args.output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
