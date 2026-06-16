"""Event window selection and high-frequency rerun dry-run planning."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .timeline import as_float, as_int, normalize_path, read_json, write_json


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class EventWindowPolicy:
    pre_steps: int = 10000
    post_steps: int = 10000
    dump_every: int = 100
    analysis_every: int = 100
    min_start_step: int = 0


def load_timeline(path: str | Path) -> list[dict[str, Any]]:
    p = normalize_path(path)
    data = read_json(p, {}) or {}
    if isinstance(data, dict):
        return list(data.get("frames") or [])
    if isinstance(data, list):
        return data
    return []


def parse_step_from_restart(path: Path) -> int | None:
    numbers = re.findall(r"(?:\.|_)(\d{4,})$", path.name)
    if numbers:
        return int(numbers[-1])
    all_numbers = re.findall(r"(\d{4,})", path.name)
    return int(all_numbers[-1]) if all_numbers else None


def find_restart_candidates(run_root: str | Path, case_id: str) -> list[dict[str, Any]]:
    root = normalize_path(run_root)
    rows: list[dict[str, Any]] = []
    for path in root.glob("cases/**/production/restart*"):
        text = path.as_posix()
        if case_id not in text and case_id.replace("_production", "") not in text:
            continue
        step = parse_step_from_restart(path)
        rows.append({"path": str(path), "step": step})
    return sorted(rows, key=lambda r: (as_int(r["step"], -1) or -1, str(r["path"])))


def choose_focus_row(rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    confirmed = [r for r in rows if r.get("event_class") == "confirmed_DXA"]
    if confirmed:
        return sorted(confirmed, key=lambda r: as_int(r.get("timestep"), 10**18) or 10**18)[0], "confirmed_DXA_first"
    weak = [r for r in rows if r.get("event_class") == "weak_hcp"]
    if weak:
        return sorted(weak, key=lambda r: as_float(r.get("event_score"), 0.0) or 0.0, reverse=True)[0], "weak_hcp_best_score"
    deform = [r for r in rows if r.get("event_class") == "deformation_only"]
    if deform:
        return sorted(deform, key=lambda r: as_float(r.get("event_score"), 0.0) or 0.0, reverse=True)[0], "deformation_only_best_score"
    if rows:
        return rows[0], "no_event_first_available"
    return None, "no_frames_available"


def choose_restart(candidates: list[dict[str, Any]], start_step: int, event_step: int | None) -> dict[str, Any] | None:
    before_start = [r for r in candidates if r.get("step") is not None and int(r["step"]) <= start_step]
    if before_start:
        return before_start[-1]
    if event_step is not None:
        before_event = [r for r in candidates if r.get("step") is not None and int(r["step"]) <= event_step]
        if before_event:
            return before_event[-1]
    return candidates[0] if candidates else None


def plan_event_window(
    run_root: str | Path,
    timeline_rows: list[dict[str, Any]],
    policy: EventWindowPolicy | None = None,
) -> dict[str, Any]:
    root = normalize_path(run_root)
    p = policy or EventWindowPolicy()
    row, selection_reason = choose_focus_row(timeline_rows)
    if row is None:
        return {
            "generated_at": now_stamp(),
            "run_root": str(root),
            "status": "blocked_no_frames",
            "branch": "no_frames",
            "reason": selection_reason,
            "manual_approval_required": True,
        }
    event_step = as_int(row.get("timestep"), None)
    if event_step is None:
        start_step = p.min_start_step
        end_step = p.post_steps
    else:
        start_step = max(p.min_start_step, event_step - p.pre_steps)
        end_step = event_step + p.post_steps
    case_id = str(row.get("case_id") or "")
    restarts = find_restart_candidates(root, case_id)
    restart = choose_restart(restarts, start_step, event_step)
    branch = "confirmed_DXA" if row.get("event_class") == "confirmed_DXA" else "fallback_deformation"
    config_path = root / "event_pipeline" / "event_window_rerun.template.yaml"
    command = (
        ".venv\\Scripts\\python.exe scripts\\run_stage_sweep.py "
        f"--config {config_path} --run-stage event_window_high_frequency --gpu"
    )
    return {
        "generated_at": now_stamp(),
        "run_root": str(root),
        "status": "dry_run_plan_ready",
        "branch": branch,
        "selection_reason": selection_reason,
        "case_id": case_id,
        "event_class": row.get("event_class"),
        "event_frame_id": row.get("frame_id"),
        "event_timestep": event_step,
        "start_step": start_step,
        "end_step": end_step,
        "restart_file": restart["path"] if restart else "",
        "restart_step": restart.get("step") if restart else None,
        "recommended_dump_every": p.dump_every,
        "recommended_analysis_every": p.analysis_every,
        "source_dump_file": row.get("dump_file", ""),
        "source_analysis_file": row.get("analysis_file", ""),
        "manual_approval_required": True,
        "launch_command_template": command,
        "notes": [
            "Plan only: do not launch rerun without separate operator approval.",
            "Use confirmed_DXA branch only when DXA line signal is present.",
            "Fallback branch targets the most informative deformation/weak_hcp frame.",
        ],
    }


def window_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Event Window Dry-Run Plan",
        "",
        f"Generated: {plan.get('generated_at')}",
        f"Run root: `{plan.get('run_root')}`",
        "",
        f"- status: `{plan.get('status')}`",
        f"- branch: `{plan.get('branch')}`",
        f"- case_id: `{plan.get('case_id', '')}`",
        f"- event_class: `{plan.get('event_class', '')}`",
        f"- event_timestep: `{plan.get('event_timestep', '')}`",
        f"- start_step: `{plan.get('start_step', '')}`",
        f"- end_step: `{plan.get('end_step', '')}`",
        f"- restart_file: `{plan.get('restart_file', '')}`",
        f"- dump_every: `{plan.get('recommended_dump_every', '')}`",
        f"- analysis_every: `{plan.get('recommended_analysis_every', '')}`",
        "",
        "## Suggested Command",
        "",
        "```powershell",
        str(plan.get("launch_command_template", "")),
        "```",
        "",
        "This command is intentionally a template. Generate/review the config and obtain explicit approval before launch.",
    ]
    return "\n".join(lines) + "\n"


def rerun_template_yaml(plan: dict[str, Any]) -> str:
    payload = {
        "event_window_high_frequency": {
            "status": "template_not_auto_runnable",
            "source_run_root": plan.get("run_root"),
            "source_case_id": plan.get("case_id"),
            "event_class": plan.get("event_class"),
            "event_timestep": plan.get("event_timestep"),
            "start_step": plan.get("start_step"),
            "end_step": plan.get("end_step"),
            "restart_file": plan.get("restart_file"),
            "dump_every": plan.get("recommended_dump_every"),
            "analysis_every": plan.get("recommended_analysis_every"),
            "manual_approval_required": True,
        }
    }
    lines = ["# Event-window high-frequency rerun template.", "# Review and adapt before any operator-approved launch."]
    for key, value in payload["event_window_high_frequency"].items():
        if isinstance(value, bool):
            value = str(value).lower()
        lines.append(f"{key}: {json.dumps(value) if isinstance(value, str) else value}")
    return "\n".join(lines) + "\n"


def write_event_window_outputs(
    run_root: str | Path,
    timeline_json: str | Path | None = None,
    output_dir: str | Path | None = None,
    policy: EventWindowPolicy | None = None,
) -> dict[str, Any]:
    root = normalize_path(run_root)
    timeline_path = normalize_path(timeline_json) if timeline_json else root / "event_pipeline" / "event_timeline.json"
    out = normalize_path(output_dir) if output_dir else root / "event_pipeline"
    rows = load_timeline(timeline_path)
    plan = plan_event_window(root, rows, policy)
    json_path = out / "event_window_plan.json"
    md_path = out / "event_window_plan.md"
    cfg_path = out / "event_window_rerun.template.yaml"
    write_json(json_path, plan)
    md_path.write_text(window_markdown(plan), encoding="utf-8")
    cfg_path.write_text(rerun_template_yaml(plan), encoding="utf-8")
    return {**plan, "writes": [str(json_path), str(md_path), str(cfg_path)]}
