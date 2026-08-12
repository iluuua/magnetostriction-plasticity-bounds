#!/usr/bin/env python3
"""Stage F eps00194 smoke failure diagnostics.

Runs only diagnostic gates in fresh debug folders. It does not launch production,
eps005, F1, or F0_300A.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "runs" / "stageF_F0_planar_100A_ppf_commensurate" / "20260630-010748"
CASE = RUN / "F0_planar_100A_comm_eps00194"
EPS0000 = RUN / "F0_planar_100A_comm_eps0000"
REPORTS = REPO / "docs" / "reports"
DATA = CASE / "equil" / "data.F0_planar_100A_comm_eps00194.common_cell_minimized"
EPS0000_DATA = EPS0000 / "equil" / "data.F0_planar_100A_comm_eps0000.relaxed"
POT_DIR = REPO / "potentials" / "meam" / "Jelinek_2012"
MEAMF = POT_DIR / "Jelinek_2012_meamf"
MEAM = POT_DIR / "Jelinek_2012_meam.alsimgcufe"
CPU_LMP = Path(r"C:\Users\dille\AppData\Local\LAMMPS 64-bit 22Jul2025-MSMPI\bin\lmp.exe")
MPIEXEC = Path(r"C:\Program Files\Microsoft MPI\Bin\mpiexec.exe")
GPU_LMP = Path(r"B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe")

FATAL_PATTERNS = [
    "ERROR",
    "nan",
    "NaN",
    "lost atoms",
    "Lost atoms",
    "cudaError",
    "CUDA error",
    "Cuda error",
    "illegal",
    "illegal memory",
    "segmentation",
    "Did not assign all atoms correctly",
    "Out of range atoms",
    "Neighbor list overflow",
    "MPI_ABORT",
    "Exception",
    "failed",
    "Killed",
]


@dataclass(frozen=True)
class DiagSpec:
    key: str
    folder: str
    kind: str
    input_name: str
    run_steps: int
    include_nvt: bool
    include_dump: bool = False
    include_pe: bool = False
    include_stress: bool = False
    restart: bool = False
    custom_fix: str | None = None


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
        if len(parts) != len(cols) or not re.match(r"^[-+]?\d+(?:\.\d+)?$", parts[0]):
            continue
        row: dict[str, Any] = {}
        ok = True
        for col, raw in zip(cols, parts):
            try:
                val = float(raw)
            except ValueError:
                ok = False
                break
            row[col] = int(val) if col in {"Step", "Atoms"} and val.is_integer() else val
        if ok:
            rows.append(row)
    return rows


def parse_run(folder: Path) -> dict[str, Any]:
    stdout = (folder / "stdout.log").read_text(encoding="utf-8", errors="replace") if (folder / "stdout.log").exists() else ""
    stderr = (folder / "stderr.log").read_text(encoding="utf-8", errors="replace") if (folder / "stderr.log").exists() else ""
    log = (folder / "log.lammps").read_text(encoding="utf-8", errors="replace") if (folder / "log.lammps").exists() else ""
    text = "\n".join([log, stdout, stderr])
    rows = thermo_rows(text)
    max_step = max([int(r["Step"]) for r in rows if "Step" in r], default=None)
    final = rows[-1] if rows else {}
    fatal = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for pat in FATAL_PATTERNS:
            if pat in line:
                if pat == "illegal" and "illegal memory" not in line and "illegal address" not in line:
                    continue
                fatal.append({"line": idx, "pattern": pat, "text": line.strip()})
                break
    return {
        "folder": rel(folder),
        "returncode_file": int((folder / "returncode.txt").read_text().strip()) if (folder / "returncode.txt").exists() else None,
        "max_step": max_step,
        "final": final,
        "fatal_matches": fatal,
        "fatal": bool(fatal),
        "loop_time": "Loop time" in text,
        "total_wall_time": "Total wall time" in text,
        "stdout_tail": "\n".join(stdout.splitlines()[-20:]),
        "stderr_tail": "\n".join(stderr.splitlines()[-20:]),
        "log_tail": "\n".join(log.splitlines()[-30:]),
    }


def common_header() -> str:
    return f"""units           metal
atom_style      atomic
boundary        p p f
read_data       {posix(DATA)}
pair_style      meam
pair_coeff      * * {posix(MEAMF)} AlS SiS MgS CuS FeS {posix(MEAM)} AlS FeS
neighbor        2.0 bin
neigh_modify    delay 0 every 1 check yes
timestep        0.001

region          bottom block INF INF INF INF INF 8.0 units box
group           bottom region bottom
group           mobile subtract all bottom
fix             hold bottom setforce 0.0 0.0 0.0
velocity        mobile create 300.0 88004 mom yes rot yes dist gaussian
"""


def input_for(spec: DiagSpec, folder: Path) -> str:
    lines = [common_header()]
    if spec.include_pe:
        lines.append("compute         pe_atom all pe/atom\n")
    if spec.include_stress:
        lines.append("compute         st all stress/atom NULL virial\n")
    if spec.custom_fix:
        lines.append(spec.custom_fix.rstrip() + "\n")
    elif spec.include_nvt:
        lines.append("fix             nvt_mobile mobile nvt temp 300.0 300.0 0.1\n")
    lines.append("thermo          1\n")
    lines.append("thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz\n")
    lines.append("thermo_modify   flush yes\n")
    if spec.include_dump:
        dump_cols = "id type x y z"
        if spec.include_pe:
            dump_cols += " c_pe_atom"
        if spec.include_stress:
            dump_cols += " c_st[1] c_st[2] c_st[3] c_st[4] c_st[5] c_st[6]"
        lines.append(f"dump            d1 all custom 100 {posix(folder / 'dump.debug.lammpstrj')} {dump_cols}\n")
        lines.append("dump_modify     d1 sort id\n")
    if spec.restart:
        lines.append(f"restart         500 {posix(folder / 'restart.debug.*')}\n")
    if spec.kind == "cpu":
        lines.append("run             0\n")
        lines.append("run             10\n")
        lines.append("run             100\n")
    else:
        lines.append(f"run             {spec.run_steps}\n")
    return "".join(lines)


def run_diag(spec: DiagSpec, timeout_s: int) -> dict[str, Any]:
    folder = CASE / spec.folder
    folder.mkdir(parents=True, exist_ok=True)
    input_path = folder / spec.input_name
    write(input_path, input_for(spec, folder))
    if spec.kind == "cpu":
        cmd = [str(MPIEXEC), "-np", "8", str(CPU_LMP), "-in", spec.input_name, "-log", "log.lammps"]
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = "6"
    else:
        cmd = [
            str(GPU_LMP),
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
            "-in",
            spec.input_name,
            "-log",
            "log.lammps",
        ]
        env = os.environ.copy()
    started = now()
    with (folder / "stdout.log").open("w", encoding="utf-8") as out, (folder / "stderr.log").open("w", encoding="utf-8") as err:
        try:
            cp = subprocess.run(cmd, cwd=str(folder), stdout=out, stderr=err, env=env, timeout=timeout_s)
            returncode = cp.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            returncode = 124
            timed_out = True
    write(folder / "returncode.txt", str(returncode))
    parsed = parse_run(folder)
    parsed.update(
        {
            "key": spec.key,
            "kind": spec.kind,
            "input": rel(input_path),
            "command": cmd,
            "started": started,
            "finished": now(),
            "timed_out": timed_out,
            "passed": returncode == 0 and not parsed["fatal"] and (parsed["max_step"] is not None),
        }
    )
    if spec.kind == "gpu" and spec.run_steps == 0:
        parsed["passed"] = returncode == 0 and not parsed["fatal"] and parsed["max_step"] == 0
    if spec.kind == "cpu":
        parsed["passed"] = returncode == 0 and not parsed["fatal"] and (parsed["max_step"] or -1) >= 100
    return parsed


def extract_failed_command() -> dict[str, Any]:
    return {
        "binary": str(GPU_LMP),
        "args": ["-k", "on", "g", "1", "-sf", "kk", "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "off", "-in", "in.smoke", "-log", "log.lammps"],
        "cwd": rel(CASE / "smoke"),
        "input": rel(CASE / "smoke" / "in.smoke"),
        "stderr_tail": ((CASE / "smoke" / "stderr.log").read_text(encoding="utf-8", errors="replace").splitlines()[-20:] if (CASE / "smoke" / "stderr.log").exists() else []),
        "log_tail": ((CASE / "smoke" / "log.lammps").read_text(encoding="utf-8", errors="replace").splitlines()[-40:] if (CASE / "smoke" / "log.lammps").exists() else []),
        "dump_step0_exists": (CASE / "smoke" / "dump.stageF_F0_planar_100A_comm_smoke.lammpstrj").exists(),
        "thermo_step0_printed": " 0      113295" in (CASE / "smoke" / "log.lammps").read_text(encoding="utf-8", errors="replace"),
    }


def write_debug_start(failed: dict[str, Any]) -> None:
    md = f"""# Stage F F0 commensurate ppf eps00194 debug start

- Timestamp: {now()}
- Failed command binary: `{failed['binary']}`
- KOKKOS args: `{' '.join(failed['args'][:-4])}`
- Input path: `{failed['input']}`
- Failed cwd: `{failed['cwd']}`
- Thermo step 0 printed: `{failed['thermo_step0_printed']}`
- Dump step 0 exists: `{failed['dump_step0_exists']}`
- Failure point: after read_data, neighbor setup, and thermo step 0; before completing the first dynamics step.

## stderr tail
```text
{chr(10).join(failed['stderr_tail'])}
```

## log tail
```text
{chr(10).join(failed['log_tail'])}
```
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_debug_start.md", md)


def write_cpu_report(cpu: dict[str, Any]) -> None:
    write_json(REPORTS / "stageF_F0_commensurate_ppf_eps00194_cpu_diag_summary.json", cpu)
    status = "PASS" if cpu["passed"] else "FAIL"
    md = f"""# Stage F F0 commensurate ppf eps00194 CPU diagnostic

- Timestamp: {now()}
- Status: **{status}**
- Folder: `{cpu['folder']}`
- Command return code: `{cpu['returncode_file']}`
- Max step: `{cpu['max_step']}`
- Fatal markers: `{len(cpu['fatal_matches'])}`

## Final thermo
```json
{json.dumps(cpu['final'], indent=2, ensure_ascii=False)}
```

## stderr tail
```text
{cpu['stderr_tail']}
```

## log tail
```text
{cpu['log_tail']}
```
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_cpu_diag_report.md", md)


def write_gpu_report(diags: list[dict[str, Any]]) -> None:
    first_fail = next((d for d in diags if not d["passed"]), None)
    summary = {"timestamp": now(), "diags": diags, "first_failing_diag": first_fail["key"] if first_fail else None}
    write_json(REPORTS / "stageF_F0_commensurate_ppf_eps00194_gpu_isolation_summary.json", summary)
    rows = [
        f"| {d['key']} | `{d['folder']}` | {d['returncode_file']} | {d['max_step']} | {d['passed']} | {len(d['fatal_matches'])} |"
        for d in diags
    ]
    md = """# Stage F F0 commensurate ppf eps00194 GPU isolation

| diag | folder | return code | max step | passed | fatal markers |
|---|---|---:|---:|---|---:|
""" + "\n".join(rows)
    if first_fail:
        md += f"\n\nFirst failing diag: **{first_fail['key']}**.\n"
        md += f"\n## First failure stderr tail\n```text\n{first_fail['stderr_tail']}\n```\n"
    else:
        md += "\n\nAll GPU diagnostics passed.\n"
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_gpu_isolation_report.md", md)


def write_fix_decision(cpu: dict[str, Any], gpu_diags: list[dict[str, Any]], smoke_retry: dict[str, Any] | None) -> str:
    first_fail = next((d for d in gpu_diags if not d["passed"]), None)
    if not cpu["passed"]:
        fix = "A"
        why = "CPU diagnostic failed, so data/minimization/CPU physics must be fixed before GPU."
        root = "CPU physics issue or data/minimization issue"
    elif first_fail and first_fail["key"] == "gpu_01":
        fix = "B"
        why = "CPU diagnostic passed, but minimal GPU pair-eval run0 failed."
        root = "GPU KOKKOS/MEAM issue"
    elif first_fail and first_fail["key"] == "gpu_05":
        fix = "C"
        why = "GPU dynamics/dump passed until stress/atom was added."
        root = "stress/atom dump issue"
    elif first_fail and first_fail["key"] == "gpu_02":
        extra = {d["key"]: d for d in gpu_diags}
        nve = extra.get("gpu_02a")
        nvt_cpu_fix = extra.get("gpu_02b")
        fix = "B"
        if nve and not nve["passed"]:
            root = "GPU KOKKOS dynamics issue before dump/stress"
            why = "CPU diagnostic passed and GPU run0 passed, but both NVT/KK and NVE/KK dynamics failed at/after step 0; use CPU or a different validated GPU path."
        elif nvt_cpu_fix and nvt_cpu_fix["passed"]:
            root = "GPU KOKKOS nvt/kk integration issue"
            why = "GPU run0 passed, NVT/KK failed, and CPU-side NVT with KOKKOS suffix disabled passed; avoid KOKKOS NVT for this case."
        else:
            root = "GPU KOKKOS NVT/dynamics issue"
            why = "CPU diagnostic passed and GPU run0 passed, but production-like NVT without dump/stress failed before step 1; use CPU or a different validated GPU path."
    elif first_fail:
        fix = "D"
        why = f"First GPU failure occurred at {first_fail['key']} under diagnostic settings."
        root = "GPU settings/dynamics issue"
    else:
        fix = "D"
        why = "CPU and GPU isolation ladder passed with safer neighbor policy."
        root = "input/settings issue in failed smoke likely resolved by regenerated diagnostic-safe input"
    md = f"""# Stage F F0 commensurate ppf eps00194 fix decision

- Timestamp: {now()}
- Root cause status: **{root}**
- Chosen fix: **{fix}**
- Why: {why}
- Smoke retry: `{smoke_retry['status'] if smoke_retry else 'not_run'}`
- Production gate: blocked unless smoke retry is completed clean.

No production, eps005, F1, or F0_300A was launched by this decision.
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_fix_decision.md", md)
    return fix


def smoke_retry_cpu_input(folder: Path) -> str:
    return f"""# Stage F eps00194 CPU smoke retry after GPU/KOKKOS dynamics failure.
units           metal
atom_style      atomic
boundary        p p f
read_data       {posix(DATA)}
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
dump            d1 all custom 1000 {posix(folder / 'dump.stageF_F0_planar_100A_comm_smoke_retry1.lammpstrj')} id type x y z c_pe_atom c_st[1] c_st[2] c_st[3] c_st[4] c_st[5] c_st[6]
dump_modify     d1 sort id
restart         2000 {posix(folder / 'restart.stageF_F0_planar_100A_comm_smoke_retry1.*')}
run             10000
write_restart   {posix(folder / 'restart.stageF_F0_planar_100A_comm_smoke_retry1.final')}
write_data      {posix(folder / 'data.stageF_F0_planar_100A_comm_smoke_retry1.final')}
"""


def run_smoke_retry() -> dict[str, Any]:
    folder = CASE / "smoke_retry1"
    folder.mkdir(parents=True, exist_ok=True)
    input_path = folder / "in.smoke_retry1"
    write(input_path, smoke_retry_cpu_input(folder))
    cmd = [str(MPIEXEC), "-np", "8", str(CPU_LMP), "-in", "in.smoke_retry1", "-log", "log.lammps"]
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "6"
    with (folder / "stdout.log").open("w", encoding="utf-8") as out, (folder / "stderr.log").open("w", encoding="utf-8") as err:
        try:
            cp = subprocess.run(cmd, cwd=str(folder), stdout=out, stderr=err, env=env, timeout=10800)
            returncode = cp.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            returncode = 124
            timed_out = True
    write(folder / "returncode.txt", str(returncode))
    result = parse_run(folder)
    result.update(
        {
            "key": "smoke_retry1",
            "kind": "cpu_smoke_retry",
            "input": rel(input_path),
            "command": cmd,
            "timed_out": timed_out,
            "passed": returncode == 0 and not result["fatal"] and result["max_step"] == 10000,
        }
    )
    final_restart = folder / "restart.stageF_F0_planar_100A_comm_smoke_retry1.final"
    final_data = folder / "data.stageF_F0_planar_100A_comm_smoke_retry1.final"
    status = "completed_clean" if result["passed"] and result["max_step"] == 10000 and final_restart.exists() and final_data.exists() else ("failed" if not result["passed"] else "incomplete_outputs")
    result["status"] = status
    result["final_restart_exists"] = final_restart.exists()
    result["final_data_exists"] = final_data.exists()
    write_json(REPORTS / "stageF_F0_commensurate_ppf_eps00194_smoke_retry1_summary.json", result)
    md = f"""# Stage F F0 commensurate ppf eps00194 smoke_retry1

- Timestamp: {now()}
- Runtime path: CPU LAMMPS fallback after GPU/KOKKOS dynamics failure.
- Status: **{status}**
- Folder: `{rel(folder)}`
- Max step: `{result['max_step']}`
- Return code: `{result['returncode_file']}`
- Final restart exists: `{result['final_restart_exists']}`
- Final data exists: `{result['final_data_exists']}`
- Fatal markers: `{len(result['fatal_matches'])}`

## stderr tail
```text
{result['stderr_tail']}
```

## log tail
```text
{result['log_tail']}
```
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_smoke_retry1_report.md", md)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-smoke-retry", action="store_true", help="Run smoke_retry1 only if CPU and GPU ladder pass.")
    args = parser.parse_args()

    failed = extract_failed_command()
    write_debug_start(failed)

    cpu = run_diag(
        DiagSpec(
            key="cpu_diag",
            folder="debug_cpu_step0",
            kind="cpu",
            input_name="in.cpu_diag",
            run_steps=100,
            include_nvt=True,
        ),
        timeout_s=1800,
    )
    write_cpu_report(cpu)

    gpu_diags: list[dict[str, Any]] = []
    if cpu["passed"]:
        specs = [
            DiagSpec("gpu_01", "debug_gpu_01_run0_no_dump_no_stress", "gpu", "in.gpu_diag", 0, False),
            DiagSpec("gpu_02", "debug_gpu_02_run100_no_dump_no_stress", "gpu", "in.gpu_diag", 100, True),
            DiagSpec("gpu_03", "debug_gpu_03_run100_dump_xyz", "gpu", "in.gpu_diag", 100, True, include_dump=True),
            DiagSpec("gpu_04", "debug_gpu_04_run100_dump_pe_atom", "gpu", "in.gpu_diag", 100, True, include_dump=True, include_pe=True),
            DiagSpec("gpu_05", "debug_gpu_05_run100_dump_stress_atom", "gpu", "in.gpu_diag", 100, True, include_dump=True, include_pe=True, include_stress=True),
            DiagSpec("gpu_06", "debug_gpu_06_run1000_full_like_smoke", "gpu", "in.gpu_diag", 1000, True, include_dump=True, include_pe=True, include_stress=True, restart=True),
        ]
        for spec in specs:
            result = run_diag(spec, timeout_s=2400)
            gpu_diags.append(result)
            if not result["passed"]:
                if spec.key == "gpu_02":
                    extra_specs = [
                        DiagSpec(
                            "gpu_02a",
                            "debug_gpu_02a_run100_nve_no_dump_no_stress",
                            "gpu",
                            "in.gpu_diag",
                            100,
                            False,
                            custom_fix="fix             nve_mobile mobile nve",
                        ),
                        DiagSpec(
                            "gpu_02b",
                            "debug_gpu_02b_run100_nvt_suffix_off_no_dump_no_stress",
                            "gpu",
                            "in.gpu_diag",
                            100,
                            False,
                            custom_fix="suffix          off\nfix             nvt_mobile mobile nvt temp 300.0 300.0 0.1",
                        ),
                    ]
                    for extra in extra_specs:
                        gpu_diags.append(run_diag(extra, timeout_s=2400))
                break
    write_gpu_report(gpu_diags)

    smoke_retry: dict[str, Any] | None = None
    first_gpu_fail = next((d for d in gpu_diags if not d["passed"]), None)
    if args.run_smoke_retry and cpu["passed"] and first_gpu_fail is not None:
        smoke_retry = run_smoke_retry()
    fix = write_fix_decision(cpu, gpu_diags, smoke_retry)

    print(
        json.dumps(
            {
                "cpu_passed": cpu["passed"],
                "gpu_diags": [(d["key"], d["passed"], d["max_step"]) for d in gpu_diags],
                "first_gpu_fail": next((d["key"] for d in gpu_diags if not d["passed"]), None),
                "fix": fix,
                "smoke_retry": smoke_retry["status"] if smoke_retry else "not_run",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
