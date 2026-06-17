#!/usr/bin/env python3
"""Prepare and launch the Stage C 1M safe-prep retry only.

This launcher never resumes the failed run root and never starts production. It
creates a fresh run root, records pagefile/resource preflight, validates the
geometry, then starts a background worker that runs only the prep baseline.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner.gpu_grid import (  # noqa: E402
    GridStop,
    GpuGridRunner,
    free_disk_gb,
    load_grid_config,
    nvidia_smi_snapshot,
    read_json,
    write_json,
)


TARGET_STAGE = "C1_1M_scaleup_100k"
TARGET_CASE = "C1_1M_nearGB_vacancies_medium_eps0100"
SAFE_OUTPUT_ROOT = REPO_ROOT / "runs" / "stageC_1M_nearGB_vacancies_eps0100_safe_prep"
OLD_FAILED_ROOT = REPO_ROOT / "runs" / "stageC_1M_nearGB_vacancies_eps0100_100k" / "20260616-173123"
DEFAULT_CONFIG_TEMPLATE = REPO_ROOT / "configs" / "stageC_1M_nearGB_vacancies_eps0100_100k.template.yaml"
PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"


SAFE_PREP_SEGMENTS = [
    {
        "label": "ramp_50_to_150K",
        "timestep": 0.0001,
        "temp_start_K": 50.0,
        "temp_end_K": 150.0,
        "steps": 10000,
        "tdamp": 0.1,
    },
    {
        "label": "ramp_150_to_300K",
        "timestep": 0.0001,
        "temp_start_K": 150.0,
        "temp_end_K": 300.0,
        "steps": 20000,
        "tdamp": 0.1,
    },
    {
        "label": "hold_300K",
        "timestep": 0.0001,
        "temp_start_K": 300.0,
        "temp_end_K": 300.0,
        "steps": 20000,
        "tdamp": 0.1,
    },
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="launch_stageC_1M_safe_prep_retry.py", description=__doc__)
    parser.add_argument("--config-template", default=str(DEFAULT_CONFIG_TEMPLATE))
    parser.add_argument("--run-root", default=None)
    parser.add_argument("--old-failed-root", default=str(OLD_FAILED_ROOT))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--launch-background", action="store_true")
    parser.add_argument("--config", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--worker-run-prep", action="store_true", help=argparse.SUPPRESS)
    return parser


def command_text(cmd: list[str | Path]) -> str:
    return " ".join(str(x) for x in cmd)


def ps_json(script: str) -> Any:
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; " + script,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if proc.returncode != 0:
        return {"error": proc.stderr.strip(), "returncode": proc.returncode}
    text = proc.stdout.strip()
    if not text:
        return None
    return json.loads(text)


def admin_status() -> bool:
    result = ps_json(
        "$p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent()); "
        "$p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) | ConvertTo-Json"
    )
    return bool(result)


def pagefile_snapshot() -> dict[str, Any]:
    return ps_json(
        "$settings = @(Get-CimInstance Win32_PageFileSetting | "
        "Select-Object Name, InitialSize, MaximumSize); "
        "$usage = @(Get-CimInstance Win32_PageFileUsage | "
        "Select-Object Name, AllocatedBaseSize, CurrentUsage, PeakUsage); "
        "$computer = Get-CimInstance Win32_ComputerSystem | "
        "Select-Object AutomaticManagedPagefile, TotalPhysicalMemory; "
        "$os = Get-CimInstance Win32_OperatingSystem | "
        "Select-Object TotalVirtualMemorySize, FreeVirtualMemory, TotalVisibleMemorySize, FreePhysicalMemory; "
        "$drives = @(Get-PSDrive -PSProvider FileSystem | Select-Object Name, Used, Free); "
        "[pscustomobject]@{settings=$settings; usage=$usage; computer=$computer; os=$os; drives=$drives} | "
        "ConvertTo-Json -Depth 5"
    )


def active_md_processes() -> list[dict[str, Any]]:
    result = ps_json(
        "$rows = @(Get-CimInstance Win32_Process | Where-Object { "
        "$_.CommandLine -and "
        "$_.Name -notin @('powershell.exe','pwsh.exe') -and "
        "$_.CommandLine -notlike '*launch_stageC_1M_safe_prep_retry.py*' -and ("
        "$_.Name -like 'lmp_kokkos_cuda*' -or "
        "($_.Name -match 'python' -and $_.CommandLine -like '*run_stage_sweep.py*') -or "
        "($_.CommandLine -like '*stageC_1M*')"
        ") } | Select-Object ProcessId, ParentProcessId, Name, CommandLine); "
        "$rows | ConvertTo-Json -Depth 5"
    )
    if result is None:
        return []
    if isinstance(result, dict) and "ProcessId" in result:
        return [result]
    if isinstance(result, list):
        return result
    return [{"error": result}]


def c_drive_free_gb(snapshot: dict[str, Any]) -> float:
    drives = snapshot.get("drives") or []
    if isinstance(drives, dict):
        drives = [drives]
    for drive in drives:
        if str(drive.get("Name", "")).upper() == "C":
            return float(drive.get("Free", 0)) / (1024**3)
    return 0.0


def pagefile_ok(snapshot: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    settings = snapshot.get("settings") or []
    usage = snapshot.get("usage") or []
    if isinstance(settings, dict):
        settings = [settings]
    if isinstance(usage, dict):
        usage = [usage]
    c_settings = [s for s in settings if str(s.get("Name", "")).lower() == "c:\\pagefile.sys"]
    other_settings = [s for s in settings if str(s.get("Name", "")).lower() != "c:\\pagefile.sys"]
    if len(c_settings) != 1:
        reasons.append("expected exactly one C:\\pagefile.sys setting")
    else:
        setting = c_settings[0]
        if int(setting.get("InitialSize", 0)) != 24576 or int(setting.get("MaximumSize", 0)) != 32768:
            reasons.append("C:\\pagefile.sys setting is not 24576/32768 MB")
    if other_settings:
        reasons.append("non-C pagefile settings still exist")
    c_usage = [u for u in usage if str(u.get("Name", "")).lower() == "c:\\pagefile.sys"]
    if not c_usage or int(c_usage[0].get("AllocatedBaseSize", 0)) < 24576:
        reasons.append("active C:\\pagefile.sys allocation is below 24576 MB")
    free_gb = c_drive_free_gb(snapshot)
    if free_gb < 8.0:
        reasons.append(f"C: free disk below 8 GB after pagefile: {free_gb:.2f} GB")
    return not reasons, reasons


def safe_run_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit)
        if not root.is_absolute():
            root = REPO_ROOT / root
        return root.resolve()
    return (SAFE_OUTPUT_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")).resolve()


def safe_config(config_template: str | Path) -> dict[str, Any]:
    cfg = copy.deepcopy(load_grid_config(config_template))
    cfg["experiment"]["output_root"] = "runs/stageC_1M_nearGB_vacancies_eps0100_safe_prep"
    cfg["experiment"]["mode"] = "safe_prep_retry_only"
    cfg["experiment"]["depends_on"] = ["pagefile_preflight_passed", "no_active_md_processes"]
    cfg["experiment"]["description"] = "Stage C 1M safe-prep retry only; production disabled"

    stage = cfg["stages"][TARGET_STAGE]
    stage["prep_segments"] = copy.deepcopy(SAFE_PREP_SEGMENTS)
    stage["prep_ramp_steps"] = 30000
    stage["prep_steps"] = 20000
    stage["prep_restart_every"] = 2000
    stage["prep_dump_every"] = 2000
    stage["prep_dump_fields"] = ["id", "type", "x", "y", "z"]
    stage["safe_prep_only"] = True
    stage["run_short_after_smoke_pass"] = False
    stage["run_production_after_smoke_pass"] = False
    stage["run_production_after_gate_pass"] = False
    stage["gate_required_before_each_production"] = True
    stage["analyze_after_production"] = False

    cfg["io_policy"]["restart_every"] = 2000
    cfg["resources"]["min_free_disk_gb_before_stage"] = 8
    cfg["resources"]["min_free_disk_gb_before_large_stage"] = 8
    cfg["resources"].setdefault("max_run_hours", {})["smoke"] = 96
    cfg["production_reliability"]["max_no_progress_minutes"] = 60
    cfg["production_reliability"]["watchdog_poll_seconds"] = 60
    return cfg


def prep_case_id() -> str:
    return f"{TARGET_CASE}_prep"


def write_safe_plan(root: Path, cfg: dict[str, Any], old_failed_root: Path) -> None:
    total_steps = sum(int(seg["steps"]) for seg in SAFE_PREP_SEGMENTS)
    lines = [
        "# Stage C 1M Safe-Prep Retry Plan",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Old failed root: `{old_failed_root}`",
        f"New root: `{root}`",
        "",
        "## Scope",
        "",
        "- Run only the prep baseline.",
        "- Do not resume or overwrite the old failed root.",
        "- Do not start smoke or production from this launcher.",
        "- Use the existing `.venv` Python for the worker process.",
        "",
        "## CUDA Prep Constraint",
        "",
        "- Direct LAMMPS relaxation is not used in this KOKKOS CUDA path.",
        "- The local runner forbids it because LAMMPS overrides the validated neighbor policy during that command.",
        "- The retry instead uses smaller timestep NVT segments and keeps `neigh_modify delay 0 every 10 check no`.",
        "",
        "## Timestep Plan",
        "",
    ]
    for seg in SAFE_PREP_SEGMENTS:
        lines.append(
            f"- {seg['label']}: timestep {seg['timestep']}, "
            f"{seg['temp_start_K']} -> {seg['temp_end_K']} K, {seg['steps']} steps"
        )
    lines += [
        f"- total prep steps: {total_steps}",
        "- restart/dump cadence: 2000 steps",
        "- production: disabled",
        "",
        "## Config",
        "",
        f"- effective config: `{root / 'effective_config.yaml'}`",
        f"- lammps executable: `{cfg['gpu_profile']['lammps_executable']}`",
    ]
    (root / "safe_prep_plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def geometry_summary(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "actual_atom_count": meta.get("actual_atom_count") or meta.get("total_atoms"),
        "matrix_atoms": meta.get("matrix_atoms"),
        "inclusion_atoms": meta.get("inclusion_atoms"),
        "min_pair_distance_A": meta.get("min_pair_distance_A"),
        "pairs_below_1p8_A": meta.get("pairs_below_1p8_A"),
        "cross_source_pairs_below_2p1_A": meta.get("cross_source_pairs_below_2p1_A"),
        "vacancy_count": (meta.get("vacancy") or {}).get("vacancy_count_actual"),
        "safe_basic": meta.get("safe_basic"),
    }


def geometry_ok(meta: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    min_pair = meta.get("min_pair_distance_A")
    if min_pair is not None and float(min_pair) < 1.8:
        reasons.append(f"min_pair_distance_A < 1.8: {min_pair}")
    if int(meta.get("pairs_below_1p8_A", 0) or 0) > 0:
        reasons.append("pairs_below_1p8_A > 0")
    if int(meta.get("cross_source_pairs_below_2p1_A", 0) or 0) > 0:
        reasons.append("cross_source_pairs_below_2p1_A > 0")
    if not bool(meta.get("safe_basic", False)):
        reasons.append("geometry safe_basic is false")
    return not reasons, reasons


def write_preflight(
    root: Path,
    *,
    pagefile: dict[str, Any],
    pagefile_reasons: list[str],
    processes: list[dict[str, Any]],
    geometry: dict[str, Any] | None,
    geometry_reasons: list[str],
) -> dict[str, Any]:
    preflight = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_root": str(root),
        "old_failed_root": str(OLD_FAILED_ROOT),
        "pagefile": pagefile,
        "pagefile_ok": not pagefile_reasons,
        "pagefile_reasons": pagefile_reasons,
        "c_free_gb_after_pagefile": round(c_drive_free_gb(pagefile), 3),
        "ram_total_bytes": (pagefile.get("computer") or {}).get("TotalPhysicalMemory"),
        "nvidia_smi": nvidia_smi_snapshot(),
        "active_md_processes": processes,
        "no_active_md_processes": not processes,
        "geometry": geometry,
        "geometry_ok": geometry is not None and not geometry_reasons,
        "geometry_reasons": geometry_reasons,
        "timestep_plan": SAFE_PREP_SEGMENTS,
        "allowed_to_launch_safe_prep": (not pagefile_reasons) and (not processes) and geometry is not None and not geometry_reasons,
    }
    write_json(root / "pagefile_preflight.json", preflight)
    return preflight


def last_thermo_lines(root: Path, limit: int = 8) -> list[str]:
    case_dir = root / "cases" / TARGET_STAGE / TARGET_CASE / "prep"
    log_path = case_dir / f"log.{prep_case_id()}.lammps"
    if not log_path.is_file():
        return []
    lines = [
        line.rstrip()
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    return lines[-limit:]


def prep_temperature_blockers(record: dict[str, Any]) -> list[str]:
    log_path = Path(str(record.get("log") or ""))
    if not log_path.is_file():
        return []
    rows: list[dict[str, float]] = []
    columns: list[str] | None = None
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "Step" and "Temp" in parts:
            columns = parts
            continue
        if columns is None:
            continue
        if parts[0] == "Loop":
            columns = None
            continue
        if len(parts) != len(columns):
            continue
        try:
            parsed = {name: float(value) for name, value in zip(columns, parts)}
        except ValueError:
            continue
        temp = parsed.get("Temp")
        if temp is None or math.isnan(temp):
            rows.append(parsed)
            continue
        rows.append(parsed)

    blockers: list[str] = []
    temps = [
        (row.get("Step"), row.get("Temp"))
        for row in rows
        if row.get("Temp") is not None and not math.isnan(float(row["Temp"]))
    ]
    if not temps:
        return blockers
    max_step, max_temp = max(temps, key=lambda item: float(item[1]))
    if float(max_temp) > 1000.0:
        blockers.append(f"temperature runaway: max Temp {max_temp:g} K at step {int(max_step or 0)}")
    for (prev_step, prev_temp), (step, temp) in zip(temps, temps[1:]):
        if prev_temp is None or temp is None or float(prev_temp) <= 0.0:
            continue
        if float(temp) >= 10.0 * float(prev_temp):
            blockers.append(
                "temperature runaway: Temp jumped "
                f"{float(prev_temp):g} -> {float(temp):g} K "
                f"between steps {int(prev_step or 0)} and {int(step or 0)}"
            )
            break
    return blockers


def write_safe_final_report(root: Path, status: str, launch: dict[str, Any] | None = None) -> None:
    preflight = read_json(root / "pagefile_preflight.json", {})
    state = read_json(root / "state.json", {})
    rec = (state.get("cases") or {}).get(prep_case_id(), {})
    pagefile = preflight.get("pagefile") or {}
    usage = pagefile.get("usage") or []
    if isinstance(usage, dict):
        usage = [usage]
    setting = pagefile.get("settings") or []
    if isinstance(setting, dict):
        setting = [setting]
    outputs = [o.get("name") for o in rec.get("outputs", [])]
    lines = [
        "Safe Stage C prep retry:",
        f"- old failed root: {OLD_FAILED_ROOT}",
        f"- new root: {root}",
        f"- pagefile setting: {setting}",
        f"- pagefile usage: {usage}",
        f"- C: free before/after: before saved in diagnostics; after {preflight.get('c_free_gb_after_pagefile')} GB",
        f"- RAM: {preflight.get('ram_total_bytes')} bytes",
        f"- GPU: {preflight.get('nvidia_smi')}",
        f"- atoms: {(preflight.get('geometry') or {}).get('actual_atom_count')}",
        f"- timestep plan: {SAFE_PREP_SEGMENTS}",
        f"- launched: {bool((launch or {}).get('launched'))}",
        f"- pid: {(launch or {}).get('pid')}",
        f"- current status: {status}",
        f"- last thermo lines: {last_thermo_lines(root)}",
        f"- outputs created: {outputs}",
        "- next action: monitor prep; do not start production until a successful gate is reported",
        f"- blockers: {preflight.get('pagefile_reasons', []) + preflight.get('geometry_reasons', [])}",
        "",
        "Monitoring command:",
        (
            "Get-Content -Wait "
            f"'{root / 'cases' / TARGET_STAGE / TARGET_CASE / 'prep' / ('log.' + prep_case_id() + '.lammps')}'"
        ),
    ]
    (root / "final_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_root(config_template: str | Path, run_root: Path, old_failed_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = safe_config(config_template)
    if not run_root.is_relative_to(SAFE_OUTPUT_ROOT.resolve()):
        raise GridStop(f"run root must be under {SAFE_OUTPUT_ROOT}")
    if old_failed_root.resolve() == run_root.resolve():
        raise GridStop("new run root must not match old failed root")

    pagefile = pagefile_snapshot()
    ok_pagefile, pagefile_reasons = pagefile_ok(pagefile)
    processes = active_md_processes()
    if not admin_status():
        pagefile_reasons.append("process is not running as administrator")
    if not PYTHON_EXE.is_file():
        pagefile_reasons.append(f"missing venv python: {PYTHON_EXE}")

    runner = GpuGridRunner(cfg, run_dir=run_root)
    write_safe_plan(run_root, cfg, old_failed_root)
    geometry = None
    geometry_reasons: list[str] = []
    if ok_pagefile and not processes and PYTHON_EXE.is_file():
        case = cfg["stages"][TARGET_STAGE]["cases"][0]
        meta = runner.ensure_stageb_geometry(TARGET_STAGE, case)
        runner.write_stageb_geometry_summary(TARGET_STAGE)
        geometry = geometry_summary(meta)
        _, geometry_reasons = geometry_ok(meta)
    preflight = write_preflight(
        run_root,
        pagefile=pagefile,
        pagefile_reasons=pagefile_reasons,
        processes=processes,
        geometry=geometry,
        geometry_reasons=geometry_reasons,
    )
    write_safe_final_report(run_root, "prepared_not_launched")
    return cfg, preflight


def launch_background(root: Path) -> dict[str, Any]:
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    cmd: list[str | Path] = [
        PYTHON_EXE,
        REPO_ROOT / "scripts" / "launch_stageC_1M_safe_prep_retry.py",
        "--worker-run-prep",
        "--run-root",
        root,
        "--config",
        root / "effective_config.yaml",
    ]
    (root / "launch_command.txt").write_text(command_text(cmd) + "\n", encoding="utf-8")
    stdout_path = logs / "safe_prep_worker_stdout.txt"
    stderr_path = logs / "safe_prep_worker_stderr.txt"
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(
            [str(x) for x in cmd],
            cwd=REPO_ROOT,
            stdout=out,
            stderr=err,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    record = {
        "launched": True,
        "pid": proc.pid,
        "command": [str(x) for x in cmd],
        "new_run_root": str(root),
        "start_time": datetime.now().isoformat(timespec="seconds"),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "state": str(root / "state.json"),
        "log": str(root / "cases" / TARGET_STAGE / TARGET_CASE / "prep" / f"log.{prep_case_id()}.lammps"),
    }
    write_json(root / "launch_record.json", record)
    write_safe_final_report(root, "launched_background", record)
    return record


def worker_run_prep(config: str | Path, root: Path) -> int:
    cfg = load_grid_config(config)
    processes = active_md_processes()
    if processes:
        write_json(root / "safe_prep_result.json", {"status": "blocked", "active_md_processes": processes})
        write_safe_final_report(root, "blocked_active_md")
        return 2
    runner = GpuGridRunner(cfg, run_dir=root)
    case = cfg["stages"][TARGET_STAGE]["cases"][0]
    try:
        rec = runner.ensure_stageb_baseline(TARGET_STAGE, case)
        final_temp = rec.get("final_temp")
        blockers: list[str] = []
        if final_temp is not None and float(final_temp) > 1000.0:
            blockers.append(f"final temperature above 1000 K: {final_temp}")
        blockers.extend(prep_temperature_blockers(rec))
        if not rec.get("success"):
            blockers.extend(rec.get("failure_reasons") or ["prep failed"])
        status = "safe_prep_success" if not blockers else "safe_prep_failed"
        runner.state.mark_stage(
            TARGET_STAGE,
            {
                "status": status,
                "selected_case": TARGET_CASE,
                "prep_case_id": prep_case_id(),
                "blockers": blockers,
            },
        )
        runner.write_final_report()
        write_json(root / "safe_prep_result.json", {"status": status, "record": rec, "blockers": blockers})
        write_safe_final_report(root, status)
        return 0 if not blockers else 1
    except Exception as exc:
        runner.state.mark_stage(TARGET_STAGE, {"status": "safe_prep_failed", "blockers": [str(exc)]})
        runner.write_final_report()
        write_json(root / "safe_prep_result.json", {"status": "safe_prep_failed", "error": str(exc)})
        write_safe_final_report(root, "safe_prep_failed")
        return 1


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    root = safe_run_root(args.run_root)

    if args.worker_run_prep:
        if not args.config:
            print("ERROR: --config is required for worker", file=sys.stderr)
            return 2
        return worker_run_prep(args.config, root)

    old_failed_root = Path(args.old_failed_root)
    if not old_failed_root.is_absolute():
        old_failed_root = REPO_ROOT / old_failed_root

    cfg, preflight = prepare_root(args.config_template, root, old_failed_root.resolve())
    if not preflight["allowed_to_launch_safe_prep"]:
        result = {"launched": False, "reason": "preflight_blocked", "run_root": str(root), "preflight": preflight}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2
    if args.prepare_only:
        result = {"launched": False, "reason": "prepare_only", "run_root": str(root), "preflight": preflight}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if not args.launch_background:
        result = {"launched": False, "reason": "launch_background_flag_required", "run_root": str(root)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2
    record = launch_background(root)
    print(json.dumps({"run_root": str(root), "preflight": preflight, "launch": record}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
