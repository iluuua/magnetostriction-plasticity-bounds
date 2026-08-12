#!/usr/bin/env python3
"""Prepare, smoke, and launch the Stage E4 700k DXA confirmation run.

The foreground launcher performs preflight and smoke, then starts a monitored
background worker for the long production run. The worker runs the existing
GPU-grid pipeline and keeps the run-root status file fresh while production is
in progress.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_ROOT = REPO_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner import gpu_grid  # noqa: E402

CONFIG = REPO_ROOT / "configs" / "stageE_700k_dxa_confirm.template.yaml"
RUN_STAGE = "E4_700k_dxa_confirm"
CASE_ID = "E4_phys001942_700k_80k"
STATUS_NAME = "stageE_700k_dxa_confirm_status"
TEMP_LIMIT_K = 1000.0
DISK_MIN_GIB = 22.0
DISK_RECOMMENDED_GIB = 25.0


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


def command_text(cmd: list[str | Path]) -> str:
    return " ".join(str(x) for x in cmd)


def disk_free_gib(path: Path | str) -> float:
    return shutil.disk_usage(str(path)).free / (1024**3)


def powershell_json(command: str) -> Any:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
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
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text, "stderr": proc.stderr.strip(), "returncode": proc.returncode}
    return data if isinstance(data, list) else [data]


def active_stage_processes(ignore_pids: set[int] | None = None) -> list[dict[str, Any]]:
    ignore_pids = set(ignore_pids or set())
    query = (
        "$items = Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -and ("
        "$_.CommandLine -like '*run_stage_sweep.py*' -or "
        "$_.CommandLine -like '*E4_700k_dxa_confirm*' -or "
        "$_.CommandLine -like '*stageE_700k_dxa_confirm*' -or "
        "$_.CommandLine -like '*stageE*' -or "
        "$_.Name -like 'lmp_kokkos_cuda*' -or "
        "$_.Name -like 'lmp.exe' -or "
        "$_.Name -like 'mpiexec*') }; "
        "$items | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    )
    rows = powershell_json(query)
    if not isinstance(rows, list):
        return [{"error": rows}]
    out: list[dict[str, Any]] = []
    for row in rows:
        pid = int(row.get("ProcessId") or -1)
        name = str(row.get("Name") or "")
        cmd = str(row.get("CommandLine") or "")
        low = f"{name} {cmd}".lower()
        if pid in ignore_pids:
            continue
        if name.lower() == "powershell.exe" and "get-ciminstance win32_process" in low:
            continue
        if "run_stagee_700k_dxa_confirm.py" in low and "--worker" not in low:
            continue
        out.append(
            {
                "pid": pid,
                "parent": row.get("ParentProcessId"),
                "name": name,
                "command": cmd,
            }
        )
    return out


def gpu_snapshot() -> dict[str, Any]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {"available": False, "reason": "nvidia-smi not found"}
    proc = subprocess.run(
        [
            exe,
            "--query-gpu=name,memory.total,memory.used,temperature.gpu,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
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


def nvidia_pmon_rows() -> list[dict[str, Any]]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    proc = subprocess.run(
        [exe, "pmon", "-c", "1"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    rows: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 8 or parts[1] == "-":
            continue
        rows.append({"gpu": parts[0], "pid": parts[1], "type": parts[2], "command": " ".join(parts[7:])})
    return rows


def memory_snapshot() -> dict[str, Any]:
    rows = powershell_json(
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object TotalVisibleMemorySize,FreePhysicalMemory,TotalVirtualMemorySize,FreeVirtualMemory | "
        "ConvertTo-Json -Compress"
    )
    if isinstance(rows, list) and rows:
        return rows[0]
    return {}


def thermo_rows(log_path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    if not log_path.is_file():
        return rows
    header: list[str] | None = None
    numeric = re.compile(r"^\s*[-+]?\d")
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("Step") and "Temp" in stripped:
            header = stripped.split()
            continue
        if not header or not numeric.match(line):
            continue
        parts = stripped.split()
        if len(parts) < len(header):
            continue
        try:
            rows.append({key: float(value) for key, value in zip(header, parts)})
        except ValueError:
            continue
    return rows


def thermal_status(run_dir: Path) -> dict[str, Any]:
    max_temp = None
    latest = None
    source = None
    for log in sorted(run_dir.glob("cases/**/*.lammps"), key=lambda p: p.stat().st_mtime):
        for row in thermo_rows(log):
            temp = row.get("Temp")
            if temp is not None:
                max_temp = temp if max_temp is None else max(max_temp, temp)
            latest = row
            source = str(log)
    return {
        "max_temp_K": max_temp,
        "latest_thermo": latest,
        "latest_log": source,
        "current_step": int(latest["Step"]) if latest and latest.get("Step") is not None else None,
        "current_temp_K": latest.get("Temp") if latest else None,
        "current_press_bar": latest.get("Press") if latest else None,
    }


def kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, timeout=60)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def status_paths(run_dir: Path) -> tuple[Path, Path]:
    return run_dir / f"{STATUS_NAME}.json", run_dir / f"{STATUS_NAME}.md"


def write_status(run_dir: Path, status: dict[str, Any]) -> None:
    status["updated_at"] = now()
    status["disk_free_gib"] = {
        "C": round(disk_free_gib("C:\\"), 3),
        "B": round(disk_free_gib("B:\\") if Path("B:\\").exists() else 0.0, 3),
        "run_root": round(disk_free_gib(run_dir), 3),
    }
    status["thermal"] = thermal_status(run_dir)
    status["active_processes"] = active_stage_processes(ignore_pids={os.getpid()})
    json_path, md_path = status_paths(run_dir)
    write_json(json_path, status)
    lines = [
        "# Stage E4 700k DXA confirmation status",
        "",
        f"Updated: `{status['updated_at']}`",
        f"Run root: `{run_dir}`",
        f"Status: `{status.get('status')}`",
        f"Smoke returncode: `{status.get('smoke_returncode')}`",
        f"Production returncode: `{status.get('production_returncode')}`",
        f"Analysis status: `{status.get('analysis_status')}`",
        f"Current phase: `{status.get('current_phase')}`",
        f"Current step: `{status.get('thermal', {}).get('current_step')}`",
        f"Current temp K: `{status.get('thermal', {}).get('current_temp_K')}`",
        f"Max temp K: `{status.get('thermal', {}).get('max_temp_K')}`",
        f"C free disk GiB: `{status.get('disk_free_gib', {}).get('C')}`",
        f"B free disk GiB: `{status.get('disk_free_gib', {}).get('B')}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = status.get("blockers") or []
    lines.extend([f"- {item}" for item in blockers] if blockers else ["- none"])
    lines += [
        "",
        "## Commands",
        "",
        f"- smoke: `{status.get('smoke_command')}`",
        f"- production: `{status.get('production_command')}`",
        f"- worker: `{status.get('worker_command')}`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def preflight(run_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    env_ok, env_report, env_lines = gpu_grid.check_environment(cfg)
    active = active_stage_processes(ignore_pids={os.getpid()})
    c_free = disk_free_gib("C:\\")
    b_free = disk_free_gib("B:\\") if Path("B:\\").exists() else None
    gpu = gpu_snapshot()
    blockers: list[str] = []
    if active:
        blockers.append("live Stage E/LAMMPS/run_stage_sweep process exists")
    if c_free < DISK_MIN_GIB:
        blockers.append(f"C: free disk below {DISK_MIN_GIB:.0f} GiB: {c_free:.3f} GiB")
    if not gpu.get("available"):
        blockers.append(f"nvidia-smi unavailable: {gpu}")
    if not env_ok:
        blockers.extend(line for line in env_lines if line.startswith("FAIL"))
    return {
        "generated_at": now(),
        "run_root": str(run_dir),
        "disk_free_gib": {
            "C": round(c_free, 3),
            "B": round(b_free, 3) if b_free is not None else None,
            "required_C_for_production": DISK_MIN_GIB,
            "recommended_C_for_production": DISK_RECOMMENDED_GIB,
        },
        "active_stage_processes": active,
        "gpu": gpu,
        "nvidia_pmon": nvidia_pmon_rows(),
        "memory": memory_snapshot(),
        "environment_ok": env_ok,
        "environment_lines": env_lines,
        "environment_report": env_report,
        "blockers": blockers,
        "cleanup_performed": False,
        "cleanup_note": "No old run roots were deleted.",
        "raw_output_policy": "run root remains under project output_root on C:; no new B: raw-output scheme was invented.",
        "neighbor_workaround": "neigh_modify    delay 0 every 10 check no",
        "neighbor_workaround_note": "run-local workaround only; not an upstream LAMMPS/KOKKOS fix",
    }


def assert_command_gate(cmd: list[str | Path], cfg: dict[str, Any]) -> dict[str, Any]:
    text = command_text(cmd)
    stage = cfg["stages"][RUN_STAGE]
    case = stage["cases"][0]
    checks = {
        "uses_run_stage_sweep": "run_stage_sweep.py" in text,
        "uses_expected_stage": "--run-stage" in text and RUN_STAGE in text,
        "uses_gpu": "--gpu" in text,
        "target_atoms_700000": int(case["atom_target"]) == 700000,
        "production_steps_80000": int(stage["production_steps"]) == 80000,
        "eps_z_0p001942": math.isclose(float(case["eps_z"]), 0.001942, rel_tol=0, abs_tol=1e-12),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError(f"launch command/config gate failed: {failed}; command={text}")
    return {"command": text, "checks": checks}


def run_phase(run_dir: Path, status: dict[str, Any], label: str, cmd: list[str | Path]) -> int:
    status["current_phase"] = label
    status["status"] = f"{label}_running"
    status[f"{label}_command"] = command_text(cmd)
    write_status(run_dir, status)
    stdout_path = run_dir / f"stageE_700k_{label}_stdout.txt"
    stderr_path = run_dir / f"stageE_700k_{label}_stderr.txt"
    with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as err:
        proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=out, stderr=err, text=True)
        status[f"{label}_pid"] = proc.pid
        while True:
            rc = proc.poll()
            thermal = thermal_status(run_dir)
            status["thermal"] = thermal
            if thermal.get("max_temp_K") is not None and float(thermal["max_temp_K"]) > TEMP_LIMIT_K:
                status["status"] = f"{label}_invalid_temperature"
                status[f"{label}_returncode"] = None
                status.setdefault("blockers", []).append(
                    f"{label} exceeded thermal sanity stop: max Temp {thermal['max_temp_K']} K > {TEMP_LIMIT_K} K"
                )
                write_status(run_dir, status)
                kill_process_tree(proc.pid)
                return 70
            if rc is not None:
                status[f"{label}_returncode"] = int(rc)
                status[f"{label}_finished_at"] = now()
                status["status"] = f"{label}_completed" if rc == 0 else f"{label}_failed"
                write_status(run_dir, status)
                return int(rc)
            write_status(run_dir, status)
            time.sleep(30)


def production_record(run_dir: Path) -> dict[str, Any]:
    state = read_json(run_dir / "state.json", {})
    return (state.get("cases") or {}).get(f"{CASE_ID}_production") or {}


def smoke_record(run_dir: Path) -> dict[str, Any]:
    state = read_json(run_dir / "state.json", {})
    return (state.get("cases") or {}).get(f"{CASE_ID}_smoke") or {}


def analysis_path(run_dir: Path) -> Path | None:
    rec = production_record(run_dir)
    raw = rec.get("analysis")
    if raw and Path(raw).is_file():
        return Path(raw)
    candidates = sorted(run_dir.glob(f"cases/{RUN_STAGE}/{CASE_ID}/production/analysis.json"))
    return candidates[0] if candidates else None


def positive_burgers_lengths(analysis: dict[str, Any]) -> dict[str, float]:
    attrs = analysis.get("dxa_attributes") or {}
    out: dict[str, float] = {}
    for key, value in attrs.items():
        if not key.startswith("DislocationAnalysis.length."):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0.0:
            out[key.replace("DislocationAnalysis.length.", "")] = round(number, 6)
    return out


def write_final_summary(run_dir: Path, status: dict[str, Any]) -> None:
    rec = production_record(run_dir)
    a_path = analysis_path(run_dir)
    analysis = read_json(a_path, {}) if a_path else {}
    summary = {
        "status": "analysis_completed" if analysis else status.get("status"),
        "generated_at": now(),
        "run_root": str(run_dir),
        "stage": RUN_STAGE,
        "case_id": CASE_ID,
        "target_atoms": 700000,
        "actual_atoms": rec.get("atom_count"),
        "eps_z": 0.001942,
        "production_steps": 80000,
        "dump_every": 10000,
        "restart_every": 10000,
        "thermal_sanity_stop_K": TEMP_LIMIT_K,
        "max_temp_K": status.get("thermal", {}).get("max_temp_K"),
        "smoke_returncode": status.get("smoke_returncode"),
        "production_returncode": status.get("production_returncode"),
        "final_step": rec.get("steps_completed"),
        "steps_target": rec.get("steps_target"),
        "analysis_json": str(a_path) if a_path else None,
        "dxa": {
            "segments": analysis.get("dislocation_segments"),
            "total_length_A": analysis.get("dislocation_length_A"),
            "burgers_lengths_A": positive_burgers_lengths(analysis),
        },
        "cna": {
            "fcc_atoms": analysis.get("fcc_atoms"),
            "hcp_atoms": analysis.get("hcp_atoms"),
            "other_atoms": analysis.get("other_atoms"),
            "fcc_pct": analysis.get("fcc_pct"),
            "hcp_pct": analysis.get("hcp_pct"),
            "other_pct": analysis.get("other_pct"),
        },
        "ptm": analysis.get("ptm") or {},
        "plastic_zone": analysis.get("plastic_zone") or {},
        "disk_free_gib": status.get("disk_free_gib"),
    }
    write_json(run_dir / "stageE_700k_final_summary.json", summary)
    write_json(SYSTEM_ROOT / "state" / "reports" / "physics_md_al_fe" / "stageE_700k_dxa_confirm_final.json", summary)


def monitor_command(run_dir: Path) -> str:
    return f"Get-Content -Raw {run_dir / (STATUS_NAME + '.json')}"


def log_tail_command(run_dir: Path) -> str:
    return (
        f"$root = '{run_dir}'; "
        "Get-ChildItem $root -Recurse -File -Filter \"log*.lammps\" | "
        "Sort-Object LastWriteTime -Descending | "
        "Select-Object -First 1 | "
        "ForEach-Object { Get-Content $_.FullName -Tail 40 }"
    )


def process_monitor_command() -> str:
    return (
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ("
        "$_.CommandLine -like '*E4_700k_dxa_confirm*' -or "
        "$_.CommandLine -like '*stageE_700k_dxa_confirm*' -or "
        "$_.Name -like 'lmp_kokkos_cuda*') } | "
        "Select-Object ProcessId, ParentProcessId, Name, CommandLine | Format-List"
    )


def write_launch_records(
    run_dir: Path,
    status: dict[str, Any],
    preflight_record: dict[str, Any],
    smoke_cmd: list[str | Path],
    production_cmd: list[str | Path],
    worker_cmd: list[str | Path],
    initial_processes: list[dict[str, Any]],
) -> dict[str, Any]:
    smoke = smoke_record(run_dir)
    lammps_pids = [p["pid"] for p in initial_processes if str(p.get("name", "")).lower().startswith("lmp")]
    record = {
        "generated_at": now(),
        "run_root": str(run_dir),
        "stage": RUN_STAGE,
        "case": CASE_ID,
        "target_atoms": 700000,
        "actual_atoms": smoke.get("atom_count"),
        "eps_z": 0.001942,
        "production_steps": 80000,
        "dump_every": 10000,
        "restart_every": 10000,
        "temperature_K": 300,
        "thermal_sanity_stop_K": TEMP_LIMIT_K,
        "smoke_command": command_text(smoke_cmd),
        "production_command": command_text(production_cmd),
        "worker_command": command_text(worker_cmd),
        "smoke_returncode": status.get("smoke_returncode"),
        "worker_pid": status.get("worker_pid"),
        "production_pid": status.get("production_pid"),
        "lammps_pids_initial": lammps_pids,
        "gpu_name": preflight_record.get("gpu", {}).get("name"),
        "gpu_memory_total_mib": preflight_record.get("gpu", {}).get("memory_total_mib"),
        "gpu_memory_used_mib_at_preflight": preflight_record.get("gpu", {}).get("memory_used_mib"),
        "disk_free_gib": preflight_record.get("disk_free_gib"),
        "stdout_stderr_paths": {
            "smoke_stdout": str(run_dir / "stageE_700k_smoke_stdout.txt"),
            "smoke_stderr": str(run_dir / "stageE_700k_smoke_stderr.txt"),
            "worker_stdout": str(run_dir / "stageE_700k_worker_stdout.txt"),
            "worker_stderr": str(run_dir / "stageE_700k_worker_stderr.txt"),
            "production_stdout": str(run_dir / "stageE_700k_production_stdout.txt"),
            "production_stderr": str(run_dir / "stageE_700k_production_stderr.txt"),
        },
        "status_file": str(run_dir / f"{STATUS_NAME}.json"),
        "monitor_command": monitor_command(run_dir),
        "process_monitor_command": process_monitor_command(),
        "log_tail_command": log_tail_command(run_dir),
        "initial_processes": initial_processes,
        "blockers": status.get("blockers") or [],
        "neighbor_workaround": preflight_record.get("neighbor_workaround"),
        "neighbor_workaround_note": preflight_record.get("neighbor_workaround_note"),
    }
    write_json(run_dir / "stageE_700k_launch_record.json", record)
    lines = [
        "# Stage E4 700k DXA confirmation launch record",
        "",
        f"Generated: `{record['generated_at']}`",
        f"Run root: `{run_dir}`",
        f"Stage/case: `{RUN_STAGE}` / `{CASE_ID}`",
        f"Target atoms: `{record['target_atoms']}`",
        f"Actual atoms from smoke: `{record['actual_atoms']}`",
        f"eps_z: `{record['eps_z']}`",
        f"Production steps: `{record['production_steps']}`",
        f"Dump/restart cadence: `{record['dump_every']}` / `{record['restart_every']}`",
        f"Smoke returncode: `{record['smoke_returncode']}`",
        f"Worker PID: `{record['worker_pid']}`",
        f"Production runner PID: `{record['production_pid']}`",
        f"LAMMPS PIDs at initial check: `{record['lammps_pids_initial']}`",
        f"GPU: `{record['gpu_name']}` `{record['gpu_memory_total_mib']} MiB`",
        f"Disk: `{record['disk_free_gib']}`",
        "",
        "## Commands",
        "",
        f"- smoke: `{record['smoke_command']}`",
        f"- production: `{record['production_command']}`",
        f"- monitor: `{record['monitor_command']}`",
        f"- process monitor: `{record['process_monitor_command']}`",
        f"- log tail: `{record['log_tail_command']}`",
        "",
        "## Workaround",
        "",
        f"- `{record['neighbor_workaround']}`",
        f"- {record['neighbor_workaround_note']}",
    ]
    (run_dir / "stageE_700k_launch_record.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    runtime_lines = [
        "# Stage E4 700k initial runtime check",
        "",
        f"Generated: `{record['generated_at']}`",
        f"Status: `{status.get('status')}`",
        f"Worker PID: `{record['worker_pid']}`",
        f"Production runner PID: `{record['production_pid']}`",
        f"LAMMPS PIDs: `{record['lammps_pids_initial']}`",
        f"Thermal: `{status.get('thermal')}`",
        f"Active processes: `{initial_processes}`",
        "",
        "Blockers: " + (", ".join(record["blockers"]) if record["blockers"] else "none"),
    ]
    (run_dir / "stageE_700k_runtime_initial_check.md").write_text(
        "\n".join(runtime_lines) + "\n", encoding="utf-8"
    )
    agent_lines = [
        "# Stage E4 700k DXA confirm launch",
        "",
        f"Updated: `{record['generated_at']}`",
        f"Run root: `{run_dir}`",
        f"Status: `{status.get('status')}`",
        f"Stage/case: `{RUN_STAGE}` / `{CASE_ID}`",
        f"Target: `700000`, actual from smoke: `{record['actual_atoms']}`",
        f"eps_z: `0.001942`",
        f"Steps: `80000`",
        f"Dump/restart cadence: `10000/10000`",
        f"Smoke returncode: `{record['smoke_returncode']}`",
        f"Worker PID: `{record['worker_pid']}`",
        f"Production runner PID: `{record['production_pid']}`",
        f"LAMMPS PIDs at initial check: `{record['lammps_pids_initial']}`",
        f"GPU: `{record['gpu_name']}`",
        f"Disk: `{record['disk_free_gib']}`",
        f"Monitor command: `{record['monitor_command']}`",
        f"Log tail command: `{record['log_tail_command']}`",
        f"Blockers: `{record['blockers']}`",
    ]
    (REPO_ROOT / "agent_report_stageE_700k_dxa_confirm_launch.md").write_text(
        "\n".join(agent_lines) + "\n", encoding="utf-8"
    )
    write_json(
        SYSTEM_ROOT / "state" / "reports" / "physics_md_al_fe" / "stageE_700k_dxa_confirm_launch.json",
        record,
    )
    return record


def launch_worker(run_dir: Path, cfg_path: Path) -> tuple[int, list[str | Path]]:
    cmd: list[str | Path] = [
        sys.executable,
        Path(__file__).resolve(),
        "--worker",
        "--config",
        cfg_path,
        "--run-dir",
        run_dir,
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    with (run_dir / "stageE_700k_worker_stdout.txt").open("w", encoding="utf-8", errors="replace") as out, (
        run_dir / "stageE_700k_worker_stderr.txt"
    ).open("w", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=out, stderr=err, text=True, creationflags=creationflags)
    return int(proc.pid), cmd


def worker(run_dir: Path, cfg_path: Path) -> int:
    cfg = load_yaml(cfg_path)
    status = read_json(run_dir / f"{STATUS_NAME}.json", {})
    production_cmd: list[str | Path] = [
        sys.executable,
        REPO_ROOT / "scripts" / "run_stage_sweep.py",
        "--config",
        cfg_path,
        "--run-dir",
        run_dir,
        "--run-stage",
        RUN_STAGE,
        "--gpu",
    ]
    assert_command_gate(production_cmd, cfg)
    status["status"] = "production_worker_running"
    status["current_phase"] = "production"
    status["production_command"] = command_text(production_cmd)
    status["analysis_status"] = "pending_after_production"
    write_status(run_dir, status)
    rc = run_phase(run_dir, status, "production", production_cmd)
    status = read_json(run_dir / f"{STATUS_NAME}.json", status)
    status["production_returncode"] = rc
    if rc != 0:
        status["status"] = "blocked_production_failed"
        status["current_phase"] = "stopped"
        status.setdefault("blockers", []).append(f"production failed with return code {rc}")
        write_status(run_dir, status)
        return rc
    a_path = analysis_path(run_dir)
    status["analysis_status"] = "completed" if a_path else "missing"
    status["status"] = "analysis_completed" if a_path else "analysis_missing"
    status["current_phase"] = "done"
    if not a_path:
        status.setdefault("blockers", []).append("production completed but analysis.json was not found")
    write_status(run_dir, status)
    write_final_summary(run_dir, status)
    write_status(run_dir, status)
    return 0 if a_path else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(CONFIG))
    parser.add_argument("--run-dir", default=None)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args(argv)

    cfg_path = Path(args.config).resolve()
    if args.worker:
        if not args.run_dir:
            raise SystemExit("--worker needs --run-dir")
        return worker(Path(args.run_dir).resolve(), cfg_path)

    cfg = load_yaml(cfg_path)
    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
    else:
        run_dir = gpu_grid.output_root(cfg) / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("cases", "logs", "structures", "summaries", "tables"):
        (run_dir / sub).mkdir(exist_ok=True)
    effective_config = run_dir / "effective_config.yaml"
    effective_config.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=False), encoding="utf-8")
    (run_dir / "launch_command.txt").write_text(
        command_text([sys.executable, Path(__file__).resolve(), "--config", cfg_path, "--run-dir", run_dir]) + "\n",
        encoding="utf-8",
    )

    preflight_record = preflight(run_dir, cfg)
    write_json(run_dir / "stageE_700k_preflight.json", preflight_record)
    status: dict[str, Any] = {
        "status": "blocked_preflight"
        if preflight_record["blockers"]
        else ("prepared_preflight_only" if args.preflight_only else "preflight_passed"),
        "started_at": now(),
        "run_root": str(run_dir),
        "stage": RUN_STAGE,
        "case_id": CASE_ID,
        "target_atoms": 700000,
        "eps_z": 0.001942,
        "production_steps": 80000,
        "dump_every": 10000,
        "restart_every": 10000,
        "thermal_sanity_stop_K": TEMP_LIMIT_K,
        "preflight": preflight_record,
        "blockers": list(preflight_record["blockers"]),
        "smoke_returncode": None,
        "production_returncode": None,
        "analysis_status": "not_started",
    }
    write_status(run_dir, status)
    if preflight_record["blockers"] or args.preflight_only:
        print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "blockers": status["blockers"]}, ensure_ascii=False, indent=2))
        return 1 if preflight_record["blockers"] else 0

    smoke_cmd: list[str | Path] = [
        sys.executable,
        REPO_ROOT / "scripts" / "run_stage_sweep.py",
        "--config",
        effective_config,
        "--run-dir",
        run_dir,
        "--run-stage",
        RUN_STAGE,
        "--gpu",
        "--smoke-only",
    ]
    production_cmd: list[str | Path] = [
        sys.executable,
        REPO_ROOT / "scripts" / "run_stage_sweep.py",
        "--config",
        effective_config,
        "--run-dir",
        run_dir,
        "--run-stage",
        RUN_STAGE,
        "--gpu",
    ]
    status["smoke_command_gate"] = assert_command_gate(smoke_cmd, cfg)
    status["production_command_gate"] = assert_command_gate(production_cmd, cfg)
    status["smoke_command"] = command_text(smoke_cmd)
    status["production_command"] = command_text(production_cmd)
    write_status(run_dir, status)

    smoke_rc = run_phase(run_dir, status, "smoke", smoke_cmd)
    status["smoke_returncode"] = smoke_rc
    if smoke_rc != 0:
        status["status"] = "blocked_smoke_failed"
        status["current_phase"] = "stopped"
        status.setdefault("blockers", []).append(f"smoke failed with return code {smoke_rc}; production not launched")
        write_status(run_dir, status)
        write_launch_records(run_dir, status, preflight_record, smoke_cmd, production_cmd, [], active_stage_processes(ignore_pids={os.getpid()}))
        print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "blockers": status["blockers"]}, ensure_ascii=False, indent=2))
        return smoke_rc

    live = active_stage_processes(ignore_pids={os.getpid()})
    if live:
        status["status"] = "blocked_live_process_after_smoke"
        status["current_phase"] = "stopped"
        status.setdefault("blockers", []).append("live Stage E/LAMMPS/run_stage_sweep process found after smoke")
        status["post_smoke_live_processes"] = live
        write_status(run_dir, status)
        write_launch_records(run_dir, status, preflight_record, smoke_cmd, production_cmd, [], live)
        print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "blockers": status["blockers"]}, ensure_ascii=False, indent=2))
        return 2

    c_free = disk_free_gib("C:\\")
    if c_free < DISK_MIN_GIB:
        status["status"] = "blocked_disk_after_smoke"
        status["current_phase"] = "stopped"
        status.setdefault("blockers", []).append(f"C: free disk below {DISK_MIN_GIB:.0f} GiB after smoke: {c_free:.3f} GiB")
        write_status(run_dir, status)
        write_launch_records(run_dir, status, preflight_record, smoke_cmd, production_cmd, [], active_stage_processes(ignore_pids={os.getpid()}))
        print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "blockers": status["blockers"]}, ensure_ascii=False, indent=2))
        return 3

    worker_pid, worker_cmd = launch_worker(run_dir, effective_config)
    status["worker_pid"] = worker_pid
    status["worker_command"] = command_text(worker_cmd)
    status["status"] = "production_launched"
    status["current_phase"] = "production"
    status["production_launched_at"] = now()
    write_status(run_dir, status)
    time.sleep(60)
    status = read_json(run_dir / f"{STATUS_NAME}.json", status)
    status["status"] = status.get("status") or "production_launched"
    initial_processes = active_stage_processes(ignore_pids={os.getpid()})
    status["initial_runtime_processes"] = initial_processes
    write_status(run_dir, status)
    record = write_launch_records(run_dir, status, preflight_record, smoke_cmd, production_cmd, worker_cmd, initial_processes)
    print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "launch_record": record}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
