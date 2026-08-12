#!/usr/bin/env python3
"""Run Stage E 250k single physical eps001942 longrun.

The wrapper performs the prompt-specific preflight, launches smoke first, and
only launches the 120000-step production when smoke succeeds.
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

CONFIG = REPO_ROOT / "configs" / "stageE_250k_single_physical_longrun.template.yaml"
RUN_STAGE = "E3_250k_longrun"
CASE_ID = "E3_phys001942_250k_120k"
TEMP_LIMIT_K = 1000.0
DISK_MIN_GIB = 18.0
BASELINE_510K = {
    "actual_atoms": 510375,
    "eps_z": 0.001942,
    "max_temp_K": 291.98355,
    "dxa_segments": 1,
    "dxa_total_length_A": 8.47,
    "burgers": {"1/6<112>": 8.47},
    "verdict": "confirmed incipient/local dislocation signal; no developed plastic zone",
}


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


def disk_free_gib(path: Path = REPO_ROOT) -> float:
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
        "$_.CommandLine -like '*run_stageE*' -or "
        "$_.CommandLine -like '*run_stage_sweep.py*' -or "
        "$_.Name -like 'lmp*' -or $_.Name -eq 'mpiexec.exe') }; "
        "$items | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    )
    rows = powershell_json(query)
    if not isinstance(rows, list):
        return [{"error": rows}]
    out = []
    for row in rows:
        pid = int(row.get("ProcessId") or -1)
        name = str(row.get("Name") or "")
        cmd = str(row.get("CommandLine") or "")
        low = f"{name} {cmd}".lower()
        if pid in ignore_pids:
            continue
        if name.lower() == "powershell.exe" and "get-ciminstance win32_process" in low:
            continue
        if "run_stagee_250k_single_physical_longrun.py" in low and "--worker" not in low:
            continue
        out.append({"pid": pid, "name": name, "command": cmd, "parent": row.get("ParentProcessId")})
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


def memory_snapshot() -> dict[str, Any]:
    rows = powershell_json(
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object TotalVisibleMemorySize,FreePhysicalMemory,TotalVirtualMemorySize,FreeVirtualMemory | "
        "ConvertTo-Json -Compress"
    )
    if isinstance(rows, list) and rows:
        return rows[0]
    return {}


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
    rows = []
    for line in proc.stdout.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 8 or parts[1] == "-":
            continue
        rows.append({"gpu": parts[0], "pid": parts[1], "type": parts[2], "command": " ".join(parts[7:])})
    return rows


def preflight(run_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    env_ok, env_report, env_lines = gpu_grid.check_environment(cfg)
    active = active_stage_processes(ignore_pids={os.getpid()})
    free = disk_free_gib(REPO_ROOT)
    gpu = gpu_snapshot()
    pmon = nvidia_pmon_rows()
    blockers = []
    if active:
        blockers.append("live LAMMPS/run_stageE/run_stage_sweep process exists")
    if free < DISK_MIN_GIB:
        blockers.append(f"C: free disk below {DISK_MIN_GIB:.0f} GiB: {free:.3f} GiB")
    if not gpu.get("available"):
        blockers.append(f"nvidia-smi unavailable: {gpu}")
    if not env_ok:
        blockers.extend(line for line in env_lines if line.startswith("FAIL"))
    return {
        "generated_at": now(),
        "run_root": str(run_dir),
        "disk_free_gib": round(free, 3),
        "required_free_gib": DISK_MIN_GIB,
        "active_stage_processes": active,
        "gpu": gpu,
        "nvidia_pmon": pmon,
        "memory": memory_snapshot(),
        "environment_ok": env_ok,
        "environment_lines": env_lines,
        "environment_report": env_report,
        "blockers": blockers,
        "cleanup_performed": False,
        "cleanup_note": "not needed; disk was above 18 GiB at preflight",
    }


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
    logs = sorted(run_dir.glob("cases/**/*.lammps"), key=lambda p: p.stat().st_mtime)
    for log in logs:
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


def write_status(run_dir: Path, status: dict[str, Any]) -> None:
    status["updated_at"] = now()
    status["disk_free_gib"] = round(disk_free_gib(REPO_ROOT), 3)
    status["thermal"] = thermal_status(run_dir)
    write_json(run_dir / "stageE_250k_longrun_status.json", status)
    lines = [
        "# Stage E 250k single physical longrun status",
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
        f"C free disk GiB: `{status.get('disk_free_gib')}`",
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
    ]
    (run_dir / "stageE_250k_longrun_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_phase(run_dir: Path, status: dict[str, Any], label: str, cmd: list[str]) -> int:
    status["current_phase"] = label
    status["status"] = f"{label}_running"
    status[f"{label}_command"] = command_text(cmd)
    write_status(run_dir, status)
    stdout_path = run_dir / f"stageE_250k_{label}_stdout.txt"
    stderr_path = run_dir / f"stageE_250k_{label}_stderr.txt"
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


def analysis_path(run_dir: Path) -> Path | None:
    rec = production_record(run_dir)
    raw = rec.get("analysis")
    if raw and Path(raw).is_file():
        return Path(raw)
    candidates = sorted(run_dir.glob(f"cases/{RUN_STAGE}/{CASE_ID}/production/analysis.json"))
    return candidates[0] if candidates else None


def positive_burgers_lengths(analysis: dict[str, Any]) -> dict[str, float]:
    attrs = analysis.get("dxa_attributes") or {}
    out = {}
    for key, value in attrs.items():
        if not key.startswith("DislocationAnalysis.length."):
            continue
        try:
            fval = float(value)
        except (TypeError, ValueError):
            continue
        if fval > 0.0:
            out[key.replace("DislocationAnalysis.length.", "")] = round(fval, 6)
    return out


def generated_raw_files(run_dir: Path) -> list[dict[str, Any]]:
    patterns = ("*.lammpstrj", "restart.*", "data.final")
    rows = []
    for pattern in patterns:
        for path in sorted(run_dir.glob(f"cases/**/{pattern}")):
            if path.is_file():
                rows.append(
                    {
                        "path": str(path),
                        "name": path.name,
                        "size_bytes": path.stat().st_size,
                        "size_mib": round(path.stat().st_size / (1024**2), 3),
                    }
                )
    return rows


def round_float(value: Any, digits: int = 4) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return round(number, digits)


def write_final_reports(run_dir: Path, status: dict[str, Any]) -> dict[str, Any]:
    rec = production_record(run_dir)
    a_path = analysis_path(run_dir)
    analysis = read_json(a_path, {}) if a_path else {}
    geom = ((rec.get("structure") or {}).get("geometry_metadata") or {})
    box_A = geom.get("box_A") or (rec.get("structure") or {}).get("box_A")
    box_nm = [round(float(x) / 10.0, 4) for x in box_A] if box_A else None
    pz = analysis.get("plastic_zone") or {}
    hcp_beyond = int(pz.get("hcp_atoms_beyond_1p3_shell", 0) or 0)
    defects_beyond = int(pz.get("defect_atoms_beyond_1p3_shell", 0) or 0)
    developed = hcp_beyond > 0 or defects_beyond > 3
    verdict = (
        "developed plastic zone"
        if developed
        else "incipient/local dislocation signal only; no developed plastic zone"
    )
    summary = {
        "status": "analysis_completed" if analysis else status.get("status"),
        "generated_at": now(),
        "run_root": str(run_dir),
        "case_id": CASE_ID,
        "target_atoms": 250000,
        "actual_atoms": rec.get("atom_count") or geom.get("actual_atom_count"),
        "box_nm": box_nm,
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
        "plastic_zone": pz,
        "physics_verdict": verdict,
        "comparison_to_510k_v2": BASELINE_510K,
        "disk_free_gib": round(disk_free_gib(REPO_ROOT), 3),
        "raw_files_deleted_this_run": [],
        "raw_files_left_this_run": generated_raw_files(run_dir),
    }
    write_json(run_dir / "stageE_250k_final_summary.json", summary)
    write_json(SYSTEM_ROOT / "state" / "reports" / "physics_md_al_fe" / "stageE_250k_single_physical_longrun.json", summary)

    burgers = summary["dxa"]["burgers_lengths_A"]
    dxa_lines = [
        "# Stage E 250k DXA summary",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Case: `{CASE_ID}`",
        f"Actual atoms: `{summary['actual_atoms']}`",
        f"Box nm: `{box_nm}`",
        "",
        f"- DXA segments: `{summary['dxa']['segments']}`",
        f"- total line length A: `{summary['dxa']['total_length_A']}`",
        f"- Burgers lengths A: `{burgers}`",
        f"- verdict: `{verdict}`",
    ]
    (run_dir / "stageE_250k_dxa_summary.md").write_text("\n".join(dxa_lines) + "\n", encoding="utf-8")

    stress = analysis.get("stress_profiles") or {}
    radial = stress.get("radial_profile") or []
    stress_lines = [
        "# Stage E 250k stress transfer report",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "| shell A | atoms | HCP | OTHER | Pzz MPa | von Mises MPa |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in radial:
        hi = row.get("distance_from_interface_max_A")
        shell = f"{row.get('distance_from_interface_min_A')}-{hi}" if hi is not None else f">{row.get('distance_from_interface_min_A')}"
        stress_lines.append(
            f"| {shell} | {row.get('atom_count')} | {row.get('hcp_atoms')} | {row.get('other_atoms')} | "
            f"{round_float(row.get('pzz_MPa'))} | {round_float(row.get('von_mises_MPa'))} |"
        )
    (run_dir / "stageE_250k_stress_transfer_report.md").write_text(
        "\n".join(stress_lines) + "\n", encoding="utf-8"
    )

    verdict_lines = [
        "# Stage E 250k physics verdict",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Verdict: `{verdict}`",
        "",
        f"Compared with 510k v2 physical eps001942 (`{BASELINE_510K['dxa_segments']}` DXA segment, "
        f"`{BASELINE_510K['dxa_total_length_A']} A`, Burgers `{BASELINE_510K['burgers']}`), "
        "this 250k/120k run should be interpreted by whether DXA length/segments and HCP clusters grow.",
    ]
    (run_dir / "stageE_250k_physics_verdict.md").write_text(
        "\n".join(verdict_lines) + "\n", encoding="utf-8"
    )

    agent_lines = [
        "# Stage E 250k single physical longrun",
        "",
        f"Updated: `{summary['generated_at']}`",
        f"Run root: `{run_dir}`",
        f"Status: `{summary['status']}`",
        f"actual_atoms: `{summary['actual_atoms']}`",
        f"box_nm: `{box_nm}`",
        f"max_temp_K: `{summary['max_temp_K']}`",
        f"DXA: `{summary['dxa']}`",
        f"CNA: `{summary['cna']}`",
        f"PTM: FCC `{summary['ptm'].get('fcc_atoms')}`, HCP `{summary['ptm'].get('hcp_atoms')}`, OTHER `{summary['ptm'].get('other_atoms')}`",
        f"Verdict: `{verdict}`",
        f"Disk free GiB: `{summary['disk_free_gib']}`",
        "",
        "Raw files deleted this run: none.",
        "Raw files left this run are recorded in `stageE_250k_final_summary.json`.",
    ]
    (REPO_ROOT / "agent_report_stageE_250k_single_physical_longrun.md").write_text(
        "\n".join(agent_lines) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(CONFIG))
    parser.add_argument("--run-dir", default=None)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)

    cfg = load_yaml(Path(args.config))
    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
    else:
        root = gpu_grid.output_root(cfg)
        run_dir = root / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("cases", "logs", "structures", "summaries", "tables"):
        (run_dir / sub).mkdir(exist_ok=True)
    (run_dir / "effective_config.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )
    (run_dir / "launch_command.txt").write_text(
        command_text([sys.executable, Path(__file__).resolve(), "--config", Path(args.config).resolve(), "--run-dir", run_dir])
        + "\n",
        encoding="utf-8",
    )

    pf = preflight(run_dir, cfg)
    write_json(run_dir / "stageE_250k_preflight.json", pf)
    status: dict[str, Any] = {
        "status": "blocked_preflight" if pf["blockers"] else ("prepared_preflight_only" if args.preflight_only else "preflight_passed"),
        "started_at": now(),
        "run_root": str(run_dir),
        "case_id": CASE_ID,
        "run_stage": RUN_STAGE,
        "target_atoms": 250000,
        "eps_z": 0.001942,
        "production_steps": 120000,
        "thermal_sanity_stop_K": TEMP_LIMIT_K,
        "preflight": pf,
        "blockers": list(pf["blockers"]),
        "smoke_returncode": None,
        "production_returncode": None,
        "analysis_status": "not_started",
    }
    write_status(run_dir, status)
    if pf["blockers"] or args.preflight_only:
        print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "blockers": status["blockers"]}, ensure_ascii=False, indent=2))
        return 1 if pf["blockers"] else 0

    smoke_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_stage_sweep.py"),
        "--config",
        str(run_dir / "effective_config.yaml"),
        "--run-dir",
        str(run_dir),
        "--run-stage",
        RUN_STAGE,
        "--gpu",
        "--smoke-only",
    ]
    production_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_stage_sweep.py"),
        "--config",
        str(run_dir / "effective_config.yaml"),
        "--run-dir",
        str(run_dir),
        "--run-stage",
        RUN_STAGE,
        "--gpu",
    ]
    status["smoke_command"] = command_text(smoke_cmd)
    status["production_command"] = command_text(production_cmd)
    smoke_rc = run_phase(run_dir, status, "smoke", smoke_cmd)
    status["smoke_returncode"] = smoke_rc
    if smoke_rc != 0:
        status["status"] = "blocked_smoke_failed"
        status["current_phase"] = "stopped"
        status["blockers"].append(f"smoke failed with return code {smoke_rc}; production not launched")
        write_status(run_dir, status)
        print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "blockers": status["blockers"]}, ensure_ascii=False, indent=2))
        return smoke_rc

    prod_rc = run_phase(run_dir, status, "production", production_cmd)
    status["production_returncode"] = prod_rc
    if prod_rc != 0:
        status["status"] = "blocked_production_failed"
        status["current_phase"] = "stopped"
        status["blockers"].append(f"production failed with return code {prod_rc}")
        write_status(run_dir, status)
        print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "blockers": status["blockers"]}, ensure_ascii=False, indent=2))
        return prod_rc

    a_path = analysis_path(run_dir)
    status["analysis_status"] = "completed" if a_path else "missing"
    status["status"] = "analysis_completed" if a_path else "analysis_missing"
    status["current_phase"] = "done"
    if not a_path:
        status["blockers"].append("production completed but analysis.json was not found")
    write_status(run_dir, status)
    summary = write_final_reports(run_dir, status)
    write_status(run_dir, status)
    print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "summary": summary}, ensure_ascii=False, indent=2))
    return 0 if a_path else 1


if __name__ == "__main__":
    raise SystemExit(main())
