#!/usr/bin/env python3
"""Build or execute a reproducible 30 FPS ffmpeg command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from event_pipeline.video import execute_ffmpeg, write_video_plan_outputs  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="encode_animation_30fps.py", description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--frame-manifest-json", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--output-name", default="event_animation_30fps.mp4")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--execute", action="store_true", help="run ffmpeg; default writes dry-run command only")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    result = write_video_plan_outputs(
        args.run_root,
        frame_manifest_json=args.frame_manifest_json,
        output_dir=args.output_dir,
        output_name=args.output_name,
        fps=args.fps,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") != "dry_run_plan_ready":
        return 1
    if not args.execute:
        print("DRY-RUN: ffmpeg command written; ffmpeg was not invoked.")
        return 0
    return execute_ffmpeg(list(result["ffmpeg_command"]))


if __name__ == "__main__":
    raise SystemExit(main())
