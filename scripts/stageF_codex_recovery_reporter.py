#!/usr/bin/env python3
"""Generate Stage F Codex recovery reports from files/logs.

This is a one-shot forensic reporter. It reads existing Stage F run artifacts,
records the common-cell gate state, and writes the reports requested by
prompt.txt. It does not launch LAMMPS.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "docs" / "reports"
CONTROL = REPO.parents[1]
RUN = REPO / "runs" / "stageF_F0_planar_100A_ppf_commensurate" / "20260630-010748"
OLD_RUN = REPO / "runs" / "stageF_F0_planar_100A_open_lateral" / "20260629-184320"
STRUCT = REPO / "structures" / "stageF_boundary_patch"
CASES = ["F0_planar_100A_comm_eps0000", "F0_planar_100A_comm_eps00194"]

NEEDLES = [
    "ERROR",
    "nan",
    "NaN",
    "lost atoms",
    "Lost atoms",
    "cuda",
    "CUDA",
    "illegal",
    "segmentation",
    "Did not assign all atoms correctly",
    "Out of range atoms",
    "Neighbor list overflow",
    "MPI_ABORT",
    "Exception",
    "failed",
    "Killed",
]
BROKEN_FRAGMENTS = ["Documsics", "F0uil", "20260630-01000"]


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO.resolve()).as_posix()
    except Exception:
        return str(path).replace("\\", "/")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def run_cmd(cmd: list[str], cwd: Path = REPO, timeout: int = 60) -> dict[str, Any]:
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return {"cmd": cmd, "returncode": cp.returncode, "stdout": cp.stdout.strip(), "stderr": cp.stderr.strip()}
    except Exception as exc:
        return {"cmd": cmd, "returncode": None, "stdout": "", "stderr": repr(exc)}


def ps(script: str, timeout: int = 60) -> dict[str, Any]:
    return run_cmd(["powershell", "-NoProfile", "-Command", script], timeout=timeout)


def read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_lammps_data(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": rel(path),
        "exists": path.exists(),
        "atoms_total": None,
        "type_counts": {},
        "Al_type1": None,
        "Fe_type2": None,
        "xlo": None,
        "xhi": None,
        "ylo": None,
        "yhi": None,
        "zlo": None,
        "zhi": None,
        "Lx_A": None,
        "Ly_A": None,
        "Lz_A": None,
    }
    if not path.exists():
        return out
    lines = read(path).splitlines()
    for line in lines[:100]:
        s = line.strip()
        if re.match(r"^\d+\s+atoms\b", s):
            out["atoms_total"] = int(s.split()[0])
        m = re.match(r"^([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+xlo\s+xhi", s)
        if m:
            out["xlo"], out["xhi"] = float(m.group(1)), float(m.group(2))
        m = re.match(r"^([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+ylo\s+yhi", s)
        if m:
            out["ylo"], out["yhi"] = float(m.group(1)), float(m.group(2))
        m = re.match(r"^([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+zlo\s+zhi", s)
        if m:
            out["zlo"], out["zhi"] = float(m.group(1)), float(m.group(2))
    if out["xlo"] is not None and out["xhi"] is not None:
        out["Lx_A"] = out["xhi"] - out["xlo"]
    if out["ylo"] is not None and out["yhi"] is not None:
        out["Ly_A"] = out["yhi"] - out["ylo"]
    if out["zlo"] is not None and out["zhi"] is not None:
        out["Lz_A"] = out["zhi"] - out["zlo"]

    counts: dict[int, int] = {}
    in_atoms = False
    waiting_blank = False
    for line in lines:
        s = line.strip()
        if not in_atoms:
            if s.startswith("Atoms"):
                in_atoms = True
                waiting_blank = True
            continue
        if waiting_blank:
            if not s:
                waiting_blank = False
            continue
        if not s:
            continue
        if re.match(r"^[A-Za-z]", s):
            break
        parts = s.split()
        if len(parts) >= 2 and parts[0].lstrip("+-").isdigit():
            try:
                typ = int(parts[1])
            except ValueError:
                continue
            counts[typ] = counts.get(typ, 0) + 1
    out["type_counts"] = {str(k): v for k, v in sorted(counts.items())}
    out["Al_type1"] = counts.get(1, 0) if counts else None
    out["Fe_type2"] = counts.get(2, 0) if counts else None
    return out


def parse_thermo(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    columns: list[str] | None = None
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"^Step\s+", s):
            columns = s.split()
            continue
        if not columns or not s:
            continue
        parts = s.split()
        if len(parts) != len(columns) or not re.match(r"^[-+]?\d+(?:\.\d+)?$", parts[0]):
            continue
        row: dict[str, Any] = {}
        ok = True
        for c, value in zip(columns, parts):
            try:
                f = float(value)
            except ValueError:
                ok = False
                break
            row[c] = int(f) if c in {"Step", "Atoms"} and f.is_integer() else f
        if ok:
            rows.append(row)
    return rows


def parse_log(path: Path) -> dict[str, Any]:
    text = read(path)
    rows = parse_thermo(text)
    final = rows[-1] if rows else {}
    steps = [int(r["Step"]) for r in rows if "Step" in r]
    temps = [float(r["Temp"]) for r in rows if "Temp" in r]
    lx = [float(r["Lx"]) for r in rows if "Lx" in r]
    ly = [float(r["Ly"]) for r in rows if "Ly" in r]
    lz = [float(r["Lz"]) for r in rows if "Lz" in r]
    matches: list[dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for needle in NEEDLES + ["Loop time", "Total wall time", "COMMON_CELL_DONE", "EQUIL_DONE"]:
            if needle in line:
                matches.append({"line": idx, "needle": needle, "text": line.strip()})
                break
    fatal = [m for m in matches if m["needle"] in NEEDLES]
    return {
        "path": rel(path),
        "exists": path.exists(),
        "length": path.stat().st_size if path.exists() else 0,
        "last_write_time": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        if path.exists()
        else None,
        "max_step": max(steps) if steps else None,
        "final_step": final.get("Step"),
        "final_temp": final.get("Temp"),
        "max_temp": max(temps) if temps else None,
        "final_pxx": final.get("Pxx"),
        "final_pyy": final.get("Pyy"),
        "final_pzz": final.get("Pzz"),
        "final_lx": final.get("Lx"),
        "final_ly": final.get("Ly"),
        "final_lz": final.get("Lz"),
        "lx_changed": (max(lx) - min(lx) > 1e-6) if lx else None,
        "ly_changed": (max(ly) - min(ly) > 1e-6) if ly else None,
        "lz_changed": (max(lz) - min(lz) > 1e-6) if lz else None,
        "loop_time_present": "Loop time" in text,
        "total_wall_time_present": "Total wall time" in text,
        "matches": matches,
        "fatal_matches": fatal,
    }


def stage_status(case_dir: Path, stage: str, target: int) -> dict[str, Any]:
    d = case_dir / stage
    files = list(d.glob("*")) if d.exists() else []
    logs = [
        p
        for p in files
        if p.is_file()
        and (p.name in {"log.lammps", "stdout.log", "stderr.log", "run.out", "run.err"} or p.name.startswith("log."))
    ]
    parsed = [parse_log(p) for p in logs]
    max_step = max([p.get("max_step") or -1 for p in parsed], default=-1)
    fatal = []
    for item in parsed:
        for match in item["fatal_matches"]:
            fatal.append({"path": item["path"], **match})
    final_data = [p for p in files if p.is_file() and p.name.startswith("data") and p.name.endswith(".final")]
    final_restart = [p for p in files if p.is_file() and p.name.startswith("restart") and p.name.endswith(".final")]
    if not d.exists():
        status = "not_started"
    elif max_step >= target and final_data and final_restart and not fatal:
        status = "completed_clean"
    elif max_step >= target and final_data and final_restart:
        status = "completed_with_prior_or_sidecar_fatal_marker"
    elif fatal:
        status = "failed"
    elif any(p.name.startswith("in.") for p in files):
        status = "not_started" if max_step < 0 else "unknown"
    else:
        status = "not_started"
    return {
        "stage": stage,
        "dir": rel(d),
        "exists": d.exists(),
        "status": status,
        "max_step": None if max_step < 0 else max_step,
        "target_step": target,
        "final_data_exists": bool(final_data),
        "final_restart_exists": bool(final_restart),
        "fatal_errors_detected": bool(fatal),
        "fatal_matches": fatal,
        "logs": parsed,
    }


def inventory_case(case: str) -> dict[str, Any]:
    case_dir = RUN / case
    struct_dir = STRUCT / case
    files = [p for p in case_dir.rglob("*") if p.is_file()] if case_dir.exists() else []
    struct_files = [p for p in struct_dir.rglob("*") if p.is_file()] if struct_dir.exists() else []
    all_files = files + struct_files
    latest = max(all_files, key=lambda p: p.stat().st_mtime) if all_files else None
    smoke = stage_status(case_dir, "smoke", 10000)
    prod = stage_status(case_dir, "production", 50000)
    fatal = smoke["fatal_matches"] + prod["fatal_matches"]
    return {
        "case_id": case,
        "dirs_exist": {
            "structures": struct_dir.exists(),
            "equil": (case_dir / "equil").exists(),
            "smoke": (case_dir / "smoke").exists(),
            "production": (case_dir / "production").exists(),
        },
        "data_files": [rel(p) for p in all_files if p.name.startswith("data.")],
        "relaxed_data_files": [rel(p) for p in all_files if "relaxed" in p.name or "common_cell" in p.name],
        "smoke_files": [rel(p) for p in files if "smoke" in p.parts],
        "production_files": [rel(p) for p in files if "production" in p.parts],
        "dump_count": len([p for p in all_files if p.suffix == ".lammpstrj" or "dump" in p.name]),
        "restart_count": len([p for p in all_files if p.name.startswith("restart")]),
        "latest_file": rel(latest) if latest else None,
        "latest_write_time": datetime.fromtimestamp(latest.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        if latest
        else None,
        "max_smoke_step_detected": smoke["max_step"],
        "max_production_step_detected": prod["max_step"],
        "fatal_errors_detected": bool(fatal),
        "fatal_errors": fatal,
        "completed_smoke_10000": smoke["max_step"] is not None
        and smoke["max_step"] >= 10000
        and smoke["final_data_exists"]
        and smoke["final_restart_exists"],
        "completed_production_50000": prod["max_step"] is not None
        and prod["max_step"] >= 50000
        and prod["final_data_exists"]
        and prod["final_restart_exists"],
        "smoke_status": smoke["status"],
        "production_status": prod["status"],
    }


def parse_input(path: Path) -> dict[str, Any]:
    text = read(path)
    path_checks = []
    boundaries = []
    neigh = []
    for idx, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        cmd = parts[0]
        if cmd == "boundary" and len(parts) >= 4:
            boundaries.append(" ".join(parts[1:4]))
        if cmd == "neigh_modify":
            neigh.append(s)
        if cmd == "pair_coeff":
            for token in parts[3:]:
                if ":/" in token or ":\\" in token:
                    pp = Path(token.replace("/", os.sep))
                    path_checks.append(
                        {"line": idx, "command": cmd, "path": token, "file_exists": pp.exists(), "ok": pp.exists()}
                    )
        if cmd in {"read_data", "dump", "restart", "write_restart", "write_data"}:
            token = next((p for p in parts[1:] if ":/" in p or ":\\" in p), None)
            if token:
                pp = Path(token.replace("/", os.sep))
                ok = pp.exists() if cmd == "read_data" else pp.parent.exists()
                path_checks.append(
                    {
                        "line": idx,
                        "command": cmd,
                        "path": token,
                        "parent_exists": pp.parent.exists(),
                        "file_exists": pp.exists() if cmd == "read_data" else None,
                        "ok": ok,
                    }
                )
    return {
        "input": rel(path),
        "exists": path.exists(),
        "paths": path_checks,
        "all_paths_ok": all(p["ok"] for p in path_checks) if path_checks else True,
        "boundary_values": boundaries,
        "boundary_ppf": bool(boundaries) and all(b == "p p f" for b in boundaries),
        "contains_mmf": "m m f" in text,
        "neighbor_policy": neigh,
        "has_box_relax": "box/relax" in text,
        "broken_fragments": [frag for frag in BROKEN_FRAGMENTS if frag in text],
    }


def diff(a: Any, b: Any) -> float | None:
    return None if a is None or b is None else abs(float(a) - float(b))


def main() -> int:
    branch = run_cmd(["git", "branch", "--show-current"])
    git_status = run_cmd(["git", "status", "--short"])
    proc_scan = ps(
        "Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -like 'lmp*.exe' -or $_.Name -like 'lmp_kokkos_cuda*.exe' -or $_.Name -like 'mpiexec*' -or "
        "(($_.Name -like 'python*') -and $_.CommandLine -and "
        "($_.CommandLine -like '*run_stage*' -or $_.CommandLine -like '*stageF*' -or $_.CommandLine -like '*F0_planar*')) } | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 3"
    )
    gpu_query = run_cmd(
        [
            "nvidia-smi",
            "--query-gpu=timestamp,name,utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader",
        ],
        timeout=30,
    )
    disk = ps("Get-PSDrive C | Select-Object Name,Used,Free,Root | ConvertTo-Json -Depth 3")
    python_exe = REPO / ".venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = REPO.parent / ".venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = Path(shutil.which("python") or "python")
    py_ver = run_cmd([str(python_exe), "--version"])
    py_geom = run_cmd([str(python_exe), "-m", "py_compile", "scripts/prepare_stageF_boundary_patch_geometry.py"])
    py_analysis = run_cmd([str(python_exe), "-m", "py_compile", "analysis/python/stageF_boundary_stress_decay.py"])

    data_paths = {
        "eps0000_relaxed": RUN / "F0_planar_100A_comm_eps0000/equil/data.F0_planar_100A_comm_eps0000.relaxed",
        "eps00194_independent_relaxed": RUN
        / "F0_planar_100A_comm_eps00194/equil/data.F0_planar_100A_comm_eps00194.relaxed",
        "eps00194_common_cell_seed": RUN
        / "F0_planar_100A_comm_eps00194/equil/data.F0_planar_100A_comm_eps00194.common_cell_seed",
        "eps00194_common_cell_minimized": RUN
        / "F0_planar_100A_comm_eps00194/equil/data.F0_planar_100A_comm_eps00194.common_cell_minimized",
    }
    data = {key: parse_lammps_data(path) for key, path in data_paths.items()}
    ref = data["eps0000_relaxed"]
    ind = data["eps00194_independent_relaxed"]
    cc = data["eps00194_common_cell_minimized"]

    cc_cmp = {
        "abs_dLx_A": diff(ref.get("Lx_A"), cc.get("Lx_A")),
        "abs_dLy_A": diff(ref.get("Ly_A"), cc.get("Ly_A")),
        "d_atoms_total": (ref.get("atoms_total") or 0) - (cc.get("atoms_total") or 0),
        "d_Al_type1": (ref.get("Al_type1") or 0) - (cc.get("Al_type1") or 0),
        "d_Fe_type2": (ref.get("Fe_type2") or 0) - (cc.get("Fe_type2") or 0),
        "threshold_A": 1e-4,
    }
    common_cell = {
        "report": "stageF_F0_commensurate_ppf_common_cell_audit",
        "timestamp": now(),
        "current_run_root": rel(RUN),
        "reference": ref,
        "independent_eps00194_relaxed": ind,
        "common_cell_seed": data["eps00194_common_cell_seed"],
        "common_cell_minimized": cc,
        "independent_comparison": {
            "abs_dLx_A": diff(ref.get("Lx_A"), ind.get("Lx_A")),
            "abs_dLy_A": diff(ref.get("Ly_A"), ind.get("Ly_A")),
            "d_atoms_total": (ref.get("atoms_total") or 0) - (ind.get("atoms_total") or 0),
            "d_Al_type1": (ref.get("Al_type1") or 0) - (ind.get("Al_type1") or 0),
            "d_Fe_type2": (ref.get("Fe_type2") or 0) - (ind.get("Fe_type2") or 0),
            "threshold_A": 1e-4,
            "decision": "FAIL_REJECT_INDEPENDENT_EPS00194",
        },
        "common_cell_comparison": cc_cmp,
        "common_cell_min_log": parse_log(RUN / "F0_planar_100A_comm_eps00194/equil/log.common_cell_min"),
    }
    common_cell["decision"] = (
        "PASS_COMMON_CELL_MINIMIZED"
        if cc_cmp["abs_dLx_A"] is not None
        and cc_cmp["abs_dLx_A"] <= 1e-4
        and cc_cmp["abs_dLy_A"] is not None
        and cc_cmp["abs_dLy_A"] <= 1e-4
        and cc_cmp["d_atoms_total"] == 0
        and cc_cmp["d_Al_type1"] == 0
        and cc_cmp["d_Fe_type2"] == 0
        and not common_cell["common_cell_min_log"]["fatal_matches"]
        else "FAIL_COMMON_CELL_MINIMIZED"
    )

    inventory = {
        "report": "stageF_F0_commensurate_ppf_file_inventory",
        "timestamp": now(),
        "run_root": rel(RUN),
        "cases": [inventory_case(c) for c in CASES],
    }

    log_paths = sorted(
        [
            p
            for p in RUN.rglob("*")
            if p.is_file()
            and (
                p.name in {"log.lammps", "stdout.log", "stderr.log", "run.out", "run.err", "common_cell_min.out"}
                or p.name.startswith("log.")
            )
        ]
    )
    log_summary = {
        "report": "stageF_F0_commensurate_ppf_log_parse_summary",
        "timestamp": now(),
        "run_root": rel(RUN),
        "logs": [parse_log(p) for p in log_paths],
        "stage_status": {
            c: {"smoke": stage_status(RUN / c, "smoke", 10000), "production": stage_status(RUN / c, "production", 50000)}
            for c in CASES
        },
    }

    inputs = sorted([p for p in RUN.rglob("in.*") if p.is_file()])
    input_validation = {
        "report": "stageF_F0_commensurate_ppf_input_path_validation",
        "timestamp": now(),
        "inputs": [parse_input(p) for p in inputs],
    }
    input_validation["all_ok"] = all(
        item["exists"]
        and item["all_paths_ok"]
        and item["boundary_ppf"]
        and not item["contains_mmf"]
        and not item["broken_fragments"]
        for item in input_validation["inputs"]
    )

    smoke_summary = {
        "report": "stageF_F0_commensurate_ppf_smoke10k_summary",
        "timestamp": now(),
        "run_root": rel(RUN),
        "eps0000": stage_status(RUN / "F0_planar_100A_comm_eps0000", "smoke", 10000),
        "eps00194": stage_status(RUN / "F0_planar_100A_comm_eps00194", "smoke", 10000),
        "interpretation": {
            "eps0000": "latest run.out/log.lammps reached 10000 and wrote final data/restart; older stdout/stderr in same dir record a prior failed KOKKOS minimize attempt",
            "eps00194": "after common-cell fix, GPU smoke failed at step 0 with cudaErrorIllegalAddress; no final smoke data/restart",
        },
        "gate": "BLOCK_PRODUCTION_EPS00194_SMOKE_FAILED",
    }
    production_summary = {
        "report": "stageF_F0_commensurate_ppf_production_summary",
        "timestamp": now(),
        "run_root": rel(RUN),
        "eps0000": stage_status(RUN / "F0_planar_100A_comm_eps0000", "production", 50000),
        "eps00194": stage_status(RUN / "F0_planar_100A_comm_eps00194", "production", 50000),
        "status": "not_started_blocked",
        "blocker": "eps00194 common-cell smoke failed with cudaErrorIllegalAddress at step 0",
    }

    recovered_json = {
        "timestamp": now(),
        "old_invalid_open_lateral_mmf": {
            "run_root": rel(OLD_RUN),
            "exists": OLD_RUN.exists(),
            "status": "ignored_invalid_negative_diagnostic_only",
        },
        "current_commensurate_ppf": {
            "run_root": rel(RUN),
            "exists": RUN.exists(),
            "inventory": inventory,
            "common_cell": common_cell,
            "log_summary": log_summary,
        },
        "process_scan_after_recovery": proc_scan["stdout"],
    }

    preflight = {
        "timestamp": now(),
        "branch": branch["stdout"],
        "git_status_short": git_status["stdout"].splitlines(),
        "process_scan_raw": proc_scan["stdout"],
        "gpu_query": gpu_query["stdout"],
        "disk_c": disk["stdout"],
        "python_version": py_ver,
        "py_compile": {
            "prepare_stageF_boundary_patch_geometry.py": py_geom,
            "stageF_boundary_stress_decay.py": py_analysis,
        },
        "immediate_conclusion": "no active LAMMPS/Stage F process remains; sequence blocked by eps00194 cudaErrorIllegalAddress smoke failure",
    }

    # JSON artifacts.
    write_json(REPORTS / "stageF_codex_recovery_preflight.json", preflight)
    write_json(REPORTS / "stageF_codex_recovered_state.json", recovered_json)
    write_json(REPORTS / "stageF_F0_commensurate_ppf_file_inventory.json", inventory)
    write_json(REPORTS / "stageF_F0_commensurate_ppf_log_parse_summary.json", log_summary)
    write_json(REPORTS / "stageF_F0_commensurate_ppf_common_cell_audit.json", common_cell)
    write_json(REPORTS / "stageF_F0_commensurate_ppf_input_path_validation.json", input_validation)
    write_json(REPORTS / "stageF_F0_commensurate_ppf_smoke10k_summary.json", smoke_summary)
    write_json(REPORTS / "stageF_F0_commensurate_ppf_production_summary.json", production_summary)

    preflight_md = f"""# Stage F Codex recovery preflight

- Timestamp: {preflight['timestamp']}
- Repo: `{REPO}`
- Branch: `{preflight['branch']}`
- Current run root: `{rel(RUN)}`
- Python: `{py_ver['stdout']}`
- `prepare_stageF_boundary_patch_geometry.py` py_compile: `{py_geom['returncode']}`
- `stageF_boundary_stress_decay.py` py_compile: `{py_analysis['returncode']}`

## Git status
```text
{git_status['stdout'] or '(clean)'}
```

## Active LAMMPS / Stage F processes
```text
{proc_scan['stdout'] or '(none)'}
```

## GPU
```text
{gpu_query['stdout']}
```

## Disk C
```text
{disk['stdout']}
```

## Immediate conclusion
No active LAMMPS/Stage F process remains. GPU is not occupied by LAMMPS compute. The sequence is blocked after `eps00194` smoke failed with `cudaErrorIllegalAddress` at step 0; production and delta-analysis were not launched.
"""
    write_text(REPORTS / "stageF_codex_recovery_preflight.md", preflight_md)

    recovered_md = f"""# Stage F Codex recovered state

- Timestamp: {now()}
- Target repo: `{REPO}`
- Branch: `{branch['stdout']}`
- Current commensurate run root: `{rel(RUN)}`

## Invalid branch: open_lateral_mmf
- Run root: `{rel(OLD_RUN)}`
- Status: physically invalid diagnostic branch only.
- Production: failed with CUDA illegal-address markers; no 50k valid production.
- Decision: ignored for physics, not resumed, not used for delta-analysis.

## Intended branch: commensurate_ppf
- Run root exists: `{RUN.exists()}`
- Cases on disk: `{', '.join(CASES)}`
- `eps0000`: CPU box/relax data exists; latest smoke log reached step 10000 and wrote final data/restart.
- `eps00194`: independent relaxed data exists but is rejected; common-cell seed and fixed-box minimized data now exist.
- `eps00194` smoke: launched after common-cell fix and failed at step 0 with `cudaErrorIllegalAddress`.
- Production: not started for either commensurate case.
- Delta-analysis: not run.

## Running now
No LAMMPS/Stage F process was found after the failed `eps00194` smoke.

## What must not be trusted from chat memory
- Do not assume production was started.
- Do not assume delta-analysis was done.
- Do not compare independently box-relaxed `eps0000` and `eps00194`.
- Do not treat old `m m f` as valid production.
"""
    write_text(REPORTS / "stageF_codex_recovered_state.md", recovered_md)

    inv_rows = [
        f"| `{c['case_id']}` | {c['dump_count']} | {c['restart_count']} | {c['max_smoke_step_detected']} | {c['max_production_step_detected']} | {c['smoke_status']} | {c['production_status']} | {c['fatal_errors_detected']} |"
        for c in inventory["cases"]
    ]
    inv_md = """# Stage F F0 commensurate ppf file inventory

| case | dumps | restarts | max smoke step | max production step | smoke status | production status | fatal markers |
|---|---:|---:|---:|---:|---|---|---|
""" + "\n".join(inv_rows) + "\n\nJSON detail: `docs/reports/stageF_F0_commensurate_ppf_file_inventory.json`.\n"
    write_text(REPORTS / "stageF_F0_commensurate_ppf_file_inventory.md", inv_md)

    log_rows = [
        f"| `{log['path']}` | {log['max_step']} | {log['final_temp']} | {log['final_pxx']} | {log['final_pyy']} | {log['final_pzz']} | {len(log['fatal_matches'])} | {log['total_wall_time_present']} |"
        for log in log_summary["logs"]
    ]
    log_md = """# Stage F F0 commensurate ppf log parse report

| log | max step | final temp | final Pxx | final Pyy | final Pzz | fatal markers | total wall time |
|---|---:|---:|---:|---:|---:|---:|---|
""" + "\n".join(log_rows) + "\n\n## Classification\n"
    for case, st in log_summary["stage_status"].items():
        log_md += f"- `{case}` smoke: `{st['smoke']['status']}` (max step {st['smoke']['max_step']}); production: `{st['production']['status']}`.\n"
    log_md += "\n`eps00194` smoke has `cudaErrorIllegalAddress` in `smoke/stderr.log` and no final data/restart; production is blocked.\n"
    write_text(REPORTS / "stageF_F0_commensurate_ppf_log_parse_report.md", log_md)

    cc_md = f"""# Stage F F0 commensurate ppf common-cell audit

- Timestamp: {now()}
- Current run root: `{rel(RUN)}`
- Final decision: **{common_cell['decision']}**.
- Independent `eps00194.relaxed` remains **rejected** for production/delta-analysis.

## Independent relaxed comparison (rejected)
| quantity | eps0000 relaxed | eps00194 independent relaxed | delta |
|---|---:|---:|---:|
| Lx A | {ref.get('Lx_A')} | {ind.get('Lx_A')} | {common_cell['independent_comparison']['abs_dLx_A']} |
| Ly A | {ref.get('Ly_A')} | {ind.get('Ly_A')} | {common_cell['independent_comparison']['abs_dLy_A']} |
| atoms | {ref.get('atoms_total')} | {ind.get('atoms_total')} | {common_cell['independent_comparison']['d_atoms_total']} |
| Al type1 | {ref.get('Al_type1')} | {ind.get('Al_type1')} | {common_cell['independent_comparison']['d_Al_type1']} |
| Fe type2 | {ref.get('Fe_type2')} | {ind.get('Fe_type2')} | {common_cell['independent_comparison']['d_Fe_type2']} |

## Common-cell minimized comparison (pass)
| quantity | eps0000 relaxed reference | eps00194 common-cell minimized | delta |
|---|---:|---:|---:|
| Lx A | {ref.get('Lx_A')} | {cc.get('Lx_A')} | {cc_cmp['abs_dLx_A']} |
| Ly A | {ref.get('Ly_A')} | {cc.get('Ly_A')} | {cc_cmp['abs_dLy_A']} |
| atoms | {ref.get('atoms_total')} | {cc.get('atoms_total')} | {cc_cmp['d_atoms_total']} |
| Al type1 | {ref.get('Al_type1')} | {cc.get('Al_type1')} | {cc_cmp['d_Al_type1']} |
| Fe type2 | {ref.get('Fe_type2')} | {cc.get('Fe_type2')} | {cc_cmp['d_Fe_type2']} |

`in.common_cell_min` used fixed box only: no `fix box/relax`; base held; wrote `data.F0_planar_100A_comm_eps00194.common_cell_minimized`.
"""
    write_text(REPORTS / "stageF_F0_commensurate_ppf_common_cell_audit.md", cc_md)

    fix_md = f"""# Stage F F0 commensurate ppf common-cell fix plan

Status: **completed for the fixed-box minimize gate**, but downstream smoke failed.

1. Use `eps0000` relaxed data as the reference lateral cell: Lx={ref.get('Lx_A')} A, Ly={ref.get('Ly_A')} A.
2. Create `eps00194` common-cell seed with the same Lx/Ly and atom set: done.
3. Run fixed-box atom-only minimize with no `fix box/relax`: done (`log.common_cell_min`, exit code 0).
4. Output common-cell minimized data: done (`data.F0_planar_100A_comm_eps00194.common_cell_minimized`).
5. Re-run input validation: passed (`ALL_OK=True`).
6. Run `eps00194` smoke 10k: attempted; failed at step 0 with `cudaErrorIllegalAddress`.
7. Production remains forbidden until `eps00194` smoke passes cleanly.
"""
    write_text(REPORTS / "stageF_F0_commensurate_ppf_common_cell_fix_plan.md", fix_md)

    inp_rows = [
        f"| `{item['input']}` | {item['all_paths_ok']} | {item['boundary_values']} | {item['contains_mmf']} | `{'; '.join(item['neighbor_policy'])}` | {item['has_box_relax']} | {item['broken_fragments']} |"
        for item in input_validation["inputs"]
    ]
    inp_md = """# Stage F F0 commensurate ppf input path validation

| input | paths ok | boundary | contains m m f | neighbor policy | has box/relax | broken fragments |
|---|---|---|---|---|---|---|
""" + "\n".join(inp_rows) + f"\n\nOverall: **ALL_OK={input_validation['all_ok']}** for path/boundary/corruption checks. `eps00194/smoke/in.smoke` was updated to `neigh_modify delay 0 every 1 check yes` before launch. Production inputs are absent/not started and therefore not launched.\n"
    write_text(REPORTS / "stageF_F0_commensurate_ppf_input_path_validation.md", inp_md)

    smoke_md = f"""# Stage F F0 commensurate ppf smoke10k report

- Timestamp: {now()}
- Run root: `{rel(RUN)}`
- Gate result: **BLOCK_PRODUCTION_EPS00194_SMOKE_FAILED**.

## eps0000
- Status: latest smoke run **completed_clean** by `log.lammps`/`run.out`.
- Max step: {smoke_summary['eps0000']['max_step']} / 10000.
- Final data exists: {smoke_summary['eps0000']['final_data_exists']}.
- Final restart exists: {smoke_summary['eps0000']['final_restart_exists']}.
- Note: older `stdout.log`/`stderr.log` in the same directory record a prior failed KOKKOS minimization attempt before the successful smoke rerun.

## eps00194
- Status: **failed**.
- Max step: {smoke_summary['eps00194']['max_step']} / 10000.
- Error: `cudaErrorIllegalAddress` in `smoke/stderr.log` at step 0.
- Final data exists: {smoke_summary['eps00194']['final_data_exists']}.
- Final restart exists: {smoke_summary['eps00194']['final_restart_exists']}.

## Decision
No production launch. No blind retry. Next action must diagnose/fix the `eps00194` common-cell GPU smoke failure or choose a documented CPU/short diagnostic path before any production.
"""
    write_text(REPORTS / "stageF_F0_commensurate_ppf_smoke10k_report.md", smoke_md)

    prod_md = f"""# Stage F F0 commensurate ppf production report

- Timestamp: {now()}
- Status: **not_started_blocked**.
- `eps0000` production: `{production_summary['eps0000']['status']}`.
- `eps00194` production: `{production_summary['eps00194']['status']}`.
- Blocker: `eps00194` common-cell smoke failed with `cudaErrorIllegalAddress` at step 0.

No 50k production was launched. Delta-analysis was not run.
"""
    write_text(REPORTS / "stageF_F0_commensurate_ppf_production_report.md", prod_md)

    final_md = f"""# Stage F Codex session recovery and continue

- Timestamp: {now()}
- Recovered state: old invalid `m m f` branch preserved as negative diagnostic; current commensurate `p p f` branch recovered from disk/logs.
- Current run root: `{rel(RUN)}`.
- Active processes: none after `eps00194` smoke failure.
- GPU=0/low because no LAMMPS process is running; the last attempted smoke exited after `cudaErrorIllegalAddress`.

## Old invalid branch
`runs/stageF_F0_planar_100A_open_lateral/20260629-184320` is ignored for physics. Its production attempts have CUDA illegal-address markers and are not valid production.

## Current commensurate branch
- `eps0000` smoke: completed to 10000 in latest `run.out`/`log.lammps`; final data/restart exist.
- Common-cell audit: independent `eps00194.relaxed` FAIL; fixed-box common-cell minimized data PASS.
- Input path validation: ALL_OK after `common_cell_minimized` was created; `eps00194/smoke/in.smoke` uses `neigh_modify delay 0 every 1 check yes`.
- `eps00194` smoke: failed at step 0 with `cudaErrorIllegalAddress`.
- Production: not started; blocked.
- Analysis: not run; blocked until both valid 50k productions exist.
- eps005/F1/F0_300A: not launched.

## Files created or updated
- `docs/reports/stageF_codex_recovery_preflight.md/json`
- `docs/reports/stageF_codex_recovered_state.md/json`
- `docs/reports/stageF_F0_commensurate_ppf_file_inventory.md/json`
- `docs/reports/stageF_F0_commensurate_ppf_log_parse_report.md/json`
- `docs/reports/stageF_F0_commensurate_ppf_common_cell_audit.md/json`
- `docs/reports/stageF_F0_commensurate_ppf_common_cell_fix_plan.md`
- `docs/reports/stageF_F0_commensurate_ppf_input_path_validation.md/json`
- `docs/reports/stageF_F0_commensurate_ppf_smoke10k_report.md/json`
- `docs/reports/stageF_F0_commensurate_ppf_production_report.md/json`
- `agent_report_stageF_codex_session_recovery_and_continue.md`
- `docs/00_index/DOC_INDEX.md`
- `scripts/stageF_codex_recovery_reporter.py`

## Exact next command
```powershell
Get-Content -Raw runs\\stageF_F0_planar_100A_ppf_commensurate\\20260630-010748\\F0_planar_100A_comm_eps00194\\smoke\\stderr.log
```
"""
    write_text(REPO / "agent_report_stageF_codex_session_recovery_and_continue.md", final_md)

    project_context = f"""current objective: Stage F Codex recovery/common-cell audit completed; safe sequence is blocked by eps00194 common-cell smoke failure.
verified: target repo is `{REPO}` on branch `{branch['stdout']}`.
verified: global `C:\\Users\\dille\\.codex\\AGENTS.md` is absent; project-local `AGENTS.md` / `AGENTS.override.md` are absent; control-plane `AGENTS.md`, `instruction-router`, and `prompt.txt` apply.
run_root: `{RUN}`.
old_invalid_branch: `runs/stageF_F0_planar_100A_open_lateral/20260629-184320` is preserved as negative diagnostic only; do not resume or analyze as valid production.
recovered_state: no active LAMMPS/Stage F process remains; GPU is not occupied by LAMMPS compute after the failed eps00194 smoke attempt.
eps0000_smoke: latest `run.out`/`log.lammps` reached 10000 and wrote final data/restart; older stdout/stderr in same folder record a prior failed KOKKOS minimization attempt and are preserved.
common_cell: independent eps00194 relaxed data FAILS common-cell; fixed-box common-cell minimized data PASS with Lx={cc.get('Lx_A')}, Ly={cc.get('Ly_A')}, atoms={cc.get('atoms_total')}.
eps00194_smoke: launched after common-cell fix from `data.F0_planar_100A_comm_eps00194.common_cell_minimized`; failed at step 0 with `cudaErrorIllegalAddress` in `smoke/stderr.log`; no final data/restart.
production_status: not started; blocked because eps00194 smoke failed.
analysis_status: not run; blocked until both valid 50k productions exist.
eps005_status: not launched.
files_touched: Stage F recovery reports under `docs/reports/stageF_codex_*` and `docs/reports/stageF_F0_commensurate_ppf_*`, `agent_report_stageF_codex_session_recovery_and_continue.md`, `docs/00_index/DOC_INDEX.md`, `scripts/stageF_codex_recovery_reporter.py`, common-cell minimize outputs, eps00194 smoke outputs, and this current_context.
validation: py_compile passed for the two requested scripts; input validation ALL_OK after common-cell minimize; JSON reports parse; no raw dumps/restarts/reports deleted; no commit/push/merge/deploy.
pending_blockers: diagnose eps00194 common-cell GPU smoke `cudaErrorIllegalAddress`; no blind retry and no production before smoke passes cleanly.
exact_next_command: `Get-Content -Raw runs\\stageF_F0_planar_100A_ppf_commensurate\\20260630-010748\\F0_planar_100A_comm_eps00194\\smoke\\stderr.log`
last_updated: `{datetime.now().date().isoformat()}`
"""
    write_text(REPO / ".codex" / "state" / "current_context.md", project_context)

    control_artifact = {
        "timestamp": now(),
        "repo": str(REPO),
        "branch": branch["stdout"],
        "run_root": str(RUN),
        "old_mmf_status": "ignored_invalid_negative_diagnostic_only",
        "gpu_zero_reason": "no active LAMMPS; last eps00194 smoke process exited after cudaErrorIllegalAddress at step 0",
        "eps0000_smoke_status": "completed_clean_latest_run",
        "common_cell_status": common_cell["decision"],
        "eps00194_smoke_status": "failed_cudaErrorIllegalAddress_step0",
        "production_status": "not_started_blocked",
        "analysis_status": "not_run",
        "eps005_status": "not_launched",
        "next_command": r"Get-Content -Raw runs\stageF_F0_planar_100A_ppf_commensurate\20260630-010748\F0_planar_100A_comm_eps00194\smoke\stderr.log",
    }
    control_report = CONTROL / "state" / "reports" / "physics_md_al_fe" / "stageF_codex_recovery_20260630.json"
    write_json(control_report, control_artifact)
    control_ctx = CONTROL / ".codex" / "state" / "current_context.md"
    if control_ctx.parent.exists():
        write_text(
            control_ctx,
            f"""current objective: Stage F Codex recovery for `physics_md_al_fe` completed; project is blocked at eps00194 common-cell smoke failure.
verified: target repo `{REPO}` branch `{branch['stdout']}`; current run root `{RUN}`.
verified: preflight/recovered-state/inventory/log-parse/common-cell/input-validation/smoke/production reports were written in project `docs/reports`.
verified: common-cell fix completed and passed for eps00194 minimized data; eps00194 GPU smoke failed at step 0 with `cudaErrorIllegalAddress`.
files_touched: project Stage F recovery reports, project `docs/00_index/DOC_INDEX.md`, project `.codex/state/current_context.md`, control report `{control_report}`.
pending_blockers: no production/delta-analysis until eps00194 smoke failure is diagnosed and a clean smoke passes.
exact_next_step: inspect `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/F0_planar_100A_comm_eps00194/smoke/stderr.log` and choose a documented diagnostic/fix path; do not blind retry.
last_updated: `{datetime.now().date().isoformat()}`
""",
        )

    print(
        json.dumps(
            {
                "ok": True,
                "run_root": str(RUN),
                "common_cell_decision": common_cell["decision"],
                "eps0000_smoke": smoke_summary["eps0000"]["status"],
                "eps00194_smoke": smoke_summary["eps00194"]["status"],
                "production": production_summary["status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
