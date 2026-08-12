#!/usr/bin/env python3
"""Stage F dual-lane CPU fallback production plus GPU repair tracking.

The CPU lane is strictly self-contained: eps0000 and eps00194 use the same
CPU binary, MPI/OpenMP policy, zhi=200 data treatment, and LAMMPS protocol.
The worker runs comparable 10k smokes first and only then starts the 50k
CPU production pair sequentially.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
RUN_ROOT = REPO / "runs" / "stageF_F0_planar_100A_ppf_commensurate" / "20260630-010748"
EPS0000 = RUN_ROOT / "F0_planar_100A_comm_eps0000"
EPS00194 = RUN_ROOT / "F0_planar_100A_comm_eps00194"
REPORTS = REPO / "docs" / "reports"

DATA_EPS0000_RELAXED = EPS0000 / "equil" / "data.F0_planar_100A_comm_eps0000.relaxed"
DATA_EPS00194_Z200_SOURCE = EPS00194 / "debug_fix1_z_headroom_cpu" / "data.F0_planar_100A_comm_eps00194.zheadroom30"

POT_DIR = REPO / "potentials" / "meam" / "Jelinek_2012"
MEAMF = POT_DIR / "Jelinek_2012_meamf"
MEAM = POT_DIR / "Jelinek_2012_meam.alsimgcufe"

CPU_LMP = Path(r"C:\Users\dille\AppData\Local\LAMMPS 64-bit 22Jul2025-MSMPI\bin\lmp.exe")
MPIEXEC = Path(r"C:\Program Files\Microsoft MPI\Bin\mpiexec.exe")

RUN_ID = datetime.now().strftime("%Y%m%d-%H%M%S")
CPU_MPI_RANKS = 6
CPU_OMP_THREADS = 2
SMOKE_STEPS = 10000
PRODUCTION_STEPS = 50000

FATAL_PATTERNS = [
    "ERROR:",
    "Lost atoms",
    "lost atoms",
    "nan",
    "NaN",
    "cudaError",
    "CUDA error",
    "illegal memory",
    "illegal address",
    "segmentation fault",
    "Segmentation fault",
    "MPI_ABORT",
    "Kokkos::abort",
    "Neighbor list overflow",
    "Out of range atoms",
    "Did not assign all atoms correctly",
]

FORBIDDEN_INPUT_PATTERNS = [
    "thermo_modify lost ignore",
    "thermo_modify   lost ignore",
    "fix box/relax",
    "boundary        m m f",
    "boundary m m f",
]


@dataclass(frozen=True)
class CaseSpec:
    key: str
    title: str
    data: Path


@dataclass(frozen=True)
class RunCase:
    case_key: str
    stage: str
    steps: int
    data: Path
    folder: Path


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def posix(path: Path) -> str:
    return path.resolve().as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False, default=str))


def run_capture(cmd: list[str], cwd: Path | None = None, timeout_s: int = 60) -> dict[str, Any]:
    started = time.time()
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout_s,
        )
        return {
            "command": cmd,
            "cwd": str(cwd) if cwd else None,
            "returncode": cp.returncode,
            "stdout": cp.stdout,
            "stderr": cp.stderr,
            "timed_out": False,
            "elapsed_s": round(time.time() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return {
            "command": cmd,
            "cwd": str(cwd) if cwd else None,
            "returncode": 124,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
            "elapsed_s": round(time.time() - started, 3),
        }


def ps(script: str, timeout_s: int = 60) -> dict[str, Any]:
    return run_capture(["powershell", "-NoProfile", "-Command", script], timeout_s=timeout_s)


def parse_data_header(path: Path) -> dict[str, Any]:
    text = read_text(path)
    header: dict[str, Any] = {
        "path": rel(path),
        "exists": path.exists(),
        "atoms_total": None,
        "atom_types": None,
        "type_counts": {},
        "xlo": None,
        "xhi": None,
        "ylo": None,
        "yhi": None,
        "zlo": None,
        "zhi": None,
        "Lx_A": None,
        "Ly_A": None,
        "Lz_A": None,
        "min_z": None,
        "max_z": None,
    }
    if not text:
        return header
    lines = text.splitlines()
    for line in lines[:80]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "atoms":
            header["atoms_total"] = int(parts[0])
        elif len(parts) >= 3 and parts[1] == "atom" and parts[2] == "types":
            header["atom_types"] = int(parts[0])
        elif len(parts) >= 4 and parts[2] == "xlo" and parts[3] == "xhi":
            header["xlo"], header["xhi"] = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[2] == "ylo" and parts[3] == "yhi":
            header["ylo"], header["yhi"] = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[2] == "zlo" and parts[3] == "zhi":
            header["zlo"], header["zhi"] = float(parts[0]), float(parts[1])
    for lo, hi, key in (("xlo", "xhi", "Lx_A"), ("ylo", "yhi", "Ly_A"), ("zlo", "zhi", "Lz_A")):
        if header[lo] is not None and header[hi] is not None:
            header[key] = header[hi] - header[lo]

    in_atoms = False
    seen_atom_line = False
    type_counts: dict[str, int] = {}
    min_z = None
    max_z = None
    section_header = re.compile(r"^[A-Za-z][A-Za-z0-9_ /-]*$")
    for line in lines:
        stripped = line.strip()
        if not in_atoms:
            if stripped.startswith("Atoms"):
                in_atoms = True
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if seen_atom_line and section_header.match(stripped) and not re.match(r"^\d+\s+", stripped):
            break
        parts = stripped.split()
        if len(parts) < 5 or not parts[0].lstrip("-").isdigit() or not parts[1].lstrip("-").isdigit():
            continue
        seen_atom_line = True
        atom_type = parts[1]
        type_counts[atom_type] = type_counts.get(atom_type, 0) + 1
        try:
            z = float(parts[4])
        except ValueError:
            continue
        min_z = z if min_z is None else min(min_z, z)
        max_z = z if max_z is None else max(max_z, z)
    header["type_counts"] = type_counts
    header["min_z"] = min_z
    header["max_z"] = max_z
    return header


def write_zhi200_copy(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    original = parse_data_header(src)
    lines = []
    changed = False
    for line in read_text(src).splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[2] == "zlo" and parts[3] == "zhi":
            zlo = float(parts[0])
            lines.append(f"{zlo:.16g} {200.0:.16g} zlo zhi")
            changed = True
        else:
            lines.append(line)
    if not changed:
        raise RuntimeError(f"Could not find zlo/zhi line in {src}")
    write_text(dst, "\n".join(lines))
    updated = parse_data_header(dst)
    return {
        "source": rel(src),
        "target": rel(dst),
        "operation": "changed only zhi to 200.0 A; atom coordinates unchanged",
        "original": original,
        "updated": updated,
    }


def copy_eps00194_z200(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {
        "source": rel(src),
        "target": rel(dst),
        "operation": "copied stabilized zhi=200 data for comparable CPU lane",
        "updated": parse_data_header(dst),
    }


def lammps_input(run_case: RunCase) -> str:
    text = f"""# Stage F comparable CPU fallback {run_case.case_key} {run_case.stage}.
units           metal
atom_style      atomic
boundary        p p f
read_data       {posix(run_case.data)}
pair_style      meam
pair_coeff      * * {posix(MEAMF)} AlS SiS MgS CuS FeS {posix(MEAM)} AlS FeS
neighbor        2.0 bin
neigh_modify    delay 0 every 1 check yes
timestep        0.001

compute         pe_atom all pe/atom
compute         st all stress/atom NULL virial

region          bottom block INF INF INF INF INF 8.0 units box
group           bottom region bottom
group           mobile subtract all bottom
fix             hold bottom setforce 0.0 0.0 0.0
velocity        mobile create 300.0 88004 mom yes rot yes dist gaussian
fix             nvt_mobile mobile nvt temp 300.0 300.0 0.1

thermo          200
thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz
thermo_modify   flush yes
dump            d1 all custom 1000 dump.lammpstrj id type x y z c_pe_atom c_st[1] c_st[2] c_st[3] c_st[4] c_st[5] c_st[6]
dump_modify     d1 sort id
restart         5000 restart.*
run             {run_case.steps}
write_restart   restart.final
write_data      data.final
"""
    lowered = " ".join(text.lower().split())
    hits = [pattern for pattern in FORBIDDEN_INPUT_PATTERNS if pattern in lowered]
    if hits:
        raise RuntimeError(f"Forbidden LAMMPS input pattern(s) in {run_case.case_key}: {hits}")
    return text


def thermo_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cols: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^Step\s+", stripped):
            cols = stripped.split()
            continue
        if not cols or not stripped:
            continue
        parts = stripped.split()
        if len(parts) != len(cols):
            continue
        if not re.match(r"^[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$", parts[0]):
            continue
        try:
            row = {col: float(raw) for col, raw in zip(cols, parts)}
        except ValueError:
            continue
        for key in ("Step", "Atoms"):
            if key in row:
                row[key] = int(row[key])
        rows.append(row)
    return rows


def parse_lammps_run(folder: Path, case_key: str, stage: str, target_step: int) -> dict[str, Any]:
    log = read_text(folder / "log.lammps")
    stdout = read_text(folder / "stdout.log")
    stderr = read_text(folder / "stderr.log")
    combined = "\n".join([log, stdout, stderr])
    rows = thermo_rows(combined)
    fatal = []
    for idx, line in enumerate(combined.splitlines(), start=1):
        for pattern in FATAL_PATTERNS:
            if pattern in line:
                fatal.append({"line": idx, "pattern": pattern, "text": line.strip()})
                break
    rc = None
    if (folder / "returncode.txt").exists():
        raw = read_text(folder / "returncode.txt").strip()
        try:
            rc = int(raw)
        except ValueError:
            rc = raw
    final_data = folder / "data.final"
    final_restart = folder / "restart.final"
    max_step = max([row["Step"] for row in rows], default=None)
    clean = rc == 0 and not fatal and max_step == target_step and final_data.exists() and final_restart.exists()
    return {
        "case": case_key,
        "stage": stage,
        "folder": rel(folder),
        "returncode": rc,
        "status": "completed_clean" if clean else ("running_or_not_finished" if rc is None else "failed"),
        "fatal": bool(fatal),
        "fatal_matches": fatal,
        "target_step": target_step,
        "max_step": max_step,
        "last_thermo": rows[-1] if rows else None,
        "loop_time": "Loop time" in combined,
        "total_wall_time": "Total wall time" in combined,
        "final_data_exists": final_data.exists(),
        "final_restart_exists": final_restart.exists(),
        "stdout_tail": "\n".join(stdout.splitlines()[-30:]),
        "stderr_tail": "\n".join(stderr.splitlines()[-30:]),
        "log_tail": "\n".join(log.splitlines()[-50:]),
    }


def cpu_command(input_name: str) -> list[str]:
    return [str(MPIEXEC), "-np", str(CPU_MPI_RANKS), str(CPU_LMP), "-in", input_name, "-log", "log.lammps"]


def prepare_roots(run_id: str) -> dict[str, Any]:
    comparable_root = RUN_ROOT / f"cpu_fallback_comparable_{run_id}"
    production_root = RUN_ROOT / f"cpu_fallback_production_{run_id}"
    comparable_root.mkdir(parents=True, exist_ok=False)
    production_root.mkdir(parents=True, exist_ok=False)

    data_dir = comparable_root / "data"
    eps0000_data = data_dir / "data.F0_planar_100A_comm_eps0000.cpu_zhi200"
    eps00194_data = data_dir / "data.F0_planar_100A_comm_eps00194.cpu_zhi200"
    eps0000_info = write_zhi200_copy(DATA_EPS0000_RELAXED, eps0000_data)
    eps00194_info = copy_eps00194_z200(DATA_EPS00194_Z200_SOURCE, eps00194_data)

    cases = [
        CaseSpec("F0_planar_100A_comm_eps0000_cpu_zhi200", "eps0000 CPU zhi=200", eps0000_data),
        CaseSpec("F0_planar_100A_comm_eps00194_cpu_zhi200", "eps00194 CPU zhi=200", eps00194_data),
    ]
    smoke_cases = []
    production_cases = []
    for case in cases:
        smoke_folder = comparable_root / case.key / "smoke10k"
        prod_folder = production_root / case.key / "production50k"
        smoke_folder.mkdir(parents=True, exist_ok=True)
        prod_folder.mkdir(parents=True, exist_ok=True)
        smoke_case = RunCase(case.key, "smoke10k", SMOKE_STEPS, case.data, smoke_folder)
        prod_case = RunCase(case.key, "production50k", PRODUCTION_STEPS, case.data, prod_folder)
        write_text(smoke_folder / "in.cpu_smoke10k", lammps_input(smoke_case))
        write_text(prod_folder / "in.cpu_production50k", lammps_input(prod_case))
        smoke_cases.append(smoke_case)
        production_cases.append(prod_case)

    setup = {
        "timestamp": now(),
        "run_id": run_id,
        "comparable_root": rel(comparable_root),
        "production_root": rel(production_root),
        "cpu_binary": str(CPU_LMP),
        "mpiexec": str(MPIEXEC),
        "cpu_policy": {"mpi_ranks": CPU_MPI_RANKS, "omp_threads": CPU_OMP_THREADS},
        "protocol": {
            "boundary": "p p f",
            "zhi_A": 200.0,
            "timestep_ps": 0.001,
            "thermostat": "mobile NVT 300 K to 300 K, damping 0.1",
            "velocity_seed": 88004,
            "neighbor": "delay 0 every 1 check yes",
            "dump_every": 1000,
            "restart_every": 5000,
            "box_relax": False,
            "wall": False,
            "thermo_modify_lost_ignore": False,
        },
        "data": {
            "eps0000": eps0000_info,
            "eps00194": eps00194_info,
        },
        "smoke_cases": [run_case_record(case, "in.cpu_smoke10k") for case in smoke_cases],
        "production_cases": [run_case_record(case, "in.cpu_production50k") for case in production_cases],
    }
    write_setup_reports(setup)
    return {
        "setup": setup,
        "comparable_root": comparable_root,
        "production_root": production_root,
        "smoke_cases": smoke_cases,
        "production_cases": production_cases,
    }


def run_case_record(case: RunCase, input_name: str) -> dict[str, Any]:
    return {
        "case": case.case_key,
        "stage": case.stage,
        "steps": case.steps,
        "data": rel(case.data),
        "folder": rel(case.folder),
        "input": rel(case.folder / input_name),
        "command": cpu_command(input_name),
    }


def preflight() -> dict[str, Any]:
    venv_path = REPO / ".venv" / "Scripts" / "python.exe"
    parent_venv = REPO.parent / ".venv" / "Scripts" / "python.exe"
    if venv_path.exists():
        python_for_task = venv_path
        venv_note = "used project .venv; prompt path ..venv was not needed"
    elif parent_venv.exists():
        python_for_task = parent_venv
        venv_note = "used parent ..venv"
    else:
        python_for_task = Path(sys.executable)
        venv_note = "used current Python executable"

    checks = {
        "git_branch": run_capture(["git", "branch", "--show-current"], cwd=REPO, timeout_s=30),
        "git_status_short": run_capture(["git", "status", "--short"], cwd=REPO, timeout_s=30),
        "active_processes": ps(
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -match 'lmp|mpiexec|stageF|python' } | "
            "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 4",
            timeout_s=30,
        ),
        "nvidia_smi": run_capture(["nvidia-smi"], timeout_s=30),
        "psdrive_c": ps("Get-PSDrive C | Select-Object Name,Used,Free,Provider,Root | ConvertTo-Json -Depth 4", timeout_s=30),
        "memory": ps("Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory | ConvertTo-Json", timeout_s=30),
        "cpu": ps("Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Depth 4", timeout_s=30),
        "python_version": run_capture([str(python_for_task), "--version"], cwd=REPO, timeout_s=30),
        "python_executable": run_capture(
            [str(python_for_task), "-c", "import sys,json; print(json.dumps({'executable': sys.executable, 'version': sys.version}))"],
            cwd=REPO,
            timeout_s=30,
        ),
        "cpu_binary_help": run_capture([str(CPU_LMP), "-h"], timeout_s=45) if CPU_LMP.exists() else {"returncode": None, "stdout": "", "stderr": "missing", "timed_out": False},
    }
    data = {
        "timestamp": now(),
        "target_repo": str(REPO),
        "branch_expected": "ilua/auto/stageD-local-interface-100k-mechanics",
        "run_root": rel(RUN_ROOT),
        "venv_path_correction": venv_note,
        "python_for_task": str(python_for_task),
        "checks": checks,
        "cpu_lane_safe_to_launch": CPU_LMP.exists() and MPIEXEC.exists(),
    }
    write_json(REPORTS / "stageF_dual_lane_preflight.json", data)
    write_text(REPORTS / "stageF_dual_lane_preflight.md", render_preflight_md(data))
    return data


def render_preflight_md(data: dict[str, Any]) -> str:
    return f"""# Stage F dual-lane preflight

- Timestamp: {data['timestamp']}
- Target repo: `{data['target_repo']}`
- Expected branch: `{data['branch_expected']}`
- Actual branch: `{data['checks']['git_branch']['stdout'].strip()}`
- Run root: `{data['run_root']}`
- Python path: `{data['python_for_task']}`
- Venv note: {data['venv_path_correction']}
- CPU binary exists: `{CPU_LMP.exists()}`
- MPIEXEC exists: `{MPIEXEC.exists()}`
- CPU lane safe to launch: `{data['cpu_lane_safe_to_launch']}`

## Git status

```text
{data['checks']['git_status_short']['stdout'].strip()}
```

## Active process query

```json
{data['checks']['active_processes']['stdout'].strip()}
```

## GPU

```text
{data['checks']['nvidia_smi']['stdout'].strip()}
```

## CPU and memory

```json
{data['checks']['cpu']['stdout'].strip()}
{data['checks']['memory']['stdout'].strip()}
```

## Disk C

```json
{data['checks']['psdrive_c']['stdout'].strip()}
```
"""


def write_start_report(run_id: str) -> None:
    data = {
        "timestamp": now(),
        "run_id": run_id,
        "mode": "STAGE F DUAL-LANE EXECUTION",
        "cpu_fallback_approval": "explicitly approved by prompt.txt on 2026-06-30",
        "valid_delta_pairs": ["CPU_eps00194 - CPU_eps0000", "GPU_eps00194 - GPU_eps0000"],
        "invalid_pairs": ["mixed CPU/GPU", "different zhi/protocol pairs"],
        "cpu_plan": [
            "prepare eps0000 and eps00194 zhi=200 data under a fresh comparable CPU root",
            "run eps0000 CPU 10k smoke",
            "run eps00194 CPU 10k smoke",
            "if both smokes complete clean, run eps0000 50k CPU production",
            "if eps0000 production completes clean, run eps00194 50k CPU production",
        ],
        "gpu_plan": [
            "keep GPU repair lane separate",
            "do not launch GPU production until comparable GPU smokes pass",
            "do not use GPU artifacts in the CPU delta pair",
        ],
        "non_mixing_rule": "No CPU/GPU mixed delta pair is valid.",
    }
    write_json(REPORTS / "stageF_dual_lane_cpu_production_gpu_repair_start.json", data)
    md = f"""# Stage F dual-lane CPU production / GPU repair start

- Timestamp: {data['timestamp']}
- Run ID: `{run_id}`
- CPU fallback approval: {data['cpu_fallback_approval']}
- Target run root: `{rel(RUN_ROOT)}`

## Pair rule

Valid pairs are `CPU_eps00194 - CPU_eps0000` or `GPU_eps00194 - GPU_eps0000`.
Mixed CPU/GPU deltas, mixed zhi values, or mixed protocols are invalid.

## CPU lane

1. Prepare eps0000 and eps00194 zhi=200 data under a fresh comparable CPU root.
2. Run eps0000 CPU 10k smoke.
3. Run eps00194 CPU 10k smoke.
4. Only if both smokes are clean, run eps0000 50k CPU production.
5. Only if eps0000 production is clean, run eps00194 50k CPU production.

## GPU lane

GPU backend repair remains separate. GPU production is still gated behind a valid comparable GPU smoke pair and no GPU result will be mixed into the CPU fallback delta.
"""
    write_text(REPORTS / "stageF_dual_lane_cpu_production_gpu_repair_start.md", md)


def write_setup_reports(setup: dict[str, Any]) -> None:
    write_json(REPORTS / "stageF_dual_lane_cpu_setup.json", setup)
    eps0000 = setup["data"]["eps0000"]["updated"]
    eps00194 = setup["data"]["eps00194"]["updated"]
    md = f"""# Stage F dual-lane CPU setup

- Timestamp: {setup['timestamp']}
- Comparable root: `{setup['comparable_root']}`
- Production root: `{setup['production_root']}`
- CPU binary: `{setup['cpu_binary']}`
- MPI policy: `{setup['cpu_policy']['mpi_ranks']}` ranks x `{setup['cpu_policy']['omp_threads']}` OpenMP threads
- Boundary: `p p f`
- zhi: `200.0 A` for both cases
- No wall, no box/relax, no lost-ignore policy.

## Data comparability

| case | atoms | type counts | Lx | Ly | Lz | min z | max z |
|---|---:|---|---:|---:|---:|---:|---:|
| eps0000 CPU zhi200 | {eps0000['atoms_total']} | `{eps0000['type_counts']}` | {eps0000['Lx_A']} | {eps0000['Ly_A']} | {eps0000['Lz_A']} | {eps0000['min_z']} | {eps0000['max_z']} |
| eps00194 CPU zhi200 | {eps00194['atoms_total']} | `{eps00194['type_counts']}` | {eps00194['Lx_A']} | {eps00194['Ly_A']} | {eps00194['Lz_A']} | {eps00194['min_z']} | {eps00194['max_z']} |
"""
    write_text(REPORTS / "stageF_dual_lane_cpu_setup.md", md)
    write_resource_policy_report(setup)


def write_resource_policy_report(setup: dict[str, Any]) -> None:
    md = f"""# Stage F dual-lane resource policy

- Timestamp: {now()}
- CPU lane policy: `{CPU_MPI_RANKS}` MPI ranks x `{CPU_OMP_THREADS}` OpenMP threads.
- Reason: local preflight reports 6 cores / 12 logical processors; this avoids the earlier 8 x 6 oversubscription while keeping eps0000 and eps00194 identical.
- Execution order: smoke eps0000, smoke eps00194, production eps0000, production eps00194.
- GPU lane: no GPU production launch while CPU fallback pair is running; GPU repair evidence remains separate.
- Output policy: dump every 1000, restart every 5000, final data and final restart.
- Forbidden policy: no `thermo_modify lost ignore`, no wall, no `fix box/relax`, no eps005/F1/F0_300A launch.

CPU comparable root: `{setup['comparable_root']}`
CPU production root: `{setup['production_root']}`
"""
    write_text(REPORTS / "stageF_dual_lane_resource_policy.md", md)


def write_gpu_repair_status() -> dict[str, Any]:
    data = {
        "timestamp": now(),
        "status": "not_recovered",
        "separate_lane": True,
        "latest_evidence": {
            "extended_variants": "docs/reports/stageF_gpu_fix_extended_kokkos_runtime_variants.md",
            "blocker_decision": "docs/reports/stageF_F0_commensurate_ppf_gpu_backend_blocker_decision.md",
            "final_handoff": "agent_report_stageF_gpu_fix_to_production_final.md",
        },
        "production": "not_started",
        "reason": "release, debug, and clean CUDA 12.4 rebuild all failed KOKKOS CUDA MEAM/KK dynamics at step 0",
        "next_viable_gpu_work": "source-level KOKKOS/MEAM debug or different validated GPU MEAM path; no GPU production until both comparable GPU smokes pass",
    }
    write_json(REPORTS / "stageF_parallel_gpu_repair_status.json", data)
    md = f"""# Stage F parallel GPU repair status

- Timestamp: {data['timestamp']}
- GPU backend status: **not recovered**
- Production: not started.
- Separate lane: `{data['separate_lane']}`
- Reason: {data['reason']}.

## Current evidence

- `docs/reports/stageF_gpu_fix_extended_kokkos_runtime_variants.md`
- `docs/reports/stageF_F0_commensurate_ppf_gpu_backend_blocker_decision.md`
- `agent_report_stageF_gpu_fix_to_production_final.md`

## Next GPU gate

GPU production remains closed until a GPU path completes eps00194 zhi=200 smoke 10k and eps0000 comparable zhi=200 smoke 10k with the same GPU binary, flags, zhi, and protocol.
"""
    write_text(REPORTS / "stageF_parallel_gpu_repair_status.md", md)
    return data


def write_smoke_report(status: dict[str, Any]) -> None:
    write_json(REPORTS / "stageF_dual_lane_cpu_smoke_gate.json", status)
    rows = []
    for item in status.get("smoke_results", []):
        rows.append(
            f"| {item['case']} | {item['status']} | {item.get('max_step')} | {item.get('returncode')} | `{item['folder']}` |"
        )
    rows_text = "\n".join(rows) if rows else "| pending | running |  |  |  |"
    md = f"""# Stage F dual-lane CPU smoke gate

- Timestamp: {status['timestamp']}
- Gate status: **{status['status']}**
- Current case: `{status.get('current_case')}`
- Worker PID: `{status.get('worker_pid')}`
- Comparable root: `{status.get('comparable_root')}`

| case | status | max step | return code | folder |
|---|---|---:|---:|---|
{rows_text}

Production starts only if both CPU smokes complete clean under the same CPU binary, rank/thread policy, zhi=200, and protocol.
"""
    write_text(REPORTS / "stageF_dual_lane_cpu_smoke_gate.md", md)


def write_production_report(status: dict[str, Any]) -> None:
    write_json(REPORTS / "stageF_dual_lane_cpu_production_status.json", status)
    rows = []
    for item in status.get("production_results", []):
        rows.append(
            f"| {item['case']} | {item['status']} | {item.get('max_step')} | {item.get('returncode')} | `{item['folder']}` |"
        )
    rows_text = "\n".join(rows) if rows else "| pending | not_started |  |  |  |"
    md = f"""# Stage F dual-lane CPU production status

- Timestamp: {status['timestamp']}
- Production status: **{status['status']}**
- Current case: `{status.get('current_case')}`
- Worker PID: `{status.get('worker_pid')}`
- Production root: `{status.get('production_root')}`

| case | status | max step | return code | folder |
|---|---|---:|---:|---|
{rows_text}

The valid CPU delta pair requires both 50k production cases to complete clean. No analysis is run before that gate.
"""
    write_text(REPORTS / "stageF_dual_lane_cpu_production_status.md", md)


def worker_status_path(comparable_root: Path) -> Path:
    return comparable_root / "cpu_fallback_worker_status.json"


def write_worker_status(status_path: Path, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload["timestamp"] = now()
    write_json(status_path, payload)


def run_lammps_monitored(run_case: RunCase, input_name: str, status_path: Path, base_status: dict[str, Any]) -> dict[str, Any]:
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(CPU_OMP_THREADS)
    env["OMP_PROC_BIND"] = "false"
    cmd = cpu_command(input_name)
    write_text(run_case.folder / "command.json", json.dumps({"command": cmd, "env_overrides": {"OMP_NUM_THREADS": CPU_OMP_THREADS}}, indent=2))
    with (run_case.folder / "stdout.log").open("w", encoding="utf-8") as stdout, (run_case.folder / "stderr.log").open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(cmd, cwd=str(run_case.folder), stdout=stdout, stderr=stderr, env=env)
        while True:
            parsed = parse_lammps_run(run_case.folder, run_case.case_key, run_case.stage, run_case.steps)
            current = dict(base_status)
            current.update(
                {
                    "status": "running",
                    "current_case": run_case.case_key,
                    "current_stage": run_case.stage,
                    "current_lammps_pid": proc.pid,
                    "current_max_step": parsed["max_step"],
                    "current_folder": rel(run_case.folder),
                    "current_log": rel(run_case.folder / "log.lammps"),
                }
            )
            write_worker_status(status_path, current)
            if proc.poll() is not None:
                break
            time.sleep(60)
    write_text(run_case.folder / "returncode.txt", str(proc.returncode))
    return parse_lammps_run(run_case.folder, run_case.case_key, run_case.stage, run_case.steps)


def worker(config_path: Path) -> int:
    config = json.loads(read_text(config_path))
    comparable_root = Path(config["comparable_root"])
    production_root = Path(config["production_root"])
    status_path = Path(config["status_json"])
    smoke_cases = [case_from_config(item) for item in config["smoke_cases"]]
    production_cases = [case_from_config(item) for item in config["production_cases"]]

    base = {
        "worker_pid": os.getpid(),
        "run_id": config["run_id"],
        "comparable_root": rel(comparable_root),
        "production_root": rel(production_root),
        "cpu_policy": config["cpu_policy"],
        "smoke_results": [],
        "production_results": [],
    }
    write_worker_status(status_path, {**base, "status": "running_smoke_gate", "current_case": smoke_cases[0].case_key})
    write_smoke_report({**base, "timestamp": now(), "status": "running_smoke_gate", "current_case": smoke_cases[0].case_key})
    write_production_report({**base, "timestamp": now(), "status": "not_started_smoke_gate_open", "current_case": None})

    smoke_results = []
    for case in smoke_cases:
        result = run_lammps_monitored(case, "in.cpu_smoke10k", status_path, {**base, "smoke_results": smoke_results, "production_results": []})
        smoke_results.append(result)
        smoke_status = {**base, "timestamp": now(), "status": "running_smoke_gate", "current_case": None, "smoke_results": smoke_results}
        write_smoke_report(smoke_status)
        if result["status"] != "completed_clean":
            blocked = {**base, "timestamp": now(), "status": "blocked_smoke_failed", "current_case": None, "smoke_results": smoke_results}
            write_worker_status(status_path, blocked)
            write_smoke_report(blocked)
            write_production_report({**blocked, "status": "not_started_smoke_failed", "production_results": []})
            write_root_agent_report(blocked)
            return 1

    production_results = []
    write_worker_status(status_path, {**base, "status": "running_production", "current_case": production_cases[0].case_key, "smoke_results": smoke_results})
    write_production_report({**base, "timestamp": now(), "status": "running_production", "current_case": production_cases[0].case_key, "smoke_results": smoke_results, "production_results": production_results})
    for case in production_cases:
        result = run_lammps_monitored(case, "in.cpu_production50k", status_path, {**base, "smoke_results": smoke_results, "production_results": production_results})
        production_results.append(result)
        prod_status = {
            **base,
            "timestamp": now(),
            "status": "running_production",
            "current_case": None,
            "smoke_results": smoke_results,
            "production_results": production_results,
        }
        write_production_report(prod_status)
        if result["status"] != "completed_clean":
            failed = {**prod_status, "status": "failed_production", "current_case": None}
            write_worker_status(status_path, failed)
            write_production_report(failed)
            write_root_agent_report(failed)
            return 1

    complete = {
        **base,
        "timestamp": now(),
        "status": "completed_clean_cpu_pair",
        "current_case": None,
        "smoke_results": smoke_results,
        "production_results": production_results,
        "analysis_status": "not_run",
    }
    write_worker_status(status_path, complete)
    write_smoke_report({**complete, "status": "completed_clean_smoke_pair"})
    write_production_report(complete)
    write_root_agent_report(complete)
    return 0


def case_from_config(item: dict[str, Any]) -> RunCase:
    return RunCase(
        case_key=item["case"],
        stage=item["stage"],
        steps=int(item["steps"]),
        data=Path(item["data_abs"]),
        folder=Path(item["folder_abs"]),
    )


def launch_worker(pre: dict[str, Any], prepared: dict[str, Any]) -> dict[str, Any]:
    comparable_root: Path = prepared["comparable_root"]
    production_root: Path = prepared["production_root"]
    status_path = worker_status_path(comparable_root)
    config_path = comparable_root / "cpu_fallback_worker_config.json"
    smoke_cases = prepared["smoke_cases"]
    production_cases = prepared["production_cases"]
    config = {
        "run_id": prepared["setup"]["run_id"],
        "comparable_root": str(comparable_root),
        "production_root": str(production_root),
        "status_json": str(status_path),
        "cpu_policy": prepared["setup"]["cpu_policy"],
        "smoke_cases": [case_config(case) for case in smoke_cases],
        "production_cases": [case_config(case) for case in production_cases],
    }
    write_json(config_path, config)
    write_worker_status(
        status_path,
        {
            "status": "starting",
            "run_id": config["run_id"],
            "worker_pid": None,
            "comparable_root": rel(comparable_root),
            "production_root": rel(production_root),
            "cpu_policy": config["cpu_policy"],
            "smoke_results": [],
            "production_results": [],
        },
    )
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", str(config_path)]
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    stdout = (comparable_root / "worker_stdout.log").open("w", encoding="utf-8")
    stderr = (comparable_root / "worker_stderr.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=str(REPO), stdout=stdout, stderr=stderr, creationflags=creationflags)
    stdout.close()
    stderr.close()
    launch = {
        "timestamp": now(),
        "status": "running_smoke_gate",
        "worker_pid": proc.pid,
        "config": rel(config_path),
        "status_json": rel(status_path),
        "stdout": rel(comparable_root / "worker_stdout.log"),
        "stderr": rel(comparable_root / "worker_stderr.log"),
        "comparable_root": rel(comparable_root),
        "production_root": rel(production_root),
        "monitor_command": f"Get-Content -Raw {rel(status_path).replace('/', os.sep)}",
        "preflight_report": "docs/reports/stageF_dual_lane_preflight.md",
    }
    write_json(REPORTS / "stageF_dual_lane_cpu_worker_launch.json", launch)
    md = f"""# Stage F dual-lane CPU worker launch

- Timestamp: {launch['timestamp']}
- Status: **{launch['status']}**
- Worker PID: `{launch['worker_pid']}`
- Comparable root: `{launch['comparable_root']}`
- Production root: `{launch['production_root']}`
- Status JSON: `{launch['status_json']}`
- Worker stdout: `{launch['stdout']}`
- Worker stderr: `{launch['stderr']}`

The worker is currently in the smoke gate. It will launch production only after both CPU zhi=200 smokes complete clean.

Monitor:

```powershell
{launch['monitor_command']}
```
"""
    write_text(REPORTS / "stageF_dual_lane_cpu_worker_launch.md", md)
    return launch


def case_config(case: RunCase) -> dict[str, Any]:
    return {
        "case": case.case_key,
        "stage": case.stage,
        "steps": case.steps,
        "data": rel(case.data),
        "data_abs": str(case.data),
        "folder": rel(case.folder),
        "folder_abs": str(case.folder),
    }


def write_root_agent_report(status: dict[str, Any]) -> None:
    smoke_results = status.get("smoke_results", [])
    production_results = status.get("production_results", [])
    eps0000_smoke = next((r for r in smoke_results if "eps0000" in r.get("case", "")), None)
    eps00194_smoke = next((r for r in smoke_results if "eps00194" in r.get("case", "")), None)
    eps0000_prod = next((r for r in production_results if "eps0000" in r.get("case", "")), None)
    eps00194_prod = next((r for r in production_results if "eps00194" in r.get("case", "")), None)
    md = f"""# Stage F dual-lane CPU production / GPU repair handoff

- Timestamp: {now()}
- Status: `{status.get('status')}`
- Worker PID: `{status.get('worker_pid')}`
- Comparable root: `{status.get('comparable_root')}`
- Production root: `{status.get('production_root')}`

## CPU lane

- eps0000 smoke: `{(eps0000_smoke or {}).get('status', 'running_or_not_done')}`, max step `{(eps0000_smoke or {}).get('max_step')}`.
- eps00194 smoke: `{(eps00194_smoke or {}).get('status', 'not_started_or_not_done')}`, max step `{(eps00194_smoke or {}).get('max_step')}`.
- eps0000 production: `{(eps0000_prod or {}).get('status', 'not_started')}`, max step `{(eps0000_prod or {}).get('max_step')}`.
- eps00194 production: `{(eps00194_prod or {}).get('status', 'not_started')}`, max step `{(eps00194_prod or {}).get('max_step')}`.
- Analysis: not run until both CPU 50k productions complete clean.

## GPU lane

GPU backend is still not recovered. Existing release, debug, and clean CUDA 12.4 rebuild evidence remains the current blocker; no GPU production was launched.

## Reports

- `docs/reports/stageF_dual_lane_cpu_production_gpu_repair_start.md`
- `docs/reports/stageF_dual_lane_preflight.md`
- `docs/reports/stageF_dual_lane_cpu_setup.md`
- `docs/reports/stageF_dual_lane_cpu_smoke_gate.md`
- `docs/reports/stageF_dual_lane_cpu_production_status.md`
- `docs/reports/stageF_parallel_gpu_repair_status.md`
"""
    write_text(REPO / "agent_report_stageF_dual_lane_cpu_production_gpu_repair.md", md)


def write_initial_root_report(launch: dict[str, Any]) -> None:
    status = {
        "timestamp": now(),
        "status": launch["status"],
        "worker_pid": launch["worker_pid"],
        "comparable_root": launch["comparable_root"],
        "production_root": launch["production_root"],
        "smoke_results": [],
        "production_results": [],
    }
    write_root_agent_report(status)
    write_smoke_report(status)
    write_production_report({**status, "status": "not_started_smoke_gate_open"})


def validate_script() -> dict[str, Any]:
    py_files = [Path(__file__).resolve()]
    result = run_capture([sys.executable, "-m", "py_compile", *[str(path) for path in py_files]], cwd=REPO, timeout_s=120)
    json_files = [
        REPORTS / "stageF_dual_lane_cpu_production_gpu_repair_start.json",
        REPORTS / "stageF_dual_lane_preflight.json",
        REPORTS / "stageF_dual_lane_cpu_setup.json",
        REPORTS / "stageF_dual_lane_cpu_worker_launch.json",
        REPORTS / "stageF_parallel_gpu_repair_status.json",
    ]
    parsed = []
    for path in json_files:
        if not path.exists():
            parsed.append({"path": rel(path), "exists": False, "ok": False})
            continue
        try:
            json.loads(read_text(path))
            parsed.append({"path": rel(path), "exists": True, "ok": True})
        except json.JSONDecodeError as exc:
            parsed.append({"path": rel(path), "exists": True, "ok": False, "error": str(exc)})
    data = {"timestamp": now(), "py_compile": result, "json_parse": parsed}
    write_json(REPORTS / "stageF_dual_lane_validation.json", data)
    return data


def launch() -> int:
    run_id = RUN_ID
    write_start_report(run_id)
    pre = preflight()
    if not pre["cpu_lane_safe_to_launch"]:
        raise RuntimeError("CPU lane preflight failed: CPU LAMMPS or MPIEXEC missing")
    prepared = prepare_roots(run_id)
    gpu = write_gpu_repair_status()
    launch_info = launch_worker(pre, prepared)
    write_initial_root_report(launch_info)
    validation = validate_script()
    print(
        json.dumps(
            {
                "status": launch_info["status"],
                "worker_pid": launch_info["worker_pid"],
                "status_json": launch_info["status_json"],
                "comparable_root": launch_info["comparable_root"],
                "production_root": launch_info["production_root"],
                "gpu_repair_status": gpu["status"],
                "py_compile_returncode": validation["py_compile"]["returncode"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--worker", type=Path)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    if not args.launch:
        args.launch = True
    return launch()


if __name__ == "__main__":
    raise SystemExit(main())
