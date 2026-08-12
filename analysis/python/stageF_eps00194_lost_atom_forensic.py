#!/usr/bin/env python3
"""Stage F eps00194 lost-atom forensic and stabilization diagnostics.

CPU runs here are diagnostic/reference only. Production remains GPU-targeted and
blocked until a clean GPU smoke exists.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
RUN = REPO / "runs" / "stageF_F0_planar_100A_ppf_commensurate" / "20260630-010748"
EPS0000 = RUN / "F0_planar_100A_comm_eps0000"
EPS00194 = RUN / "F0_planar_100A_comm_eps00194"
REPORTS = REPO / "docs" / "reports"
DATA_EPS0000 = EPS0000 / "equil" / "data.F0_planar_100A_comm_eps0000.relaxed"
DATA_EPS00194 = EPS00194 / "equil" / "data.F0_planar_100A_comm_eps00194.common_cell_minimized"
SMOKE_RETRY1 = EPS00194 / "smoke_retry1"
POT_DIR = REPO / "potentials" / "meam" / "Jelinek_2012"
MEAMF = POT_DIR / "Jelinek_2012_meamf"
MEAM = POT_DIR / "Jelinek_2012_meam.alsimgcufe"
CPU_LMP = Path(r"C:\Users\dille\AppData\Local\LAMMPS 64-bit 22Jul2025-MSMPI\bin\lmp.exe")
MPIEXEC = Path(r"C:\Program Files\Microsoft MPI\Bin\mpiexec.exe")
GPU_LMP = Path(r"B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe")


FATAL_PATTERNS = [
    "ERROR",
    "Lost atoms",
    "lost atoms",
    "nan",
    "NaN",
    "cudaError",
    "illegal memory",
    "segmentation",
    "MPI_ABORT",
    "Neighbor list overflow",
]


@dataclass(frozen=True)
class AtomSet:
    path: Path
    ids: np.ndarray
    types: np.ndarray
    xyz: np.ndarray
    box: dict[str, float]
    vxvyvz: np.ndarray | None = None
    step: int | None = None

    @property
    def lx(self) -> float:
        return self.box["xhi"] - self.box["xlo"]

    @property
    def ly(self) -> float:
        return self.box["yhi"] - self.box["ylo"]

    @property
    def lz(self) -> float:
        return self.box["zhi"] - self.box["zlo"]


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
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=json_default) + "\n", encoding="utf-8")


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(type(value).__name__)


def read_data(path: Path) -> AtomSet:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    box: dict[str, float] = {}
    atoms: list[tuple[int, int, float, float, float]] = []
    velocities: dict[int, tuple[float, float, float]] = {}
    section: str | None = None
    waiting_blank = False
    for line in lines:
        s = line.strip()
        if not s:
            if waiting_blank:
                waiting_blank = False
            continue
        parts = s.split()
        if len(parts) >= 4 and parts[2] == "xlo" and parts[3] == "xhi":
            box["xlo"], box["xhi"] = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[2] == "ylo" and parts[3] == "yhi":
            box["ylo"], box["yhi"] = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[2] == "zlo" and parts[3] == "zhi":
            box["zlo"], box["zhi"] = float(parts[0]), float(parts[1])
        if s.startswith("Atoms"):
            section = "Atoms"
            waiting_blank = True
            continue
        if s.startswith("Velocities"):
            section = "Velocities"
            waiting_blank = True
            continue
        if s[0].isalpha() and not s.startswith(("Atoms", "Velocities")):
            section = None
            continue
        if waiting_blank:
            continue
        if section == "Atoms" and len(parts) >= 5 and parts[0].lstrip("+-").isdigit():
            atoms.append((int(parts[0]), int(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])))
        elif section == "Velocities" and len(parts) >= 4 and parts[0].lstrip("+-").isdigit():
            velocities[int(parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]))
    ids = np.array([a[0] for a in atoms], dtype=np.int64)
    types = np.array([a[1] for a in atoms], dtype=np.int32)
    xyz = np.array([[a[2], a[3], a[4]] for a in atoms], dtype=np.float64)
    vel = None
    if velocities:
        vel = np.array([velocities.get(int(i), (np.nan, np.nan, np.nan)) for i in ids], dtype=np.float64)
    return AtomSet(path, ids, types, xyz, box, vel, None)


def dump_frames(path: Path) -> list[AtomSet]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    frames: list[AtomSet] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() != "ITEM: TIMESTEP":
            i += 1
            continue
        step = int(lines[i + 1].strip())
        n = int(lines[i + 3].strip())
        bounds_header = lines[i + 4].strip()
        _ = bounds_header
        xlo, xhi = map(float, lines[i + 5].split()[:2])
        ylo, yhi = map(float, lines[i + 6].split()[:2])
        zlo, zhi = map(float, lines[i + 7].split()[:2])
        cols = lines[i + 8].split()[2:]
        rows = lines[i + 9 : i + 9 + n]
        col_index = {name: idx for idx, name in enumerate(cols)}
        ids: list[int] = []
        types: list[int] = []
        xyz: list[list[float]] = []
        vel: list[list[float]] = []
        has_vel = all(name in col_index for name in ("vx", "vy", "vz"))
        for row in rows:
            parts = row.split()
            ids.append(int(float(parts[col_index["id"]])))
            types.append(int(float(parts[col_index["type"]])))
            xyz.append([float(parts[col_index["x"]]), float(parts[col_index["y"]]), float(parts[col_index["z"]])])
            if has_vel:
                vel.append([float(parts[col_index["vx"]]), float(parts[col_index["vy"]]), float(parts[col_index["vz"]])])
        frames.append(
            AtomSet(
                path,
                np.array(ids, dtype=np.int64),
                np.array(types, dtype=np.int32),
                np.array(xyz, dtype=np.float64),
                {"xlo": xlo, "xhi": xhi, "ylo": ylo, "yhi": yhi, "zlo": zlo, "zhi": zhi},
                np.array(vel, dtype=np.float64) if has_vel else None,
                step,
            )
        )
        i += 9 + n
    return frames


def thermo_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cols: list[str] | None = None
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"^Step\s+", s):
            cols = s.split()
            continue
        if not cols:
            continue
        parts = s.split()
        if len(parts) != len(cols) or not re.match(r"^[-+]?\d+(?:\.\d+)?$", parts[0]):
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
    log = (folder / "log.lammps").read_text(encoding="utf-8", errors="replace") if (folder / "log.lammps").exists() else ""
    stdout = (folder / "stdout.log").read_text(encoding="utf-8", errors="replace") if (folder / "stdout.log").exists() else ""
    stderr = (folder / "stderr.log").read_text(encoding="utf-8", errors="replace") if (folder / "stderr.log").exists() else ""
    text = "\n".join([log, stdout, stderr])
    rows = thermo_rows(text)
    fatal = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for pattern in FATAL_PATTERNS:
            if pattern in line:
                fatal.append({"line": idx, "pattern": pattern, "text": line.strip()})
                break
    return {
        "folder": rel(folder),
        "returncode": int((folder / "returncode.txt").read_text().strip()) if (folder / "returncode.txt").exists() else None,
        "fatal": bool(fatal),
        "fatal_matches": fatal,
        "thermo_rows": rows,
        "max_step": max([r["Step"] for r in rows], default=None),
        "last_thermo": rows[-1] if rows else None,
        "log_tail": "\n".join(log.splitlines()[-40:]),
        "stdout_tail": "\n".join(stdout.splitlines()[-30:]),
        "stderr_tail": "\n".join(stderr.splitlines()[-30:]),
    }


def boundary_summary(atoms: AtomSet, reference: AtomSet | None = None) -> dict[str, Any]:
    z = atoms.xyz[:, 2]
    order_top = np.argsort(-z)[:30]
    order_bottom = np.argsort(z)[:30]
    out: dict[str, Any] = {
        "path": rel(atoms.path),
        "step": atoms.step,
        "atom_count": int(len(atoms.ids)),
        "box": {**atoms.box, "Lx_A": atoms.lx, "Ly_A": atoms.ly, "Lz_A": atoms.lz},
        "z_range": {"min_z": float(z.min()), "max_z": float(z.max())},
        "margin_bottom_A": float(z.min() - atoms.box["zlo"]),
        "margin_top_A": float(atoms.box["zhi"] - z.max()),
        "near_bottom_counts": {},
        "near_top_counts": {},
        "near_bottom_by_type": {},
        "near_top_by_type": {},
        "top_30_atoms_by_z": atom_records(atoms, order_top),
        "bottom_30_atoms_by_z": atom_records(atoms, order_bottom),
    }
    for margin in (1.0, 2.0, 5.0, 10.0):
        bottom_mask = z - atoms.box["zlo"] <= margin
        top_mask = atoms.box["zhi"] - z <= margin
        out["near_bottom_counts"][f"{margin:g}A"] = int(bottom_mask.sum())
        out["near_top_counts"][f"{margin:g}A"] = int(top_mask.sum())
        out["near_bottom_by_type"][f"{margin:g}A"] = type_counts(atoms.types[bottom_mask])
        out["near_top_by_type"][f"{margin:g}A"] = type_counts(atoms.types[top_mask])
    if reference is not None:
        disp = displacement_by_id(reference, atoms)
        out["displacement_from_initial"] = disp
    return out


def type_counts(types: np.ndarray) -> dict[str, int]:
    if len(types) == 0:
        return {}
    unique, counts = np.unique(types, return_counts=True)
    return {str(int(k)): int(v) for k, v in zip(unique, counts)}


def atom_records(atoms: AtomSet, indices: np.ndarray) -> list[dict[str, Any]]:
    records = []
    for idx in indices:
        rec: dict[str, Any] = {
            "id": int(atoms.ids[idx]),
            "type": int(atoms.types[idx]),
            "material": material(atoms.types[idx]),
            "x": float(atoms.xyz[idx, 0]),
            "y": float(atoms.xyz[idx, 1]),
            "z": float(atoms.xyz[idx, 2]),
            "margin_bottom_A": float(atoms.xyz[idx, 2] - atoms.box["zlo"]),
            "margin_top_A": float(atoms.box["zhi"] - atoms.xyz[idx, 2]),
        }
        if atoms.vxvyvz is not None and np.isfinite(atoms.vxvyvz[idx]).all():
            rec["vx"] = float(atoms.vxvyvz[idx, 0])
            rec["vy"] = float(atoms.vxvyvz[idx, 1])
            rec["vz"] = float(atoms.vxvyvz[idx, 2])
        records.append(rec)
    return records


def material(atom_type: int | np.integer) -> str:
    return "Al" if int(atom_type) == 1 else "Fe"


def displacement_by_id(reference: AtomSet, target: AtomSet) -> dict[str, Any]:
    ref_map = {int(atom_id): i for i, atom_id in enumerate(reference.ids)}
    records = []
    missing_from_target = sorted(set(int(i) for i in reference.ids) - set(int(i) for i in target.ids))
    for j, atom_id_raw in enumerate(target.ids):
        atom_id = int(atom_id_raw)
        i = ref_map.get(atom_id)
        if i is None:
            continue
        delta = target.xyz[j] - reference.xyz[i]
        delta[0] -= round(delta[0] / reference.lx) * reference.lx
        delta[1] -= round(delta[1] / reference.ly) * reference.ly
        dist = float(np.linalg.norm(delta))
        records.append((dist, atom_id, int(target.types[j]), delta.tolist(), target.xyz[j].tolist()))
    records.sort(reverse=True, key=lambda item: item[0])
    return {
        "same_atom_count": len(reference.ids) == len(target.ids),
        "missing_from_target": missing_from_target[:50],
        "missing_count": len(missing_from_target),
        "top_30_by_displacement": [
            {
                "distance_A": dist,
                "id": atom_id,
                "type": atom_type,
                "material": material(atom_type),
                "delta_A": delta,
                "target_xyz": xyz,
            }
            for dist, atom_id, atom_type, delta, xyz in records[:30]
        ],
    }


def input_commands(path: Path) -> list[str]:
    commands = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        s = re.sub(r"F0_planar_100A_comm_eps\d+", "<CASE>", s)
        s = s.replace("smoke_retry1", "smoke")
        s = s.replace("stageF_F0_planar_100A_comm_smoke_retry1", "stageF_F0_planar_100A_comm_smoke")
        s = re.sub(r"C:/Users/dille/Documents/ilua-system/projects/physics_md_al_fe/runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/", "<RUN>/", s)
        commands.append(s)
    return commands


def audit_inputs() -> dict[str, Any]:
    eps0000 = EPS0000 / "smoke" / "in.smoke"
    eps00194 = SMOKE_RETRY1 / "in.smoke_retry1"
    a = input_commands(eps0000)
    b = input_commands(eps00194)
    diffs = []
    for idx in range(max(len(a), len(b))):
        left = a[idx] if idx < len(a) else None
        right = b[idx] if idx < len(b) else None
        if left != right:
            diffs.append({"index": idx, "eps0000": left, "eps00194": right})
    expected_prefixes = {"read_data", "dump", "restart", "write_restart", "write_data", "neigh_modify"}
    unexpected = []
    for diff in diffs:
        left_cmd = (diff["eps0000"] or "").split(" ", 1)[0]
        right_cmd = (diff["eps00194"] or "").split(" ", 1)[0]
        if left_cmd not in expected_prefixes and right_cmd not in expected_prefixes:
            unexpected.append(diff)
    result = {
        "timestamp": now(),
        "eps0000_input": rel(eps0000),
        "eps00194_input": rel(eps00194),
        "status": "PASS" if not unexpected else "FAIL",
        "differences": diffs,
        "unexpected_differences": unexpected,
        "summary": {
            "timestep": "same 0.001 ps",
            "velocity_create": "same 300 K seed 88004 mom yes rot yes dist gaussian on mobile group",
            "nvt": "same mobile nvt 300.0 300.0 damp 0.1",
            "fixed_group": "same bottom z<=8.0 setforce 0 0 0",
            "mobile_group": "same subtract all bottom",
            "boundary": "same p p f",
            "neigh_modify": "eps00194 uses safer every 1 check yes; eps0000 successful smoke used every 10 check no",
        },
    }
    write_json(REPORTS / "stageF_F0_commensurate_ppf_eps00194_smoke_input_audit.json", result)
    rows = "\n".join(f"| {d['index']} | `{d['eps0000']}` | `{d['eps00194']}` |" for d in diffs)
    md = f"""# Stage F eps00194 smoke input audit

- Timestamp: {result['timestamp']}
- Status: **{result['status']}**
- eps0000 input: `{result['eps0000_input']}`
- eps00194 smoke retry input: `{result['eps00194_input']}`

## Protocol checks
- Timestep: same `0.001`.
- Velocity create: same `mobile create 300.0 88004 mom yes rot yes dist gaussian`.
- Thermostat: same `fix nvt_mobile mobile nvt temp 300.0 300.0 0.1`.
- NVT group: same `mobile`.
- Fixed group: same `bottom` region `z <= 8.0`, `fix hold bottom setforce 0.0 0.0 0.0`.
- Fixed atoms excluded from thermostat: yes, because `mobile subtract all bottom`.
- Inclusion atoms: mobile unless inside the bottom support.
- Boundary: same `p p f`.
- `run 0` after velocity creation: absent in both smoke protocols.
- Neighbor policy: eps00194 uses safer `every 1 check yes`; eps0000 smoke used `every 10 check no`.

## Normalized diffs
| index | eps0000 | eps00194 |
|---:|---|---|
{rows}
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_smoke_input_audit.md", md)
    return result


def start_report() -> dict[str, Any]:
    run = parse_run(SMOKE_RETRY1)
    input_text = (SMOKE_RETRY1 / "in.smoke_retry1").read_text(encoding="utf-8", errors="replace")
    dump_exists = (SMOKE_RETRY1 / "dump.stageF_F0_planar_100A_comm_smoke_retry1.lammpstrj").exists()
    restart_exists = bool(list(SMOKE_RETRY1.glob("restart.stageF_F0_planar_100A_comm_smoke_retry1.*")))
    result = {
        "timestamp": now(),
        "folder": rel(SMOKE_RETRY1),
        "lost_atom_error": next((m["text"] for m in run["fatal_matches"] if "Lost atoms" in m["text"]), None),
        "last_timestep": run["max_step"],
        "last_thermo": run["last_thermo"],
        "timestep": "0.001",
        "boundary": "p p f",
        "thermostat": "fix nvt_mobile mobile nvt temp 300.0 300.0 0.1",
        "nvt_group": "mobile",
        "fixed_group": "bottom, z <= 8.0, setforce 0 0 0",
        "velocity_initialization": "velocity mobile create 300.0 88004 mom yes rot yes dist gaussian",
        "dump_exists_before_failure": dump_exists,
        "restart_exists_before_failure": restart_exists,
        "input_contains_lost_ignore": "lost ignore" in input_text,
    }
    write_json(REPORTS / "stageF_F0_commensurate_ppf_eps00194_lost_atom_debug_start.json", result)
    md = f"""# Stage F eps00194 lost atom debug start

- Timestamp: {result['timestamp']}
- Failed folder: `{result['folder']}`
- Exact lost atom line: `{result['lost_atom_error']}`
- Last timestep printed: `{result['last_timestep']}`
- Timestep: `{result['timestep']}`
- Boundary: `{result['boundary']}`
- Thermostat: `{result['thermostat']}`
- NVT group: `{result['nvt_group']}`
- Fixed group: `{result['fixed_group']}`
- Velocity initialization: `{result['velocity_initialization']}`
- Dump exists before failure: `{result['dump_exists_before_failure']}`
- Restart exists before failure: `{result['restart_exists_before_failure']}`
- Lost-ignore present: `{result['input_contains_lost_ignore']}`

## Last thermo row
```json
{json.dumps(result['last_thermo'], indent=2, ensure_ascii=False)}
```
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_lost_atom_debug_start.md", md)
    return result


def location_report(source_dump: Path | None = None) -> dict[str, Any]:
    eps00194_initial = read_data(DATA_EPS00194)
    eps0000_initial = read_data(DATA_EPS0000)
    dump_path = source_dump or SMOKE_RETRY1 / "dump.stageF_F0_planar_100A_comm_smoke_retry1.lammpstrj"
    frames = dump_frames(dump_path)
    latest = frames[-1] if frames else None
    result = {
        "timestamp": now(),
        "eps00194_initial": boundary_summary(eps00194_initial),
        "eps0000_initial": boundary_summary(eps0000_initial),
        "latest_dump": boundary_summary(latest, eps00194_initial) if latest is not None else None,
        "latest_dump_path": rel(dump_path),
        "useful_pre_failure_dump": bool(latest is not None and latest.step not in (None, 0)),
        "diagnosis": "only step-0 dump available; high-frequency capture required" if latest is None or latest.step == 0 else "pre-failure dump available",
    }
    write_json(REPORTS / "stageF_F0_commensurate_ppf_eps00194_lost_atom_location.json", result)
    latest_text = "No dump frame parsed."
    if latest is not None:
        latest_text = (
            f"- Step: `{latest.step}`\n"
            f"- Atom count: `{len(latest.ids)}`\n"
            f"- min_z/max_z: `{latest.xyz[:, 2].min()}` / `{latest.xyz[:, 2].max()}`\n"
            f"- margin bottom/top: `{latest.xyz[:, 2].min() - latest.box['zlo']}` / `{latest.box['zhi'] - latest.xyz[:, 2].max()}`"
        )
    md = f"""# Stage F eps00194 lost atom location

- Timestamp: {result['timestamp']}
- Latest dump path: `{result['latest_dump_path']}`
- Useful pre-failure dump: `{result['useful_pre_failure_dump']}`
- Diagnosis: {result['diagnosis']}

## eps00194 initial boundary margins
- zlo/zhi: `{result['eps00194_initial']['box']['zlo']}` / `{result['eps00194_initial']['box']['zhi']}`
- min_z/max_z: `{result['eps00194_initial']['z_range']['min_z']}` / `{result['eps00194_initial']['z_range']['max_z']}`
- bottom/top margin: `{result['eps00194_initial']['margin_bottom_A']}` / `{result['eps00194_initial']['margin_top_A']}`
- near top counts: `{result['eps00194_initial']['near_top_counts']}`
- near bottom counts: `{result['eps00194_initial']['near_bottom_counts']}`

## eps0000 initial comparison
- min_z/max_z: `{result['eps0000_initial']['z_range']['min_z']}` / `{result['eps0000_initial']['z_range']['max_z']}`
- bottom/top margin: `{result['eps0000_initial']['margin_bottom_A']}` / `{result['eps0000_initial']['margin_top_A']}`
- near top counts: `{result['eps0000_initial']['near_top_counts']}`
- near bottom counts: `{result['eps0000_initial']['near_bottom_counts']}`

## Latest dump
{latest_text}
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_lost_atom_location.md", md)
    return result


def common_lammps_header(data_path: Path) -> str:
    return f"""units           metal
atom_style      atomic
boundary        p p f
read_data       {posix(data_path)}
pair_style      meam
pair_coeff      * * {posix(MEAMF)} AlS SiS MgS CuS FeS {posix(MEAM)} AlS FeS
neighbor        2.0 bin
neigh_modify    delay 0 every 1 check yes
timestep        0.001
"""


def mobile_protocol() -> str:
    return """region          bottom block INF INF INF INF INF 8.0 units box
group           bottom region bottom
group           mobile subtract all bottom
fix             hold bottom setforce 0.0 0.0 0.0
velocity        mobile create 300.0 88004 mom yes rot yes dist gaussian
fix             nvt_mobile mobile nvt temp 300.0 300.0 0.1
"""


def capture_input(folder: Path, warn: bool = False) -> str:
    lost = "thermo_modify   flush yes lost warn\n" if warn else "thermo_modify   flush yes\n"
    return f"""# Stage F eps00194 lost-atom high-frequency CPU capture.
{common_lammps_header(DATA_EPS00194)}
compute         pe_atom all pe/atom

{mobile_protocol()}
thermo          10
thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz
{lost}dump            d1 all custom 10 {posix(folder / 'dump.lost_atom_capture.lammpstrj')} id type x y z vx vy vz c_pe_atom
dump_modify     d1 sort id
restart         100 {posix(folder / 'restart.lost_atom_capture.*')}
run             1000
"""


def run_lammps(folder: Path, input_name: str, input_text: str, command: list[str], timeout_s: int) -> dict[str, Any]:
    folder.mkdir(parents=True, exist_ok=True)
    input_path = folder / input_name
    if not (folder / "returncode.txt").exists():
        write(input_path, input_text)
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = "6"
        with (folder / "stdout.log").open("w", encoding="utf-8") as out, (folder / "stderr.log").open("w", encoding="utf-8") as err:
            try:
                cp = subprocess.run(command, cwd=str(folder), stdout=out, stderr=err, env=env, timeout=timeout_s)
                returncode = cp.returncode
                timed_out = False
            except subprocess.TimeoutExpired:
                returncode = 124
                timed_out = True
        write(folder / "returncode.txt", str(returncode))
    else:
        timed_out = False
    parsed = parse_run(folder)
    parsed["timed_out"] = timed_out
    parsed["input"] = rel(input_path)
    parsed["command"] = command
    return parsed


def run_capture() -> dict[str, Any]:
    folder = EPS00194 / "debug_lost_atom_capture_cpu"
    cmd = [str(MPIEXEC), "-np", "8", str(CPU_LMP), "-in", "in.lost_atom_capture", "-log", "log.lammps"]
    capture = run_lammps(folder, "in.lost_atom_capture", capture_input(folder, warn=False), cmd, 2400)
    frames = dump_frames(folder / "dump.lost_atom_capture.lammpstrj")
    initial = read_data(DATA_EPS00194)
    capture["dump_frames"] = len(frames)
    capture["last_dump_step"] = frames[-1].step if frames else None
    capture["last_dump_atom_count"] = int(len(frames[-1].ids)) if frames else None
    capture["last_dump_boundary"] = boundary_summary(frames[-1], initial) if frames else None
    capture["missing_after_capture"] = displacement_by_id(initial, frames[-1])["missing_from_target"] if frames else []

    warn_result = None
    if not capture["missing_after_capture"]:
        warn_folder = EPS00194 / "debug_lost_atom_capture_warn_cpu"
        warn_cmd = [str(MPIEXEC), "-np", "8", str(CPU_LMP), "-in", "in.lost_atom_capture_warn", "-log", "log.lammps"]
        warn_result = run_lammps(warn_folder, "in.lost_atom_capture_warn", capture_input(warn_folder, warn=True).replace("run             1000", "run             500"), warn_cmd, 1800)
        warn_frames = dump_frames(warn_folder / "dump.lost_atom_capture.lammpstrj")
        warn_result["diagnostic_only"] = True
        warn_result["dump_frames"] = len(warn_frames)
        warn_result["last_dump_step"] = warn_frames[-1].step if warn_frames else None
        warn_result["last_dump_atom_count"] = int(len(warn_frames[-1].ids)) if warn_frames else None
        warn_result["last_dump_boundary"] = boundary_summary(warn_frames[-1], initial) if warn_frames else None
        warn_result["missing_after_warn"] = displacement_by_id(initial, warn_frames[-1])["missing_from_target"] if warn_frames else []

    result = {
        "timestamp": now(),
        "capture": capture,
        "warn_capture": warn_result,
        "first_lost_step": infer_first_lost_step(capture, warn_result),
        "likely_mechanism": infer_mechanism(capture, warn_result),
    }
    write_json(REPORTS / "stageF_F0_commensurate_ppf_eps00194_lost_atom_capture_summary.json", result)
    md = f"""# Stage F eps00194 lost atom capture

- Timestamp: {result['timestamp']}
- First lost step: `{result['first_lost_step']}`
- Likely mechanism: **{result['likely_mechanism']}**
- Capture folder: `{capture['folder']}`
- Capture max step: `{capture['max_step']}`
- Capture last dump step: `{capture['last_dump_step']}`
- Capture last dump atom count: `{capture['last_dump_atom_count']}`
- Capture fatal markers: `{len(capture['fatal_matches'])}`
"""
    if warn_result:
        md += f"""
## Diagnostic lost-warn capture
- Folder: `{warn_result['folder']}`
- Diagnostic-only: true
- Max step: `{warn_result['max_step']}`
- Last dump step: `{warn_result['last_dump_step']}`
- Last dump atom count: `{warn_result['last_dump_atom_count']}`
- Missing atom IDs after warn: `{warn_result.get('missing_after_warn')}`
"""
    if capture.get("last_dump_boundary"):
        b = capture["last_dump_boundary"]
        md += f"""
## Last regular capture boundary
- min_z/max_z: `{b['z_range']['min_z']}` / `{b['z_range']['max_z']}`
- bottom/top margin: `{b['margin_bottom_A']}` / `{b['margin_top_A']}`
- top near-boundary counts: `{b['near_top_counts']}`
- bottom near-boundary counts: `{b['near_bottom_counts']}`
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_lost_atom_capture_report.md", md)
    return result


def infer_first_lost_step(capture: dict[str, Any], warn_result: dict[str, Any] | None) -> int | None:
    for row in capture.get("thermo_rows", []):
        if row.get("Atoms") is not None and row["Atoms"] < 113295:
            return int(row["Step"])
    if warn_result:
        for row in warn_result.get("thermo_rows", []):
            if row.get("Atoms") is not None and row["Atoms"] < 113295:
                return int(row["Step"])
    return capture.get("max_step")


def infer_mechanism(capture: dict[str, Any], warn_result: dict[str, Any] | None) -> str:
    for boundary in (capture.get("last_dump_boundary"), warn_result.get("last_dump_boundary") if warn_result else None):
        if not boundary:
            continue
        top_margin = boundary["margin_top_A"]
        bottom_margin = boundary["margin_bottom_A"]
        if top_margin < 0:
            return "z-boundary top surface escape"
        if bottom_margin < 0:
            return "z-boundary bottom escape"
    boundary = capture.get("last_dump_boundary") or (warn_result.get("last_dump_boundary") if warn_result else None)
    if boundary and boundary["margin_top_A"] < boundary["margin_bottom_A"]:
        return "z-boundary top surface approach"
    return "unresolved"


def write_z_headroom_data(target: Path, extra_z: float = 30.0) -> dict[str, Any]:
    src_lines = DATA_EPS00194.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines = []
    original_zhi = None
    for line in src_lines:
        parts = line.split()
        if len(parts) >= 4 and parts[2] == "zlo" and parts[3] == "zhi":
            zlo = float(parts[0])
            zhi = float(parts[1])
            original_zhi = zhi
            new_lines.append(f"{zlo:.16g} {zhi + extra_z:.16g} zlo zhi")
        else:
            new_lines.append(line)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return {"source": rel(DATA_EPS00194), "target": rel(target), "original_zhi": original_zhi, "new_zhi": None if original_zhi is None else original_zhi + extra_z, "extra_z_A": extra_z}


def fix1_diag_input(data_path: Path, folder: Path, run_steps: int, smoke_like: bool = False) -> str:
    computes = ""
    dump_cols = "id type x y z"
    if smoke_like:
        computes = "compute         pe_atom all pe/atom\ncompute         st all stress/atom NULL virial\n"
        dump_cols = "id type x y z c_pe_atom c_st[1] c_st[2] c_st[3] c_st[4] c_st[5] c_st[6]"
    return f"""# Stage F eps00194 Fix 1 z-headroom CPU {'smoke' if smoke_like else 'diagnostic'}.
{common_lammps_header(data_path)}
{computes}
{mobile_protocol()}
thermo          {200 if smoke_like else 10}
thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz
thermo_modify   flush yes
dump            d1 all custom {1000 if smoke_like else 100} {posix(folder / ('dump.fix1_smoke.lammpstrj' if smoke_like else 'dump.fix1_diag.lammpstrj'))} {dump_cols}
dump_modify     d1 sort id
restart         {2000 if smoke_like else 500} {posix(folder / ('restart.fix1_smoke.*' if smoke_like else 'restart.fix1_diag.*'))}
run             {run_steps}
write_restart   {posix(folder / ('restart.fix1_smoke.final' if smoke_like else 'restart.fix1_diag.final'))}
write_data      {posix(folder / ('data.fix1_smoke.final' if smoke_like else 'data.fix1_diag.final'))}
"""


def gpu_retry_input(data_path: Path, folder: Path) -> str:
    return f"""# Stage F eps00194 GPU smoke retry after Fix 1 z-headroom CPU validation.
{common_lammps_header(data_path)}
compute         pe_atom all pe/atom
compute         st all stress/atom NULL virial

{mobile_protocol()}
thermo          200
thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz
thermo_modify   flush yes
dump            d1 all custom 1000 {posix(folder / 'dump.stageF_F0_planar_100A_comm_smoke_retry_gpu_after_fix.lammpstrj')} id type x y z c_pe_atom c_st[1] c_st[2] c_st[3] c_st[4] c_st[5] c_st[6]
dump_modify     d1 sort id
restart         2000 {posix(folder / 'restart.stageF_F0_planar_100A_comm_smoke_retry_gpu_after_fix.*')}
run             10000
write_restart   {posix(folder / 'restart.stageF_F0_planar_100A_comm_smoke_retry_gpu_after_fix.final')}
write_data      {posix(folder / 'data.stageF_F0_planar_100A_comm_smoke_retry_gpu_after_fix.final')}
"""


def passed_clean(parsed: dict[str, Any], target_step: int, folder: Path, final_prefix: str) -> bool:
    final_restart = folder / f"restart.{final_prefix}.final"
    final_data = folder / f"data.{final_prefix}.final"
    return parsed["returncode"] == 0 and not parsed["fatal"] and parsed["max_step"] == target_step and final_restart.exists() and final_data.exists()


def run_fix1_ladder() -> dict[str, Any]:
    data_path = EPS00194 / "debug_fix1_z_headroom_cpu" / "data.F0_planar_100A_comm_eps00194.zheadroom30"
    data_info = write_z_headroom_data(data_path, extra_z=30.0)

    diag_folder = EPS00194 / "debug_fix1_z_headroom_cpu"
    diag_cmd = [str(MPIEXEC), "-np", "8", str(CPU_LMP), "-in", "in.fix1_z_headroom_diag", "-log", "log.lammps"]
    diag = run_lammps(diag_folder, "in.fix1_z_headroom_diag", fix1_diag_input(data_path, diag_folder, 1000, False), diag_cmd, 3600)
    diag["status"] = "completed_clean" if passed_clean(diag, 1000, diag_folder, "fix1_diag") else "failed"

    smoke = None
    gpu = None
    smoke_folder = EPS00194 / "debug_fix1_z_headroom_cpu_smoke10k"
    if diag["status"] == "completed_clean":
        smoke_cmd = [str(MPIEXEC), "-np", "8", str(CPU_LMP), "-in", "in.fix1_z_headroom_smoke10k", "-log", "log.lammps"]
        smoke = run_lammps(smoke_folder, "in.fix1_z_headroom_smoke10k", fix1_diag_input(data_path, smoke_folder, 10000, True), smoke_cmd, 14400)
        smoke["status"] = "completed_clean" if passed_clean(smoke, 10000, smoke_folder, "fix1_smoke") else "failed"

    gpu_folder = EPS00194 / "smoke_retry_gpu_after_fix"
    if smoke and smoke["status"] == "completed_clean":
        gpu_cmd = [
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
            "in.smoke_retry_gpu_after_fix",
            "-log",
            "log.lammps",
        ]
        gpu = run_lammps(gpu_folder, "in.smoke_retry_gpu_after_fix", gpu_retry_input(data_path, gpu_folder), gpu_cmd, 14400)
        gpu["status"] = "completed_clean" if passed_clean(gpu, 10000, gpu_folder, "stageF_F0_planar_100A_comm_smoke_retry_gpu_after_fix") else "failed"

    result = {
        "timestamp": now(),
        "fixes": {
            "fix1_z_headroom": {
                "status": "cpu_smoke_clean_gpu_" + (gpu["status"] if gpu else "not_run") if smoke and smoke["status"] == "completed_clean" else diag["status"],
                "settings": data_info,
                "cpu_diag_1000": diag,
                "cpu_smoke_10000": smoke,
                "gpu_smoke_10000": gpu,
            },
            "fix2_thermal_ramp": {"status": "not_run", "reason": "Fix 1 reached the next required gate or remained active blocker."},
            "fix3_small_timestep": {"status": "not_run", "reason": "Fix 1 reached the next required gate or remained active blocker."},
            "fix4_deeper_minimize": {"status": "not_run", "reason": "Fix 1 reached the next required gate or remained active blocker."},
            "fix5_wall": {"status": "not_used", "reason": "Last resort only."},
        },
        "chosen_fix": None,
    }
    if smoke and smoke["status"] == "completed_clean":
        result["chosen_fix"] = {
            "fix": "Fix 1 z headroom +30 A",
            "settings": "same coordinates, same Lx/Ly, zhi increased by 30 A, boundary p p f, no wall, no box/relax",
            "least_invasive_reason": "only adds nonperiodic-vacuum headroom to prevent boundary deletion; atom coordinates and lateral common cell are unchanged",
            "comparability": "eps0000 should use the same zhi headroom/protocol before production for strict Delta-sigma comparability",
        }
    write_stabilization_reports(result)
    update_smoke_gate_after_gpu(result)
    write_production_gate(result)
    return result


def write_stabilization_reports(result: dict[str, Any]) -> None:
    write_json(REPORTS / "stageF_F0_commensurate_ppf_eps00194_stabilization_ladder.json", result)
    f1 = result["fixes"]["fix1_z_headroom"]
    smoke = f1["cpu_smoke_10000"]
    gpu = f1["gpu_smoke_10000"]
    md = f"""# Stage F eps00194 stabilization ladder

- Timestamp: {result['timestamp']}
- Preferred fix order: z headroom, thermal ramp, smaller timestep, deeper fixed-box minimization, wall only as last resort.

## Fix 1 - Z headroom
- Status: **{f1['status']}**
- Settings: same atom coordinates and same Lx/Ly; zhi increased from `{f1['settings']['original_zhi']}` to `{f1['settings']['new_zhi']}` A; boundary remains `p p f`; no wall; no box/relax.
- CPU diagnostic 1000: `{f1['cpu_diag_1000']['status']}` max step `{f1['cpu_diag_1000']['max_step']}`.
- CPU smoke candidate 10000: `{smoke['status'] if smoke else 'not_run'}` max step `{smoke['max_step'] if smoke else None}`.
- GPU smoke retry 10000: `{gpu['status'] if gpu else 'not_run'}` max step `{gpu['max_step'] if gpu else None}`.

## Fix 2 - Thermal ramp
- Status: not run.

## Fix 3 - Smaller timestep
- Status: not run.

## Fix 4 - Deeper fixed-box minimization
- Status: not run.

## Fix 5 - Wall
- Status: not used.
"""
    if result.get("chosen_fix"):
        md += f"""
## Chosen fix
- Fix: `{result['chosen_fix']['fix']}`
- Exact settings: {result['chosen_fix']['settings']}
- Why least invasive: {result['chosen_fix']['least_invasive_reason']}
- Comparability: {result['chosen_fix']['comparability']}
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_eps00194_stabilization_ladder.md", md)


def update_smoke_gate_after_gpu(result: dict[str, Any]) -> None:
    summary_path = REPORTS / "stageF_F0_commensurate_ppf_smoke10k_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {}
    f1 = result["fixes"]["fix1_z_headroom"]
    summary["eps00194_stabilized_fix1"] = {
        "status": f1["status"],
        "cpu_smoke_10000_status": f1["cpu_smoke_10000"]["status"] if f1["cpu_smoke_10000"] else "not_run",
        "gpu_smoke_10000_status": f1["gpu_smoke_10000"]["status"] if f1["gpu_smoke_10000"] else "not_run",
        "gpu_smoke_max_step": f1["gpu_smoke_10000"]["max_step"] if f1["gpu_smoke_10000"] else None,
        "folder": rel(EPS00194 / "smoke_retry_gpu_after_fix"),
    }
    summary["gate"] = "BLOCK_PRODUCTION_EPS00194_GPU_SMOKE_FAILED" if f1["gpu_smoke_10000"] and f1["gpu_smoke_10000"]["status"] != "completed_clean" else summary.get("gate", "BLOCK_PRODUCTION_EPS00194_SMOKE_FAILED")
    write_json(summary_path, summary)

    report_path = REPORTS / "stageF_F0_commensurate_ppf_smoke10k_report.md"
    existing = report_path.read_text(encoding="utf-8", errors="replace") if report_path.exists() else "# Stage F F0 commensurate ppf smoke10k report\n"
    if "## eps00194 stabilized Fix 1" not in existing:
        gpu = f1["gpu_smoke_10000"]
        smoke = f1["cpu_smoke_10000"]
        existing += f"""

## eps00194 stabilized Fix 1
- Fix: z headroom +30 A, same coordinates, same Lx/Ly, boundary `p p f`, no wall.
- CPU smoke candidate 10000: `{smoke['status'] if smoke else 'not_run'}`, max step `{smoke['max_step'] if smoke else None}`.
- GPU smoke retry 10000: `{gpu['status'] if gpu else 'not_run'}`, max step `{gpu['max_step'] if gpu else None}`.
- GPU retry folder: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/F0_planar_100A_comm_eps00194/smoke_retry_gpu_after_fix`
- Production gate remains closed unless GPU smoke is completed clean and comparability is documented.
"""
        write(report_path, existing)


def write_production_gate(result: dict[str, Any]) -> None:
    f1 = result["fixes"]["fix1_z_headroom"]
    gpu = f1["gpu_smoke_10000"]
    gate = "OPEN_READY_FOR_COMPARABILITY_DECISION" if gpu and gpu["status"] == "completed_clean" else "BLOCKED"
    reason = "eps00194 stabilized GPU smoke is not completed clean" if gate == "BLOCKED" else "smokes clean; comparability decision still required before production"
    md = f"""# Stage F production gate after eps00194 fix

- Timestamp: {now()}
- Gate: **{gate}**
- Reason: {reason}
- eps0000 smoke 10k clean: yes.
- eps00194 CPU stabilized smoke 10k clean: `{f1['cpu_smoke_10000']['status'] if f1['cpu_smoke_10000'] else 'not_run'}`
- eps00194 GPU stabilized smoke 10k clean: `{gpu['status'] if gpu else 'not_run'}`
- common-cell PASS: yes.
- input path validation: previously PASS for current branch.
- stabilization fix documented: yes.
- comparability decision: pending; if z-headroom is kept, eps0000 should use the same zhi/protocol before production.

No production, eps005, F1, or F0_300A was launched.
"""
    write(REPORTS / "stageF_F0_commensurate_ppf_production_gate_after_eps00194_fix.md", md)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static", action="store_true")
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--fix1", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    outputs: dict[str, Any] = {}
    if args.static or args.all:
        outputs["start"] = start_report()
        outputs["location"] = location_report()
        outputs["input_audit"] = audit_inputs()
    if args.capture or args.all:
        outputs["capture"] = run_capture()
        capture_dump = EPS00194 / "debug_lost_atom_capture_cpu" / "dump.lost_atom_capture.lammpstrj"
        if capture_dump.exists():
            outputs["location_after_capture"] = location_report(capture_dump)
    if args.fix1 or args.all:
        outputs["fix1"] = run_fix1_ladder()
    print(json.dumps(outputs, indent=2, ensure_ascii=False, default=json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
