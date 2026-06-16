#!/usr/bin/env python3
"""Run the safe event-pipeline preparation sequence without external execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from event_pipeline.render import write_render_plan_outputs  # noqa: E402
from event_pipeline.timeline import write_event_timeline_outputs  # noqa: E402
from event_pipeline.video import write_video_plan_outputs  # noqa: E402
from event_pipeline.window import write_event_window_outputs  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_event_pipeline_dry_run.py", description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="accepted for explicit partial-run workflows; dry-run mode already tolerates incomplete inputs",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    timeline = write_event_timeline_outputs(args.run_root, args.output_dir)
    out = args.output_dir or Path(timeline["output_dir"])
    window = write_event_window_outputs(args.run_root, output_dir=out)
    render_results = []
    for mode in ("geometry", "deformation", "dxa", "event", "figures"):
        render_results.append(write_render_plan_outputs(args.run_root, output_dir=out, mode=mode))
    video = write_video_plan_outputs(
        args.run_root,
        frame_manifest_json=Path(out) / "event_frame_manifest.json",
        output_dir=Path(out) / "videos",
    )
    result = {
        "timeline": timeline,
        "window": window,
        "renders": render_results,
        "video": video,
        "external_execution": "not_run",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
