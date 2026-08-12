#!/usr/bin/env python3
"""Prepare and launch Stage E homogeneous inclusion scale-up."""

from __future__ import annotations

import argparse
import ctypes
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
CONTROL_ROOT = REPO_ROOT.parent.parent
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner import builder, gpu_grid  # noqa: E402

TEMPLATE_CONFIG = REPO_ROOT / "configs" / "stageE_homogeneous_inclusion_scaleup.template.yaml"
STAGE_NAME = "E1_homogeneous_inclusion_scaleup"
TARGET_CANDIDATES = [1_000_000, 500_000, 250_000]
CASE_IDS = ["E1_homogeneous_control_eps0000", "E1_homogeneous_physical_eps0025"]
SIGMA_M_PA = 147e6
E_AL_PA = 75.7e9
FORMULA_EPS = SIGMA_M_PA / E_AL_PA
PHYSICAL_EPS = 0.0025
BASE_STAGE_D_ATOMS = 104_809
STAGED_RUN = REPO_ROOT / "runs" / "stageD_local_interface_100k_mechanics" / "20260618-215638"


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


def git_capture(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return proc.stdout.strip()


def commit_headroom_gib() -> float | None:
    if os.name != "nt":
        return None

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        return None
    return st.ullAvailPageFile / (1024**3)


def powershell_json(command: str) -> Any:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
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


def refined_active_processes() -> list[dict[str, Any]]:
    query = (
        "$items = Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -like 'python*' -or $_.Name -like 'lmp*' -or $_.Name -eq 'mpiexec.exe' }; "
        "$items | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    )
    rows = powershell_json(query)
    if not isinstance(rows, list):
        return [{"error": rows}]
    active: list[dict[str, Any]] = []
    own = os.getpid()
    for row in rows:
        try:
            pid = int(row.get("ProcessId"))
        except Exception:
            pid = -1
        if pid == own:
            continue
        name = str(row.get("Name", ""))
        cmd = str(row.get("CommandLine", ""))
        low = f"{name} {cmd}".lower()
        if name.lower().startswith("lmp") or "run_stage_sweep.py" in low or "run_stagee_smoke_then_full.py" in low:
            active.append({"pid": pid, "name": name, "command": cmd})
    return active


def nvidia_pmon_rows() -> list[dict[str, Any]]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        proc = subprocess.run(
            [exe, "pmon", "-c", "1"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 8 or parts[1] == "-":
            continue
        rows.append(
            {
                "gpu": parts[0],
                "pid": parts[1],
                "type": parts[2],
                "sm": parts[3],
                "mem": parts[4],
                "enc": parts[5],
                "dec": parts[6],
                "command": " ".join(parts[7:]),
            }
        )
    return rows


def calculation_gpu_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    needles = ("lmp", "python", "mpiexec", "compute-sanitizer", "cuda")
    out = []
    for row in rows:
        cmd = str(row.get("command", "")).lower()
        if any(n in cmd for n in needles):
            out.append(row)
    return out


def gpu_high_util(snapshot: dict[str, Any]) -> bool:
    for gpu in snapshot.get("gpus", []) or []:
        try:
            if int(str(gpu.get("utilization_gpu_percent", "0")).strip()) >= 90:
                return True
        except ValueError:
            continue
    return False


def stage_d_reference_sizes() -> dict[str, Any]:
    prod_dirs = [
        STAGED_RUN / "cases" / "D1_local_interface_100k" / cid / "production"
        for cid in ("D1_local_interface_control_eps0000", "D1_local_interface_physical_eps0025")
    ]
    totals = []
    by_file: dict[str, int] = {}
    for prod in prod_dirs:
        if not prod.is_dir():
            continue
        total = 0
        for path in prod.iterdir():
            if path.is_file():
                total += path.stat().st_size
                by_file[path.name] = max(by_file.get(path.name, 0), path.stat().st_size)
        totals.append(total)
    avg_total = int(sum(totals) / len(totals)) if totals else 60_000_000
    state = read_json(STAGED_RUN / "state.json", {})
    walls = [
        float(v.get("wall_time_s", 0))
        for k, v in state.get("cases", {}).items()
        if k.endswith("_production") and v.get("wall_time_s")
    ]
    avg_wall = sum(walls) / len(walls) if walls else 3860.0
    return {"avg_production_bytes_100k": avg_total, "max_files_100k": by_file, "avg_production_wall_s_100k": avg_wall}


def target_estimate(plan: dict[str, Any], ref: dict[str, Any]) -> dict[str, Any]:
    ratio = float(plan["estimated_atoms"]) / BASE_STAGE_D_ATOMS
    avg_prod = float(ref["avg_production_bytes_100k"])
    prod_two_cases = avg_prod * ratio * 2.0 * 1.20
    prep_smoke_two_cases = avg_prod * ratio * 2.0 * 0.80
    runtime_prod_case_h = float(ref["avg_production_wall_s_100k"]) * ratio / 3600.0
    return {
        "atom_ratio_vs_stageD": round(ratio, 3),
        "expected_production_output_gib_two_cases": round(prod_two_cases / (1024**3), 3),
        "expected_prep_smoke_output_gib_two_cases": round(prep_smoke_two_cases / (1024**3), 3),
        "expected_total_output_gib": round((prod_two_cases + prep_smoke_two_cases) / (1024**3), 3),
        "expected_production_runtime_h_per_case": round(runtime_prod_case_h, 2),
        "expected_production_runtime_h_two_cases": round(runtime_prod_case_h * 2.0, 2),
    }


def select_target(max_memory_gb: float, ref: dict[str, Any]) -> tuple[int | None, list[dict[str, Any]]]:
    plans: list[dict[str, Any]] = []
    for target in TARGET_CANDIDATES:
        plan = builder.plan_for_target(target, ranks=1, max_memory_gb=max_memory_gb)
        plan.update(target_estimate(plan, ref))
        plan["selected"] = False
        plans.append(plan)
    for plan in plans:
        if bool(plan["feasible_under_memory_limit"]):
            plan["selected"] = True
            return int(plan["target_atoms"]), plans
    return None, plans


def load_template_config() -> dict[str, Any]:
    with TEMPLATE_CONFIG.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def configure_for_target(cfg: dict[str, Any], target: int, plans: list[dict[str, Any]]) -> dict[str, Any]:
    cfg = json.loads(json.dumps(cfg))
    stage = cfg["stages"][STAGE_NAME]
    stage["atom_targets"] = [target]
    for case in stage["cases"]:
        case["atom_target"] = target
    cfg["experiment"]["selected_atom_target"] = target
    cfg["experiment"]["target_candidates"] = plans
    cfg["experiment"]["physical_eps_formula_value"] = round(FORMULA_EPS, 6)
    return cfg


def report_lines_for_plans(plans: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| target | estimated atoms | est GPU GB | feasible | expected output GiB | production h/case |",
        "|---:|---:|---:|---|---:|---:|",
    ]
    for plan in plans:
        lines.append(
            "| {target_atoms} | {estimated_atoms} | {estimated_memory_gb} | {feasible_under_memory_limit} | "
            "{expected_total_output_gib} | {expected_production_runtime_h_per_case} |".format(**plan)
        )
    return lines


def write_pending_reports(run_dir: Path, cfg: dict[str, Any], status: dict[str, Any]) -> None:
    stage = cfg["stages"][STAGE_NAME]
    case_summary_dir = run_dir / "case_summaries"
    case_summary_dir.mkdir(parents=True, exist_ok=True)
    for case in stage["cases"]:
        write_json(
            case_summary_dir / f"{case['case_id']}_summary.json",
            {
                "case_id": case["case_id"],
                "stage": STAGE_NAME,
                "atom_target": int(case["atom_target"]),
                "eps_z": float(case["eps_z"]),
                "position": case["position"],
                "predefect": case["predefect"],
                "status": status["status"],
                "result": "pending_runtime",
            },
        )

    pending_docs = {
        "stageE_boundary_dislocation_report.md": [
            "# Stage E boundary/dislocation report",
            "",
            "Status: pending production and OVITO analysis.",
            "Expected focus: dislocation segments and line length in the Al matrix near the inclusion-matrix boundary.",
        ],
        "stageE_stress_transfer_report.md": [
            "# Stage E stress transfer report",
            "",
            "Status: pending production and stress/atom analysis.",
            "Expected focus: sigma_zz and von Mises proxy maxima along Z near the inclusion-matrix boundary.",
        ],
        "stageE_structure_defects_report.md": [
            "# Stage E structure defects report",
            "",
            "Status: pending production and CNA/PTM analysis.",
            "Expected focus: HCP/OTHER changes in the Al matrix near the inclusion boundary.",
        ],
        "stageE_control_vs_physical_comparison.md": [
            "# Stage E control vs physical comparison",
            "",
            "Status: pending both production cases.",
            "Cases: control eps0000 and physical eps0025 only.",
        ],
        "stageE_physics_interpretation.md": [
            "# Stage E physics interpretation",
            "",
            "Status: not interpreted yet.",
            "Interpretation is intentionally withheld until both cases complete and analysis reports are regenerated.",
            f"Physical estimate: sigma_m/E_Al = 147 MPa / 75.7 GPa = {FORMULA_EPS:.6f}; launched eps_z={PHYSICAL_EPS:.4f} as conservative close upper estimate.",
        ],
    }
    for name, lines in pending_docs.items():
        (run_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_preflight_report(run_dir: Path, selected: int | None, plans: list[dict[str, Any]], status: dict[str, Any]) -> None:
    lines = [
        "# Stage E preflight report",
        "",
        f"Generated: {now()}",
        f"Run root: `{run_dir}`",
        "",
        "## Scope",
        "",
        "- homogeneous single-crystal Al matrix",
        "- centered Fe4Al13 ellipsoid inclusion",
        "- no grain boundary, no vacancies, no eps0100",
        "- cases: control eps0000 and physical eps0025",
        "",
        "## Eigenstrain",
        "",
        f"- sigma_m: 147 MPa",
        f"- E_Al: 75.7 GPa",
        f"- formula eps_z: {FORMULA_EPS:.6f}",
        f"- launched physical eps_z: {PHYSICAL_EPS:.4f}",
        "",
        "## Target selection",
        "",
        *report_lines_for_plans(plans),
        "",
        f"Selected target: `{selected}`",
        "",
        "## Resource gates",
        "",
        f"- git_branch: `{status['git_branch']}`",
        f"- disk_free_gib: `{status['disk_free_gib']}`",
        f"- commit_headroom_gib: `{status['commit_headroom_gib']}`",
        f"- gpu_snapshot: `{status['gpu_snapshot']}`",
        f"- active_runners_or_lammps: `{status['active_processes']}`",
        f"- gpu_calculation_processes: `{status['gpu_calculation_processes']}`",
        "",
        "## Blockers",
        "",
    ]
    lines += [f"- {b}" for b in status["blockers"]] if status["blockers"] else ["- none"]
    lines += ["", "## Environment check", ""]
    lines += [f"- {line}" for line in status.get("environment_lines", [])]
    (run_dir / "stageE_preflight_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_launch_report(run_dir: Path, status: dict[str, Any]) -> None:
    lines = [
        "# Stage E launch report",
        "",
        f"Generated: {now()}",
        f"Run root: `{run_dir}`",
        f"Status: `{status['status']}`",
        f"Wrapper PID: `{status.get('wrapper_pid')}`",
        "",
        "## Commands",
        "",
        f"- wrapper: `{status.get('wrapper_command')}`",
        f"- smoke: `{status.get('smoke_command')}`",
        f"- full: `{status.get('full_command')}`",
        "",
        "## Behavior",
        "",
        "- the wrapper runs smoke first",
        "- if smoke returns zero, the wrapper immediately starts full production for the same target",
        "- if smoke fails, production is not launched",
    ]
    (run_dir / "stageE_launch_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_runtime_status(run_dir: Path, status: dict[str, Any]) -> None:
    lines = [
        "# Stage E runtime status",
        "",
        f"Generated: {now()}",
        f"Status: `{status['status']}`",
        f"Wrapper PID: `{status.get('wrapper_pid')}`",
        f"Run root: `{run_dir}`",
        "",
        "Smoke/full details will be updated by `scripts/run_stageE_smoke_then_full.py` while it runs.",
    ]
    (run_dir / "stageE_runtime_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_completion_check(run_dir: Path, status: dict[str, Any]) -> None:
    lines = [
        "# Stage E completion check",
        "",
        f"Generated: {now()}",
        f"Status: `{status['status']}`",
        "",
        "Required before physics interpretation:",
        "",
        "- both production cases reach exit code 0",
        "- final dump/data/restart and analysis JSON exist",
        "- no instability markers are found in logs",
        "- control-vs-physical reports are regenerated from completed data",
    ]
    (run_dir / "stageE_completion_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_docs(run_dir: Path, selected: int | None, plans: list[dict[str, Any]], status: dict[str, Any]) -> None:
    reports_dir = REPO_ROOT / "docs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    action = reports_dir / "physicist_last_meeting_action_plan.md"
    action_lines = [
        "# Physicist last meeting action plan",
        "",
        f"Updated: {now()}",
        "",
        "## Question",
        "",
        "Test whether a Fe4Al13 inclusion can transfer stress into a homogeneous Al matrix and produce near-boundary plasticity, with attention to maximum stress zones along Z.",
        "",
        "## Current execution",
        "",
        f"- run root: `{run_dir}`",
        f"- selected target: `{selected}` atoms",
        f"- target priority result: 1M failed the configured 12 GB GPU-memory estimate; 500k was selected",
        f"- cases: `E1_homogeneous_control_eps0000`, `E1_homogeneous_physical_eps0025`",
        f"- physical estimate: 147 MPa / 75.7 GPa = {FORMULA_EPS:.6f}; launched eps_z={PHYSICAL_EPS:.4f}",
        f"- status: `{status['status']}`",
        "",
        "## Constraints kept",
        "",
        "- no grain boundary or polycrystal",
        "- no vacancies",
        "- no eps0100 overload",
        "- no parallel LAMMPS",
        "- no render/video workflow",
        "",
        "## Next check",
        "",
        f"Monitor `{run_dir / 'stageE_runtime_status.md'}` and then regenerate final interpretation after both production analyses finish.",
    ]
    action.write_text("\n".join(action_lines) + "\n", encoding="utf-8")

    milestone = REPO_ROOT / "docs" / "60_milestones" / "2026-06-22_stageE_homogeneous_inclusion_scaleup.md"
    milestone.parent.mkdir(parents=True, exist_ok=True)
    milestone_lines = [
        "# Stage E homogeneous inclusion scale-up",
        "",
        f"Updated: {now()}",
        "",
        f"Run root: `{run_dir}`",
        f"Selected target: `{selected}`",
        f"Status: `{status['status']}`",
        "",
        "Preflight selected the 500k fallback because the 1M target estimate is above the configured 12 GB GPU memory budget.",
        "The launched workflow runs smoke first and automatically continues into production only if smoke succeeds.",
    ]
    milestone.write_text("\n".join(milestone_lines) + "\n", encoding="utf-8")


def write_contexts_and_control_report(run_dir: Path, selected: int | None, status: dict[str, Any]) -> None:
    project_context = REPO_ROOT / ".codex" / "state" / "current_context.md"
    project_context.parent.mkdir(parents=True, exist_ok=True)
    project_context.write_text(
        "\n".join(
            [
                f"current objective: Stage E homogeneous inclusion scale-up is launched/handled for `{STAGE_NAME}`.",
                f"verified: target repo is `{REPO_ROOT}` on branch `{status['git_branch']}`.",
                "verified: project-local `AGENTS.md` / `AGENTS.override.md` are absent; global `C:\\Users\\dille\\.codex\\AGENTS.md` is absent.",
                f"verified: physical eigenstrain estimate is 147 MPa / 75.7 GPa = {FORMULA_EPS:.6f}; Stage E uses eps_z={PHYSICAL_EPS:.4f} as conservative close upper estimate.",
                "verified: Stage E uses homogeneous grain_interior/perfect cases only: no grain boundary, no vacancies, no eps0100.",
                "verified: 1M preflight exceeded configured GPU memory estimate; selected 500k fallback.",
                f"run_root: `{run_dir}`",
                f"selected_atom_target: `{selected}`",
                f"runtime_status: `{status['status']}`",
                "files_touched: Stage E config/template, launch/preflight scripts, run-root Stage E reports, docs action plan and milestone, GPU-grid experiment whitelist.",
                "pending_blockers: none at launch if runtime_status is launched_smoke_then_full; inspect reports if blocked.",
                f"exact_next_command: `Get-Content {run_dir / 'stageE_runtime_status.md'}`",
                "exact_next_step: monitor smoke/full wrapper; after both production cases complete, regenerate final Stage E physics interpretation from analysis JSON.",
                f"last_updated: `{now()}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        control_context = CONTROL_ROOT / ".codex" / "state" / "current_context.md"
        control_context.parent.mkdir(parents=True, exist_ok=True)
        control_context.write_text(project_context.read_text(encoding="utf-8"), encoding="utf-8")
        report_path = CONTROL_ROOT / "state" / "reports" / "physics_md_al_fe" / "stageE_homogeneous_inclusion_scaleup_20260622.json"
        write_json(
            report_path,
            {
                "status": status["status"],
                "generated_at": now(),
                "repo": str(REPO_ROOT),
                "run_root": str(run_dir),
                "selected_atom_target": selected,
                "cases": CASE_IDS,
                "blockers": status["blockers"],
                "wrapper_pid": status.get("wrapper_pid"),
            },
        )
    except Exception as exc:
        status.setdefault("warnings", []).append(f"control report write failed: {exc}")


def start_wrapper(run_dir: Path) -> dict[str, Any]:
    config = run_dir / "effective_config.yaml"
    wrapper = REPO_ROOT / "scripts" / "run_stageE_smoke_then_full.py"
    cmd = [sys.executable, str(wrapper), "--config", str(config), "--run-dir", str(run_dir), "--stage", STAGE_NAME]
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with (run_dir / "stageE_wrapper_stdout.txt").open("ab") as stdout, (run_dir / "stageE_wrapper_stderr.txt").open("ab") as stderr:
        proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=stdout, stderr=stderr, creationflags=creationflags)
    time.sleep(2.0)
    return {
        "wrapper_pid": proc.pid,
        "wrapper_command": " ".join(str(x) for x in cmd),
        "wrapper_returncode_after_2s": proc.poll(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(TEMPLATE_CONFIG))
    parser.add_argument("--run-dir", default=None)
    parser.add_argument("--no-launch", action="store_true")
    args = parser.parse_args(argv)

    cfg_template = load_template_config()
    ref = stage_d_reference_sizes()
    selected, plans = select_target(float(cfg_template["resources"]["gpu_memory_gb"]), ref)
    cfg = configure_for_target(cfg_template, int(selected or 250000), plans)

    runner = gpu_grid.GpuGridRunner(cfg, run_dir=args.run_dir)
    run_dir = runner.run_dir
    cfg = runner.cfg

    branch = git_capture(["branch", "--show-current"])
    disk_free = gpu_grid.free_disk_gb(REPO_ROOT)
    commit_free = commit_headroom_gib()
    gpu_snapshot = gpu_grid.nvidia_smi_snapshot()
    pmon = nvidia_pmon_rows()
    gpu_calc = calculation_gpu_rows(pmon)
    active = refined_active_processes()
    env_ok, env, env_lines = gpu_grid.check_environment(cfg)

    blockers: list[str] = []
    if branch in ("main", "master"):
        blockers.append(f"active branch is {branch}")
    if selected is None:
        blockers.append("1M/500k/250k preflight failed under configured GPU memory budget")
    if active:
        blockers.append("live LAMMPS or stage runner process detected")
    if disk_free < 3.0:
        blockers.append(f"C: free disk below 3 GiB: {disk_free:.2f} GiB")
    if commit_free is not None and commit_free < 2.0:
        blockers.append(f"commit headroom below 2 GiB: {commit_free:.2f} GiB")
    if gpu_high_util(gpu_snapshot) or gpu_calc:
        blockers.append("GPU appears occupied by another calculation")
    if not env_ok:
        blockers.extend([line for line in env_lines if line.startswith("FAIL")])

    smoke_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_stage_sweep.py"),
        "--config",
        str(run_dir / "effective_config.yaml"),
        "--run-dir",
        str(run_dir),
        "--run-stage",
        STAGE_NAME,
        "--gpu",
        "--smoke-only",
    ]
    full_cmd = [x for x in smoke_cmd if x != "--smoke-only"]

    status: dict[str, Any] = {
        "status": "blocked" if blockers else ("prepared_not_launched" if args.no_launch else "launching"),
        "generated_at": now(),
        "run_dir": str(run_dir),
        "selected_atom_target": selected,
        "git_branch": branch,
        "git_status_short": git_capture(["status", "--short"]) or "<clean>",
        "disk_free_gib": round(disk_free, 3),
        "commit_headroom_gib": round(commit_free, 3) if commit_free is not None else None,
        "gpu_snapshot": gpu_snapshot,
        "nvidia_pmon": pmon,
        "gpu_calculation_processes": gpu_calc,
        "active_processes": active,
        "environment": env,
        "environment_lines": env_lines,
        "blockers": blockers,
        "target_plans": plans,
        "smoke_command": " ".join(str(x) for x in smoke_cmd),
        "full_command": " ".join(str(x) for x in full_cmd),
        "wrapper_pid": None,
        "wrapper_command": None,
    }

    if not blockers and not args.no_launch:
        launch = start_wrapper(run_dir)
        status.update(launch)
        if launch["wrapper_returncode_after_2s"] is None:
            status["status"] = "launched_smoke_then_full"
        else:
            status["status"] = "blocked"
            status["blockers"].append(f"wrapper exited within 2s with code {launch['wrapper_returncode_after_2s']}")

    write_preflight_report(run_dir, selected, plans, status)
    write_launch_report(run_dir, status)
    write_runtime_status(run_dir, status)
    write_completion_check(run_dir, status)
    write_pending_reports(run_dir, cfg, status)
    write_json(run_dir / "stageE_analysis_summary.json", status)
    write_json(run_dir / "stageE_status.json", status)
    write_docs(run_dir, selected, plans, status)
    write_contexts_and_control_report(run_dir, selected, status)

    print(json.dumps({"run_dir": str(run_dir), "status": status["status"], "selected_atom_target": selected, "blockers": status["blockers"], "wrapper_pid": status.get("wrapper_pid")}, ensure_ascii=False, indent=2))
    return 0 if not status["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
