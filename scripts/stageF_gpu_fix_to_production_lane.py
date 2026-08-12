#!/usr/bin/env python3
"""Stage F GPU fix/rebuild lane with strict production gates.

The script creates new timestamped runtime folders. It does not delete or
overwrite previous dumps, restarts, or reports. Production is launched only
after eps00194 and eps0000 comparable zhi=200 GPU smokes both finish cleanly.
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
EPS0000 = RUN_ROOT / "F0_planar_100A_comm_eps0000"
EPS00194 = RUN_ROOT / "F0_planar_100A_comm_eps00194"
REPORTS = REPO / "docs" / "reports"

DATA_EPS00194_Z200 = EPS00194 / "debug_fix1_z_headroom_cpu" / "data.F0_planar_100A_comm_eps00194.zheadroom30"
DATA_EPS0000_RELAXED = EPS0000 / "equil" / "data.F0_planar_100A_comm_eps0000.relaxed"
DATA_EPS0000_Z200 = EPS0000 / "smoke_retry_comparable_zhi200_gpu" / "data.F0_planar_100A_comm_eps0000.zheadroom30"

POT_DIR = REPO / "potentials" / "meam" / "Jelinek_2012"
MEAMF = POT_DIR / "Jelinek_2012_meamf"
MEAM = POT_DIR / "Jelinek_2012_meam.alsimgcufe"

GPU_RELEASE = Path(r"B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe")
GPU_DEBUG = Path(r"B:\builds\lammps-kokkos-cuda-debug\build\lmp_kokkos_cuda_debug.exe")
CPU_LMP = Path(r"C:\Users\dille\AppData\Local\LAMMPS 64-bit 22Jul2025-MSMPI\bin\lmp.exe")
MPIEXEC = Path(r"C:\Program Files\Microsoft MPI\Bin\mpiexec.exe")
CUDA124_NVCC = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin\nvcc.exe")
CUDA124_ROOT = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4")

RUN_ID = datetime.now().strftime("%Y%m%d-%H%M%S")
REPRO_ROOT = REPO / "runs" / "stageF_gpu_backend_repro_tests" / RUN_ID
BUILD_ROOT = Path(r"B:\builds") / f"lammps-kokkos-cuda-stageF-rebuild-{RUN_ID}"
PROD_ROOT = RUN_ROOT / f"gpu_backend_production_{RUN_ID}"

HARD_FATAL_PATTERNS = [
    "ERROR:",
    "Lost atoms",
    "lost atoms",
    "cudaError",
    "CUDA error",
    "illegal memory",
    "illegal address",
    "segmentation fault",
    "Segmentation fault",
    "MPI_ABORT",
    "Kokkos::abort",
    "Neighbor list overflow",
]

FORBIDDEN_PHRASES = [
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
    kokkos_args: tuple[str, ...] = (
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
    launcher: tuple[str, ...] = ()

    def command(self, input_name: str, log_name: str = "log.lammps") -> list[str]:
        return [*self.launcher, str(self.binary), *self.kokkos_args, "-in", input_name, "-log", log_name]

    def label(self) -> str:
        prefix = " ".join(self.launcher)
        return f"{prefix + ' ' if prefix else ''}{self.binary} {' '.join(self.kokkos_args)}"


@dataclass(frozen=True)
class LammpsCase:
    key: str
    title: str
    data: Path | None
    command_spec: CommandSpec
    sequence: tuple[int, ...]
    timeout_s: int = 900
    tiny: bool = False
    no_velocity: bool = False
    nve: bool = False
    nvt: bool = True
    include_computes: bool = False
    dump_mode: str = "none"
    timestep: float = 0.001
    velocity_temp: float = 300.0
    nvt_start: float = 300.0
    nvt_stop: float = 300.0
    atom_sort_off: bool = False
    final_outputs: bool = False
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def posix(path: Path) -> str:
    return path.resolve().as_posix()


def cmake_path(path: Path) -> str:
    return path.resolve().as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path = path.with_name(f"{path.stem}_{RUN_ID}{path.suffix}")
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def write_json(path: Path, data: Any) -> Path:
    return write_text(path, json.dumps(data, indent=2, ensure_ascii=False, default=str))


def write_runtime_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_runtime_json(path: Path, data: Any) -> None:
    write_runtime_text(path, json.dumps(data, indent=2, ensure_ascii=False, default=str))


def run_capture(cmd: list[str], cwd: Path | None = None, timeout_s: int = 60, env: dict[str, str] | None = None) -> dict[str, Any]:
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
    return run_capture(["powershell", "-NoProfile", "-Command", script], timeout_s=timeout_s)


def cmdline(command: str, timeout_s: int = 60) -> dict[str, Any]:
    return run_capture(["cmd", "/c", command], timeout_s=timeout_s)


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


def parse_lammps_run(folder: Path) -> dict[str, Any]:
    log = read_text(folder / "log.lammps")
    stdout = read_text(folder / "stdout.log")
    stderr = read_text(folder / "stderr.log")
    combined = "\n".join([log, stdout, stderr])
    rows = thermo_rows(combined)
    fatal_matches = []
    for idx, line in enumerate(combined.splitlines(), start=1):
        for pattern in HARD_FATAL_PATTERNS:
            if pattern in line:
                fatal_matches.append({"line": idx, "pattern": pattern, "text": line.strip()})
                break
    rc = None
    rc_path = folder / "returncode.txt"
    if rc_path.exists():
        raw = rc_path.read_text(encoding="utf-8", errors="replace").strip()
        try:
            rc = int(raw)
        except ValueError:
            rc = raw
    return {
        "folder": rel(folder),
        "returncode": rc,
        "fatal": bool(fatal_matches),
        "fatal_matches": fatal_matches,
        "max_step": max([row["Step"] for row in rows], default=None),
        "last_thermo": rows[-1] if rows else None,
        "loop_time": "Loop time" in combined,
        "total_wall_time": "Total wall time" in combined,
        "stdout_tail": "\n".join(stdout.splitlines()[-40:]),
        "stderr_tail": "\n".join(stderr.splitlines()[-40:]),
        "log_tail": "\n".join(log.splitlines()[-60:]),
    }


def target_step(sequence: tuple[int, ...]) -> int:
    return sum(step for step in sequence if step > 0)


def is_clean(parsed: dict[str, Any], sequence: tuple[int, ...], final_outputs: bool = False, folder: Path | None = None) -> bool:
    clean = parsed["returncode"] == 0 and not parsed["fatal"] and parsed["max_step"] == target_step(sequence)
    if final_outputs and folder:
        clean = clean and (folder / "data.gpu_backend.final").exists() and (folder / "restart.gpu_backend.final").exists()
    return clean


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


def classify_binary(path: Path) -> dict[str, Any]:
    exists = path.exists()
    help_result = run_capture([str(path), "-h"], timeout_s=45) if exists else {
        "returncode": None,
        "stdout": "",
        "stderr": "missing",
        "timed_out": False,
    }
    support = style_inventory((help_result.get("stdout") or "") + "\n" + (help_result.get("stderr") or ""))
    if support["kokkos_cuda"] and support["style_meam_kk"]:
        classification = "GPU KOKKOS + MEAM/KK present"
    elif support["style_meam"]:
        classification = "CPU/host MEAM present"
    elif exists and help_result.get("returncode") == 0:
        classification = "LAMMPS present, support unclear"
    else:
        classification = "missing or unusable"
    return {
        "path": str(path),
        "exists": exists,
        "size": path.stat().st_size if exists else None,
        "mtime": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds") if exists else None,
        "help_returncode": help_result.get("returncode"),
        "help_timed_out": help_result.get("timed_out"),
        "help_stderr_tail": "\n".join((help_result.get("stderr") or "").splitlines()[-8:]),
        "support": support,
        "classification": classification,
    }


def create_lane_start_report() -> dict[str, Any]:
    failed_folder = EPS00194 / "smoke_retry_gpu_after_fix"
    parsed = parse_lammps_run(failed_folder)
    input_path = failed_folder / "in.smoke_retry_gpu_after_fix"
    data = {
        "timestamp": now(),
        "target_repo": str(REPO),
        "branch_expected": "ilua/auto/stageD-local-interface-100k-mechanics",
        "run_root": rel(RUN_ROOT),
        "source_failed_gpu_retry": {
            "folder": rel(failed_folder),
            "input": rel(input_path),
            "parsed": parsed,
        },
        "strict_gates": {
            "cpu_production_without_approval": "forbidden",
            "eps005_F1_F0_300A": "forbidden",
            "thermo_modify_lost_ignore": "forbidden",
            "production_gate": "requires eps00194 GPU smoke 10k clean and eps0000 comparable zhi200 GPU smoke 10k clean",
        },
        "runtime_roots": {
            "repro_root": rel(REPRO_ROOT),
            "build_root": str(BUILD_ROOT),
            "production_root": rel(PROD_ROOT),
        },
    }
    md = f"""# Stage F GPU fix and production lane start

- Timestamp: {data['timestamp']}
- Target repo: `{REPO}`
- Branch expected: `{data['branch_expected']}`
- Run root: `{data['run_root']}`
- Failed stabilized eps00194 GPU retry: `{data['source_failed_gpu_retry']['folder']}`
- Failed retry max step: `{parsed['max_step']}`
- Failed retry return code: `{parsed['returncode']}`
- Runtime repro root for this lane: `{data['runtime_roots']['repro_root']}`
- Build root for this lane, only if preflight passes: `{data['runtime_roots']['build_root']}`
- Production root, only if both GPU smoke gates pass: `{data['runtime_roots']['production_root']}`

## Gate

Production remains closed until eps00194 zhi=200 GPU smoke 10k and eps0000 comparable zhi=200 GPU smoke 10k both complete cleanly with the same binary, KOKKOS flags, protocol, and zhi=200.

## Failed GPU stderr tail

```text
{parsed['stderr_tail']}
```
"""
    md_path = write_text(REPORTS / "stageF_gpu_fix_and_production_lane_start.md", md)
    json_path = write_json(REPORTS / "stageF_gpu_fix_and_production_lane_start.json", data)
    data["written"] = {"md": rel(md_path), "json": rel(json_path)}
    return data


def preflight() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    checks["project_git_status"] = run_capture(["git", "status", "--short", "--branch"], cwd=REPO, timeout_s=30)
    checks["control_git_status"] = run_capture(
        ["git", "status", "--short", "--branch"],
        cwd=REPO.parents[1],
        timeout_s=30,
    )
    checks["processes"] = ps(
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match 'lmp|lammps|mpiexec|python|codex' -or ($_.CommandLine -and $_.CommandLine -match 'stageF_gpu|lmp_kokkos|LAMMPS') } | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 4",
        timeout_s=30,
    )
    checks["nvidia_smi"] = run_capture(["nvidia-smi"], timeout_s=30)
    checks["nvidia_query"] = run_capture(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,compute_mode", "--format=csv,noheader"],
        timeout_s=30,
    )
    checks["psdrive_c"] = ps("Get-PSDrive C | Select-Object Name,Used,Free,Provider,Root | ConvertTo-Json", timeout_s=30)
    tool_commands = {
        "where_cmake": "where cmake",
        "cmake_version": "cmake --version",
        "where_nvcc": "where nvcc",
        "nvcc_version": "nvcc --version",
        "where_cl": "where cl",
        "cl": "cl",
        "where_ninja": "where ninja",
        "ninja_version": "ninja --version",
        "where_msbuild": "where msbuild",
        "msbuild_version": "msbuild -version",
        "where_dumpbin": "where dumpbin",
    }
    checks["tools"] = {key: cmdline(command, timeout_s=45) for key, command in tool_commands.items()}
    checks["cuda_env"] = ps(
        "Get-ChildItem Env: | Where-Object { $_.Name -match 'CUDA|KOKKOS|LAMMPS|MSMPI|MPI|PATH' } | "
        "Select-Object Name,Value | ConvertTo-Json -Depth 3",
        timeout_s=30,
    )
    checks["source_dir_search"] = {
        "B": ps(
            "Get-ChildItem -Path 'B:\\' -Recurse -Directory -ErrorAction SilentlyContinue | "
            "Where-Object { $_.FullName -match 'lammps|kokkos|build' } | Select-Object -First 200 -ExpandProperty FullName",
            timeout_s=30,
        ),
        "Documents": ps(
            "Get-ChildItem -Path 'C:\\Users\\dille\\Documents' -Recurse -Directory -ErrorAction SilentlyContinue | "
            "Where-Object { $_.FullName -match 'lammps|kokkos|build' } | Select-Object -First 200 -ExpandProperty FullName",
            timeout_s=30,
        ),
    }
    checks["binary_search"] = ps(
        "Get-ChildItem -Path 'B:\\','C:\\Users\\dille\\Documents','C:\\Users\\dille\\AppData\\Local' -Recurse -Filter 'lmp*.exe' -ErrorAction SilentlyContinue | "
        "Select-Object -First 120 FullName,Length,LastWriteTime | ConvertTo-Json -Depth 4",
        timeout_s=45,
    )
    binaries = [GPU_RELEASE, GPU_DEBUG, CPU_LMP]
    extra_paths = extract_json_paths(checks["binary_search"].get("stdout", ""), "FullName")
    for extra in extra_paths[:20]:
        p = Path(extra)
        if all(str(p).lower() != str(existing).lower() for existing in binaries):
            binaries.append(p)
    checks["binary_inventory"] = [classify_binary(path) for path in binaries]

    data = {
        "timestamp": now(),
        "checks": checks,
        "build_capability": infer_build_capability(checks, []),
    }
    write_json(REPORTS / "stageF_gpu_fix_environment_preflight.json", data)
    md = render_preflight_md(data)
    write_text(REPORTS / "stageF_gpu_fix_environment_preflight.md", md)
    return data


def extract_json_paths(stdout: str, key: str) -> list[str]:
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    paths = []
    for item in parsed if isinstance(parsed, list) else []:
        value = item.get(key)
        if isinstance(value, str):
            paths.append(value)
    return paths


def tool_ok(result: dict[str, Any]) -> bool:
    return result.get("returncode") == 0 and not result.get("timed_out")


def find_vsdevcmd() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft Visual Studio" / "2022" / "Community" / "Common7" / "Tools" / "VsDevCmd.bat",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft Visual Studio" / "2022" / "Professional" / "Common7" / "Tools" / "VsDevCmd.bat",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft Visual Studio" / "2022" / "Enterprise" / "Common7" / "Tools" / "VsDevCmd.bat",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "2022" / "BuildTools" / "Common7" / "Tools" / "VsDevCmd.bat",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "2019" / "BuildTools" / "Common7" / "Tools" / "VsDevCmd.bat",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.exists():
        result = run_capture(
            [str(vswhere), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
            timeout_s=30,
        )
        install = result.get("stdout", "").strip().splitlines()
        if install:
            candidate = Path(install[0]) / "Common7" / "Tools" / "VsDevCmd.bat"
            if candidate.exists():
                return candidate
    return None


def infer_build_capability(preflight_data: dict[str, Any], source_candidates: list[Path]) -> dict[str, Any]:
    tools = preflight_data.get("checks", {}).get("tools", {}) if "checks" in preflight_data else preflight_data.get("tools", {})
    cmake_ok = tool_ok(tools.get("where_cmake", {})) and tool_ok(tools.get("cmake_version", {}))
    nvcc_ok = tool_ok(tools.get("where_nvcc", {})) and tool_ok(tools.get("nvcc_version", {}))
    ninja_ok = tool_ok(tools.get("where_ninja", {})) and tool_ok(tools.get("ninja_version", {}))
    cl_in_path = tool_ok(tools.get("where_cl", {}))
    vsdevcmd = find_vsdevcmd()
    source_ok = any((src / "CMakeLists.txt").exists() for src in source_candidates)
    missing = []
    if not cmake_ok:
        missing.append("cmake")
    if not nvcc_ok:
        missing.append("nvcc")
    if not ninja_ok:
        missing.append("ninja")
    if not (cl_in_path or vsdevcmd):
        missing.append("MSVC cl / VsDevCmd.bat")
    if source_candidates and not source_ok:
        missing.append("LAMMPS cmake source")
    return {
        "cmake_ok": cmake_ok,
        "nvcc_ok": nvcc_ok,
        "ninja_ok": ninja_ok,
        "cl_in_path": cl_in_path,
        "vsdevcmd": str(vsdevcmd) if vsdevcmd else None,
        "source_ok": source_ok if source_candidates else None,
        "missing": missing,
        "build_capable": not missing if source_candidates else False,
    }


def render_preflight_md(data: dict[str, Any]) -> str:
    checks = data["checks"]
    tools = checks["tools"]
    inv_rows = []
    for item in checks["binary_inventory"]:
        inv_rows.append(
            f"| `{item['path']}` | {item['exists']} | {item['classification']} | "
            f"CUDA={item['support']['kokkos_cuda']} MEAM/KK={item['support']['style_meam_kk']} |"
        )
    tool_rows = []
    for key, result in tools.items():
        first = (result.get("stdout") or result.get("stderr") or "").splitlines()
        tool_rows.append(f"| `{key}` | `{result.get('returncode')}` | `{result.get('timed_out')}` | `{first[0] if first else ''}` |")
    return f"""# Stage F GPU fix environment preflight

- Timestamp: {data['timestamp']}
- Build capable before source audit: `{data['build_capability']['build_capable']}`
- Missing: `{data['build_capability']['missing']}`
- GPU query: `{checks['nvidia_query'].get('stdout', '').strip()}`

## Tool Checks

| Check | Return code | Timed out | First line |
|---|---:|---:|---|
{chr(10).join(tool_rows)}

## Binary Inventory

| Binary | Exists | Classification | Support |
|---|---:|---|---|
{chr(10).join(inv_rows)}

## Search Notes

- Source/build search over `B:\\`: return code `{checks['source_dir_search']['B']['returncode']}`, timed out `{checks['source_dir_search']['B']['timed_out']}`.
- Source/build search over `C:\\Users\\dille\\Documents`: return code `{checks['source_dir_search']['Documents']['returncode']}`, timed out `{checks['source_dir_search']['Documents']['timed_out']}`.
- Binary search return code `{checks['binary_search']['returncode']}`, timed out `{checks['binary_search']['timed_out']}`.
"""


def find_cmake_caches() -> list[Path]:
    roots = [
        Path(r"B:\builds"),
        Path(r"C:\Users\dille\Documents\builds"),
        Path(r"C:\Users\dille\Documents\ilua-system"),
    ]
    found: list[Path] = []
    deadline = time.time() + 45
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("CMakeCache.txt"):
                found.append(path)
                if time.time() > deadline or len(found) >= 50:
                    return found
        except OSError:
            continue
    return found


def parse_cmake_cache(path: Path) -> dict[str, str]:
    wanted_prefixes = (
        "CMAKE_",
        "Kokkos_",
        "PKG_",
        "BUILD_",
        "MPI_",
        "LAMMPS_",
    )
    values: dict[str, str] = {}
    for line in read_text(path).splitlines():
        if not line or line.startswith("//") or line.startswith("#") or "=" not in line:
            continue
        lhs, value = line.split("=", 1)
        key = lhs.split(":", 1)[0]
        if key.startswith(wanted_prefixes) or key in {"CMAKE_HOME_DIRECTORY"}:
            values[key] = value
    return values


def audit_existing_builds(preflight_data: dict[str, Any]) -> dict[str, Any]:
    known_dirs = [
        GPU_RELEASE.parent,
        GPU_DEBUG.parent,
        Path(r"C:\Users\dille\Documents\builds\lammps-kokkos-cuda\build"),
    ]
    for cache in find_cmake_caches():
        if cache.parent not in known_dirs:
            known_dirs.append(cache.parent)
    builds = []
    source_candidates: list[Path] = []
    for build_dir in known_dirs:
        cache_path = build_dir / "CMakeCache.txt"
        cache = parse_cmake_cache(cache_path) if cache_path.exists() else {}
        source_hint = cache.get("CMAKE_HOME_DIRECTORY") or cache.get("LAMMPS_SOURCE_DIR")
        if source_hint:
            src = Path(source_hint)
            if src.exists():
                source_candidates.append(src)
        compile_commands = build_dir / "compile_commands.json"
        compile_info = {
            "exists": compile_commands.exists(),
            "size": compile_commands.stat().st_size if compile_commands.exists() else None,
            "first_command": None,
        }
        if compile_commands.exists():
            try:
                parsed = json.loads(read_text(compile_commands))
                if isinstance(parsed, list) and parsed:
                    compile_info["first_command"] = parsed[0].get("command") or parsed[0].get("arguments")
            except json.JSONDecodeError:
                compile_info["first_command"] = "JSON parse failed"
        exes = sorted(build_dir.glob("lmp*.exe"))
        exe_infos = []
        for exe in exes[:10]:
            exe_infos.append(classify_binary(exe))
        builds.append(
            {
                "build_dir": str(build_dir),
                "exists": build_dir.exists(),
                "cache_exists": cache_path.exists(),
                "cache_path": str(cache_path),
                "cache_keys": cache,
                "compile_commands": compile_info,
                "executables": exe_infos,
            }
        )
    source_candidates.extend(find_lammps_source_candidates())
    unique_sources = []
    seen = set()
    for src in source_candidates:
        key = str(src.resolve()).lower() if src.exists() else str(src).lower()
        if key not in seen:
            unique_sources.append(src)
            seen.add(key)
    capability = infer_build_capability(preflight_data, unique_sources)
    data = {
        "timestamp": now(),
        "builds": builds,
        "source_candidates": [str(src) for src in unique_sources],
        "build_capability": capability,
    }
    write_json(REPORTS / "stageF_gpu_fix_existing_builds_audit.json", data)
    write_text(REPORTS / "stageF_gpu_fix_existing_builds_audit.md", render_build_audit_md(data))
    return data


def find_lammps_source_candidates() -> list[Path]:
    candidates = [
        Path(r"C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps\cmake"),
        Path(r"C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps"),
        Path(r"B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\lammps\cmake"),
        Path(r"B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\lammps"),
        Path(r"B:\builds\lammps-kokkos-cuda-debug\lammps\cmake"),
        Path(r"B:\builds\lammps-kokkos-cuda-debug\lammps"),
    ]
    roots = [Path(r"B:\builds"), Path(r"C:\Users\dille\Documents\builds")]
    deadline = time.time() + 20
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("CMakeLists.txt"):
                if "lammps" in str(path).lower() and path.parent.name.lower() in {"cmake", "lammps"}:
                    candidates.append(path.parent)
                if time.time() > deadline:
                    return [c for c in candidates if c.exists()]
        except OSError:
            continue
    return [c for c in candidates if c.exists()]


def render_build_audit_md(data: dict[str, Any]) -> str:
    rows = []
    for build in data["builds"]:
        cache = build["cache_keys"]
        arch = cache.get("Kokkos_ARCH_AMPERE86") or cache.get("CMAKE_CUDA_ARCHITECTURES") or ""
        pkg = " ".join(k for k, v in cache.items() if k.startswith("PKG_") and v.upper() in {"ON", "YES", "TRUE"})
        exe_summary = "; ".join(f"{Path(e['path']).name}:{e['classification']}" for e in build["executables"]) or "none"
        rows.append(f"| `{build['build_dir']}` | {build['cache_exists']} | `{arch}` | `{pkg[:120]}` | {exe_summary} |")
    return f"""# Stage F GPU fix existing builds audit

- Timestamp: {data['timestamp']}
- Build capable after source audit: `{data['build_capability']['build_capable']}`
- Missing: `{data['build_capability']['missing']}`
- Source candidates: `{data['source_candidates']}`

| Build dir | Cache | CUDA/Kokkos arch clue | Enabled package clues | Executables |
|---|---:|---|---|---|
{chr(10).join(rows)}
"""


def ensure_eps0000_z200() -> dict[str, Any]:
    if DATA_EPS0000_Z200.exists():
        return {"source": rel(DATA_EPS0000_RELAXED), "target": rel(DATA_EPS0000_Z200), "created": False, "new_zhi": 200.0}
    DATA_EPS0000_Z200.parent.mkdir(parents=True, exist_ok=True)
    original_zhi = None
    out_lines = []
    for line in read_text(DATA_EPS0000_RELAXED).splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[2] == "zlo" and parts[3] == "zhi":
            original_zhi = float(parts[1])
            out_lines.append(f"{float(parts[0]):.16g} {200.0:.16g} zlo zhi")
        else:
            out_lines.append(line)
    write_runtime_text(DATA_EPS0000_Z200, "\n".join(out_lines))
    return {
        "source": rel(DATA_EPS0000_RELAXED),
        "target": rel(DATA_EPS0000_Z200),
        "created": True,
        "original_zhi": original_zhi,
        "new_zhi": 200.0,
    }


def tiny_data(path: Path) -> None:
    text = """LAMMPS tiny Al Fe data

4 atoms
2 atom types

0.0 10.0 xlo xhi
0.0 10.0 ylo yhi
0.0 10.0 zlo zhi

Masses

1 26.9815385
2 55.845

Atoms # atomic

1 1 2.0 2.0 2.0
2 1 4.8 2.0 2.0
3 2 2.0 4.8 2.0
4 1 2.0 2.0 4.8
"""
    write_runtime_text(path, text)


def lammps_input(case: LammpsCase, folder: Path) -> str:
    if case.tiny:
        data_path = folder / "data.tiny_al_fe"
        tiny_data(data_path)
        lines = [
            f"# {case.key}: {case.title}\n",
            "units           metal\n",
            "atom_style      atomic\n",
            "boundary        p p p\n",
            f"read_data       {posix(data_path)}\n",
            "pair_style      meam\n",
            f"pair_coeff      * * {posix(MEAMF)} AlS SiS MgS CuS FeS {posix(MEAM)} AlS FeS\n",
            "neighbor        2.0 bin\n",
            "neigh_modify    delay 0 every 1 check yes\n",
            "timestep        0.001\n",
            "velocity        all create 10.0 12345 mom yes rot yes dist gaussian\n",
            "fix             nve_all all nve\n",
            "thermo          1\n",
            "thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz\n",
            "thermo_modify   flush yes\n",
        ]
        for step in case.sequence:
            lines.append(f"run             {step}\n")
        return "".join(lines)

    if case.data is None:
        raise ValueError(f"{case.key} requires a data path")
    lines = [
        f"# {case.key}: {case.title}\n",
        "units           metal\n",
        "atom_style      atomic\n",
        "boundary        p p f\n",
    ]
    if case.atom_sort_off:
        lines.append("atom_modify     sort 0 0.0\n")
    lines.extend(
        [
            f"read_data       {posix(case.data)}\n",
            "pair_style      meam\n",
            f"pair_coeff      * * {posix(MEAMF)} AlS SiS MgS CuS FeS {posix(MEAM)} AlS FeS\n",
            "neighbor        2.0 bin\n",
            "neigh_modify    delay 0 every 1 check yes\n",
            f"timestep        {case.timestep:.8g}\n",
        ]
    )
    if case.include_computes:
        lines.append("compute         pe_atom all pe/atom\n")
        lines.append("compute         st all stress/atom NULL virial\n")
    lines.extend(
        [
            "region          bottom block INF INF INF INF INF 8.0 units box\n",
            "group           bottom region bottom\n",
            "group           mobile subtract all bottom\n",
            "fix             hold bottom setforce 0.0 0.0 0.0\n",
        ]
    )
    if not case.no_velocity:
        lines.append(f"velocity        mobile create {case.velocity_temp:.8g} 88004 mom yes rot yes dist gaussian\n")
    if case.nve:
        lines.append("fix             nve_mobile mobile nve\n")
    elif case.nvt:
        lines.append(f"fix             nvt_mobile mobile nvt temp {case.nvt_start:.8g} {case.nvt_stop:.8g} 0.1\n")
    lines.extend(
        [
            "thermo          10\n",
            "thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz\n",
            "thermo_modify   flush yes\n",
        ]
    )
    if case.dump_mode == "xyz":
        lines.append(f"dump            d1 all custom 1000 {posix(folder / 'dump.xyz.lammpstrj')} id type x y z\n")
        lines.append("dump_modify     d1 sort id\n")
    elif case.dump_mode == "full":
        lines.append(
            f"dump            d1 all custom 1000 {posix(folder / 'dump.full.lammpstrj')} "
            "id type x y z c_pe_atom c_st[1] c_st[2] c_st[3] c_st[4] c_st[5] c_st[6]\n"
        )
        lines.append("dump_modify     d1 sort id\n")
    if case.final_outputs:
        lines.append(f"restart         5000 {posix(folder / 'restart.gpu_backend.*')}\n")
    for step in case.sequence:
        lines.append(f"run             {step}\n")
    if case.final_outputs:
        lines.append(f"write_restart   {posix(folder / 'restart.gpu_backend.final')}\n")
        lines.append(f"write_data      {posix(folder / 'data.gpu_backend.final')}\n")
    return "".join(lines)


def run_lammps_case(case: LammpsCase, root: Path = REPRO_ROOT) -> dict[str, Any]:
    folder = root / case.key
    folder.mkdir(parents=True, exist_ok=True)
    input_name = f"in.{case.key}"
    write_runtime_text(folder / input_name, lammps_input(case, folder))
    cmd = case.command_spec.command(input_name)
    env = os.environ.copy()
    with (folder / "stdout.log").open("w", encoding="utf-8") as out, (folder / "stderr.log").open("w", encoding="utf-8") as err:
        started = time.time()
        try:
            cp = subprocess.run(cmd, cwd=str(folder), stdout=out, stderr=err, timeout=case.timeout_s, env=env)
            rc = cp.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            rc = 124
            timed_out = True
        elapsed = round(time.time() - started, 3)
    write_runtime_text(folder / "returncode.txt", str(rc))
    parsed = parse_lammps_run(folder)
    clean = is_clean(parsed, case.sequence, case.final_outputs, folder)
    parsed.update(
        {
            "key": case.key,
            "title": case.title,
            "status": "completed_clean" if clean else "failed",
            "target_step": target_step(case.sequence),
            "input": rel(folder / input_name),
            "command": cmd,
            "command_label": case.command_spec.label(),
            "timed_out": timed_out,
            "elapsed_s": elapsed,
            "settings": {
                "sequence": case.sequence,
                "tiny": case.tiny,
                "data": rel(case.data) if case.data else None,
                "no_velocity": case.no_velocity,
                "nve": case.nve,
                "nvt": case.nvt,
                "include_computes": case.include_computes,
                "dump_mode": case.dump_mode,
                "timestep": case.timestep,
                "velocity_temp": case.velocity_temp,
                "atom_sort_off": case.atom_sort_off,
                "final_outputs": case.final_outputs,
                "notes": case.notes,
                "extra": case.extra,
            },
            "final_data_exists": (folder / "data.gpu_backend.final").exists(),
            "final_restart_exists": (folder / "restart.gpu_backend.final").exists(),
        }
    )
    return parsed


def minimal_repro_matrix(command_spec: CommandSpec | None = None, report_suffix: str = "") -> dict[str, Any]:
    ensure_eps0000_z200()
    release = command_spec or CommandSpec(GPU_RELEASE)
    mpiexec_spec = CommandSpec(GPU_RELEASE, launcher=(str(MPIEXEC), "-np", "1")) if MPIEXEC.exists() else release
    long_syntax = CommandSpec(
        GPU_RELEASE,
        (
            "-kokkos",
            "on",
            "g",
            "1",
            "-suffix",
            "kk",
            "-package",
            "kokkos",
            "newton",
            "on",
            "neigh",
            "half",
            "gpu/aware",
            "off",
        ),
    )
    cases = [
        LammpsCase("T0_tiny_meam_pair_eval", "tiny MEAM/KK pair eval", None, release, (0, 1), tiny=True, timeout_s=180),
        LammpsCase("T1_eps0000_zhi200_run0_10_1000", "eps0000 comparable zhi=200 run0/10/1000", DATA_EPS0000_Z200, release, (0, 10, 990), timeout_s=1200),
        LammpsCase("T2_eps00194_zhi200_run0_10_no_dump", "eps00194 zhi=200 full data run0/10 no dump/stress", DATA_EPS00194_Z200, release, (0, 10), timeout_s=900),
        LammpsCase("T3_eps00194_no_velocity_no_nvt_run0", "eps00194 zhi=200 no velocity and no NVT run0", DATA_EPS00194_Z200, release, (0,), no_velocity=True, nvt=False, timeout_s=600),
        LammpsCase("T4_eps00194_nve_run0_10", "eps00194 zhi=200 NVE run0/10", DATA_EPS00194_Z200, release, (0, 10), nve=True, nvt=False, timeout_s=900),
        LammpsCase("T5_eps00194_nvt_no_dump_no_computes_run1000", "eps00194 zhi=200 NVT no dump/no computes run1000", DATA_EPS00194_Z200, release, (0, 10, 990), timeout_s=1200),
        LammpsCase("T6_direct_binary_one_rank", "direct binary one rank eps00194 run10", DATA_EPS00194_Z200, release, (0, 10), timeout_s=900),
        LammpsCase("T7_mpiexec_np1", "mpiexec -np 1 eps00194 run10", DATA_EPS00194_Z200, mpiexec_spec, (0, 10), timeout_s=900),
        LammpsCase("T8_valid_kokkos_long_syntax", "valid long KOKKOS command syntax eps00194 run10", DATA_EPS00194_Z200, long_syntax, (0, 10), timeout_s=900),
    ]
    results = []
    for case in cases:
        results.append(run_lammps_case(case))
    dynamic_clean = [r for r in results if r["status"] == "completed_clean" and r["target_step"] >= 10 and r["key"] != "T0_tiny_meam_pair_eval"]
    data = {
        "timestamp": now(),
        "repro_root": rel(REPRO_ROOT),
        "command_spec": release.label(),
        "tests": results,
        "dynamic_gpu_path_recovered": bool(dynamic_clean),
        "first_clean_dynamic": dynamic_clean[0]["key"] if dynamic_clean else None,
    }
    stem = f"stageF_gpu_fix_minimal_repro_matrix{report_suffix}"
    write_json(REPORTS / f"{stem}.json", data)
    write_text(REPORTS / f"{stem}.md", render_repro_md(data))
    return data


def render_repro_md(data: dict[str, Any]) -> str:
    rows = []
    for test in data["tests"]:
        err = test["fatal_matches"][0]["text"] if test["fatal_matches"] else ""
        rows.append(
            f"| {test['key']} | {test['status']} | `{test['returncode']}` | `{test['max_step']}` | "
            f"`{test['folder']}` | {err[:160]} |"
        )
    return f"""# Stage F GPU fix minimal repro matrix

- Timestamp: {data['timestamp']}
- Repro root: `{data['repro_root']}`
- Command spec: `{data['command_spec']}`
- Dynamic GPU path recovered in existing binary tests: `{data['dynamic_gpu_path_recovered']}`
- First clean dynamic test: `{data['first_clean_dynamic']}`

| Test | Status | Return code | Max step | Folder | First fatal |
|---|---|---:|---:|---|---|
{chr(10).join(rows)}
"""


def select_source(audit: dict[str, Any]) -> Path | None:
    for raw in audit.get("source_candidates", []):
        src = Path(raw)
        if (src / "CMakeLists.txt").exists() and src.name.lower() == "cmake":
            return src
    for raw in audit.get("source_candidates", []):
        src = Path(raw)
        if (src / "cmake" / "CMakeLists.txt").exists():
            return src / "cmake"
    return None


def attempt_rebuild(preflight_data: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    source = select_source(audit)
    capability = infer_build_capability(preflight_data, [source] if source else [])
    result: dict[str, Any] = {
        "timestamp": now(),
        "source": str(source) if source else None,
        "build_root": str(BUILD_ROOT),
        "capability": capability,
        "attempted": False,
        "configure_build": None,
        "binary": None,
        "binary_inventory": None,
        "post_build_probe": None,
        "status": "blocked",
    }
    if not source or not capability["build_capable"]:
        result["status"] = "build_blocked"
        write_json(REPORTS / "stageF_gpu_fix_build_attempt.json", result)
        write_text(REPORTS / "stageF_gpu_fix_build_attempt.md", render_build_attempt_md(result))
        return result

    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    build_dir = BUILD_ROOT / "build"
    vsdev = capability.get("vsdevcmd")
    cmake_args = [
        "cmake",
        "-S",
        str(source),
        "-B",
        str(build_dir),
        "-G",
        "Ninja",
        "-D",
        "CMAKE_BUILD_TYPE=Release",
        "-D",
        "CMAKE_CXX_COMPILER=cl",
        "-D",
        f"CMAKE_CUDA_COMPILER={cmake_path(CUDA124_NVCC)}",
        "-D",
        f"CUDAToolkit_ROOT={cmake_path(CUDA124_ROOT)}",
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
    build_args = ["cmake", "--build", str(build_dir), "--config", "Release", "--target", "lmp", "-j", "8"]
    if vsdev:
        batch = BUILD_ROOT / "stageF_configure_build.bat"
        batch_text = "\n".join(
            [
                "@echo on",
                f'call "{vsdev}" -arch=x64',
                "if errorlevel 1 exit /b %errorlevel%",
                " ".join(quote_cmd(arg) for arg in cmake_args),
                "if errorlevel 1 exit /b %errorlevel%",
                " ".join(quote_cmd(arg) for arg in build_args),
            ]
        )
        write_runtime_text(batch, batch_text)
        run = run_capture(["cmd", "/c", str(batch)], timeout_s=5400)
    else:
        configure = run_capture(cmake_args, timeout_s=1200)
        build = run_capture(build_args, timeout_s=4200)
        run = {
            "command": [cmake_args, build_args],
            "returncode": build["returncode"] if configure["returncode"] == 0 else configure["returncode"],
            "stdout": configure["stdout"] + "\n" + build["stdout"],
            "stderr": configure["stderr"] + "\n" + build["stderr"],
            "timed_out": configure["timed_out"] or build["timed_out"],
            "elapsed_s": configure["elapsed_s"] + build["elapsed_s"],
        }
    result["attempted"] = True
    result["configure_build"] = run
    exes = sorted(build_dir.glob("lmp*.exe"))
    if exes:
        binary = next((exe for exe in exes if exe.name.lower() == "lmp.exe"), exes[0])
        result["binary"] = str(binary)
        result["binary_inventory"] = classify_binary(binary)
        if result["binary_inventory"]["support"]["kokkos_cuda"] and result["binary_inventory"]["support"]["style_meam_kk"]:
            probe_spec = CommandSpec(binary)
            probe_case = LammpsCase(
                "post_build_eps00194_run0_10_1000",
                "post-build eps00194 zhi=200 run0/10/1000",
                DATA_EPS00194_Z200,
                probe_spec,
                (0, 10, 990),
                timeout_s=1500,
            )
            result["post_build_probe"] = run_lammps_case(probe_case, REPRO_ROOT / "post_build")
            result["status"] = "recovered_candidate" if result["post_build_probe"]["status"] == "completed_clean" else "build_succeeded_probe_failed"
        else:
            result["status"] = "build_succeeded_binary_missing_kokkos_meam"
    else:
        result["status"] = "build_failed_no_binary"
    write_json(REPORTS / "stageF_gpu_fix_build_attempt.json", result)
    write_text(REPORTS / "stageF_gpu_fix_build_attempt.md", render_build_attempt_md(result))
    return result


def quote_cmd(arg: str) -> str:
    if re.search(r"\s|&|\(|\)", arg):
        return '"' + arg.replace('"', '""') + '"'
    return arg


def render_build_attempt_md(data: dict[str, Any]) -> str:
    run = data.get("configure_build") or {}
    return f"""# Stage F GPU fix build attempt

- Timestamp: {data['timestamp']}
- Status: `{data['status']}`
- Attempted: `{data['attempted']}`
- Source: `{data['source']}`
- Build root: `{data['build_root']}`
- Missing: `{data['capability']['missing']}`
- Build return code: `{run.get('returncode')}`
- Build timed out: `{run.get('timed_out')}`
- Candidate binary: `{data.get('binary')}`
- Post-build probe status: `{(data.get('post_build_probe') or {}).get('status')}`
- Post-build probe max step: `{(data.get('post_build_probe') or {}).get('max_step')}`

## Build stderr tail

```text
{chr(10).join((run.get('stderr') or '').splitlines()[-80:])}
```
"""


def promote_smokes_and_maybe_production(best_binary: Path, source: str) -> dict[str, Any]:
    spec = CommandSpec(best_binary)
    eps00194_case = LammpsCase(
        "eps00194_gpu_smoke10k_recovered",
        "eps00194 zhi=200 recovered GPU smoke 10k",
        DATA_EPS00194_Z200,
        spec,
        (10000,),
        timeout_s=14400,
        include_computes=True,
        dump_mode="full",
        final_outputs=True,
    )
    eps00194_smoke = run_lammps_case(eps00194_case, REPRO_ROOT / "smokes")
    eps0000_smoke = None
    production = {"status": "not_started", "reason": "eps00194 smoke not clean"}
    if eps00194_smoke["status"] == "completed_clean":
        ensure_eps0000_z200()
        eps0000_case = LammpsCase(
            "eps0000_zhi200_gpu_smoke10k_comparable",
            "eps0000 comparable zhi=200 GPU smoke 10k",
            DATA_EPS0000_Z200,
            spec,
            (10000,),
            timeout_s=14400,
            include_computes=True,
            dump_mode="full",
            final_outputs=True,
        )
        eps0000_smoke = run_lammps_case(eps0000_case, REPRO_ROOT / "smokes")
        if eps0000_smoke["status"] == "completed_clean":
            production = launch_production_worker(best_binary)
        else:
            production = {"status": "not_started", "reason": "eps0000 comparable smoke not clean"}
    data = {
        "timestamp": now(),
        "best_binary": str(best_binary),
        "best_binary_source": source,
        "kokkos_flags": list(spec.kokkos_args),
        "eps00194_gpu_smoke": eps00194_smoke,
        "eps0000_comparable_gpu_smoke": eps0000_smoke,
        "production": production,
    }
    write_json(REPORTS / "stageF_gpu_fix_smoke_and_production_gate.json", data)
    write_text(REPORTS / "stageF_gpu_fix_smoke_and_production_gate.md", render_gate_md(data))
    return data


def launch_production_worker(best_binary: Path) -> dict[str, Any]:
    PROD_ROOT.mkdir(parents=True, exist_ok=True)
    config = {
        "production_root": str(PROD_ROOT),
        "binary": str(best_binary),
        "kokkos_args": list(CommandSpec(best_binary).kokkos_args),
        "eps0000_data": str(DATA_EPS0000_Z200),
        "eps00194_data": str(DATA_EPS00194_Z200),
    }
    config_path = PROD_ROOT / "production_worker_config.json"
    write_runtime_json(config_path, config)
    status_path = PROD_ROOT / "production_worker_status.json"
    write_runtime_json(status_path, {"status": "starting", "timestamp": now(), "cases": []})
    cmd = [sys.executable, str(Path(__file__).resolve()), "--production-worker", str(config_path)]
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    stdout = (PROD_ROOT / "worker_stdout.log").open("w", encoding="utf-8")
    stderr = (PROD_ROOT / "worker_stderr.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=str(REPO), stdout=stdout, stderr=stderr, creationflags=creationflags)
    stdout.close()
    stderr.close()
    return {
        "status": "running",
        "pid": proc.pid,
        "root": rel(PROD_ROOT),
        "config": rel(config_path),
        "status_json": rel(status_path),
        "stdout": rel(PROD_ROOT / "worker_stdout.log"),
        "stderr": rel(PROD_ROOT / "worker_stderr.log"),
        "monitoring_command": f"Get-Content -Raw {rel(status_path).replace('/', '\\\\')}",
    }


def render_gate_md(data: dict[str, Any]) -> str:
    eps00194 = data["eps00194_gpu_smoke"]
    eps0000 = data["eps0000_comparable_gpu_smoke"] or {}
    prod = data["production"]
    return f"""# Stage F GPU fix smoke and production gate

- Timestamp: {data['timestamp']}
- Best binary: `{data['best_binary']}`
- Best binary source: `{data['best_binary_source']}`
- KOKKOS flags: `{' '.join(data['kokkos_flags'])}`
- eps00194 GPU smoke status: `{eps00194['status']}`, max step `{eps00194['max_step']}`, log `{eps00194['folder']}/log.lammps`
- eps0000 comparable GPU smoke status: `{eps0000.get('status', 'not_run')}`, max step `{eps0000.get('max_step')}`, log `{eps0000.get('folder', '') + '/log.lammps' if eps0000 else None}`
- Production status: `{prod['status']}`
- Production PID: `{prod.get('pid')}`
- Production status JSON: `{prod.get('status_json')}`
"""


def production_worker(config_path: Path) -> int:
    config = json.loads(read_text(config_path))
    root = Path(config["production_root"])
    status_path = root / "production_worker_status.json"
    binary = Path(config["binary"])
    spec = CommandSpec(binary, tuple(config["kokkos_args"]))
    cases = [
        LammpsCase(
            "eps0000_production_50k",
            "eps0000 zhi=200 GPU production 50k",
            Path(config["eps0000_data"]),
            spec,
            (50000,),
            timeout_s=86400,
            include_computes=True,
            dump_mode="full",
            final_outputs=True,
        ),
        LammpsCase(
            "eps00194_production_50k",
            "eps00194 zhi=200 GPU production 50k",
            Path(config["eps00194_data"]),
            spec,
            (50000,),
            timeout_s=86400,
            include_computes=True,
            dump_mode="full",
            final_outputs=True,
        ),
    ]
    results = []
    write_runtime_json(status_path, {"status": "running", "timestamp": now(), "current_case": cases[0].key, "cases": []})
    for case in cases:
        write_runtime_json(status_path, {"status": "running", "timestamp": now(), "current_case": case.key, "cases": results})
        result = run_lammps_case(case, root)
        results.append(result)
        if result["status"] != "completed_clean":
            write_runtime_json(status_path, {"status": "failed", "timestamp": now(), "current_case": None, "cases": results})
            return 1
    write_runtime_json(status_path, {"status": "completed_clean", "timestamp": now(), "current_case": None, "cases": results})
    return 0


def choose_recovered_binary(repro: dict[str, Any], build: dict[str, Any]) -> tuple[Path | None, str]:
    if build.get("status") == "recovered_candidate" and build.get("binary"):
        return Path(build["binary"]), "post_build_probe"
    clean = [t for t in repro.get("tests", []) if t["status"] == "completed_clean" and t["target_step"] >= 1000]
    if clean:
        command = clean[0]["command"]
        launcher_len = 3 if command and str(command[0]).lower().endswith("mpiexec.exe") else 0
        return Path(command[launcher_len]), clean[0]["key"]
    return None, "none"


def write_final_root_report(
    start: dict[str, Any],
    preflight_data: dict[str, Any],
    audit: dict[str, Any],
    repro: dict[str, Any],
    build: dict[str, Any],
    gate: dict[str, Any] | None,
) -> dict[str, Any]:
    best_binary = (gate or {}).get("best_binary")
    eps00194 = (gate or {}).get("eps00194_gpu_smoke") or {}
    eps0000 = (gate or {}).get("eps0000_comparable_gpu_smoke") or {}
    production = (gate or {}).get("production") or {"status": "not_started"}
    status = "recovered" if eps00194.get("status") == "completed_clean" and eps0000.get("status") == "completed_clean" else "not recovered"
    if build.get("status") == "build_blocked":
        status = "build blocked"
    elif production.get("status") == "running":
        status = "production running"
    data = {
        "timestamp": now(),
        "gpu_recovery_status": status,
        "root_cause": infer_root_cause(repro, build),
        "best_binary": best_binary,
        "eps00194_gpu_smoke": eps00194 or None,
        "eps0000_comparable_gpu_smoke": eps0000 or None,
        "production": production,
        "reports": {
            "lane_start": start.get("written"),
            "preflight": "docs/reports/stageF_gpu_fix_environment_preflight.md",
            "build_audit": "docs/reports/stageF_gpu_fix_existing_builds_audit.md",
            "minimal_repro": "docs/reports/stageF_gpu_fix_minimal_repro_matrix.md",
            "build_attempt": "docs/reports/stageF_gpu_fix_build_attempt.md",
            "gate": "docs/reports/stageF_gpu_fix_smoke_and_production_gate.md" if gate else None,
        },
        "analysis": "not_run",
        "eps005": "not_launched",
    }
    md = f"""# Stage F GPU fix to production report

- Timestamp: {data['timestamp']}
- GPU recovery status: `{data['gpu_recovery_status']}`
- Root cause class: `{data['root_cause']}`
- Existing binary dynamic GPU path recovered: `{repro['dynamic_gpu_path_recovered']}`
- Build status: `{build['status']}`
- Best binary: `{data['best_binary']}`
- eps00194 GPU smoke: `{eps00194.get('status', 'not_run')}`, max step `{eps00194.get('max_step')}`
- eps0000 comparable GPU smoke: `{eps0000.get('status', 'not_run')}`, max step `{eps0000.get('max_step')}`
- Production: `{production.get('status')}`, PID `{production.get('pid')}`
- Analysis: not run.
- eps005/F1/F0_300A: not launched.

## Reports

- `docs/reports/stageF_gpu_fix_and_production_lane_start.md`
- `docs/reports/stageF_gpu_fix_environment_preflight.md`
- `docs/reports/stageF_gpu_fix_existing_builds_audit.md`
- `docs/reports/stageF_gpu_fix_minimal_repro_matrix.md`
- `docs/reports/stageF_gpu_fix_build_attempt.md`
- `docs/reports/stageF_gpu_fix_smoke_and_production_gate.md` if smoke gate ran
"""
    write_text(REPO / "agent_report_stageF_gpu_fix_to_production.md", md)
    write_json(REPORTS / "stageF_gpu_fix_to_production_summary.json", data)
    return data


def infer_root_cause(repro: dict[str, Any], build: dict[str, Any]) -> str:
    if build.get("status") == "build_blocked":
        return "build issue"
    if repro.get("dynamic_gpu_path_recovered"):
        return "unresolved"
    failed = [t for t in repro.get("tests", []) if t["key"].startswith("T7") and t["status"] == "failed"]
    if failed and all(t["status"] == "completed_clean" for t in repro.get("tests", []) if t["key"].startswith("T6")):
        return "MPI issue"
    if any("meam/kk" in json.dumps(t).lower() for t in repro.get("tests", [])):
        return "KOKKOS MEAM issue"
    return "existing binary issue"


def validate_outputs(new_script: Path) -> dict[str, Any]:
    py_files = [
        REPO / "scripts" / "prepare_stageF_boundary_patch_geometry.py",
        REPO / "analysis" / "python" / "stageF_boundary_stress_decay.py",
        REPO / "analysis" / "python" / "stageF_eps00194_lost_atom_forensic.py",
        new_script,
    ]
    py_compile = run_capture([sys.executable, "-m", "py_compile", *[str(p) for p in py_files if p.exists()]], cwd=REPO, timeout_s=120)
    json_reports = [
        REPORTS / "stageF_gpu_fix_and_production_lane_start.json",
        REPORTS / "stageF_gpu_fix_environment_preflight.json",
        REPORTS / "stageF_gpu_fix_existing_builds_audit.json",
        REPORTS / "stageF_gpu_fix_minimal_repro_matrix.json",
        REPORTS / "stageF_gpu_fix_build_attempt.json",
        REPORTS / "stageF_gpu_fix_to_production_summary.json",
    ]
    parsed = {}
    for path in json_reports:
        matches = [path] if path.exists() else sorted(path.parent.glob(f"{path.stem}_*{path.suffix}"))
        parsed[str(path)] = []
        for candidate in matches:
            try:
                json.loads(read_text(candidate))
                parsed[str(path)].append({"path": rel(candidate), "ok": True})
            except json.JSONDecodeError as exc:
                parsed[str(path)].append({"path": rel(candidate), "ok": False, "error": str(exc)})
    csv_checks = []
    for csv_path in REPORTS.glob("stageF*.csv"):
        try:
            first = read_text(csv_path).splitlines()[0] if read_text(csv_path).splitlines() else ""
            csv_checks.append({"path": rel(csv_path), "ok": True, "header": first})
        except OSError as exc:
            csv_checks.append({"path": rel(csv_path), "ok": False, "error": str(exc)})
    forbidden = {}
    for path in [
        REPO / "agent_report_stageF_gpu_fix_to_production.md",
        REPORTS / "stageF_gpu_fix_to_production_summary.json",
    ]:
        text = read_text(path).lower()
        forbidden[rel(path)] = [phrase for phrase in FORBIDDEN_PHRASES if phrase in text]
    processes = ps(
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match 'lmp|lammps|mpiexec' -or ($_.CommandLine -and $_.CommandLine -match 'lmp_kokkos|LAMMPS') } | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 4",
        timeout_s=30,
    )
    data = {
        "timestamp": now(),
        "py_compile": py_compile,
        "json_parse": parsed,
        "csv_read": csv_checks,
        "forbidden_phrase_scan": forbidden,
        "active_lammps_processes": processes,
        "project_git_status": run_capture(["git", "status", "--short"], cwd=REPO, timeout_s=30),
    }
    write_json(REPORTS / "stageF_gpu_fix_validation.json", data)
    write_text(REPORTS / "stageF_gpu_fix_validation.md", render_validation_md(data))
    return data


def render_validation_md(data: dict[str, Any]) -> str:
    forbidden_hits = {k: v for k, v in data["forbidden_phrase_scan"].items() if v}
    json_bad = [
        item
        for checks in data["json_parse"].values()
        for item in checks
        if not item.get("ok")
    ]
    return f"""# Stage F GPU fix validation

- Timestamp: {data['timestamp']}
- py_compile return code: `{data['py_compile']['returncode']}`
- JSON parse failures: `{json_bad}`
- CSV files checked: `{len(data['csv_read'])}`
- Forbidden phrase hits: `{forbidden_hits}`
- Active LAMMPS query return code: `{data['active_lammps_processes']['returncode']}`
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-worker", type=Path)
    parser.add_argument("--start-only", action="store_true")
    args = parser.parse_args()
    if args.production_worker:
        return production_worker(args.production_worker)

    start = create_lane_start_report()
    if args.start_only:
        print(json.dumps({"status": "start_report_written", "report": start.get("written")}, indent=2, ensure_ascii=False))
        return 0

    pre = preflight()
    audit = audit_existing_builds(pre)
    repro = minimal_repro_matrix()
    build = {"status": "not_attempted"}
    if not repro.get("dynamic_gpu_path_recovered"):
        build = attempt_rebuild(pre, audit)
    best_binary, source = choose_recovered_binary(repro, build)
    gate = None
    if best_binary:
        gate = promote_smokes_and_maybe_production(best_binary, source)
    summary = write_final_root_report(start, pre, audit, repro, build, gate)
    validation = validate_outputs(Path(__file__).resolve())
    print(
        json.dumps(
            {
                "gpu_recovery_status": summary["gpu_recovery_status"],
                "root_cause": summary["root_cause"],
                "best_binary": summary["best_binary"],
                "eps00194_gpu_smoke": (summary["eps00194_gpu_smoke"] or {}).get("status") if summary["eps00194_gpu_smoke"] else "not_run",
                "eps0000_comparable_gpu_smoke": (summary["eps0000_comparable_gpu_smoke"] or {}).get("status") if summary["eps0000_comparable_gpu_smoke"] else "not_run",
                "production": summary["production"].get("status"),
                "validation_py_compile": validation["py_compile"]["returncode"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
