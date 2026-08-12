#!/usr/bin/env python3
"""Run Stage E smoke first, then full production if smoke passes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def command_text(cmd: list[str]) -> str:
    return " ".join(str(x) for x in cmd)


def write_runtime_status(run_dir: Path, status: dict[str, Any]) -> None:
    write_json(run_dir / "stageE_wrapper_status.json", status)
    lines = [
        "# Stage E runtime status",
        "",
        f"Updated: {now()}",
        f"Run root: `{run_dir}`",
        f"Wrapper PID: `{status.get('wrapper_pid')}`",
        f"Status: `{status.get('status')}`",
        f"Current phase: `{status.get('current_phase')}`",
        "",
        "## Phase results",
        "",
        f"- smoke_returncode: `{status.get('smoke_returncode')}`",
        f"- full_returncode: `{status.get('full_returncode')}`",
        "",
        "## Commands",
        "",
        f"- smoke: `{status.get('smoke_command')}`",
        f"- full: `{status.get('full_command')}`",
    ]
    (run_dir / "stageE_runtime_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_completion_check(run_dir: Path, cfg: dict[str, Any], status: dict[str, Any]) -> None:
    state = read_json(run_dir / "state.json", {})
    stage_name = next(iter(cfg.get("stages", {"unknown": {}})))
    stage_state = state.get("stages", {}).get(stage_name, {})
    lines = [
        "# Stage E completion check",
        "",
        f"Updated: {now()}",
        f"Wrapper status: `{status.get('status')}`",
        f"Stage state: `{stage_state.get('status', 'not_available')}`",
        "",
        "## Required completion criteria",
        "",
        "- control and physical production cases reach exit code 0",
        "- no ERROR/nan/lost atoms/cudaError/illegal memory markers",
        "- final dump, final data, restart, and analysis JSON exist for both production cases",
        "- control-vs-physical defect and stress reports are regenerated from completed analysis",
        "",
        "## Current result",
        "",
    ]
    if status.get("status") == "full_completed":
        lines.append("- full production command returned zero; inspect `state.json` and production case artifacts before final physics interpretation")
    elif status.get("status") == "smoke_failed":
        lines.append("- smoke failed; full production was not launched")
    elif status.get("status") == "full_failed":
        lines.append("- full production returned nonzero; inspect runner logs")
    else:
        lines.append("- run is still in progress")
    (run_dir / "stageE_completion_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def refresh_case_summaries(run_dir: Path, cfg: dict[str, Any], status: dict[str, Any]) -> None:
    stage = next(iter(cfg["stages"]))
    state = read_json(run_dir / "state.json", {})
    case_dir = run_dir / "case_summaries"
    case_dir.mkdir(parents=True, exist_ok=True)
    for case in cfg["stages"][stage]["cases"]:
        cid = str(case["case_id"])
        summary = {
            "case_id": cid,
            "stage": stage,
            "atom_target": int(case["atom_target"]),
            "eps_z": float(case["eps_z"]),
            "position": case["position"],
            "predefect": case["predefect"],
            "wrapper_status": status.get("status"),
            "prep": state.get("cases", {}).get(f"{cid}_prep"),
            "smoke": state.get("cases", {}).get(f"{cid}_smoke"),
            "production": state.get("cases", {}).get(f"{cid}_production"),
        }
        write_json(case_dir / f"{cid}_summary.json", summary)


def run_phase(label: str, cmd: list[str], stdout_path: Path, stderr_path: Path, run_dir: Path, status: dict[str, Any]) -> int:
    status["current_phase"] = label
    status["status"] = f"{label}_running"
    write_runtime_status(run_dir, status)
    with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), stdout=stdout, stderr=stderr)
    status[f"{label}_returncode"] = proc.returncode
    status[f"{label}_finished_at"] = now()
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--stage", required=True)
    args = parser.parse_args(argv)

    config = Path(args.config).resolve()
    run_dir = Path(args.run_dir).resolve()
    cfg = load_yaml(config)
    smoke_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_stage_sweep.py"),
        "--config",
        str(config),
        "--run-dir",
        str(run_dir),
        "--run-stage",
        args.stage,
        "--gpu",
        "--smoke-only",
    ]
    full_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_stage_sweep.py"),
        "--config",
        str(config),
        "--run-dir",
        str(run_dir),
        "--run-stage",
        args.stage,
        "--gpu",
    ]
    status: dict[str, Any] = {
        "wrapper_pid": None,
        "started_at": now(),
        "status": "starting",
        "current_phase": "init",
        "config": str(config),
        "run_dir": str(run_dir),
        "stage": args.stage,
        "smoke_command": command_text(smoke_cmd),
        "full_command": command_text(full_cmd),
        "smoke_returncode": None,
        "full_returncode": None,
    }
    try:
        import os

        status["wrapper_pid"] = os.getpid()
    except Exception:
        pass

    write_runtime_status(run_dir, status)
    smoke_rc = run_phase(
        "smoke",
        smoke_cmd,
        run_dir / "stageE_smoke_stdout.txt",
        run_dir / "stageE_smoke_stderr.txt",
        run_dir,
        status,
    )
    refresh_case_summaries(run_dir, cfg, status)
    write_completion_check(run_dir, cfg, status)
    if smoke_rc != 0:
        status["status"] = "smoke_failed"
        status["current_phase"] = "stopped"
        write_runtime_status(run_dir, status)
        write_completion_check(run_dir, cfg, status)
        refresh_case_summaries(run_dir, cfg, status)
        return smoke_rc

    full_rc = run_phase(
        "full",
        full_cmd,
        run_dir / "stageE_full_stdout.txt",
        run_dir / "stageE_full_stderr.txt",
        run_dir,
        status,
    )
    status["status"] = "full_completed" if full_rc == 0 else "full_failed"
    status["current_phase"] = "done" if full_rc == 0 else "stopped"
    status["finished_at"] = now()
    write_runtime_status(run_dir, status)
    write_completion_check(run_dir, cfg, status)
    refresh_case_summaries(run_dir, cfg, status)
    return full_rc


if __name__ == "__main__":
    raise SystemExit(main())
