#!/usr/bin/env python3
"""Stage F stabilized eps00194 GPU backend recovery lane.

This script only runs smoke/diagnostic gates. It does not launch production,
eps005, F1, or F0_300A.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "runs" / "stageF_F0_planar_100A_ppf_commensurate" / "20260630-010748"
EPS00194 = RUN / "F0_planar_100A_comm_eps00194"
EPS0000 = RUN / "F0_planar_100A_comm_eps0000"
REPORTS = REPO / "docs" / "reports"
DIAG_ROOT = EPS00194 / "gpu_backend_diagnostics"

DATA_EPS00194_Z200 = EPS00194 / "debug_fix1_z_headroom_cpu" / "data.F0_planar_100A_comm_eps00194.zheadroom30"
DATA_EPS0000_RELAXED = EPS0000 / "equil" / "data.F0_planar_100A_comm_eps0000.relaxed"
DATA_EPS0000_Z200 = EPS0000 / "smoke_retry_comparable_zhi200_gpu" / "data.F0_planar_100A_comm_eps0000.zheadroom30"

POT_DIR = REPO / "potentials" / "meam" / "Jelinek_2012"
MEAMF = POT_DIR / "Jelinek_2012_meamf"
MEAM = POT_DIR / "Jelinek_2012_meam.alsimgcufe"

GPU_RELEASE = Path(r"B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe")
GPU_DEBUG = Path(r"B:\builds\lammps-kokkos-cuda-debug\build\lmp_kokkos_cuda_debug.exe")
CPU_LMP = Path(r"C:\Users\dille\AppData\Local\LAMMPS 64-bit 22Jul2025-MSMPI\bin\lmp.exe")

FATAL_PATTERNS = [
    "ERROR",
    "Lost atoms",
    "lost atoms",
    "nan",
    "NaN",
    "cudaError",
    "CUDA error",
    "illegal memory",
    "illegal address",
    "segmentation",
    "MPI_ABORT",
    "Neighbor list overflow",
    "Kokkos::abort",
    "Exception",
    "failed",
]


@dataclass(frozen=True)
class CommandSpec:
    binary: Path
    kokkos_args: list[str]

    def command(self, input_name: str = "in.gpu_diag", log_name: str = "log.lammps") -> list[str]:
        return [str(self.binary), *self.kokkos_args, "-in", input_name, "-log", log_name]

    def label(self) -> str:
        return f"{self.binary} {' '.join(self.kokkos_args)}"


@dataclass(frozen=True)
class Diagnostic:
    key: str
    title: str
    folder: str
    command_spec: CommandSpec
    run_sequence: tuple[int, ...] = (0, 10, 90, 900)
    timestep: float = 0.001
    velocity_temp: float = 300.0
    nvt_start: float = 300.0
    nvt_stop: float = 300.0
    nvt: bool = True
    nve: bool = False
    include_pe: bool = False
    include_stress: bool = False
    dump_mode: str = "none"
    restart: bool = False
    atom_sort_off: bool = False
    suffix_off_before_fix: bool = False
    notes: str = ""
    timeout_s: int = 1200
    extra_meta: dict[str, Any] = field(default_factory=dict)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def posix(path: Path) -> str:
    return path.resolve().as_posix()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def run_command(cmd: list[str], cwd: Path | None = None, timeout_s: int = 60) -> dict[str, Any]:
    try:
        cp = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout_s)
        return {"returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr, "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "stdout": exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            "stderr": exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
            "timed_out": True,
        }


def thermo_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cols: list[str] | None = None
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"^Step\s+", s):
            cols = s.split()
            continue
        if not cols or not s:
            continue
        parts = s.split()
        if len(parts) != len(cols) or not re.match(r"^[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$", parts[0]):
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


def parse_run(folder: Path) -> dict[str, Any]:
    log = read_text(folder / "log.lammps")
    stdout = read_text(folder / "stdout.log")
    stderr = read_text(folder / "stderr.log")
    text = "\n".join([log, stdout, stderr])
    rows = thermo_rows(text)
    fatal = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for pattern in FATAL_PATTERNS:
            if pattern in line:
                fatal.append({"line": idx, "pattern": pattern, "text": line.strip()})
                break
    rc = None
    if (folder / "returncode.txt").exists():
        raw = (folder / "returncode.txt").read_text(encoding="utf-8", errors="replace").strip()
        rc = int(raw) if raw else None
    return {
        "folder": rel(folder),
        "returncode": rc,
        "fatal": bool(fatal),
        "fatal_matches": fatal,
        "thermo_rows": rows,
        "max_step": max([int(r["Step"]) for r in rows], default=None),
        "last_thermo": rows[-1] if rows else None,
        "loop_time": "Loop time" in text,
        "total_wall_time": "Total wall time" in text,
        "stdout_tail": "\n".join(stdout.splitlines()[-30:]),
        "stderr_tail": "\n".join(stderr.splitlines()[-30:]),
        "log_tail": "\n".join(log.splitlines()[-50:]),
    }


def style_inventory(help_text: str) -> dict[str, Any]:
    return {
        "lammps_version": next((line.strip() for line in help_text.splitlines() if line.strip().startswith("LAMMPS ")), None),
        "kokkos_cuda": "KOKKOS package API: CUDA" in help_text,
        "kokkos_openmp": "KOKKOS package API: OpenMP" in help_text,
        "gpu_package": "GPU package API:" in help_text,
        "installed_meam": " MEAM" in help_text or "\nMEAM " in help_text,
        "installed_kokkos": "KOKKOS" in help_text,
        "style_meam": bool(re.search(r"\bmeam\b", help_text)),
        "style_meam_kk": "meam/kk" in help_text,
        "style_meam_gpu": "meam/gpu" in help_text,
    }


def classify_binary(info: dict[str, Any]) -> str:
    s = info["support"]
    if s["kokkos_cuda"] and s["installed_meam"] and s["style_meam_kk"]:
        return "GPU KOKKOS + MEAM usable"
    if s["style_meam"] and not s["kokkos_cuda"]:
        return "CPU MEAM usable"
    if info["exists"] and info["help"]["returncode"] == 0:
        return "unknown usable"
    return "broken or missing"


def inventory_binaries() -> dict[str, Any]:
    candidates = []
    seen: set[str] = set()
    for path in (GPU_RELEASE, GPU_DEBUG, CPU_LMP):
        if str(path).lower() not in seen:
            candidates.append(path)
            seen.add(str(path).lower())
    for root in (Path(r"B:\builds"), Path(r"C:\Users\dille\Documents\builds"), Path(r"C:\Users\dille\AppData\Local")):
        if not root.exists():
            continue
        try:
            for path in root.rglob("lmp*.exe"):
                key = str(path).lower()
                if key not in seen:
                    candidates.append(path)
                    seen.add(key)
        except OSError:
            continue

    infos = []
    for path in candidates:
        exists = path.exists()
        help_result = run_command([str(path), "-h"], timeout_s=45) if exists else {"returncode": None, "stdout": "", "stderr": "missing", "timed_out": False}
        support = style_inventory((help_result.get("stdout") or "") + "\n" + (help_result.get("stderr") or ""))
        entry = {
            "path": str(path),
            "exists": exists,
            "length": path.stat().st_size if exists else None,
            "last_write_time": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds") if exists else None,
            "help": {
                "returncode": help_result["returncode"],
                "timed_out": help_result["timed_out"],
                "stderr_tail": "\n".join((help_result.get("stderr") or "").splitlines()[-10:]),
            },
            "support": support,
            "classification": "pending",
        }
        entry["classification"] = classify_binary(entry)
        infos.append(entry)

    nvidia_full = run_command(["nvidia-smi"], timeout_s=30)
    nvidia_query = run_command(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,compute_mode", "--format=csv,noheader"],
        timeout_s=30,
    )
    windows = run_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-ComputerInfo | Select-Object WindowsProductName,WindowsVersion,OsHardwareAbstractionLayer,OsArchitecture | ConvertTo-Json",
        ],
        timeout_s=30,
    )
    result = {
        "timestamp": now(),
        "search_note": "Initial full Get-ChildItem over B: and Documents timed out; inventory uses B:\\builds, Documents\\builds, AppData Local LAMMPS, and explicit known binaries.",
        "binaries": infos,
        "nvidia_smi": {
            "returncode": nvidia_full["returncode"],
            "stdout": nvidia_full["stdout"],
            "stderr": nvidia_full["stderr"],
        },
        "nvidia_query": {
            "returncode": nvidia_query["returncode"],
            "stdout": nvidia_query["stdout"],
            "stderr": nvidia_query["stderr"],
        },
        "windows": {
            "returncode": windows["returncode"],
            "stdout": windows["stdout"],
            "stderr": windows["stderr"],
        },
    }
    write_inventory_reports(result)
    return result


def write_inventory_reports(inv: dict[str, Any]) -> None:
    write_json(REPORTS / "stageF_F0_commensurate_ppf_gpu_binary_inventory.json", inv)
    rows = []
    for b in inv["binaries"]:
        rows.append(
            f"| `{b['path']}` | {b['exists']} | {b['classification']} | "
            f"KOKKOS CUDA={b['support']['kokkos_cuda']} MEAM={b['support']['style_meam']} MEAM/KK={b['support']['style_meam_kk']} |"
        )
    md = f"""# Stage F GPU binary inventory

- Timestamp: {inv['timestamp']}
- Search note: {inv['search_note']}

## GPU environment

```text
{inv['nvidia_smi']['stdout'].strip()}
```

## Windows

```json
{inv['windows']['stdout'].strip()}
```

## Binaries

| Binary | Exists | Classification | Support |
|---|---:|---|---|
{chr(10).join(rows)}
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_gpu_binary_inventory.md", md)


def failed_gpu_retry_summary() -> dict[str, Any]:
    folder = EPS00194 / "smoke_retry_gpu_after_fix"
    parsed = parse_run(folder)
    ladder = json.loads((REPORTS / "stageF_F0_commensurate_ppf_eps00194_stabilization_ladder.json").read_text(encoding="utf-8"))
    gpu = ladder["fixes"]["fix1_z_headroom"]["gpu_smoke_10000"]
    cpu = ladder["fixes"]["fix1_z_headroom"]["cpu_smoke_10000"]
    command = gpu.get("command") or [str(GPU_RELEASE), "-k", "on", "g", "1", "-sf", "kk", "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "off", "-in", "in.smoke_retry_gpu_after_fix", "-log", "log.lammps"]
    return {
        "folder": rel(folder),
        "input": rel(folder / "in.smoke_retry_gpu_after_fix"),
        "command": command,
        "binary": command[0],
        "kokkos_flags": command[1:-4],
        "parsed": parsed,
        "cpu_stabilized_smoke": {
            "status": cpu.get("status"),
            "max_step": cpu.get("max_step"),
            "last_thermo": cpu.get("last_thermo"),
        },
        "failure_point": "after run setup and thermo step 0, before completing the first NVT dynamics step",
    }


def write_lane_start() -> dict[str, Any]:
    failed = failed_gpu_retry_summary()
    md = f"""# Stage F GPU backend lane start

- Timestamp: {now()}
- Failed GPU retry folder: `{failed['folder']}`
- Input file: `{failed['input']}`
- Binary: `{failed['binary']}`
- KOKKOS/package flags: `{' '.join(failed['kokkos_flags'])}`
- Exact command: `{' '.join(failed['command'])}`
- Failure point: {failed['failure_point']}
- Max step: `{failed['parsed']['max_step']}`
- Return code: `{failed['parsed']['returncode']}`
- CPU stabilized 10k clean: `{failed['cpu_stabilized_smoke']['status']}` max step `{failed['cpu_stabilized_smoke']['max_step']}`

## stderr tail

```text
{failed['parsed']['stderr_tail']}
```

## last thermo

```json
{json.dumps(failed['parsed']['last_thermo'], indent=2, ensure_ascii=False)}
```
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_gpu_backend_lane_start.md", md)
    return failed


def base_input(data_path: Path, diag: Diagnostic, folder: Path, final_outputs: bool = False, smoke: bool = False) -> str:
    lines = [
        f"# Stage F GPU backend diagnostic {diag.key}: {diag.title}\n",
        "units           metal\n",
        "atom_style      atomic\n",
        "boundary        p p f\n",
    ]
    if diag.atom_sort_off:
        lines.append("atom_modify     sort 0 0.0\n")
    lines.extend(
        [
            f"read_data       {posix(data_path)}\n",
            "pair_style      meam\n",
            f"pair_coeff      * * {posix(MEAMF)} AlS SiS MgS CuS FeS {posix(MEAM)} AlS FeS\n",
            "neighbor        2.0 bin\n",
            "neigh_modify    delay 0 every 1 check yes\n",
            f"timestep        {diag.timestep:.8g}\n\n",
        ]
    )
    if diag.include_pe:
        lines.append("compute         pe_atom all pe/atom\n")
    if diag.include_stress:
        lines.append("compute         st all stress/atom NULL virial\n")
    lines.extend(
        [
            "\nregion          bottom block INF INF INF INF INF 8.0 units box\n",
            "group           bottom region bottom\n",
            "group           mobile subtract all bottom\n",
            "fix             hold bottom setforce 0.0 0.0 0.0\n",
            f"velocity        mobile create {diag.velocity_temp:.8g} 88004 mom yes rot yes dist gaussian\n",
        ]
    )
    if diag.suffix_off_before_fix:
        lines.append("suffix          off\n")
    if diag.nve:
        lines.append("fix             nve_mobile mobile nve\n")
    elif diag.nvt:
        lines.append(f"fix             nvt_mobile mobile nvt temp {diag.nvt_start:.8g} {diag.nvt_stop:.8g} 0.1\n")
    lines.extend(
        [
            "\nthermo          10\n",
            "thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz\n",
            "thermo_modify   flush yes\n",
        ]
    )
    if diag.dump_mode == "xyz":
        lines.append(f"dump            d1 all custom 100 {posix(folder / 'dump.xyz.lammpstrj')} id type x y z\n")
        lines.append("dump_modify     d1 sort id\n")
    elif diag.dump_mode == "full":
        cols = "id type x y z"
        if diag.include_pe:
            cols += " c_pe_atom"
        if diag.include_stress:
            cols += " c_st[1] c_st[2] c_st[3] c_st[4] c_st[5] c_st[6]"
        lines.append(f"dump            d1 all custom 1000 {posix(folder / 'dump.full.lammpstrj')} {cols}\n")
        lines.append("dump_modify     d1 sort id\n")
    if diag.restart or smoke:
        lines.append(f"restart         2000 {posix(folder / 'restart.gpu_backend.*')}\n")
    for step in diag.run_sequence:
        lines.append(f"run             {step}\n")
    if final_outputs:
        lines.append(f"write_restart   {posix(folder / 'restart.gpu_backend.final')}\n")
        lines.append(f"write_data      {posix(folder / 'data.gpu_backend.final')}\n")
    return "".join(lines)


def diagnostics() -> list[Diagnostic]:
    current = CommandSpec(GPU_RELEASE, ["-k", "on", "g", "1", "-sf", "kk", "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "off"])
    newton_off = CommandSpec(GPU_RELEASE, ["-k", "on", "g", "1", "-sf", "kk", "-pk", "kokkos", "newton", "off", "neigh", "half", "gpu/aware", "off"])
    neigh_full = CommandSpec(GPU_RELEASE, ["-k", "on", "g", "1", "-sf", "kk", "-pk", "kokkos", "newton", "on", "neigh", "full", "gpu/aware", "off"])
    no_gpu_aware = CommandSpec(GPU_RELEASE, ["-k", "on", "g", "1", "-sf", "kk", "-pk", "kokkos", "newton", "on", "neigh", "half"])
    gpu_aware_on = CommandSpec(GPU_RELEASE, ["-k", "on", "g", "1", "-sf", "kk", "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "on"])
    debug = CommandSpec(GPU_DEBUG, ["-k", "on", "g", "1", "-sf", "kk", "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "off"])
    return [
        Diagnostic("D1", "current failing config reproduction", "D1_current_repro", current, run_sequence=(0, 10), include_pe=True, include_stress=True, dump_mode="full", restart=True),
        Diagnostic("D2", "KOKKOS newton off", "D2_newton_off", newton_off),
        Diagnostic("D3", "KOKKOS neigh full with required MEAM newton on", "D3_newton_on_neigh_full", neigh_full),
        Diagnostic("D4a", "GPU-aware omitted", "D4a_gpu_aware_omitted", no_gpu_aware),
        Diagnostic("D4b", "GPU-aware on", "D4b_gpu_aware_on", gpu_aware_on),
        Diagnostic("D5", "disable atom sorting", "D5_atom_sort_off", current, atom_sort_off=True),
        Diagnostic("D6", "no per-atom computes or dumps", "D6_no_per_atom_compute_dump", current),
        Diagnostic("D7", "coordinates-only dump", "D7_xyz_dump_only", current, dump_mode="xyz"),
        Diagnostic("D8", "smaller timestep 0.0005 ps", "D8_small_timestep_0005", current, timestep=0.0005),
        Diagnostic("D9", "thermal ramp 10 K to 300 K", "D9_thermal_ramp_10_to_300", current, velocity_temp=10.0, nvt_start=10.0, nvt_stop=300.0),
        Diagnostic("D10", "alternative debug KOKKOS CUDA binary", "D10_alt_debug_binary", debug, timeout_s=1800),
    ]


def run_lammps_diag(diag: Diagnostic) -> dict[str, Any]:
    folder = DIAG_ROOT / diag.folder
    folder.mkdir(parents=True, exist_ok=True)
    input_name = "in.gpu_diag"
    input_path = folder / input_name
    if not (folder / "returncode.txt").exists():
        write(input_path, base_input(DATA_EPS00194_Z200, diag, folder))
        cmd = diag.command_spec.command(input_name)
        with (folder / "stdout.log").open("w", encoding="utf-8") as out, (folder / "stderr.log").open("w", encoding="utf-8") as err:
            try:
                cp = subprocess.run(cmd, cwd=str(folder), stdout=out, stderr=err, env=os.environ.copy(), timeout=diag.timeout_s)
                rc = cp.returncode
                timed_out = False
            except subprocess.TimeoutExpired:
                rc = 124
                timed_out = True
        write(folder / "returncode.txt", str(rc))
    else:
        timed_out = False
        cmd = diag.command_spec.command(input_name)
    parsed = parse_run(folder)
    target_step = sum(step for step in diag.run_sequence if step > 0)
    status = "completed_clean_1000" if parsed["returncode"] == 0 and not parsed["fatal"] and parsed["max_step"] == target_step and target_step >= 1000 else None
    if status is None and parsed["returncode"] == 0 and not parsed["fatal"]:
        status = "completed_clean_partial"
    if status is None:
        status = "failed"
    parsed.update(
        {
            "key": diag.key,
            "title": diag.title,
            "input": rel(input_path),
            "command": cmd,
            "command_label": diag.command_spec.label(),
            "binary": str(diag.command_spec.binary),
            "kokkos_args": diag.command_spec.kokkos_args,
            "target_step": target_step,
            "status": status,
            "timed_out": timed_out,
            "notes": diag.notes,
            "diagnostic_settings": {
                "run_sequence": diag.run_sequence,
                "timestep": diag.timestep,
                "velocity_temp": diag.velocity_temp,
                "nvt_start": diag.nvt_start,
                "nvt_stop": diag.nvt_stop,
                "nvt": diag.nvt,
                "nve": diag.nve,
                "include_pe": diag.include_pe,
                "include_stress": diag.include_stress,
                "dump_mode": diag.dump_mode,
                "atom_sort_off": diag.atom_sort_off,
                "suffix_off_before_fix": diag.suffix_off_before_fix,
            },
        }
    )
    return parsed


def write_matrix_reports(matrix: dict[str, Any]) -> None:
    write_json(REPORTS / "stageF_F0_commensurate_ppf_eps00194_gpu_backend_matrix.json", matrix)
    rows = []
    for d in matrix["diagnostics"]:
        first_error = d["fatal_matches"][0]["text"] if d["fatal_matches"] else ""
        rows.append(
            f"| {d['key']} | {d['status']} | `{d['returncode']}` | `{d['max_step']}` | "
            f"`{Path(d['folder']).name}` | {first_error[:140]} |"
        )
    best = matrix.get("best_config")
    md = f"""# Stage F eps00194 GPU backend matrix

- Timestamp: {matrix['timestamp']}
- Stabilized data: `{rel(DATA_EPS00194_Z200)}`
- GPU backend status: **{matrix['gpu_backend_status']}**
- First failing config: `{matrix.get('first_failing_config')}`
- First passing 1000 config: `{matrix.get('first_passing_1000_config')}`
- Best config command: `{best['command'] if best else None}`

| Diag | Status | Return code | Max step | Folder | First error |
|---|---|---:|---:|---|---|
{chr(10).join(rows)}
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_gpu_backend_matrix.md", md)


def write_smoke_report(smoke: dict[str, Any]) -> None:
    write_json(REPORTS / "stageF_F0_commensurate_ppf_eps00194_gpu_recovered_smoke.json", smoke)
    md = f"""# Stage F eps00194 GPU recovered smoke

- Timestamp: {now()}
- Status: **{smoke['status']}**
- Folder: `{smoke['folder']}`
- Max step: `{smoke['max_step']}`
- Command: `{' '.join(smoke['command'])}`
- Final data exists: `{smoke['final_data_exists']}`
- Final restart exists: `{smoke['final_restart_exists']}`

## stderr tail

```text
{smoke['stderr_tail']}
```
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_gpu_recovered_smoke.md", md)


def promote_eps00194_smoke(best_diag: dict[str, Any]) -> dict[str, Any]:
    folder = EPS00194 / "smoke_retry_gpu_backend_fix"
    folder.mkdir(parents=True, exist_ok=True)
    cmd_spec = CommandSpec(Path(best_diag["binary"]), list(best_diag["kokkos_args"]))
    diag = Diagnostic(
        key="eps00194_gpu_smoke_backend_fix",
        title="eps00194 GPU 10k smoke with recovered backend config",
        folder="smoke_retry_gpu_backend_fix",
        command_spec=cmd_spec,
        run_sequence=(10000,),
        timestep=best_diag["diagnostic_settings"]["timestep"],
        velocity_temp=best_diag["diagnostic_settings"]["velocity_temp"],
        nvt_start=best_diag["diagnostic_settings"]["nvt_start"],
        nvt_stop=best_diag["diagnostic_settings"]["nvt_stop"],
        include_pe=True,
        include_stress=True,
        dump_mode="full",
        restart=True,
        atom_sort_off=best_diag["diagnostic_settings"]["atom_sort_off"],
        timeout_s=14400,
    )
    input_name = "in.smoke_retry_gpu_backend_fix"
    input_path = folder / input_name
    if not (folder / "returncode.txt").exists():
        write(input_path, base_input(DATA_EPS00194_Z200, diag, folder, final_outputs=True, smoke=True))
        cmd = cmd_spec.command(input_name)
        with (folder / "stdout.log").open("w", encoding="utf-8") as out, (folder / "stderr.log").open("w", encoding="utf-8") as err:
            try:
                cp = subprocess.run(cmd, cwd=str(folder), stdout=out, stderr=err, timeout=diag.timeout_s)
                rc = cp.returncode
                timed_out = False
            except subprocess.TimeoutExpired:
                rc = 124
                timed_out = True
        write(folder / "returncode.txt", str(rc))
    else:
        timed_out = False
        cmd = cmd_spec.command(input_name)
    parsed = parse_run(folder)
    final_data = folder / "data.gpu_backend.final"
    final_restart = folder / "restart.gpu_backend.final"
    clean = parsed["returncode"] == 0 and not parsed["fatal"] and parsed["max_step"] == 10000 and final_data.exists() and final_restart.exists()
    parsed.update(
        {
            "status": "completed_clean" if clean else "failed",
            "folder": rel(folder),
            "input": rel(input_path),
            "command": cmd,
            "timed_out": timed_out,
            "final_data_exists": final_data.exists(),
            "final_restart_exists": final_restart.exists(),
        }
    )
    write_smoke_report(parsed)
    return parsed


def write_eps0000_zheadroom_data() -> dict[str, Any]:
    src = DATA_EPS0000_RELAXED
    dst = DATA_EPS0000_Z200
    dst.parent.mkdir(parents=True, exist_ok=True)
    original_zhi = None
    lines = []
    for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[2] == "zlo" and parts[3] == "zhi":
            zlo = float(parts[0])
            zhi = float(parts[1])
            original_zhi = zhi
            lines.append(f"{zlo:.16g} {200.0:.16g} zlo zhi")
        else:
            lines.append(line)
    if not dst.exists():
        dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"source": rel(src), "target": rel(dst), "original_zhi": original_zhi, "new_zhi": 200.0}


def run_eps0000_comparable_smoke(best_diag: dict[str, Any]) -> dict[str, Any]:
    data_info = write_eps0000_zheadroom_data()
    folder = EPS0000 / "smoke_retry_comparable_zhi200_gpu"
    folder.mkdir(parents=True, exist_ok=True)
    cmd_spec = CommandSpec(Path(best_diag["binary"]), list(best_diag["kokkos_args"]))
    diag = Diagnostic(
        key="eps0000_comparable_gpu_smoke",
        title="eps0000 comparable zhi200 GPU smoke",
        folder="smoke_retry_comparable_zhi200_gpu",
        command_spec=cmd_spec,
        run_sequence=(10000,),
        timestep=best_diag["diagnostic_settings"]["timestep"],
        velocity_temp=best_diag["diagnostic_settings"]["velocity_temp"],
        nvt_start=best_diag["diagnostic_settings"]["nvt_start"],
        nvt_stop=best_diag["diagnostic_settings"]["nvt_stop"],
        include_pe=True,
        include_stress=True,
        dump_mode="full",
        restart=True,
        atom_sort_off=best_diag["diagnostic_settings"]["atom_sort_off"],
        timeout_s=14400,
    )
    input_name = "in.smoke_retry_comparable_zhi200_gpu"
    input_path = folder / input_name
    if not (folder / "returncode.txt").exists():
        write(input_path, base_input(DATA_EPS0000_Z200, diag, folder, final_outputs=True, smoke=True))
        cmd = cmd_spec.command(input_name)
        with (folder / "stdout.log").open("w", encoding="utf-8") as out, (folder / "stderr.log").open("w", encoding="utf-8") as err:
            try:
                cp = subprocess.run(cmd, cwd=str(folder), stdout=out, stderr=err, timeout=diag.timeout_s)
                rc = cp.returncode
                timed_out = False
            except subprocess.TimeoutExpired:
                rc = 124
                timed_out = True
        write(folder / "returncode.txt", str(rc))
    else:
        timed_out = False
        cmd = cmd_spec.command(input_name)
    parsed = parse_run(folder)
    final_data = folder / "data.gpu_backend.final"
    final_restart = folder / "restart.gpu_backend.final"
    clean = parsed["returncode"] == 0 and not parsed["fatal"] and parsed["max_step"] == 10000 and final_data.exists() and final_restart.exists()
    parsed.update(
        {
            "status": "completed_clean" if clean else "failed",
            "folder": rel(folder),
            "input": rel(input_path),
            "command": cmd,
            "timed_out": timed_out,
            "data_info": data_info,
            "final_data_exists": final_data.exists(),
            "final_restart_exists": final_restart.exists(),
        }
    )
    write_comparability_report(parsed)
    return parsed


def write_comparability_report(result: dict[str, Any]) -> None:
    payload = {"timestamp": now(), "eps0000_comparable_smoke": result}
    write_json(REPORTS / "stageF_F0_commensurate_ppf_comparability_gate_gpu.json", payload)
    md = f"""# Stage F F0 commensurate ppf GPU comparability gate

- Timestamp: {payload['timestamp']}
- eps0000 comparable zhi200 GPU smoke: **{result['status']}**
- Folder: `{result['folder']}`
- Max step: `{result['max_step']}`
- Production gate: {'PASS-ready only if eps00194 comparable smoke is also clean' if result['status'] == 'completed_clean' else 'BLOCKED'}
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_comparability_gate_gpu.md", md)


def update_smoke10k_summary(eps00194_smoke: dict[str, Any] | None, eps0000_smoke: dict[str, Any] | None) -> None:
    path = REPORTS / "stageF_F0_commensurate_ppf_smoke10k_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"run_root": rel(RUN)}
    if eps00194_smoke:
        summary["eps00194_gpu_backend_fix_smoke"] = {
            "status": eps00194_smoke["status"],
            "max_step": eps00194_smoke["max_step"],
            "folder": eps00194_smoke["folder"],
        }
    if eps0000_smoke:
        summary["eps0000_comparable_zhi200_gpu_smoke"] = {
            "status": eps0000_smoke["status"],
            "max_step": eps0000_smoke["max_step"],
            "folder": eps0000_smoke["folder"],
        }
    if eps00194_smoke and eps00194_smoke["status"] == "completed_clean" and eps0000_smoke and eps0000_smoke["status"] == "completed_clean":
        summary["gate"] = "GPU_COMPARABLE_SMOKES_CLEAN_PRODUCTION_GATE_CAN_OPEN"
    else:
        summary["gate"] = "BLOCK_PRODUCTION_GPU_BACKEND_NOT_RECOVERED_OR_COMPARABILITY_PENDING"
    write_json(path, summary)

    report_path = REPORTS / "stageF_F0_commensurate_ppf_smoke10k_report.md"
    existing = read_text(report_path) or "# Stage F F0 commensurate ppf smoke10k report\n"
    if "## GPU backend recovery lane" not in existing:
        existing += "\n\n## GPU backend recovery lane\n"
    existing += f"\n- Timestamp: {now()}\n"
    existing += f"- eps00194 GPU backend fix smoke: `{eps00194_smoke['status'] if eps00194_smoke else 'not_run'}` max step `{eps00194_smoke['max_step'] if eps00194_smoke else None}`.\n"
    existing += f"- eps0000 comparable zhi200 GPU smoke: `{eps0000_smoke['status'] if eps0000_smoke else 'not_run'}` max step `{eps0000_smoke['max_step'] if eps0000_smoke else None}`.\n"
    existing += "- Production remains blocked unless both comparable GPU smokes are completed clean.\n"
    write(report_path, existing)


def write_blocker_decision(matrix: dict[str, Any]) -> None:
    md = f"""# Stage F GPU backend blocker decision

- Timestamp: {now()}
- Status: all attempted stabilized eps00194 GPU diagnostics failed before a clean 1000-step path.
- CPU reference: stabilized eps00194 CPU smoke 10000 completed clean.
- Production: not launched.
- CPU production fallback: not used and requires explicit user approval.

## Option 1 - Build/fix GPU LAMMPS

Rebuild or patch KOKKOS CUDA LAMMPS and retest MEAM + `p p f` + stabilized eps00194 zhi=200. This keeps the target as GPU production.

## Option 2 - CPU fallback for both eps0000 and eps00194

Run both cases with the same CPU binary and same zhi=200/protocol for strict comparability. This is slower and requires explicit user approval before production.

## Option 3 - Simplify GPU outputs

Only valid if a GPU dynamics path can run without stress/dump. In the current matrix, dynamics itself still fails, so this option is not sufficient yet.

## Option 4 - Stop and report to Pshonkin

Show stabilized CPU smoke evidence and the GPU backend blocker; do not present production or Delta-sigma results.

## First errors

See `docs/reports/stageF_F0_commensurate_ppf_eps00194_gpu_backend_matrix.md` for D1-D10.
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_gpu_backend_blocker_decision.md", md)


def run_matrix() -> dict[str, Any]:
    DIAG_ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    for diag in diagnostics():
        result = run_lammps_diag(diag)
        results.append(result)

    first_failing = next((d for d in results if d["status"] == "failed"), None)
    first_passing_1000 = next((d for d in results if d["status"] == "completed_clean_1000"), None)
    best = None
    eps00194_smoke = None
    eps0000_smoke = None
    status = "not recovered"
    if first_passing_1000:
        best = {
            "diagnostic": first_passing_1000["key"],
            "command": " ".join(first_passing_1000["command"]),
            "binary": first_passing_1000["binary"],
            "kokkos_args": first_passing_1000["kokkos_args"],
        }
        eps00194_smoke = promote_eps00194_smoke(first_passing_1000)
        if eps00194_smoke["status"] == "completed_clean":
            status = "recovered"
            eps0000_smoke = run_eps0000_comparable_smoke(first_passing_1000)
        else:
            status = "partially recovered"
    matrix = {
        "timestamp": now(),
        "diagnostics": results,
        "gpu_backend_status": status,
        "first_failing_config": first_failing["key"] if first_failing else None,
        "first_passing_1000_config": first_passing_1000["key"] if first_passing_1000 else None,
        "best_config": best,
        "eps00194_gpu_smoke": eps00194_smoke,
        "eps0000_comparability_smoke": eps0000_smoke,
    }
    write_matrix_reports(matrix)
    update_smoke10k_summary(eps00194_smoke, eps0000_smoke)
    if not first_passing_1000:
        write_blocker_decision(matrix)
    return matrix


def write_root_report(inv: dict[str, Any], matrix: dict[str, Any]) -> None:
    release = next((b for b in inv["binaries"] if b["path"] == str(GPU_RELEASE)), None)
    alternatives = [b for b in inv["binaries"] if b["path"] != str(GPU_RELEASE) and "GPU KOKKOS" in b["classification"]]
    cpu = next((b for b in inv["binaries"] if b["path"] == str(CPU_LMP)), None)
    diag_rows = []
    for d in matrix["diagnostics"]:
        diag_rows.append(f"- {d['key']}: `{d['status']}`, max step `{d['max_step']}`, folder `{d['folder']}`")
    eps00194_smoke = matrix.get("eps00194_gpu_smoke")
    eps0000_smoke = matrix.get("eps0000_comparability_smoke")
    md = f"""# Stage F GPU backend recovery lane

- Timestamp: {now()}
- Target repo: `{REPO}`
- Run root: `{rel(RUN)}`
- Stabilized data: `{rel(DATA_EPS00194_Z200)}`

## GPU backend status

{matrix['gpu_backend_status']}.

## Binary inventory

- Current GPU binary: `{GPU_RELEASE}` -> `{release['classification'] if release else 'missing'}`
- Alternative GPU KOKKOS binaries found: `{[b['path'] for b in alternatives]}`
- CPU binary reference: `{CPU_LMP}` -> `{cpu['classification'] if cpu else 'missing'}`
- GPU environment: `{inv['nvidia_query']['stdout'].strip()}`

## Diagnostic matrix

{chr(10).join(diag_rows)}

- First failing config: `{matrix.get('first_failing_config')}`
- First passing 1000 config: `{matrix.get('first_passing_1000_config')}`
- Best config command: `{matrix['best_config']['command'] if matrix.get('best_config') else None}`

## eps00194 GPU smoke

- Status: `{eps00194_smoke['status'] if eps00194_smoke else 'not_run'}`
- Max step: `{eps00194_smoke['max_step'] if eps00194_smoke else None}`
- Log path: `{eps00194_smoke['folder'] + '/log.lammps' if eps00194_smoke else None}`

## eps0000 comparability smoke

- Status: `{eps0000_smoke['status'] if eps0000_smoke else 'not_run'}`
- Reason: `{'GPU eps00194 smoke did not complete cleanly' if not eps0000_smoke else 'run completed; see comparability gate'}`

## Production gate

- Production: not started.
- Gate status: `{'PASS-ready' if eps00194_smoke and eps00194_smoke['status'] == 'completed_clean' and eps0000_smoke and eps0000_smoke['status'] == 'completed_clean' else 'BLOCKED'}`

## CPU fallback

CPU production fallback was not used. It remains an option only with explicit user approval after GPU lane evidence is reviewed.

## Analysis and eps005

- Analysis: not run.
- eps005: not launched.
- F1/F0_300A: not launched.

## Files created

- `docs/reports/stageF_F0_commensurate_ppf_gpu_backend_lane_start.md`
- `docs/reports/stageF_F0_commensurate_ppf_gpu_binary_inventory.md`
- `docs/reports/stageF_F0_commensurate_ppf_gpu_binary_inventory.json`
- `docs/reports/stageF_F0_commensurate_ppf_eps00194_gpu_backend_matrix.md`
- `docs/reports/stageF_F0_commensurate_ppf_eps00194_gpu_backend_matrix.json`
- `docs/reports/stageF_F0_commensurate_ppf_gpu_backend_blocker_decision.md` if no GPU path recovered
- `agent_report_stageF_gpu_backend_recovery_lane.md`

## Exact next command

```powershell
Get-Content -Raw docs\\reports\\stageF_F0_commensurate_ppf_eps00194_gpu_backend_matrix.md
```
"""
    write(REPO / "agent_report_stageF_gpu_backend_recovery_lane.md", md)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if not any((args.inventory, args.matrix, args.all)):
        args.all = True

    outputs: dict[str, Any] = {}
    if args.inventory or args.all:
        outputs["lane_start"] = write_lane_start()
        outputs["inventory"] = inventory_binaries()
    if args.matrix or args.all:
        if "inventory" not in outputs:
            outputs["lane_start"] = write_lane_start()
            outputs["inventory"] = inventory_binaries()
        outputs["matrix"] = run_matrix()
        write_root_report(outputs["inventory"], outputs["matrix"])

    print(json.dumps({
        "inventory_binaries": len(outputs.get("inventory", {}).get("binaries", [])),
        "gpu_backend_status": outputs.get("matrix", {}).get("gpu_backend_status"),
        "first_passing_1000": outputs.get("matrix", {}).get("first_passing_1000_config"),
        "production": "not_started",
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
