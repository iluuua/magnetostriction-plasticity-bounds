#!/usr/bin/env python3
"""Extract Stage B unstable-run context without launching MD."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner.stageb_postrun import collect_postrun_summary, now_stamp, write_json  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="extract_stageB_failed_case.py", description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = collect_postrun_summary(args.run_root)
    out = Path(args.output_dir) if args.output_dir else summary.run_root / "unstable_debug"
    if not out.is_absolute():
        out = REPO_ROOT / out
    manifest = {
        "generated_at": now_stamp(),
        "run_root": str(summary.run_root),
        "status": summary.status,
        "failed_cases": summary.failed_cases,
        "running_cases": summary.running_cases,
        "action": "debug_geometry_or_protocol; no MD launch",
    }
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    if args.dry_run:
        return 0
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "failed_case_manifest.json", manifest)
    (out / "geometry_debug_report.md").write_text(
        "# Stage B Geometry/Protocol Debug Report\n\n"
        f"Generated: {manifest['generated_at']}\n\n"
        f"Status: `{summary.status}`\n\n"
        f"Failed cases: `{', '.join(summary.failed_cases) or 'none'}`\n\n"
        "No MD was launched. Use the recorded case input/log paths from state.json for manual inspection.\n",
        encoding="utf-8",
    )
    (out / "minimal_reproduction_command.txt").write_text(
        "Manual-only: copy the failed case input into an isolated run directory after owner approval.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

