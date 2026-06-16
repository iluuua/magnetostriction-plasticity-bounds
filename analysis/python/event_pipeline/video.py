"""ffmpeg command and video manifest helpers."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .timeline import normalize_path, read_json, write_json


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def build_ffmpeg_command(
    input_pattern: str | Path,
    output_mp4: str | Path,
    *,
    fps: int = 30,
    width: int = 1920,
    overwrite: bool = False,
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    return [
        ffmpeg,
        "-y" if overwrite else "-n",
        "-framerate",
        str(fps),
        "-i",
        str(input_pattern),
        "-vf",
        f"scale={width}:-2:flags=lanczos",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_mp4),
    ]


def load_manifest(path: str | Path) -> list[dict[str, Any]]:
    data = read_json(normalize_path(path), {}) or {}
    return list(data.get("frames") or [])


def write_video_plan_outputs(
    run_root: str | Path,
    *,
    frame_manifest_json: str | Path | None = None,
    output_dir: str | Path | None = None,
    output_name: str = "event_animation_30fps.mp4",
    fps: int = 30,
    overwrite: bool = False,
) -> dict[str, Any]:
    root = normalize_path(run_root)
    manifest_path = (
        normalize_path(frame_manifest_json)
        if frame_manifest_json
        else root / "event_pipeline" / "event_frame_manifest.json"
    )
    out = normalize_path(output_dir) if output_dir else root / "event_pipeline" / "videos"
    frames = load_manifest(manifest_path)
    if not frames:
        return {
            "generated_at": now_stamp(),
            "run_root": str(root),
            "status": "blocked_no_frames",
            "frame_manifest_json": str(manifest_path),
            "manual_execute_required": True,
        }
    first_output = Path(str(frames[0]["output_png"]))
    pattern = first_output.parent / "*.png"
    output_mp4 = out / output_name
    command = build_ffmpeg_command(pattern, output_mp4, fps=fps, overwrite=overwrite)
    video_manifest = {
        "generated_at": now_stamp(),
        "run_root": str(root),
        "status": "dry_run_plan_ready",
        "fps": fps,
        "frame_count": len(frames),
        "frame_manifest_json": str(manifest_path),
        "source_frame_glob": str(pattern),
        "output_mp4": str(output_mp4),
        "ffmpeg_command": command,
        "manual_execute_required": True,
        "overwrite": overwrite,
    }
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{Path(output_name).stem}.manifest.json"
    command_path = out / f"{Path(output_name).stem}.ffmpeg.txt"
    write_json(json_path, video_manifest)
    command_path.write_text(" ".join(command) + "\n", encoding="utf-8")
    return {**video_manifest, "writes": [str(json_path), str(command_path)]}


def execute_ffmpeg(command: list[str]) -> int:
    proc = subprocess.run(command)
    return int(proc.returncode)
