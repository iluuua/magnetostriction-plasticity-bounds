#!/usr/bin/env python3
"""Create or execute an OVITO render plan for event animation frames."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from event_pipeline.render import RENDER_PRESETS, render_one_with_ovito, write_render_plan_outputs  # noqa: E402
from event_pipeline.timeline import read_json  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=Path(__file__).name, description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--timeline-json", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--mode", choices=["event", "dxa", "deformation", "geometry", "figures"], default="event")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--execute", action="store_true", help="render with OVITO; default writes dry-run manifests only")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    result = write_render_plan_outputs(
        args.run_root,
        timeline_json=args.timeline_json,
        output_dir=args.output_dir,
        mode=args.mode,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not args.execute:
        print("DRY-RUN: render manifests written; OVITO was not invoked.")
        return 0
    manifest_path = Path(result["writes"][1])
    frames = read_json(manifest_path, {}).get("frames", [])
    for row in frames:
        rendered = render_one_with_ovito(row, RENDER_PRESETS[args.mode], overwrite=args.overwrite)
        print(f"rendered={rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
