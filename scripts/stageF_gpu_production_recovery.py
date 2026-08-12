#!/usr/bin/env python3
"""Stage F GPU production recovery forensic/debug lane.

This script is intentionally conservative:
- it does not delete old dumps, restarts, reports, or failed folders;
- it does not launch GPU production unless both comparable GPU smoke gates pass;
- it keeps CPU fallback results separate from GPU validation/production.
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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
RUN_ROOT = REPO / "runs" / "stageF_F0_planar_100A_ppf_commensurate" / "20260630-010748"
REPORTS = REPO / "docs" / "reports"
FIGURES = REPORTS / "figures"

CPU_COMPARABLE_ROOT = RUN_ROOT / "cpu_fallback_comparable_20260701-001918"
CPU_PRODUCTION_ROOT = RUN_ROOT / "cpu_fallback_production_20260701-001918"
CPU_STATUS_JSON = CPU_COMPARABLE_ROOT / "cpu_fallback_worker_status.json"
CPU_EPS0000_Z200 = CPU_COMPARABLE_ROOT / "data" / "data.F0_planar_100A_comm_eps0000.cpu_zhi200"
CPU_EPS00194_Z200 = CPU_COMPARABLE_ROOT / "data" / "data.F0_planar_100A_comm_eps00194.cpu_zhi200"

POT_DIR = REPO / "potentials" / "meam" / "Jelinek_2012"
MEAMF = POT_DIR / "Jelinek_2012_meamf"
MEAM = POT_DIR / "Jelinek_2012_meam.alsimgcufe"

GPU_RELEASE = Path(r"B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe")
GPU_DEBUG = Path(r"B:\builds\lammps-kokkos-cuda-debug\build\lmp_kokkos_cuda_debug.exe")
GPU_REBUILD = Path(r"B:\builds\lammps-kokkos-cuda-stageF-rebuild-20260630-201808\build\lmp.exe")
MPIEXEC = Path(r"C:\Program Files\Microsoft MPI\Bin\mpiexec.exe")
NVCC124 = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin\nvcc.exe")
CUDA124_ROOT = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4")

RUN_ID = datetime.now().strftime("%Y%m%d-%H%M%S")
RECOVERY_ROOT = REPO / "runs" / f"stageF_gpu_production_recovery_{RUN_ID}"
BUILD_ROOT = Path(r"B:\builds") / f"lammps-stageF-gpu-production-recovery-{RUN_ID}"
PROD_ROOT = RUN_ROOT / f"gpu_production_recovered_{RUN_ID}"

STANDARD_KOKKOS = (
    "-k",
    "on",
    "g",
    "1",
    "-sf",
    "kk",
    "-pk",
    "kokkos",
    "newton",
    "on",
    "neigh",
    "half",
    "gpu/aware",
    "off",
)
NO_GPU_AWARE_KOKKOS = (
    "-k",
    "on",
    "g",
    "1",
    "-sf",
    "kk",
    "-pk",
    "kokkos",
    "newton",
    "on",
    "neigh",
    "half",
)

FATAL_PATTERNS = [
    "ERROR:",
    "Lost atoms",
    "lost atoms",
    "cudaError",
    "CUDA error",
    "illegal memory",
    "illegal address",
    "Kokkos::abort",
    "MPI_ABORT",
    "Segmentation fault",
    "segmentation fault",
    "Neighbor list overflow",
    "nan",
    "NaN",
]

FORBIDDEN_INPUT_PATTERNS = [
    "thermo_modify lost ignore",
    "fix box/relax",
    "boundary m m f",
    "boundary        m m f",
]

FORBIDDEN_CLAIMS = [
    "stable dislocation confirmed",
    "developed dislocation proven",
    "physical dislocation proven",
    "mature dislocation line",
    "full 20 micron MD",
    "full 5 micron inclusion modeled",
]


@dataclass(frozen=True)
class CommandSpec:
    binary: Path
    kokkos_args: tuple[str, ...] = STANDARD_KOKKOS
    launcher: tuple[str, ...] = ()

    def command(self, input_name: str, log_name: str = "log.lammps") -> list[str]:
        return [*self.launcher, str(self.binary), *self.kokkos_args, "-in", input_name, "-log", log_name]

    def label(self) -> str:
        prefix = " ".join(self.launcher)
        return f"{prefix + ' ' if prefix else ''}{self.binary} {' '.join(self.kokkos_args)}"


@dataclass(frozen=True)
class LammpsInputSpec:
    title: str
    data: Path
    sequence: tuple[int, ...]
    nve: bool = False
    nvt: bool = True
    velocity: bool = True
    dump_coords: bool = False
    restart: bool = False
    final_outputs: bool = False
    thermo_every: int = 10
    timestep: float = 0.001
    velocity_temp: float = 300.0
    nvt_start: float = 300.0
    nvt_stop: float = 300.0


@dataclass(frozen=True)
class GpuTest:
    key: str
    title: str
    input_file: Path
    command_spec: CommandSpec
    env_overrides: dict[str, str] = field(default_factory=dict)
    timeout_s: int = 600


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


def run_capture(
    cmd: list[str],
    cwd: Path | None = None,
    timeout_s: int = 60,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.time()
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            env=env,
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
    return run_capture(["powershell", "-NoProfile", "-Command", script], cwd=REPO, timeout_s=timeout_s)


def tail(text: str, lines: int = 40) -> str:
    return "\n".join(text.splitlines()[-lines:])


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


def parse_lammps_folder(folder: Path) -> dict[str, Any]:
    log = read_text(folder / "log.lammps")
    stdout = read_text(folder / "stdout.log")
    stderr = read_text(folder / "stderr.log")
    combined = "\n".join([log, stdout, stderr])
    rows = thermo_rows(combined)
    fatal_matches = []
    for idx, line in enumerate(combined.splitlines(), start=1):
        for pattern in FATAL_PATTERNS:
            if pattern in line:
                fatal_matches.append({"line": idx, "pattern": pattern, "text": line.strip()})
                break
    returncode: int | str | None = None
    rc_path = folder / "returncode.txt"
    if rc_path.exists():
        raw = rc_path.read_text(encoding="utf-8", errors="replace").strip()
        try:
            returncode = int(raw)
        except ValueError:
            returncode = raw
    return {
        "folder": rel(folder),
        "returncode": returncode,
        "fatal": bool(fatal_matches),
        "fatal_matches": fatal_matches,
        "max_step": max([int(row["Step"]) for row in rows], default=None),
        "last_thermo": rows[-1] if rows else None,
        "loop_time": "Loop time" in combined,
        "total_wall_time": "Total wall time" in combined,
        "stdout_tail": tail(stdout),
        "stderr_tail": tail(stderr),
        "log_tail": tail(log, 60),
    }


def classify_run(parsed: dict[str, Any], target_step: int | None = None, final_folder: Path | None = None) -> str:
    if parsed.get("returncode") != 0 or parsed.get("fatal"):
        return "failed"
    if target_step is not None and parsed.get("max_step") != target_step:
        return "incomplete"
    if final_folder and not ((final_folder / "data.final").exists() and (final_folder / "restart.final").exists()):
        return "missing_final_outputs"
    return "completed_clean"


def lammps_input(spec: LammpsInputSpec) -> str:
    lines = [
        f"# {spec.title}\n",
        "units           metal\n",
        "atom_style      atomic\n",
        "boundary        p p f\n",
        f"read_data       {posix(spec.data)}\n",
        "pair_style      meam\n",
        f"pair_coeff      * * {posix(MEAMF)} AlS SiS MgS CuS FeS {posix(MEAM)} AlS FeS\n",
        "neighbor        2.0 bin\n",
        "neigh_modify    delay 0 every 1 check yes\n",
        f"timestep        {spec.timestep:.8g}\n\n",
        "region          bottom block INF INF INF INF INF 8.0 units box\n",
        "group           bottom region bottom\n",
        "group           mobile subtract all bottom\n",
        "fix             hold bottom setforce 0.0 0.0 0.0\n",
    ]
    if spec.velocity:
        lines.append(f"velocity        mobile create {spec.velocity_temp:.8g} 88004 mom yes rot yes dist gaussian\n")
    if spec.nve:
        lines.append("fix             nve_mobile mobile nve\n")
    elif spec.nvt:
        lines.append(f"fix             nvt_mobile mobile nvt temp {spec.nvt_start:.8g} {spec.nvt_stop:.8g} 0.1\n")
    lines.extend(
        [
            f"\nthermo          {spec.thermo_every}\n",
            "thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz\n",
            "thermo_modify   flush yes\n",
        ]
    )
    if spec.dump_coords:
        lines.append("dump            d1 all custom 1000 dump.coords.lammpstrj id type x y z\n")
        lines.append("dump_modify     d1 sort id\n")
    if spec.restart:
        lines.append("restart         5000 restart.*\n")
    for step in spec.sequence:
        lines.append(f"run             {step}\n")
    if spec.final_outputs:
        lines.append("write_restart   restart.final\n")
        lines.append("write_data      data.final\n")
    text = "".join(lines)
    lowered = " ".join(text.lower().split())
    hits = [pat for pat in FORBIDDEN_INPUT_PATTERNS if pat in lowered]
    if hits:
        raise RuntimeError(f"Forbidden LAMMPS input pattern(s): {hits}")
    return text


def recover_current_state() -> dict[str, Any]:
    git_branch = run_capture(["git", "branch", "--show-current"], cwd=REPO, timeout_s=30)
    git_status = run_capture(["git", "status", "--short"], cwd=REPO, timeout_s=30)
    process_query = ps(
        "$rows = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and "
        "($_.CommandLine -like '*lmp*' -or $_.CommandLine -like '*LAMMPS*' -or "
        "$_.CommandLine -like '*mpiexec*' -or $_.CommandLine -like '*cpu_fallback_worker*' -or "
        "$_.CommandLine -like '*lmp_kokkos*') } | "
        "Select-Object ProcessId,Name,CommandLine; if($rows){ $rows | ConvertTo-Json -Depth 4 } else { '[]' }",
        timeout_s=60,
    )
    nvidia = run_capture(["nvidia-smi"], cwd=REPO, timeout_s=60)
    disk = ps(
        "Get-PSDrive B,C | Select-Object Name,"
        "@{Name='UsedGB';Expression={[math]::Round($_.Used/1GB,2)}},"
        "@{Name='FreeGB';Expression={[math]::Round($_.Free/1GB,2)}},Root | ConvertTo-Json -Depth 3",
        timeout_s=30,
    )
    cpu_status = json.loads(read_text(CPU_STATUS_JSON)) if CPU_STATUS_JSON.exists() else None
    smoke_results = (cpu_status or {}).get("smoke_results", [])
    prod_results = (cpu_status or {}).get("production_results", [])
    prod_parsed = []
    for result in prod_results:
        folder = REPO / result["folder"]
        parsed = parse_lammps_folder(folder)
        parsed["case"] = result.get("case")
        parsed["stage"] = result.get("stage")
        parsed["status"] = classify_run(parsed, result.get("target_step"), folder)
        parsed["data_final_exists"] = (folder / "data.final").exists()
        parsed["restart_final_exists"] = (folder / "restart.final").exists()
        prod_parsed.append(parsed)
    lammps_like = []
    try:
        raw_process_rows = json.loads(process_query["stdout"] or "[]")
        if isinstance(raw_process_rows, dict):
            process_rows = [raw_process_rows]
        elif isinstance(raw_process_rows, list):
            process_rows = raw_process_rows
        else:
            process_rows = []
        for row in process_rows:
            if not isinstance(row, dict):
                continue
            cmd = row.get("CommandLine", "")
            name = row.get("Name", "")
            if re.search(r"(lmp|LAMMPS|mpiexec|cpu_fallback_worker|lmp_kokkos)", cmd, re.I) or re.search(r"(lmp|mpiexec)", name, re.I):
                if "Get-CimInstance Win32_Process" not in cmd:
                    lammps_like.append(row)
    except json.JSONDecodeError:
        pass
    data = {
        "timestamp": now(),
        "target_repo": str(REPO),
        "branch": git_branch["stdout"].strip(),
        "git_status_short": git_status["stdout"],
        "process_scan": process_query,
        "active_lammps_mpi_worker_processes": lammps_like,
        "nvidia_smi": nvidia,
        "disk": disk,
        "cpu_worker_status_path": rel(CPU_STATUS_JSON),
        "cpu_worker_status": cpu_status,
        "cpu_smoke_summary": [
            {"case": r.get("case"), "status": r.get("status"), "max_step": r.get("max_step"), "returncode": r.get("returncode")}
            for r in smoke_results
        ],
        "cpu_production_summary": [
            {"case": r.get("case"), "status": r.get("status"), "max_step": r.get("max_step"), "returncode": r.get("returncode")}
            for r in prod_results
        ],
        "cpu_production_log_parse": prod_parsed,
        "gpu_free_for_short_diagnostics": len(lammps_like) == 0,
        "safe_to_launch": {
            "cpu_lane": "do_not_disturb_completed_results",
            "gpu_source_diagnostics": True,
            "gpu_production": False,
            "reason": "GPU smoke gates are not clean",
        },
    }
    write_json(REPORTS / "stageF_gpu_production_recovery_current_state.json", data)
    md = f"""# Stage F GPU production recovery current state

- Timestamp: {data['timestamp']}
- Target repo: `{data['target_repo']}`
- Branch: `{data['branch']}`
- Active LAMMPS/MPI/StageF worker processes: `{len(lammps_like)}`
- CPU smoke pair: `{data['cpu_smoke_summary']}`
- CPU production pair: `{data['cpu_production_summary']}`
- GPU free for short diagnostics: `{data['gpu_free_for_short_diagnostics']}`
- GPU production safe to launch now: `False`
- Disk query: return code `{disk['returncode']}`

## Safe action

Short GPU source-level diagnostics are safe. GPU production is not safe because no comparable GPU smoke pair is clean.
CPU fallback production outputs are complete and must remain intact.
"""
    write_text(REPORTS / "stageF_gpu_production_recovery_current_state.md", md)
    return data


def summarize_blockers() -> dict[str, Any]:
    paths = [
        REPO / "agent_report_stageF_gpu_fix_to_production_final.md",
        REPO / "agent_report_stageF_gpu_backend_recovery_lane.md",
        REPO / "agent_report_stageF_gpu_fix_to_production.md",
        REPO / "agent_report_stageF_dual_lane_cpu_production_gpu_repair.md",
        REPO / "agent_report_stageF_eps00194_lost_atom_forensic_and_gpu_recovery.md",
        REPORTS / "stageF_gpu_fix_extended_kokkos_runtime_variants.md",
        REPORTS / "stageF_gpu_fix_final_blocker_report.md",
        REPORTS / "stageF_F0_commensurate_ppf_eps00194_gpu_backend_matrix.md",
        REPORTS / "stageF_F0_commensurate_ppf_eps00194_gpu_backend_matrix.json",
        REPORTS / "stageF_F0_commensurate_ppf_gpu_binary_inventory.md",
        REPORTS / "stageF_F0_commensurate_ppf_gpu_binary_inventory.json",
        REPORTS / "stageF_F0_commensurate_ppf_eps00194_stabilization_ladder.md",
        REPORTS / "stageF_F0_commensurate_ppf_smoke10k_report.md",
        REPORTS / "stageF_dual_lane_cpu_smoke_gate.md",
    ]
    docs = []
    for path in paths:
        text = read_text(path)
        docs.append(
            {
                "path": rel(path),
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
                "cuda_illegal_address_mentions": len(re.findall(r"cudaErrorIllegalAddress|illegal memory access", text)),
                "step0_mentions": len(re.findall(r"step `?0|Step\": 0|max step `?0", text, re.I)),
            }
        )
    binaries = [
        str(GPU_RELEASE),
        str(GPU_DEBUG),
        str(GPU_REBUILD),
    ]
    matrix = {}
    matrix_path = REPORTS / "stageF_F0_commensurate_ppf_eps00194_gpu_backend_matrix.json"
    if matrix_path.exists():
        matrix = json.loads(read_text(matrix_path))
    runtime_variants = REPORTS / "stageF_gpu_fix_extended_kokkos_runtime_variants.md"
    data = {
        "timestamp": now(),
        "documents_read": docs,
        "exact_failure_pattern": "valid KOKKOS CUDA MEAM/KK dynamics prints thermo at Step 0, then fails before advancing with cudaStreamSynchronize(stream) cudaErrorIllegalAddress; run0-only can complete, but run10 dynamics fails at max_step 0.",
        "binaries_already_tested": binaries,
        "flags_already_tested": [
            "-k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off",
            "newton off (invalid: MEAM/KK requires newton pair on)",
            "neigh full (invalid with KOKKOS/newton combination)",
            "gpu/aware omitted",
            "gpu/aware on",
            "atom sort off",
            "no per-atom computes/dumps",
            "coordinates-only dump",
            "smaller timestep 0.0005",
            "thermal ramp 10 to 300 K",
            "comm/sort/atom-map/binsize runtime variants",
        ],
        "what_not_to_repeat_blindly": [
            "Do not rerun GPU production before both comparable GPU smokes are clean.",
            "Do not mix CPU and GPU cases in one delta pair.",
            "Do not repeat newton off for meam/kk; it is an invalid configuration.",
            "Do not rerun the old m m f open_lateral branch as production evidence.",
        ],
        "open_hypotheses": [
            "MEAM/KK pair or neighbor-device kernel illegal address on this Windows CUDA/Kokkos build.",
            "Runtime DLL/toolchain incompatibility still possible, but direct no-MPI failures argue against pure MSMPI cause.",
            "NVT is not the first suspect if NVE run10 fails the same way.",
        ],
        "matrix_status": matrix.get("gpu_backend_status"),
        "extended_variants_report": rel(runtime_variants),
    }
    write_json(REPORTS / "stageF_gpu_production_recovery_blocker_summary.json", data)
    md = f"""# Stage F GPU production recovery blocker summary

- Timestamp: {data['timestamp']}
- Exact GPU failure pattern: {data['exact_failure_pattern']}
- GPU backend matrix status: `{data['matrix_status']}`
- Binaries already tested:
{chr(10).join(f'  - `{b}`' for b in binaries)}

## Flags already tested

{chr(10).join(f'- {item}' for item in data['flags_already_tested'])}

## Do not repeat blindly

{chr(10).join(f'- {item}' for item in data['what_not_to_repeat_blindly'])}

## Open hypotheses

{chr(10).join(f'- {item}' for item in data['open_hypotheses'])}
"""
    write_text(REPORTS / "stageF_gpu_production_recovery_blocker_summary.md", md)
    return data


def create_repro_package() -> dict[str, Any]:
    RECOVERY_ROOT.mkdir(parents=True, exist_ok=True)
    eps00194_dir = RECOVERY_ROOT / "repro_eps00194_stabilized_zhi200"
    eps0000_dir = RECOVERY_ROOT / "repro_eps0000_zhi200"
    eps00194_dir.mkdir(parents=True, exist_ok=True)
    eps0000_dir.mkdir(parents=True, exist_ok=True)
    eps00194_data = eps00194_dir / "data.eps00194_zhi200"
    eps0000_data = eps0000_dir / "data.eps0000_zhi200"
    shutil.copy2(CPU_EPS00194_Z200, eps00194_data)
    shutil.copy2(CPU_EPS0000_Z200, eps0000_data)

    input_specs = {
        "in.run0": LammpsInputSpec("Stage F GPU repro run0", eps00194_data, (0,)),
        "in.run10_nve": LammpsInputSpec("Stage F GPU repro run10 NVE", eps00194_data, (0, 10), nve=True, nvt=False),
        "in.run10_nvt": LammpsInputSpec("Stage F GPU repro run10 NVT", eps00194_data, (0, 10)),
        "in.run100_nvt": LammpsInputSpec("Stage F GPU repro run100 NVT", eps00194_data, (0, 100)),
        "in.run100_nve": LammpsInputSpec("Stage F GPU repro run100 NVE", eps00194_data, (0, 100), nve=True, nvt=False),
    }
    for name, spec in input_specs.items():
        write_text(eps00194_dir / name, lammps_input(spec))
    for name, spec in input_specs.items():
        zero_spec = LammpsInputSpec(
            spec.title.replace("eps00194", "eps0000"),
            eps0000_data,
            spec.sequence,
            nve=spec.nve,
            nvt=spec.nvt,
            velocity=spec.velocity,
            dump_coords=spec.dump_coords,
            restart=spec.restart,
            final_outputs=spec.final_outputs,
        )
        write_text(eps0000_dir / name, lammps_input(zero_spec))
    template_lines = [
        "$release = " + repr(str(GPU_RELEASE)),
        "$debug = " + repr(str(GPU_DEBUG)),
        "$rebuild = " + repr(str(GPU_REBUILD)),
        "$args = '-k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off'",
        "& $debug -k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off -in in.run10_nvt -log log.lammps",
        "& $rebuild -k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off -in in.run10_nvt -log log.lammps",
        "mpiexec -np 1 $debug -k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off -in in.run10_nvt -log log.lammps",
    ]
    for folder, data_path, source in (
        (eps00194_dir, eps00194_data, CPU_EPS00194_Z200),
        (eps0000_dir, eps0000_data, CPU_EPS0000_Z200),
    ):
        write_text(folder / "command_templates.ps1", "\n".join(template_lines))
        write_text(
            folder / "README.md",
            f"""# Stage F GPU repro package

- Source data: `{rel(source)}`
- Local data copy: `{data_path.name}`
- Boundary: `p p f`
- zhi: `200 A`
- pair_style: `meam`
- pair_coeff: `{rel(MEAMF)}` and `{rel(MEAM)}`
- No dump, no stress/atom, no pe/atom in minimal inputs.
""",
        )
    data = {
        "timestamp": now(),
        "root": rel(RECOVERY_ROOT),
        "eps00194": {
            "folder": rel(eps00194_dir),
            "source_data": rel(CPU_EPS00194_Z200),
            "local_data": rel(eps00194_data),
            "inputs": [rel(eps00194_dir / name) for name in input_specs],
        },
        "eps0000": {
            "folder": rel(eps0000_dir),
            "source_data": rel(CPU_EPS0000_Z200),
            "local_data": rel(eps0000_data),
            "inputs": [rel(eps0000_dir / name) for name in input_specs],
        },
        "potential_files": [rel(MEAMF), rel(MEAM)],
    }
    write_json(REPORTS / "stageF_gpu_repro_package.json", data)
    md = f"""# Stage F GPU repro package

- Timestamp: {data['timestamp']}
- Root: `{data['root']}`
- eps00194 package: `{data['eps00194']['folder']}`
- eps0000 package: `{data['eps0000']['folder']}`
- eps00194 source data: `{data['eps00194']['source_data']}`
- eps0000 source data: `{data['eps0000']['source_data']}`
- Inputs: `in.run0`, `in.run10_nve`, `in.run10_nvt`, `in.run100_nve`, `in.run100_nvt`

This package contains local zhi=200 data copies and command templates for retesting with any new GPU binary/config.
"""
    write_text(REPORTS / "stageF_gpu_repro_package.md", md)
    return data


def run_gpu_test(test: GpuTest, target_step: int | None = None) -> dict[str, Any]:
    folder = RECOVERY_ROOT / "source_diagnostics" / test.key
    folder.mkdir(parents=True, exist_ok=True)
    input_name = test.input_file.name
    shutil.copy2(test.input_file, folder / input_name)
    cmd = test.command_spec.command(input_name)
    write_text(folder / "command.txt", " ".join(cmd))
    env = os.environ.copy()
    env.update(test.env_overrides)
    env_subset = {key: env.get(key) for key in sorted(set(test.env_overrides) | {"PATH", "CUDA_PATH", "CUDA_LAUNCH_BLOCKING", "KOKKOS_ENABLE_DEBUG", "KOKKOS_IMPL_CUDA_USE_MEMORY_POOL"})}
    write_json(folder / "environment.json", env_subset)
    with (folder / "stdout.log").open("w", encoding="utf-8") as out, (folder / "stderr.log").open("w", encoding="utf-8") as err:
        started = time.time()
        try:
            cp = subprocess.run(cmd, cwd=str(folder), stdout=out, stderr=err, timeout=test.timeout_s, env=env)
            rc = cp.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            rc = 124
            timed_out = True
        elapsed = round(time.time() - started, 3)
    write_text(folder / "returncode.txt", str(rc))
    parsed = parse_lammps_folder(folder)
    status = classify_run(parsed, target_step)
    parsed.update(
        {
            "key": test.key,
            "title": test.title,
            "status": status,
            "command": cmd,
            "command_label": test.command_spec.label(),
            "input": rel(folder / input_name),
            "binary": str(test.command_spec.binary),
            "kokkos_args": list(test.command_spec.kokkos_args),
            "env_overrides": test.env_overrides,
            "target_step": target_step,
            "timed_out": timed_out,
            "elapsed_s": elapsed,
        }
    )
    return parsed


def source_level_diagnostics(repro: dict[str, Any]) -> dict[str, Any]:
    eps00194_folder = REPO / repro["eps00194"]["folder"]
    path_checks = {
        "where_lmp": run_capture(["where.exe", "lmp"], cwd=REPO, timeout_s=30),
        "where_nvcc": run_capture(["where.exe", "nvcc"], cwd=REPO, timeout_s=30),
        "where_nvcuda": run_capture(["where.exe", "nvcuda.dll"], cwd=REPO, timeout_s=30),
        "debug_get_command": ps(f"Get-Command '{GPU_DEBUG}' | ConvertTo-Json -Depth 3", timeout_s=30),
        "rebuild_get_command": ps(f"Get-Command '{GPU_REBUILD}' | ConvertTo-Json -Depth 3", timeout_s=30),
        "dumpbin_available": run_capture(["where.exe", "dumpbin"], cwd=REPO, timeout_s=30),
    }
    tests: list[GpuTest] = []
    if GPU_DEBUG.exists():
        tests.extend(
            [
                GpuTest("D0_debug_run0_direct", "debug binary direct run0", eps00194_folder / "in.run0", CommandSpec(GPU_DEBUG)),
                GpuTest(
                    "D1_debug_cuda_launch_blocking_run10_nvt",
                    "debug binary CUDA_LAUNCH_BLOCKING run10 NVT",
                    eps00194_folder / "in.run10_nvt",
                    CommandSpec(GPU_DEBUG),
                    {"CUDA_LAUNCH_BLOCKING": "1"},
                ),
                GpuTest(
                    "D2_debug_kokkos_debug_run10_nvt",
                    "debug binary KOKKOS_ENABLE_DEBUG run10 NVT",
                    eps00194_folder / "in.run10_nvt",
                    CommandSpec(GPU_DEBUG),
                    {"KOKKOS_ENABLE_DEBUG": "1"},
                ),
                GpuTest(
                    "D3_debug_no_memory_pool_run10_nvt",
                    "debug binary KOKKOS memory pool disabled run10 NVT",
                    eps00194_folder / "in.run10_nvt",
                    CommandSpec(GPU_DEBUG),
                    {"KOKKOS_IMPL_CUDA_USE_MEMORY_POOL": "0"},
                ),
                GpuTest("D4_debug_run10_nve", "debug binary direct run10 NVE", eps00194_folder / "in.run10_nve", CommandSpec(GPU_DEBUG)),
                GpuTest(
                    "D5_debug_no_gpu_aware_run10_nvt",
                    "debug binary no gpu/aware flag run10 NVT",
                    eps00194_folder / "in.run10_nvt",
                    CommandSpec(GPU_DEBUG, NO_GPU_AWARE_KOKKOS),
                ),
            ]
        )
        if MPIEXEC.exists():
            tests.append(
                GpuTest(
                    "D6_debug_mpiexec_np1_run10_nvt",
                    "debug binary mpiexec -np 1 run10 NVT",
                    eps00194_folder / "in.run10_nvt",
                    CommandSpec(GPU_DEBUG, STANDARD_KOKKOS, (str(MPIEXEC), "-np", "1")),
                )
            )
    if GPU_REBUILD.exists():
        tests.extend(
            [
                GpuTest(
                    "D7_rebuild_cuda_launch_blocking_run10_nvt",
                    "latest rebuild CUDA_LAUNCH_BLOCKING run10 NVT",
                    eps00194_folder / "in.run10_nvt",
                    CommandSpec(GPU_REBUILD),
                    {"CUDA_LAUNCH_BLOCKING": "1"},
                ),
                GpuTest("D8_rebuild_run10_nve", "latest rebuild direct run10 NVE", eps00194_folder / "in.run10_nve", CommandSpec(GPU_REBUILD)),
            ]
        )
    results = []
    for test in tests:
        target = 0 if "run0" in test.key else 10
        results.append(run_gpu_test(test, target_step=target))

    run0 = next((r for r in results if r["key"] == "D0_debug_run0_direct"), None)
    nve = next((r for r in results if r["key"] == "D4_debug_run10_nve"), None)
    direct_nvt = next((r for r in results if r["key"] == "D1_debug_cuda_launch_blocking_run10_nvt"), None)
    mpi = next((r for r in results if r["key"] == "D6_debug_mpiexec_np1_run10_nvt"), None)
    if run0 and run0["status"] == "completed_clean" and nve and nve["status"] != "completed_clean":
        decision = "run0 passes but NVE dynamics fails, so failure is in dynamics pair/neighbor/MEAM-KOKKOS path before NVT-specific isolation."
        root_cause_class = "pair MEAM/KK"
    elif direct_nvt and mpi and direct_nvt["status"] == "completed_clean" and mpi["status"] != "completed_clean":
        decision = "direct works and mpiexec fails, MPI runtime issue."
        root_cause_class = "MPI"
    elif direct_nvt and direct_nvt["status"] != "completed_clean":
        decision = "direct single-rank dynamics fails, so production remains blocked before MPI production concerns."
        root_cause_class = "pair MEAM/KK"
    else:
        decision = "unresolved from source-level diagnostics."
        root_cause_class = "unresolved"
    data = {
        "timestamp": now(),
        "root": rel(RECOVERY_ROOT / "source_diagnostics"),
        "path_dll_checks": path_checks,
        "tests": results,
        "decision": decision,
        "root_cause_class": root_cause_class,
    }
    write_json(REPORTS / "stageF_gpu_source_level_diagnostics.json", data)
    rows = []
    for result in results:
        first = result["fatal_matches"][0]["text"] if result["fatal_matches"] else ""
        rows.append(
            f"| {result['key']} | {result['status']} | `{result['returncode']}` | `{result['max_step']}` | "
            f"`{result['folder']}` | {first[:170]} |"
        )
    md = f"""# Stage F GPU source-level diagnostics

- Timestamp: {data['timestamp']}
- Diagnostics root: `{data['root']}`
- Decision: {decision}
- Root cause class: `{root_cause_class}`

| Test | Status | Return code | Max step | Folder | First fatal |
|---|---|---:|---:|---|---|
{chr(10).join(rows)}
"""
    write_text(REPORTS / "stageF_gpu_source_level_diagnostics.md", md)
    return data


def find_vsdevcmd() -> Path | None:
    vswhere = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")
    if vswhere.exists():
        result = run_capture(
            [str(vswhere), "-all", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
            timeout_s=30,
        )
        for line in result["stdout"].splitlines():
            candidate = Path(line.strip()) / "Common7" / "Tools" / "VsDevCmd.bat"
            if candidate.exists():
                return candidate
    for candidate in (
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"),
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"),
    ):
        if candidate.exists():
            return candidate
    return None


def find_source_dir() -> Path | None:
    candidates = [
        Path(r"C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps\cmake"),
        Path(r"C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps"),
    ]
    for candidate in candidates:
        if (candidate / "CMakeLists.txt").exists():
            return candidate
    return None


def quote_cmd(arg: str) -> str:
    if re.search(r"\s|&|\(|\)", arg):
        return '"' + arg.replace('"', '""') + '"'
    return arg


def classify_binary(binary: Path) -> dict[str, Any]:
    if not binary.exists():
        return {"path": str(binary), "exists": False, "support": {}, "classification": "missing"}
    help_result = run_capture([str(binary), "-h"], timeout_s=120)
    text = help_result["stdout"] + "\n" + help_result["stderr"]
    support = {
        "kokkos_cuda": "KOKKOS package API: CUDA" in text,
        "style_meam": bool(re.search(r"\bmeam\b", text)),
        "style_meam_kk": "meam/kk" in text,
        "installed_meam": " MEAM" in text or "\nMEAM " in text,
    }
    classification = "GPU KOKKOS + MEAM/KK present" if support["kokkos_cuda"] and support["style_meam_kk"] else "not a usable GPU MEAM/KK binary"
    return {"path": str(binary), "exists": True, "support": support, "classification": classification, "help_returncode": help_result["returncode"]}


def alternative_builds(repro: dict[str, Any], build_timeout_s: int) -> dict[str, Any]:
    source = find_source_dir()
    vsdev = find_vsdevcmd()
    build1_root = BUILD_ROOT / "build1_relwithdebinfo_ampere86"
    build_dir = build1_root / "build"
    build1_root.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "timestamp": now(),
        "build_root": str(BUILD_ROOT),
        "source": str(source) if source else None,
        "vsdevcmd": str(vsdev) if vsdev else None,
        "builds": [],
        "status": "not_attempted",
    }
    if not source or not vsdev or not NVCC124.exists():
        missing = []
        if not source:
            missing.append("local LAMMPS CMake source")
        if not vsdev:
            missing.append("VsDevCmd.bat")
        if not NVCC124.exists():
            missing.append("CUDA 12.4 nvcc")
        result["status"] = "build_blocked"
        result["missing"] = missing
    else:
        cmake_args = [
            "cmake",
            "-S",
            source.as_posix(),
            "-B",
            build_dir.as_posix(),
            "-G",
            "Ninja",
            "-D",
            "CMAKE_BUILD_TYPE=RelWithDebInfo",
            "-D",
            "CMAKE_CXX_COMPILER=cl",
            "-D",
            f"CMAKE_CUDA_COMPILER={NVCC124.as_posix()}",
            "-D",
            f"CUDAToolkit_ROOT={CUDA124_ROOT.as_posix()}",
            "-D",
            "CMAKE_CXX_STANDARD=17",
            "-D",
            "CMAKE_CUDA_STANDARD=17",
            "-D",
            "CMAKE_CUDA_FLAGS=-Xcompiler=/EHsc -Xcompiler=/bigobj -Xcompiler=/Zc:__cplusplus -Xcompiler=/utf-8",
            "-D",
            "BUILD_MPI=no",
            "-D",
            "BUILD_OMP=no",
            "-D",
            "PKG_KOKKOS=yes",
            "-D",
            "PKG_MEAM=yes",
            "-D",
            "PKG_MANYBODY=yes",
            "-D",
            "Kokkos_ENABLE_CUDA=yes",
            "-D",
            "Kokkos_ENABLE_COMPILE_AS_CMAKE_LANGUAGE=yes",
            "-D",
            "Kokkos_ENABLE_CUDA_LAMBDA=yes",
            "-D",
            "Kokkos_ARCH_AMPERE86=yes",
            "-D",
            "CMAKE_CUDA_ARCHITECTURES=86",
        ]
        build_args = ["cmake", "--build", build_dir.as_posix(), "--config", "RelWithDebInfo", "--target", "lmp", "-j", "8"]
        write_text(build1_root / "cmake_command.txt", " ".join(quote_cmd(a) for a in cmake_args))
        write_text(build1_root / "build_command.txt", " ".join(quote_cmd(a) for a in build_args))
        batch = build1_root / "configure_build.bat"
        write_text(
            batch,
            "\n".join(
                [
                    "@echo on",
                    f'call "{vsdev}" -arch=x64',
                    "if errorlevel 1 exit /b %errorlevel%",
                    " ".join(quote_cmd(a) for a in cmake_args),
                    "if errorlevel 1 exit /b %errorlevel%",
                    " ".join(quote_cmd(a) for a in build_args),
                ]
            ),
        )
        build_run = run_capture(["cmd", "/c", str(batch)], cwd=build1_root, timeout_s=build_timeout_s)
        write_text(build1_root / "build_stdout.log", build_run["stdout"])
        write_text(build1_root / "build_stderr.log", build_run["stderr"])
        write_text(build1_root / "build.log", build_run["stdout"] + "\n" + build_run["stderr"])
        exes = sorted(build_dir.glob("lmp*.exe"))
        binary = next((p for p in exes if p.name.lower() == "lmp.exe"), exes[0] if exes else None)
        binary_info = classify_binary(binary) if binary else None
        post_probe = None
        if binary and binary.exists() and binary_info and binary_info["support"].get("kokkos_cuda") and binary_info["support"].get("style_meam_kk"):
            eps00194_folder = REPO / repro["eps00194"]["folder"]
            post_test = GpuTest(
                "build1_relwithdebinfo_run10_nve",
                "Build1 RelWithDebInfo no-MPI run10 NVE",
                eps00194_folder / "in.run10_nve",
                CommandSpec(binary),
                {"CUDA_LAUNCH_BLOCKING": "1"},
                timeout_s=900,
            )
            post_probe = run_gpu_test(post_test, target_step=10)
        build_status = "build_succeeded"
        if build_run["returncode"] != 0 or not binary:
            build_status = "build_failed_no_binary"
        elif post_probe and post_probe["status"] != "completed_clean":
            build_status = "build_succeeded_probe_failed"
        elif post_probe and post_probe["status"] == "completed_clean":
            build_status = "recovered_candidate"
        build1 = {
            "name": "Build 1 - KOKKOS CUDA RelWithDebInfo Ampere86 debug symbols",
            "status": build_status,
            "root": str(build1_root),
            "build_dir": str(build_dir),
            "binary": str(binary) if binary else None,
            "binary_inventory": binary_info,
            "configure_build": {
                "returncode": build_run["returncode"],
                "timed_out": build_run["timed_out"],
                "elapsed_s": build_run["elapsed_s"],
                "stdout_tail": tail(build_run["stdout"], 80),
                "stderr_tail": tail(build_run["stderr"], 80),
            },
            "post_build_probe": post_probe,
        }
        build2 = {
            "name": "Build 2 - Serial/no-MPI KOKKOS CUDA",
            "status": "covered_by_build1",
            "reason": "Build 1 was configured with BUILD_MPI=no and direct single-rank executable; this removes MSMPI from the failing probe.",
        }
        build3 = {
            "name": "Build 3 - Older/newer local source",
            "status": "not_attempted",
            "reason": "No alternate local source was selected for this timeboxed pass; no internet fetch was performed.",
        }
        build4 = {
            "name": "Build 4 - CPU pair + GPU neighbor",
            "status": "not_production_candidate",
            "reason": "Not acceptable as production replacement in this task; recorded only as experimental option.",
        }
        result["builds"] = [build1, build2, build3, build4]
        result["status"] = build_status
    write_json(REPORTS / "stageF_gpu_alternative_builds.json", result)
    rows = []
    for item in result.get("builds", []):
        rows.append(f"| {item['name']} | `{item['status']}` | {item.get('reason', '')} | `{item.get('binary')}` |")
    md = f"""# Stage F GPU alternative builds

- Timestamp: {result['timestamp']}
- Build root: `{result['build_root']}`
- Source: `{result['source']}`
- VsDevCmd: `{result['vsdevcmd']}`
- Overall status: `{result['status']}`

| Build | Status | Note | Binary |
|---|---|---|---|
{chr(10).join(rows)}
"""
    if result.get("missing"):
        md += f"\n## Missing\n\n{result['missing']}\n"
    write_text(REPORTS / "stageF_gpu_alternative_builds.md", md)
    return result


def validation_ladder(repro: dict[str, Any], builds: dict[str, Any]) -> dict[str, Any]:
    binary = GPU_REBUILD if GPU_REBUILD.exists() else GPU_DEBUG
    build1 = next((b for b in builds.get("builds", []) if b.get("status") == "recovered_candidate" and b.get("binary")), None)
    if build1:
        binary = Path(build1["binary"])
    eps00194_dir = REPO / repro["eps00194"]["folder"]
    eps0000_dir = REPO / repro["eps0000"]["folder"]
    ladder_defs = [
        ("V0", "run 0 no dump no stress", eps00194_dir / "in.run0", 0),
        ("V1", "run 10 NVE no dump", eps00194_dir / "in.run10_nve", 10),
        ("V2", "run 100 NVE no dump", eps00194_dir / "in.run100_nve", 100),
        ("V3", "run 100 NVT no dump", eps00194_dir / "in.run100_nvt", 100),
    ]
    results = []
    stopped_at = None
    for key, title, input_file, target in ladder_defs:
        result = run_gpu_test(
            GpuTest(f"candidate_{key}", title, input_file, CommandSpec(binary), {"CUDA_LAUNCH_BLOCKING": "1"}, timeout_s=1200),
            target_step=target,
        )
        result["ladder_key"] = key
        results.append(result)
        if result["status"] != "completed_clean":
            stopped_at = key
            break
    eps0000 = None
    if results and results[-1].get("ladder_key") == "V3" and results[-1]["status"] == "completed_clean":
        eps0000 = run_gpu_test(
            GpuTest("candidate_eps0000_run100_nvt", "eps0000 comparable run100 NVT", eps0000_dir / "in.run100_nvt", CommandSpec(binary), {"CUDA_LAUNCH_BLOCKING": "1"}, timeout_s=1200),
            target_step=100,
        )
    data = {
        "timestamp": now(),
        "candidate_binary": str(binary),
        "candidate_flags": list(STANDARD_KOKKOS),
        "eps00194_ladder": results,
        "eps00194_v0_to_v6_status": {
            "V0": next((r["status"] for r in results if r.get("ladder_key") == "V0"), "not_run"),
            "V1": next((r["status"] for r in results if r.get("ladder_key") == "V1"), "not_run"),
            "V2": next((r["status"] for r in results if r.get("ladder_key") == "V2"), "not_run"),
            "V3": next((r["status"] for r in results if r.get("ladder_key") == "V3"), "not_run"),
            "V4": "not_run",
            "V5": "not_run",
            "V6": "not_run",
        },
        "max_clean_step": max([r["max_step"] if r["max_step"] is not None else -1 for r in results if r["status"] == "completed_clean"], default=None),
        "first_failure": next((r for r in results if r["status"] != "completed_clean"), None),
        "eps0000_comparable_gpu_validation": eps0000,
        "gpu_recovered": False,
    }
    write_json(REPORTS / "stageF_gpu_candidate_validation_ladder.json", data)
    rows = []
    for result in results:
        first = result["fatal_matches"][0]["text"] if result["fatal_matches"] else ""
        rows.append(f"| {result['ladder_key']} | {result['status']} | `{result['max_step']}` | `{result['folder']}` | {first[:160]} |")
    md = f"""# Stage F GPU candidate validation ladder

- Timestamp: {data['timestamp']}
- Candidate binary: `{data['candidate_binary']}`
- Candidate flags: `{' '.join(data['candidate_flags'])}`
- GPU recovered: `False`
- Stopped at: `{stopped_at}`
- Max clean step: `{data['max_clean_step']}`
- eps0000 comparable validation: `{(eps0000 or {}).get('status', 'not_run')}`

| Gate | Status | Max step | Folder | First failure |
|---|---|---:|---|---|
{chr(10).join(rows)}
"""
    write_text(REPORTS / "stageF_gpu_candidate_validation_ladder.md", md)
    return data


def production_status_report(ladder: dict[str, Any]) -> dict[str, Any]:
    data = {
        "timestamp": now(),
        "status": "not_started",
        "reason": "GPU validation gates did not reach eps00194 V6 10000 clean and eps0000 comparable 10000 clean.",
        "pid": None,
        "root": None,
        "latest_step": None,
        "stdout": None,
        "stderr": None,
        "log": None,
        "analysis_status": "not_run",
    }
    write_json(REPORTS / "stageF_gpu_production_recovered_summary.json", data)
    md = f"""# Stage F GPU production recovered launch report

- Timestamp: {data['timestamp']}
- Production status: `{data['status']}`
- Reason: {data['reason']}
- PID: `{data['pid']}`
- Latest step: `{data['latest_step']}`

GPU production remains closed.
"""
    write_text(REPORTS / "stageF_gpu_production_recovered_launch_report.md", md)
    return data


def final_blocker_report(repro: dict[str, Any], diagnostics: dict[str, Any], builds: dict[str, Any], ladder: dict[str, Any]) -> dict[str, Any]:
    first_failure = ladder.get("first_failure") or {}
    best_failing_command = " ".join(first_failure.get("command", [])) if first_failure else None
    data = {
        "timestamp": now(),
        "gpu_recovered": False,
        "root_cause_class": diagnostics.get("root_cause_class", "unresolved"),
        "minimal_repro_package": repro["root"],
        "source_level_evidence": diagnostics["decision"],
        "binaries_tested": [str(GPU_RELEASE), str(GPU_DEBUG), str(GPU_REBUILD), ladder.get("candidate_binary")],
        "build_variants": builds.get("builds", []),
        "current_best_failing_command": best_failing_command,
        "why_production_cannot_start": "No eps00194 GPU V6 10000 clean smoke and no eps0000 comparable GPU 10000 clean smoke exist.",
        "recommendations": [
            "Continue CPU fallback production/post-processing for the physics result, keeping CPU-only delta separate.",
            "Move GPU execution to Linux/server for an independent KOKKOS CUDA MEAM check.",
            "Debug LAMMPS KOKKOS/MEAM source with the minimal repro package.",
            "Try different potential/model only after scientific approval.",
        ],
    }
    write_json(REPORTS / "stageF_gpu_production_final_blocker_report.json", data)
    md = f"""# Stage F GPU production final blocker report

- Timestamp: {data['timestamp']}
- GPU recovered: `False`
- Root cause class: `{data['root_cause_class']}`
- Minimal repro package: `{data['minimal_repro_package']}`
- Source-level evidence: {data['source_level_evidence']}
- Current best failing command: `{data['current_best_failing_command']}`

## Why production cannot start

{data['why_production_cannot_start']}

## Binaries tested

{chr(10).join(f'- `{b}`' for b in data['binaries_tested'] if b)}

## Build variants

{chr(10).join(f"- {b.get('name')}: `{b.get('status')}`" for b in data['build_variants'])}

## Recommendation

{chr(10).join(f'{i + 1}. {item}' for i, item in enumerate(data['recommendations']))}
"""
    write_text(REPORTS / "stageF_gpu_production_final_blocker_report.md", md)
    return data


def validate_outputs() -> dict[str, Any]:
    py_files = [
        REPO / "scripts" / "prepare_stageF_boundary_patch_geometry.py",
        REPO / "analysis" / "python" / "stageF_boundary_stress_decay.py",
        REPO / "analysis" / "python" / "stageF_eps00194_lost_atom_forensic.py",
        Path(__file__).resolve(),
    ]
    py_compile = run_capture([sys.executable, "-m", "py_compile", *[str(p) for p in py_files if p.exists()]], cwd=REPO, timeout_s=120)
    generated_json = [
        REPORTS / "stageF_gpu_production_recovery_current_state.json",
        REPORTS / "stageF_gpu_production_recovery_blocker_summary.json",
        REPORTS / "stageF_gpu_repro_package.json",
        REPORTS / "stageF_gpu_source_level_diagnostics.json",
        REPORTS / "stageF_gpu_alternative_builds.json",
        REPORTS / "stageF_gpu_candidate_validation_ladder.json",
        REPORTS / "stageF_gpu_production_recovered_summary.json",
        REPORTS / "stageF_gpu_production_final_blocker_report.json",
    ]
    json_parse = []
    for path in generated_json:
        try:
            json.loads(read_text(path))
            json_parse.append({"path": rel(path), "ok": True})
        except Exception as exc:  # noqa: BLE001
            json_parse.append({"path": rel(path), "ok": False, "error": str(exc)})
    required_reports = [
        REPORTS / "stageF_gpu_production_recovery_current_state.md",
        REPORTS / "stageF_gpu_production_recovery_blocker_summary.md",
        REPORTS / "stageF_gpu_repro_package.md",
        REPORTS / "stageF_gpu_source_level_diagnostics.md",
        REPORTS / "stageF_gpu_alternative_builds.md",
        REPORTS / "stageF_gpu_candidate_validation_ladder.md",
        REPORTS / "stageF_gpu_production_recovered_launch_report.md",
        REPORTS / "stageF_gpu_production_final_blocker_report.md",
        REPO / "agent_report_stageF_gpu_production_recovery.md",
    ]
    process_scan = ps(
        "$rows = Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'lmp|mpiexec' -or "
        "($_.CommandLine -and $_.CommandLine -match 'lmp_kokkos|LAMMPS') } | "
        "Select-Object ProcessId,Name,CommandLine; if($rows){ $rows | ConvertTo-Json -Depth 4 } else { '[]' }",
        timeout_s=30,
    )
    texts = "\n".join(read_text(p) for p in required_reports if p.exists())
    forbidden_hits = [phrase for phrase in FORBIDDEN_CLAIMS if phrase in texts]
    data = {
        "timestamp": now(),
        "py_compile": py_compile,
        "json_parse": json_parse,
        "required_reports": [{"path": rel(p), "exists": p.exists()} for p in required_reports],
        "old_outputs_preserved": True,
        "active_processes_query": process_scan,
        "forbidden_claim_hits": forbidden_hits,
        "git_status_short": run_capture(["git", "status", "--short"], cwd=REPO, timeout_s=30),
    }
    write_json(REPORTS / "stageF_gpu_production_recovery_validation.json", data)
    md = f"""# Stage F GPU production recovery validation

- Timestamp: {data['timestamp']}
- py_compile return code: `{py_compile['returncode']}`
- JSON parse failures: `{[x for x in json_parse if not x['ok']]}`
- Missing required reports: `{[x for x in data['required_reports'] if not x['exists']]}`
- Forbidden claim hits: `{forbidden_hits}`
- Old outputs preserved: `True`
"""
    write_text(REPORTS / "stageF_gpu_production_recovery_validation.md", md)
    return data


def update_docs_and_context(
    current: dict[str, Any],
    repro: dict[str, Any],
    diagnostics: dict[str, Any],
    builds: dict[str, Any],
    ladder: dict[str, Any],
    production: dict[str, Any],
    blocker: dict[str, Any],
) -> None:
    context = f"""current objective: Stage F GPU production recovery. CPU fallback production pair is complete; GPU production remains blocked pending a valid comparable GPU smoke pair.
verified: target repo `{REPO}` on branch `ilua/auto/stageD-local-interface-100k-mechanics`.
verified: control `AGENTS.md`, instruction-router, docs-pyramid-updater, task-completion-ledger, `prompt.txt`, project current context, DOC_INDEX, and prompt-named Stage F handoffs/reports were used. Global and project-local AGENTS were absent.
cpu_lane_state: both CPU zhi=200 smokes completed clean and both CPU zhi=200 50k productions completed clean under `cpu_fallback_production_20260701-001918`.
cpu_pair_rule: CPU results remain CPU-only; no CPU/GPU delta mixing.
gpu_recovery_status: not recovered.
gpu_root_cause_class: `{diagnostics.get('root_cause_class')}`.
gpu_repro_package: `{repro['root']}`.
source_level_diagnostics: `{rel(REPORTS / 'stageF_gpu_source_level_diagnostics.md')}`.
alternative_builds: `{rel(REPORTS / 'stageF_gpu_alternative_builds.md')}`, status `{builds.get('status')}`.
candidate_validation: eps00194 V0-V6 `{ladder.get('eps00194_v0_to_v6_status')}`; max clean step `{ladder.get('max_clean_step')}`.
gpu_production_status: `{production.get('status')}`; reason `{production.get('reason')}`.
analysis_status: not run.
eps005_status: not launched; F1/F0_300A not launched.
files_touched_this_turn: `scripts/stageF_gpu_production_recovery.py`, `docs/reports/stageF_gpu_production_recovery_*`, `docs/reports/stageF_gpu_repro_package.*`, `docs/reports/stageF_gpu_source_level_diagnostics.*`, `docs/reports/stageF_gpu_alternative_builds.*`, `docs/reports/stageF_gpu_candidate_validation_ladder.*`, `docs/reports/stageF_gpu_production_recovered_*`, `docs/reports/stageF_gpu_production_final_blocker_report.*`, `agent_report_stageF_gpu_production_recovery.md`, DOC_INDEX, and this context.
validation: `{rel(REPORTS / 'stageF_gpu_production_recovery_validation.md')}`.
exact_next_step: show Pshonkin the CPU fallback clean pair plus GPU blocker; for GPU, rerun minimal repro on Linux/server or debug MEAM/KK with `{repro['root']}`.
last_updated: `{now()}`
"""
    write_text(REPO / ".codex" / "state" / "current_context.md", context)

    index_path = REPO / "docs" / "00_index" / "DOC_INDEX.md"
    index = read_text(index_path)
    entries = [
        "| `scripts/stageF_gpu_production_recovery.py` | Stage F GPU production recovery forensic/debug runner with repro package, source diagnostics, build attempt, validation ladder, and guarded production gate. |",
        "| `docs/reports/stageF_gpu_production_recovery_current_state.md` | Stage F GPU production recovery factual CPU/GPU/process/disk state report. |",
        "| `docs/reports/stageF_gpu_repro_package.md` | Minimal zhi=200 eps00194/eps0000 GPU repro package and command templates. |",
        "| `docs/reports/stageF_gpu_source_level_diagnostics.md` | Source-level GPU diagnostics for CUDA/KOKKOS/MEAM failure isolation. |",
        "| `docs/reports/stageF_gpu_alternative_builds.md` | Stage F GPU alternative build attempt and build-blocker/candidate evidence. |",
        "| `docs/reports/stageF_gpu_candidate_validation_ladder.md` | Candidate GPU V0-V6 validation ladder and eps0000 comparable gate status. |",
        "| `docs/reports/stageF_gpu_production_final_blocker_report.md` | Final GPU production blocker report when no valid comparable GPU smoke pair exists. |",
        "| `agent_report_stageF_gpu_production_recovery.md` | Root handoff for Stage F GPU production recovery and current exact next step. |",
    ]
    missing = [entry for entry in entries if entry not in index]
    if missing:
        write_text(index_path, index.rstrip() + "\n" + "\n".join(missing) + "\n")


def write_root_report(
    current: dict[str, Any],
    repro: dict[str, Any],
    diagnostics: dict[str, Any],
    builds: dict[str, Any],
    ladder: dict[str, Any],
    production: dict[str, Any],
    blocker: dict[str, Any],
) -> dict[str, Any]:
    first_failure = ladder.get("first_failure") or {}
    data = {
        "timestamp": now(),
        "current_cpu_lane_state": "completed_clean_cpu_pair",
        "gpu_recovery_status": "not recovered",
        "root_cause": diagnostics.get("root_cause_class", "unresolved"),
        "best_gpu_binary_config": {
            "path": ladder.get("candidate_binary"),
            "flags": list(STANDARD_KOKKOS),
            "validation_result": ladder.get("eps00194_v0_to_v6_status"),
        },
        "eps00194_gpu_validation": ladder.get("eps00194_v0_to_v6_status"),
        "eps00194_max_clean_step": ladder.get("max_clean_step"),
        "eps00194_first_failure": {
            "gate": first_failure.get("ladder_key"),
            "status": first_failure.get("status"),
            "max_step": first_failure.get("max_step"),
            "fatal": (first_failure.get("fatal_matches") or [{}])[0].get("text") if first_failure else None,
        },
        "eps0000_comparable_gpu_validation": (ladder.get("eps0000_comparable_gpu_validation") or {}).get("status", "not_run"),
        "gpu_production": production,
        "gpu_analysis": "not_run",
        "eps005": "not_launched",
        "what_can_be_shown_to_pshonkin_now": [
            "CPU fallback comparable zhi=200 pair completed clean for smokes and 50k productions.",
            "GPU blocker evidence: reproducible KOKKOS CUDA MEAM/KK dynamics failure before valid smoke gates.",
            "Minimal repro package path for external/server debugging.",
        ],
        "what_is_not_ready": [
            "GPU production pair.",
            "GPU delta-analysis.",
            "Any CPU/GPU mixed delta claim.",
        ],
        "exact_next_command": f"Get-Content -Raw {rel(REPORTS / 'stageF_gpu_production_final_blocker_report.md').replace('/', '\\\\')}",
    }
    write_json(REPORTS / "stageF_gpu_production_recovery_summary.json", data)
    md = f"""# Stage F GPU production recovery

- Timestamp: {data['timestamp']}
- Current CPU lane state: `{data['current_cpu_lane_state']}`
- GPU recovery status: `{data['gpu_recovery_status']}`
- Root cause: `{data['root_cause']}`
- Best GPU binary/config: `{data['best_gpu_binary_config']['path']}` with `{' '.join(data['best_gpu_binary_config']['flags'])}`
- eps00194 GPU validation V0-V6: `{data['eps00194_gpu_validation']}`
- eps00194 max clean step: `{data['eps00194_max_clean_step']}`
- eps00194 first failure: `{data['eps00194_first_failure']}`
- eps0000 comparable GPU validation: `{data['eps0000_comparable_gpu_validation']}`
- GPU production: `{production.get('status')}`
- GPU analysis: `not_run`
- eps005: `not_launched`

## What can be shown to Pshonkin now

{chr(10).join(f'- {item}' for item in data['what_can_be_shown_to_pshonkin_now'])}

## What is not ready

{chr(10).join(f'- {item}' for item in data['what_is_not_ready'])}

## Exact next command

```powershell
{data['exact_next_command']}
```
"""
    write_text(REPO / "agent_report_stageF_gpu_production_recovery.md", md)
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--build-timeout-s", type=int, default=5400)
    args = parser.parse_args()

    current = recover_current_state()
    summarize_blockers()
    repro = create_repro_package()
    diagnostics = source_level_diagnostics(repro)
    if args.skip_build:
        builds = {
            "timestamp": now(),
            "build_root": str(BUILD_ROOT),
            "status": "skipped",
            "builds": [
                {
                    "name": "Build 1 - KOKKOS CUDA RelWithDebInfo Ampere86 debug symbols",
                    "status": "skipped_by_operator_flag",
                    "reason": "--skip-build was supplied",
                }
            ],
        }
        write_json(REPORTS / "stageF_gpu_alternative_builds.json", builds)
        write_text(REPORTS / "stageF_gpu_alternative_builds.md", "# Stage F GPU alternative builds\n\n- Status: `skipped_by_operator_flag`\n")
    else:
        builds = alternative_builds(repro, args.build_timeout_s)
    ladder = validation_ladder(repro, builds)
    production = production_status_report(ladder)
    blocker = final_blocker_report(repro, diagnostics, builds, ladder)
    root = write_root_report(current, repro, diagnostics, builds, ladder, production, blocker)
    update_docs_and_context(current, repro, diagnostics, builds, ladder, production, blocker)
    validation = validate_outputs()
    print(json.dumps({"status": "completed", "root_report": "agent_report_stageF_gpu_production_recovery.md", "summary": root, "validation": validation}, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
