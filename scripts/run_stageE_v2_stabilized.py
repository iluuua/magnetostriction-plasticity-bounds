#!/usr/bin/env python3
"""Stage E v2 stabilized supervisor.

Creates a v2 run root, runs smoke with a live temperature gate, and starts
production only after stable smoke. It never runs more than one child LAMMPS
process at a time.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner import builder, gpu_grid  # noqa: E402

BASE_CONFIG = REPO_ROOT / "configs" / "stageE_homogeneous_inclusion_scaleup.template.yaml"
RUN_ROOT = REPO_ROOT / "runs" / "stageE_homogeneous_inclusion_scaleup_v2"
STAGE = "E2v2"
TARGETS = [500_000, 250_000]
TEMP_LIMIT_K = 1000.0
PHYSICAL_EPS = 0.001942


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


def active_stage_processes(ignore_pids: set[int] | None = None) -> list[dict[str, Any]]:
    ignore_pids = set(ignore_pids or set())
    ps = (
        "$items = Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -and ("
        "$_.CommandLine -like '*run_stageE*' -or "
        "$_.CommandLine -like '*run_stage_sweep.py*' -or "
        "$_.Name -like 'lmp_kokkos_cuda*') }; "
        "$items | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    text = proc.stdout.strip()
    if not text:
        return []
    try:
        rows = json.loads(text)
    except json.JSONDecodeError:
        return [{"error": text}]
    if isinstance(rows, dict):
        rows = [rows]
    out = []
    for row in rows:
        pid = int(row.get("ProcessId") or -1)
        cmd = str(row.get("CommandLine") or "")
        name = str(row.get("Name") or "")
        if pid in ignore_pids:
            continue
        # The one-shot launcher itself contains "run_stageE" in its command
        # line; only a --worker instance represents a live supervised run.
        if "run_stageE_v2_stabilized.py" in cmd and "--worker" not in cmd:
            continue
        # Ignore the transient PowerShell process that performs this query.
        if name.lower() == "powershell.exe" and "Get-CimInstance Win32_Process" in cmd:
            continue
        out.append({"pid": pid, "name": name, "command": cmd, "parent": row.get("ParentProcessId")})
    return out


def gpu_line() -> dict[str, Any]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {"available": False}
    proc = subprocess.run(
        [
            exe,
            "--query-gpu=name,memory.total,memory.used,temperature.gpu,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    parts = [p.strip() for p in proc.stdout.split(",", maxsplit=4)]
    if len(parts) < 5:
        return {"available": False, "raw": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    return {
        "available": proc.returncode == 0,
        "name": parts[0],
        "memory_total_mib": int(parts[1]),
        "memory_used_mib": int(parts[2]),
        "temperature_c": int(parts[3]),
        "utilization_gpu_percent": int(parts[4]),
    }


def disk_free_gib() -> float:
    return round(shutil.disk_usage(str(REPO_ROOT)).free / (1024**3), 3)


def build_config(target: int) -> dict[str, Any]:
    base = load_yaml(BASE_CONFIG)
    cfg = copy.deepcopy(base)
    cfg["experiment"]["output_root"] = "runs/stageE_homogeneous_inclusion_scaleup_v2"
    cfg["experiment"]["mode"] = "stageE_v2_stabilized_smoke_then_gated_production"
    cfg["experiment"]["description"] = "Stage E v2 stabilized homogeneous inclusion scale-up"
    cfg["experiment"]["physical_eps_z"] = PHYSICAL_EPS
    cfg["experiment"]["physical_eps_formula_value"] = PHYSICAL_EPS
    cfg["experiment"]["selected_atom_target"] = int(target)
    cfg["experiment"]["stabilization"] = {
        "thermal_sanity_stop_K": TEMP_LIMIT_K,
        "prep_segments": "low-timestep staged NVT ramp",
        "phase_timestep_overrides": {"smoke": 0.0002, "production": 0.0002},
        "no_eps0100": True,
    }
    cfg["production_reliability"]["production_chunk_steps"] = 2000
    cfg["production_reliability"]["max_no_progress_minutes"] = 45
    cfg["io_policy"]["thermo_every"]["smoke"] = 50
    cfg["io_policy"]["thermo_every"]["production"] = 500
    cfg["resources"]["max_run_hours"]["smoke"] = 20
    cfg["resources"]["max_run_hours"][f"production_{STAGE}"] = 72
    cfg["stages"] = {
        STAGE: {
            "enabled": True,
            "structure_mode": "build_stageB_realism_100k",
            "atom_targets": [int(target)],
            "eps_z": [0.0, PHYSICAL_EPS],
            "smoke_steps": 500,
            "short_steps": 0,
            "production_steps": 10000,
            "phase_timesteps": {"smoke": 0.0002, "production": 0.0002},
            "prep_t_start_K": 10.0,
            "prep_ramp_steps": 0,
            "prep_steps": 0,
            "prep_restart_every": 2000,
            "prep_dump_every": 2000,
            "prep_dump_fields": ["id", "type", "x", "y", "z"],
            "prep_segments": [
                {"label": "cold_settle_10K", "steps": 500, "timestep": 0.0001, "temp_start_K": 10, "temp_end_K": 10, "tdamp": 0.05},
                {"label": "ramp_10_100K", "steps": 500, "timestep": 0.0001, "temp_start_K": 10, "temp_end_K": 100, "tdamp": 0.10},
                {"label": "ramp_100_200K", "steps": 500, "timestep": 0.0001, "temp_start_K": 100, "temp_end_K": 200, "tdamp": 0.10},
                {"label": "ramp_200_300K", "steps": 500, "timestep": 0.0001, "temp_start_K": 200, "temp_end_K": 300, "tdamp": 0.10},
                {"label": "hold_300K_low_dt", "steps": 1000, "timestep": 0.0001, "temp_start_K": 300, "temp_end_K": 300, "tdamp": 0.10},
            ],
            "run_short_after_smoke_pass": False,
            "run_production_after_smoke_pass": True,
            "gate_required_before_each_production": False,
            "analyze_after_production": True,
            "max_smoke_cases": 2,
            "max_production_cases": 2,
            "production_case_ids": ["E2_ctl0", "E2_phys00194"],
            "cases": [
                {
                    "case_id": "E2_ctl0",
                    "atom_target": int(target),
                    "position": "grain_interior",
                    "predefect": "perfect",
                    "eps_z": 0.0,
                    "deterministic_seed": 86001,
                },
                {
                    "case_id": "E2_phys00194",
                    "atom_target": int(target),
                    "position": "grain_interior",
                    "predefect": "perfect",
                    "eps_z": PHYSICAL_EPS,
                    "deterministic_seed": 86002,
                },
            ],
        }
    }
    return cfg


def thermo_rows(log_path: Path) -> list[dict[str, float]]:
    if not log_path.is_file():
        return []
    rows: list[dict[str, float]] = []
    columns: list[str] | None = None
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if parts and parts[0] == "Step":
            columns = parts
            continue
        if not columns or len(parts) != len(columns):
            continue
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            continue
        rows.append(dict(zip(columns, vals)))
    return rows


def latest_thermal_status(run_dir: Path) -> dict[str, Any]:
    logs = sorted((run_dir / "cases").glob("**/log.*.lammps"), key=lambda p: p.stat().st_mtime)
    max_temp = None
    latest = None
    source = None
    for log in logs:
        for row in thermo_rows(log):
            temp = row.get("Temp")
            if temp is not None and (max_temp is None or temp > max_temp):
                max_temp = temp
            latest = row
            source = str(log)
    return {"max_temp_K": max_temp, "latest_thermo": latest, "latest_log": source}


def kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, timeout=60)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def write_reports(run_dir: Path, status: dict[str, Any]) -> None:
    write_json(run_dir / "stageE_v2_status.json", status)
    write_json(run_dir / "stageE_v2_analysis_summary.json", status)
    lines = [
        "# Stage E v2 runtime status",
        "",
        f"Updated: {now()}",
        f"Run root: `{run_dir}`",
        f"Status: `{status.get('status')}`",
        f"Target atoms: `{status.get('target_atoms')}`",
        f"Smoke status: `{status.get('smoke_status')}`",
        f"Production status: `{status.get('production_status')}`",
        f"Current phase: `{status.get('current_phase')}`",
        f"Current case: `{status.get('current_case')}`",
        f"Current step: `{status.get('current_step')}`",
        f"Temperature K: `{status.get('current_temp_K')}`",
        f"Max temperature K: `{status.get('max_temp_K')}`",
        f"GPU: `{status.get('gpu')}`",
        f"C free disk GiB: `{status.get('disk_free_gib')}`",
        "",
        "## Notes",
        "",
        f"- thermal_sanity_stop_K: `{TEMP_LIMIT_K}`",
        "- production is gated on smoke stability and output checks",
        "- v1 failed output is not used as a physics result",
    ]
    if status.get("blockers"):
        lines += ["", "## Blockers", ""]
        lines += [f"- {item}" for item in status["blockers"]]
    (run_dir / "stageE_v2_runtime_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (run_dir / "stageE_v2_boundary_dislocation_report.md").write_text(
        "\n".join(
            [
                "# Stage E v2 boundary/dislocation report",
                "",
                f"Status: `{status.get('status')}`",
                "",
                "DXA/dislocation analysis is pending until stable production and analyze-only complete.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "stageE_v2_failure_or_success_report.md").write_text(
        "\n".join(
            [
                "# Stage E v2 failure or success report",
                "",
                f"Status: `{status.get('status')}`",
                f"Target atoms: `{status.get('target_atoms')}`",
                f"Max temperature K: `{status.get('max_temp_K')}`",
                f"Smoke status: `{status.get('smoke_status')}`",
                f"Production status: `{status.get('production_status')}`",
                "",
                "The v2 protocol uses low-timestep prep segments, exact physical eps00194, and a live 1000 K thermal sanity stop.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def update_status_from_run(run_dir: Path, status: dict[str, Any]) -> dict[str, Any]:
    thermal = latest_thermal_status(run_dir)
    latest = thermal.get("latest_thermo") or {}
    status.update(
        {
            "updated_at": now(),
            "max_temp_K": thermal.get("max_temp_K"),
            "current_step": int(latest.get("Step")) if latest.get("Step") is not None else None,
            "current_temp_K": latest.get("Temp"),
            "current_press_bar": latest.get("Press"),
            "current_pzz_bar": latest.get("Pzz"),
            "latest_log": thermal.get("latest_log"),
            "gpu": gpu_line(),
            "disk_free_gib": disk_free_gib(),
        }
    )
    return status


def run_guarded(status_root: Path, scan_dir: Path, status: dict[str, Any], label: str, cmd: list[str]) -> int:
    status["current_phase"] = label
    status["status"] = f"{label}_running"
    status[f"{label}_status"] = "running"
    status[f"{label}_command"] = command_text(cmd)
    write_reports(status_root, update_status_from_run(scan_dir, status))
    stdout_path = status_root / f"stageE_v2_{label}_stdout.txt"
    stderr_path = status_root / f"stageE_v2_{label}_stderr.txt"
    with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as err:
        proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=out, stderr=err, text=True)
        status[f"{label}_pid"] = proc.pid
        while True:
            rc = proc.poll()
            status = update_status_from_run(scan_dir, status)
            if status.get("max_temp_K") is not None and float(status["max_temp_K"]) > TEMP_LIMIT_K:
                status["status"] = f"{label}_invalid_temperature"
                status[f"{label}_status"] = "invalid_temperature"
                status[f"{label}_returncode"] = None
                status.setdefault("blockers", []).append(
                    f"{label} exceeded thermal sanity stop: max Temp {status['max_temp_K']} K > {TEMP_LIMIT_K} K"
                )
                write_reports(status_root, status)
                kill_process_tree(proc.pid)
                return 70
            if rc is not None:
                status[f"{label}_status"] = "completed" if rc == 0 else "failed"
                status[f"{label}_returncode"] = int(rc)
                status[f"{label}_finished_at"] = now()
                write_reports(status_root, status)
                return int(rc)
            write_reports(status_root, status)
            time.sleep(30)


def smoke_outputs_ok(run_dir: Path, target: int) -> tuple[bool, list[str]]:
    state = read_json(run_dir / "state.json", {})
    reasons: list[str] = []
    cases = ["E2_ctl0_smoke", "E2_phys00194_smoke"]
    for cid in cases:
        rec = state.get("cases", {}).get(cid) or {}
        if not rec.get("success"):
            reasons.append(f"{cid} not successful")
        names = {o.get("name") for o in rec.get("outputs", [])}
        for expected in (f"data.{cid}_final", f"dump.{cid}_final.lammpstrj"):
            if expected not in names:
                reasons.append(f"{cid} missing {expected}")
    return not reasons, reasons


def prepare_run_dir() -> Path:
    cfg0 = build_config(TARGETS[0])
    run_dir = gpu_grid.make_run_dir(cfg0)
    return run_dir


def write_agent_report(run_dir: Path, status: dict[str, Any]) -> None:
    path = REPO_ROOT / "agent_report_stageE_v2_stabilized_scaleup.md"
    lines = [
        "# Stage E v2 stabilized scale-up",
        "",
        f"Updated: {now()}",
        f"Run root: `{run_dir}`",
        f"Status: `{status.get('status')}`",
        f"Target atoms: `{status.get('target_atoms')}`",
        f"Smoke status: `{status.get('smoke_status')}`",
        f"Production status: `{status.get('production_status')}`",
        f"Max temp K: `{status.get('max_temp_K')}`",
        "",
        "v1 is invalid as physics output because prep overheated and production failed with CUDA illegal memory access.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def worker(run_dir: Path) -> int:
    status: dict[str, Any] = {
        "status": "starting",
        "started_at": now(),
        "run_dir": str(run_dir),
        "thermal_sanity_stop_K": TEMP_LIMIT_K,
        "targets_attempted": [],
        "smoke_status": "not_started",
        "production_status": "not_started",
        "analysis_status": "not_started",
        "valid_physics_result": False,
        "blockers": [],
    }
    for target in TARGETS:
        cfg = build_config(target)
        attempt_dir = run_dir / "attempts" / f"a{int(target / 1000)}k"
        gpu_grid.make_run_dir(cfg, explicit_run_dir=attempt_dir)
        (attempt_dir / "effective_config.yaml").write_text(
            yaml.safe_dump(cfg, sort_keys=False, allow_unicode=False), encoding="utf-8"
        )
        status.update(
            {
                "target_atoms": int(target),
                "active_attempt_run_dir": str(attempt_dir),
                "targets_attempted": status["targets_attempted"] + [int(target)],
                "max_temp_K": None,
                "current_step": None,
                "current_temp_K": None,
                "current_press_bar": None,
                "current_pzz_bar": None,
                "latest_log": None,
            }
        )
        write_reports(run_dir, update_status_from_run(attempt_dir, status))
        smoke_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_stage_sweep.py"),
            "--config",
            str(attempt_dir / "effective_config.yaml"),
            "--run-dir",
            str(attempt_dir),
            "--run-stage",
            STAGE,
            "--gpu",
            "--smoke-only",
        ]
        smoke_rc = run_guarded(run_dir, attempt_dir, status, "smoke", smoke_cmd)
        status = read_json(run_dir / "stageE_v2_status.json", status)
        if smoke_rc != 0:
            status["smoke_status"] = "invalid_or_failed"
            status["production_status"] = "not_started"
            write_reports(run_dir, status)
            if target == TARGETS[-1]:
                write_agent_report(run_dir, status)
                return smoke_rc
            status.setdefault("blockers", []).append(f"{target} smoke failed/invalid; preparing fallback")
            write_reports(run_dir, status)
            continue
        ok, reasons = smoke_outputs_ok(attempt_dir, target)
        if not ok:
            status["smoke_status"] = "failed_outputs"
            status.setdefault("blockers", []).extend(reasons)
            write_reports(run_dir, status)
            if target == TARGETS[-1]:
                write_agent_report(run_dir, status)
                return 71
            continue
        status["smoke_status"] = "stable"
        write_reports(run_dir, status)

        full_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_stage_sweep.py"),
            "--config",
            str(attempt_dir / "effective_config.yaml"),
            "--run-dir",
            str(attempt_dir),
            "--run-stage",
            STAGE,
            "--gpu",
        ]
        full_rc = run_guarded(run_dir, attempt_dir, status, "production", full_cmd)
        status = read_json(run_dir / "stageE_v2_status.json", status)
        if full_rc != 0:
            status["production_status"] = "failed_or_invalid"
            write_reports(run_dir, status)
            write_agent_report(run_dir, status)
            return full_rc
        status["production_status"] = "completed"
        analyze_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_stage_sweep.py"),
            "--config",
            str(attempt_dir / "effective_config.yaml"),
            "--run-dir",
            str(attempt_dir),
            "--analyze-only",
        ]
        analyze_rc = run_guarded(run_dir, attempt_dir, status, "analyze", analyze_cmd)
        status = read_json(run_dir / "stageE_v2_status.json", status)
        status["analysis_status"] = "completed" if analyze_rc == 0 else "failed"
        status["valid_physics_result"] = analyze_rc == 0
        status["status"] = "analysis_completed" if analyze_rc == 0 else "analysis_failed"
        write_reports(run_dir, status)
        write_agent_report(run_dir, status)
        return analyze_rc
    write_agent_report(run_dir, status)
    return 1


def launch_worker(run_dir: Path) -> int:
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", "--run-dir", str(run_dir)]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    with (run_dir / "stageE_v2_worker_stdout.txt").open("ab") as out, (
        run_dir / "stageE_v2_worker_stderr.txt"
    ).open("ab") as err:
        proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=out, stderr=err, text=True, creationflags=creationflags)
    return int(proc.pid)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--run-dir", default=None)
    args = parser.parse_args(argv)
    if args.worker:
        if not args.run_dir:
            raise SystemExit("--worker needs --run-dir")
        return worker(Path(args.run_dir).resolve())

    live = active_stage_processes(ignore_pids={os.getpid()})
    if live:
        run_dir = RUN_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "status": "blocked_live_process",
            "started_at": now(),
            "run_dir": str(run_dir),
            "live_processes": live,
            "blockers": ["live Stage E/runner/LAMMPS process exists"],
            "smoke_status": "not_started",
            "production_status": "not_started",
            "valid_physics_result": False,
        }
        write_reports(run_dir, status)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 2

    run_dir = prepare_run_dir()
    status = {
        "status": "launched_worker",
        "started_at": now(),
        "run_dir": str(run_dir),
        "target_atoms": TARGETS[0],
        "smoke_status": "starting",
        "production_status": "not_started",
        "analysis_status": "not_started",
        "valid_physics_result": False,
        "blockers": [],
        "gpu": gpu_line(),
        "disk_free_gib": disk_free_gib(),
    }
    worker_pid = launch_worker(run_dir)
    status["worker_pid"] = worker_pid
    write_reports(run_dir, status)
    write_agent_report(run_dir, status)
    print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "worker_pid": worker_pid}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
