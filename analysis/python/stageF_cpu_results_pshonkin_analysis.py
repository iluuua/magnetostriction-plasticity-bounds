#!/usr/bin/env python3
"""Analyze completed Stage F CPU fallback results against Pshonkin criteria.

Reads existing CPU production dumps only. It does not launch LAMMPS, delete raw
outputs, change restarts, or mix CPU/GPU results.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "docs" / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
CONTROL_ROOT = REPO_ROOT.parents[1]
PROMPT_PATH = CONTROL_ROOT / "prompt.txt"
PRODUCTION_ROOT = (
    REPO_ROOT
    / "runs"
    / "stageF_F0_planar_100A_ppf_commensurate"
    / "20260630-010748"
    / "cpu_fallback_production_20260701-001918"
)
STATUS_JSON = (
    REPO_ROOT
    / "runs"
    / "stageF_F0_planar_100A_ppf_commensurate"
    / "20260630-010748"
    / "cpu_fallback_comparable_20260701-001918"
    / "cpu_fallback_worker_status.json"
)
SETUP_JSON = REPORTS_DIR / "stageF_dual_lane_cpu_setup.json"
PRODUCTION_STATUS_JSON = REPORTS_DIR / "stageF_dual_lane_cpu_production_status.json"

INTERFACE_Z_A = 50.0
YIELD_THRESHOLD_MPA = 120.0
BAR_TO_MPA = 0.1
LAST_WINDOW_START_STEP = 40000
FINAL_STEP = 50000


@dataclass(frozen=True)
class CaseSpec:
    key: str
    case_id: str
    eps_z: float
    production_dir: Path
    dump_path: Path
    log_path: Path
    input_path: Path
    command_path: Path


@dataclass(frozen=True)
class FrameData:
    case_key: str
    case_id: str
    eps_z: float
    step: int
    columns: list[str]
    bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
    array: np.ndarray

    @property
    def lx(self) -> float:
        return self.bounds[0][1] - self.bounds[0][0]

    @property
    def ly(self) -> float:
        return self.bounds[1][1] - self.bounds[1][0]

    @property
    def lz(self) -> float:
        return self.bounds[2][1] - self.bounds[2][0]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=json_default) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    try:
        val = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(val):
        return "n/a"
    if abs(val) >= 1000:
        return f"{val:.1f}"
    return f"{val:.{digits}f}".rstrip("0").rstrip(".")


def markdown_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(lines)


def case_specs(production_root: Path) -> dict[str, CaseSpec]:
    specs = {}
    for key, eps in [("eps0000", 0.0), ("eps00194", 0.00194)]:
        case_id = f"F0_planar_100A_comm_{key}_cpu_zhi200"
        production_dir = production_root / case_id / "production50k"
        specs[key] = CaseSpec(
            key=key,
            case_id=case_id,
            eps_z=eps,
            production_dir=production_dir,
            dump_path=production_dir / "dump.lammpstrj",
            log_path=production_dir / "log.lammps",
            input_path=production_dir / "in.cpu_production50k",
            command_path=production_dir / "command.json",
        )
    return specs


def parse_thermo_log(path: Path) -> dict[int, dict[str, float]]:
    rows: dict[int, dict[str, float]] = {}
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "Step" and "Temp" in parts and "Pzz" in parts:
            header = parts
            continue
        if header is None:
            continue
        if len(parts) < len(header):
            continue
        try:
            values = [float(v) for v in parts[: len(header)]]
        except ValueError:
            header = None
            continue
        item = dict(zip(header, values))
        rows[int(item["Step"])] = item
    return rows


def scan_dump_steps(path: Path) -> list[int]:
    steps: list[int] = []
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip() == "ITEM: TIMESTEP":
                value = next(handle, "").strip()
                if value:
                    steps.append(int(value))
    return steps


def iter_dump_frames(path: Path, wanted_steps: set[int] | None = None) -> Iterable[tuple[int, list[str], tuple[tuple[float, float], tuple[float, float], tuple[float, float]], np.ndarray]]:
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        while True:
            line = handle.readline()
            if not line:
                return
            if line.strip() != "ITEM: TIMESTEP":
                continue
            step = int(handle.readline().strip())
            if handle.readline().strip() != "ITEM: NUMBER OF ATOMS":
                raise RuntimeError(f"Unexpected dump format in {path} at step {step}: missing atom count")
            atom_count = int(handle.readline().strip())
            bounds_header = handle.readline().strip()
            if not bounds_header.startswith("ITEM: BOX BOUNDS"):
                raise RuntimeError(f"Unexpected dump format in {path} at step {step}: missing bounds")
            bounds = tuple(tuple(float(x) for x in handle.readline().split()[:2]) for _ in range(3))
            atoms_header = handle.readline().strip()
            if not atoms_header.startswith("ITEM: ATOMS"):
                raise RuntimeError(f"Unexpected dump format in {path} at step {step}: missing atoms header")
            columns = atoms_header.split()[2:]
            if wanted_steps is not None and step not in wanted_steps:
                for _ in range(atom_count):
                    handle.readline()
                continue
            atom_lines = [handle.readline() for _ in range(atom_count)]
            flat = np.fromstring("".join(atom_lines), sep=" ", dtype=float)
            if flat.size != atom_count * len(columns):
                raise RuntimeError(
                    f"Cannot parse frame {step} in {path}: got {flat.size} values, "
                    f"expected {atom_count * len(columns)}"
                )
            yield step, columns, bounds, flat.reshape((atom_count, len(columns)))


def bin_edges(max_r: float) -> list[tuple[float, float]]:
    max_r = max(0.0, float(max_r))
    bins: list[tuple[float, float]] = []
    lo = 0.0
    while lo < min(50.0, max_r):
        hi = min(lo + 2.0, max_r)
        if hi > lo:
            bins.append((lo, hi))
        lo = hi
    lo = 50.0
    while lo < min(100.0, max_r):
        hi = min(lo + 5.0, max_r)
        if hi > lo:
            bins.append((lo, hi))
        lo = hi
    lo = 100.0
    while lo < max_r:
        hi = min(lo + 10.0, max_r)
        if hi > lo:
            bins.append((lo, hi))
        lo = hi
    return bins


def von_mises(tensor: np.ndarray) -> np.ndarray:
    xx, yy, zz, xy, xz, yz = [tensor[:, i] for i in range(6)]
    return np.sqrt(0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2) + 3.0 * (xy**2 + xz**2 + yz**2))


def principal_max(tensor: np.ndarray) -> np.ndarray:
    mats = np.zeros((len(tensor), 3, 3), dtype=float)
    mats[:, 0, 0] = tensor[:, 0]
    mats[:, 1, 1] = tensor[:, 1]
    mats[:, 2, 2] = tensor[:, 2]
    mats[:, 0, 1] = mats[:, 1, 0] = tensor[:, 3]
    mats[:, 0, 2] = mats[:, 2, 0] = tensor[:, 4]
    mats[:, 1, 2] = mats[:, 2, 1] = tensor[:, 5]
    return np.linalg.eigvalsh(mats)[:, -1]


def percentile(values: np.ndarray, q: float) -> float | None:
    if values.size == 0:
        return None
    return float(np.percentile(values, q))


def mean_or_none(values: np.ndarray) -> float | None:
    if values.size == 0:
        return None
    return float(np.mean(values))


def frame_from_raw(case: CaseSpec, step: int, columns: list[str], bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]], array: np.ndarray) -> FrameData:
    required = ["id", "type", "x", "y", "z", "c_pe_atom"] + [f"c_st[{i}]" for i in range(1, 7)]
    missing = [col for col in required if col not in columns]
    if missing:
        raise RuntimeError(f"Missing dump columns for {case.case_id} step {step}: {missing}")
    return FrameData(case.key, case.case_id, case.eps_z, step, columns, bounds, array)


def matrix_mask(frame: FrameData) -> np.ndarray:
    type_col = frame.columns.index("type")
    z_col = frame.columns.index("z")
    atom_type = frame.array[:, type_col].astype(int)
    z = frame.array[:, z_col]
    return (atom_type == 1) & (z >= INTERFACE_Z_A)


def max_al_r(frames: list[FrameData]) -> float:
    z_col = frames[0].columns.index("z")
    max_vals = []
    for frame in frames:
        mask = matrix_mask(frame)
        if np.any(mask):
            max_vals.append(float(np.max(frame.array[mask, z_col] - INTERFACE_Z_A)))
    return max(max_vals) if max_vals else 0.0


def stress_profile_for_frame(frame: FrameData, bins: list[tuple[float, float]], thermo: dict[str, float] | None, window: str) -> list[dict[str, Any]]:
    z_col = frame.columns.index("z")
    pe_col = frame.columns.index("c_pe_atom")
    stress_cols = [frame.columns.index(f"c_st[{i}]") for i in range(1, 7)]
    z = frame.array[:, z_col]
    pe = frame.array[:, pe_col]
    stress = frame.array[:, stress_cols]
    r = z - INTERFACE_Z_A
    base_mask = matrix_mask(frame)
    rows: list[dict[str, Any]] = []
    for lo, hi in bins:
        mask = base_mask & (r >= lo) & (r < hi)
        count = int(np.count_nonzero(mask))
        bin_width = hi - lo
        bin_volume = frame.lx * frame.ly * bin_width
        if count:
            atom_volume = bin_volume / count
            atom_tensor = -stress[mask] / atom_volume * BAR_TO_MPA
            mean_tensor = -np.sum(stress[mask], axis=0, keepdims=True) / bin_volume * BAR_TO_MPA
            atom_vm = von_mises(atom_tensor)
            atom_principal = principal_max(atom_tensor)
            atom_abs_zz = np.abs(atom_tensor[:, 2])
            atom_max_component = np.max(np.abs(atom_tensor), axis=1)
            mean_vm = float(von_mises(mean_tensor)[0])
            mean_principal = float(principal_max(mean_tensor)[0])
            mean_pe = float(np.mean(pe[mask]))
            frac_vm = float(np.count_nonzero(atom_vm > YIELD_THRESHOLD_MPA) / count)
            frac_abs_zz = float(np.count_nonzero(atom_abs_zz > YIELD_THRESHOLD_MPA) / count)
            frac_any = float(np.count_nonzero((atom_vm > YIELD_THRESHOLD_MPA) | (atom_abs_zz > YIELD_THRESHOLD_MPA)) / count)
            tensor_values = mean_tensor[0]
        else:
            atom_tensor = np.empty((0, 6))
            atom_vm = np.array([])
            atom_principal = np.array([])
            atom_abs_zz = np.array([])
            atom_max_component = np.array([])
            mean_vm = None
            mean_principal = None
            mean_pe = None
            frac_vm = 0.0
            frac_abs_zz = 0.0
            frac_any = 0.0
            tensor_values = np.array([np.nan] * 6)
        rows.append(
            {
                "case": frame.case_key,
                "case_id": frame.case_id,
                "eps_z": frame.eps_z,
                "window": window,
                "step": frame.step,
                "time_ps": frame.step * 0.001,
                "interface_z_A": INTERFACE_Z_A,
                "r_bin_min_A": lo,
                "r_bin_max_A": hi,
                "r_bin_center_A": 0.5 * (lo + hi),
                "r_bin_width_A": bin_width,
                "matrix_atoms_in_bin": count,
                "bin_volume_A3": bin_volume,
                "atom_volume_proxy_A3": bin_volume / count if count else None,
                "sigma_xx_mean_mpa": None if count == 0 else float(tensor_values[0]),
                "sigma_yy_mean_mpa": None if count == 0 else float(tensor_values[1]),
                "sigma_zz_mean_mpa": None if count == 0 else float(tensor_values[2]),
                "sigma_xy_mean_mpa": None if count == 0 else float(tensor_values[3]),
                "sigma_xz_mean_mpa": None if count == 0 else float(tensor_values[4]),
                "sigma_yz_mean_mpa": None if count == 0 else float(tensor_values[5]),
                "abs_sigma_zz_mean_mpa": None if count == 0 else abs(float(tensor_values[2])),
                "sigma_vm_mean_mpa": mean_vm,
                "sigma_principal_max_mean_mpa": mean_principal,
                "sigma_vm_median_mpa": percentile(atom_vm, 50),
                "sigma_vm_p90_mpa": percentile(atom_vm, 90),
                "sigma_vm_p95_mpa": percentile(atom_vm, 95),
                "sigma_vm_p99_mpa": percentile(atom_vm, 99),
                "sigma_principal_max_p95_mpa": percentile(atom_principal, 95),
                "abs_sigma_zz_p95_mpa": percentile(atom_abs_zz, 95),
                "max_component_p95_mpa": percentile(atom_max_component, 95),
                "fraction_vm_gt_120mpa": frac_vm,
                "fraction_abs_sigma_zz_gt_120mpa": frac_abs_zz,
                "fraction_any_gt_120mpa": frac_any,
                "pe_atom_mean_ev": mean_pe,
                "thermo_temp_K": None if thermo is None else thermo.get("Temp"),
                "thermo_press_bar": None if thermo is None else thermo.get("Press"),
                "thermo_pxx_bar": None if thermo is None else thermo.get("Pxx"),
                "thermo_pyy_bar": None if thermo is None else thermo.get("Pyy"),
                "thermo_pzz_bar": None if thermo is None else thermo.get("Pzz"),
                "stress_conversion_note": "sigma_mpa = -sum(c_stress_atom_virial)/(Lx*Ly*bin_width)*0.1; per-atom percentiles use bin_volume/count proxy",
            }
        )
    return rows


def average_window_rows(rows: list[dict[str, Any]], case_key: str, bins: list[tuple[float, float]], window: str) -> list[dict[str, Any]]:
    numeric_skip = {"step"}
    out: list[dict[str, Any]] = []
    for lo, hi in bins:
        members = [r for r in rows if r["case"] == case_key and r["r_bin_min_A"] == lo and r["r_bin_max_A"] == hi]
        if not members:
            continue
        row = dict(members[-1])
        row["window"] = window
        row["step"] = None
        row["time_ps"] = None
        row["window_step_min"] = min(int(m["step"]) for m in members)
        row["window_step_max"] = max(int(m["step"]) for m in members)
        row["window_frame_count"] = len(members)
        for key in list(row):
            if key in numeric_skip:
                continue
            values = [m.get(key) for m in members]
            if all(isinstance(v, (int, float, np.number)) and v is not None for v in values):
                row[key] = float(np.mean(values))
        row["case"] = case_key
        row["r_bin_min_A"] = lo
        row["r_bin_max_A"] = hi
        row["r_bin_center_A"] = 0.5 * (lo + hi)
        out.append(row)
    return out


def layer_thickness(rows: list[dict[str, Any]], metric: str, threshold: float = YIELD_THRESHOLD_MPA) -> float | None:
    selected = sorted(rows, key=lambda r: float(r["r_bin_min_A"]))
    thickness = 0.0
    started = False
    for row in selected:
        value = row.get(metric)
        if value is None:
            break
        above = abs(float(value)) > threshold if metric.startswith("sigma_zz") else float(value) > threshold
        if not started and float(row["r_bin_min_A"]) <= 0.0:
            started = True
        if started and above:
            thickness = float(row["r_bin_max_A"])
        elif started:
            break
    return thickness


def max_distance_above(rows: list[dict[str, Any]], metric: str, threshold: float = YIELD_THRESHOLD_MPA) -> float | None:
    values = []
    for row in rows:
        value = row.get(metric)
        if value is None:
            continue
        above = abs(float(value)) > threshold if metric.startswith("sigma_zz") else float(value) > threshold
        if above:
            values.append(float(row["r_bin_max_A"]))
    return max(values) if values else None


def profile_summary(rows: list[dict[str, Any]], case: str, window: str) -> dict[str, Any]:
    selected = [r for r in rows if r["case"] == case and r["window"] == window]
    near = [r for r in selected if float(r["r_bin_min_A"]) < 10.0]
    far = [r for r in selected if float(r["r_bin_min_A"]) >= 50.0]
    metrics = {
        "case": case,
        "window": window,
        "bins": len(selected),
        "matrix_atoms_total_proxy": sum(int(r.get("matrix_atoms_in_bin") or 0) for r in selected),
        "layer_mean_vm_gt_120_A": layer_thickness(selected, "sigma_vm_mean_mpa"),
        "layer_p95_vm_gt_120_A": layer_thickness(selected, "sigma_vm_p95_mpa"),
        "layer_abs_zz_mean_gt_120_A": layer_thickness(selected, "abs_sigma_zz_mean_mpa"),
        "layer_abs_zz_p95_gt_120_A": layer_thickness(selected, "abs_sigma_zz_p95_mpa"),
        "max_distance_mean_vm_gt_120_A": max_distance_above(selected, "sigma_vm_mean_mpa"),
        "max_distance_p95_vm_gt_120_A": max_distance_above(selected, "sigma_vm_p95_mpa"),
        "near_0_10A_sigma_vm_mean_mpa": mean_or_none(np.array([r["sigma_vm_mean_mpa"] for r in near if r.get("sigma_vm_mean_mpa") is not None], dtype=float)),
        "far_50A_plus_sigma_vm_mean_mpa": mean_or_none(np.array([r["sigma_vm_mean_mpa"] for r in far if r.get("sigma_vm_mean_mpa") is not None], dtype=float)),
        "near_0_10A_abs_sigma_zz_mean_mpa": mean_or_none(np.array([r["abs_sigma_zz_mean_mpa"] for r in near if r.get("abs_sigma_zz_mean_mpa") is not None], dtype=float)),
        "max_sigma_vm_mean_mpa": max((float(r["sigma_vm_mean_mpa"]) for r in selected if r.get("sigma_vm_mean_mpa") is not None), default=None),
        "max_sigma_vm_p95_mpa": max((float(r["sigma_vm_p95_mpa"]) for r in selected if r.get("sigma_vm_p95_mpa") is not None), default=None),
    }
    return metrics


def delta_rows(rows: list[dict[str, Any]], window: str, bins: list[tuple[float, float]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for lo, hi in bins:
        control = next((r for r in rows if r["case"] == "eps0000" and r["window"] == window and r["r_bin_min_A"] == lo and r["r_bin_max_A"] == hi), None)
        physical = next((r for r in rows if r["case"] == "eps00194" and r["window"] == window and r["r_bin_min_A"] == lo and r["r_bin_max_A"] == hi), None)
        if control is None or physical is None:
            continue
        row = {
            "window": window,
            "r_bin_min_A": lo,
            "r_bin_max_A": hi,
            "r_bin_center_A": 0.5 * (lo + hi),
            "eps00194_atoms": physical.get("matrix_atoms_in_bin"),
            "eps0000_atoms": control.get("matrix_atoms_in_bin"),
        }
        for metric in [
            "sigma_xx_mean_mpa",
            "sigma_yy_mean_mpa",
            "sigma_zz_mean_mpa",
            "abs_sigma_zz_mean_mpa",
            "sigma_vm_mean_mpa",
            "sigma_vm_p95_mpa",
            "abs_sigma_zz_p95_mpa",
            "fraction_vm_gt_120mpa",
            "fraction_abs_sigma_zz_gt_120mpa",
            "pe_atom_mean_ev",
        ]:
            cval = control.get(metric)
            pval = physical.get(metric)
            row[f"eps0000_{metric}"] = cval
            row[f"eps00194_{metric}"] = pval
            row[f"delta_{metric}"] = None if cval is None or pval is None else float(pval) - float(cval)
        out.append(row)
    return out


def ovito_available() -> tuple[bool, str]:
    try:
        import ovito  # noqa: F401

        return True, ".".join(str(x) for x in ovito.version)
    except Exception as exc:  # pragma: no cover - environment dependent
        return False, f"{type(exc).__name__}: {exc}"


def defect_profile_for_frame(case: CaseSpec, step: int, frame_index: int, bins: list[tuple[float, float]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from ovito.io import import_file
    from ovito.modifiers import CommonNeighborAnalysisModifier, DislocationAnalysisModifier

    pipe = import_file(str(case.dump_path), multiple_frames=True)
    pipe.modifiers.append(CommonNeighborAnalysisModifier())
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)
    data = pipe.compute(frame_index)

    positions = np.asarray(data.particles.positions, dtype=float)
    types = np.asarray(data.particles["Particle Type"], dtype=int)
    structure_type = np.asarray(data.particles["Structure Type"], dtype=int)
    z = positions[:, 2]
    r = z - INTERFACE_Z_A
    base_mask = (types == 1) & (z >= INTERFACE_Z_A)

    rows: list[dict[str, Any]] = []
    for lo, hi in bins:
        mask = base_mask & (r >= lo) & (r < hi)
        count = int(np.count_nonzero(mask))
        fcc = int(np.count_nonzero(mask & (structure_type == 1)))
        hcp = int(np.count_nonzero(mask & (structure_type == 2)))
        bcc = int(np.count_nonzero(mask & (structure_type == 3)))
        ico = int(np.count_nonzero(mask & (structure_type == 4)))
        other = int(np.count_nonzero(mask & (structure_type == 0)))
        rows.append(
            {
                "case": case.key,
                "case_id": case.case_id,
                "eps_z": case.eps_z,
                "window": "initial" if step == 0 else "final",
                "step": step,
                "interface_z_A": INTERFACE_Z_A,
                "r_bin_min_A": lo,
                "r_bin_max_A": hi,
                "r_bin_center_A": 0.5 * (lo + hi),
                "matrix_atoms_in_bin": count,
                "fcc_atoms": fcc,
                "hcp_atoms": hcp,
                "bcc_atoms": bcc,
                "ico_atoms": ico,
                "other_atoms": other,
                "hcp_fraction": hcp / count if count else 0.0,
                "other_fraction": other / count if count else 0.0,
                "non_fcc_fraction": (count - fcc) / count if count else 0.0,
                "dmin2_status": "unavailable_not_stored_in_dump_not_computed",
            }
        )

    dislocation_segments = 0
    dislocation_line = 0.0
    try:
        dislocation_segments = int(len(data.dislocations.segments))
        dislocation_line = float(data.attributes.get("DislocationAnalysis.total_line_length", 0.0))
        if dislocation_segments and dislocation_line == 0.0:
            dislocation_line = float(sum(segment.length for segment in data.dislocations.segments))
    except Exception:
        dislocation_segments = 0
        dislocation_line = 0.0
    frame_summary = {
        "case": case.key,
        "case_id": case.case_id,
        "step": step,
        "frame_index": frame_index,
        "matrix_atoms": int(np.count_nonzero(base_mask)),
        "fcc_atoms": int(np.count_nonzero(base_mask & (structure_type == 1))),
        "hcp_atoms": int(np.count_nonzero(base_mask & (structure_type == 2))),
        "other_atoms": int(np.count_nonzero(base_mask & (structure_type == 0))),
        "non_fcc_atoms": int(np.count_nonzero(base_mask & (structure_type != 1))),
        "dislocation_segments": dislocation_segments,
        "dislocation_line_length_A": dislocation_line,
        "dmin2_status": "unavailable_not_stored_in_dump_not_computed",
    }
    return rows, frame_summary


def delta_defect_rows(rows: list[dict[str, Any]], window: str, bins: list[tuple[float, float]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for lo, hi in bins:
        control = next((r for r in rows if r["case"] == "eps0000" and r["window"] == window and r["r_bin_min_A"] == lo and r["r_bin_max_A"] == hi), None)
        physical = next((r for r in rows if r["case"] == "eps00194" and r["window"] == window and r["r_bin_min_A"] == lo and r["r_bin_max_A"] == hi), None)
        if control is None or physical is None:
            continue
        row = {
            "window": window,
            "r_bin_min_A": lo,
            "r_bin_max_A": hi,
            "r_bin_center_A": 0.5 * (lo + hi),
            "eps0000_matrix_atoms": control["matrix_atoms_in_bin"],
            "eps00194_matrix_atoms": physical["matrix_atoms_in_bin"],
        }
        for metric in ["hcp_atoms", "other_atoms", "non_fcc_fraction", "hcp_fraction", "other_fraction"]:
            cval = control.get(metric)
            pval = physical.get(metric)
            row[f"eps0000_{metric}"] = cval
            row[f"eps00194_{metric}"] = pval
            row[f"delta_{metric}"] = None if cval is None or pval is None else float(pval) - float(cval)
        out.append(row)
    return out


def write_inventory(specs: dict[str, CaseSpec], steps_by_case: dict[str, list[int]], setup: dict[str, Any], status: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    cases = []
    for spec in specs.values():
        files = []
        for path in sorted(spec.production_dir.iterdir()):
            files.append(
                {
                    "name": path.name,
                    "path": str(path.relative_to(REPO_ROOT)),
                    "size_bytes": path.stat().st_size,
                    "last_write_time": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                }
            )
        cases.append(
            {
                "case": spec.key,
                "case_id": spec.case_id,
                "production_dir": str(spec.production_dir.relative_to(REPO_ROOT)),
                "dump_steps": steps_by_case.get(spec.key, []),
                "dump_frame_count": len(steps_by_case.get(spec.key, [])),
                "dump_cadence_steps": 1000,
                "files": files,
            }
        )
    inventory = {
        "generated_at": now_iso(),
        "status": "completed",
        "production_root": str(PRODUCTION_ROOT.relative_to(REPO_ROOT)),
        "protocol": setup.get("protocol", {}),
        "worker_status": status.get("status"),
        "cases": cases,
    }
    json_path = REPORTS_DIR / "stageF_cpu_results_dump_inventory.json"
    md_path = REPORTS_DIR / "stageF_cpu_results_dump_inventory.md"
    write_json(json_path, inventory)
    lines = [
        "# Stage F CPU results: dump inventory",
        "",
        f"Дата: {inventory['generated_at']}",
        "",
        f"Production root: `{inventory['production_root']}`",
        "",
        markdown_table(
            ["case", "frames", "first step", "last step", "dump size GB", "folder"],
            [
                [
                    case["case"],
                    case["dump_frame_count"],
                    case["dump_steps"][0] if case["dump_steps"] else None,
                    case["dump_steps"][-1] if case["dump_steps"] else None,
                    next((f["size_bytes"] for f in case["files"] if f["name"] == "dump.lammpstrj"), 0) / 1e9,
                    case["production_dir"],
                ]
                for case in cases
            ],
        ),
        "",
        "## Files",
    ]
    for case in cases:
        lines.extend(["", f"### {case['case']}"])
        lines.append(markdown_table(["name", "size bytes"], [[f["name"], f["size_bytes"]] for f in case["files"]]))
    write_text(md_path, "\n".join(lines))
    return md_path, json_path, inventory


def write_production_verification(specs: dict[str, CaseSpec], setup: dict[str, Any], status: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    results = status.get("production_results", [])
    cases = []
    for result in results:
        cases.append(
            {
                "case": result.get("case"),
                "status": result.get("status"),
                "returncode": result.get("returncode"),
                "max_step": result.get("max_step"),
                "fatal": result.get("fatal"),
                "final_data_exists": result.get("final_data_exists"),
                "final_restart_exists": result.get("final_restart_exists"),
                "last_thermo": result.get("last_thermo"),
            }
        )
    verification = {
        "generated_at": now_iso(),
        "status": "completed_clean_cpu_pair" if all(c.get("status") == "completed_clean" and c.get("returncode") == 0 and c.get("max_step") == 50000 for c in cases) else "check_required",
        "analysis_scope": "CPU fallback production results only",
        "no_new_production_launched_by_this_analysis": True,
        "no_gpu_cpu_mixing": True,
        "protocol": setup.get("protocol", {}),
        "cpu_policy": setup.get("cpu_policy", {}),
        "cases": cases,
    }
    json_path = REPORTS_DIR / "stageF_cpu_results_production_verification.json"
    md_path = REPORTS_DIR / "stageF_cpu_results_production_verification.md"
    write_json(json_path, verification)
    lines = [
        "# Stage F CPU results: production verification",
        "",
        f"Дата: {verification['generated_at']}",
        "",
        f"Status: `{verification['status']}`",
        "",
        "Проверка относится только к CPU fallback pair. GPU результаты не смешивались с CPU delta pair.",
        "",
        markdown_table(
            ["case", "status", "return", "max step", "final data", "final restart"],
            [[c["case"], c["status"], c["returncode"], c["max_step"], c["final_data_exists"], c["final_restart_exists"]] for c in cases],
        ),
        "",
        "## Protocol gates",
        "",
        markdown_table(
            ["gate", "value"],
            [
                ["boundary", setup.get("protocol", {}).get("boundary")],
                ["zhi_A", setup.get("protocol", {}).get("zhi_A")],
                ["dump_every", setup.get("protocol", {}).get("dump_every")],
                ["thermo_modify_lost_ignore", setup.get("protocol", {}).get("thermo_modify_lost_ignore")],
                ["box_relax", setup.get("protocol", {}).get("box_relax")],
                ["wall", setup.get("protocol", {}).get("wall")],
            ],
        ),
    ]
    write_text(md_path, "\n".join(lines))
    return md_path, json_path, verification


def write_stress_outputs(stress_rows: list[dict[str, Any]], delta: list[dict[str, Any]], summaries: list[dict[str, Any]]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for case in ["eps0000", "eps00194"]:
        case_rows = [r for r in stress_rows if r["case"] == case and r["window"] in {"initial", "final", "last20_mean"}]
        path = REPORTS_DIR / f"stageF_cpu_results_{case}_sigma_profile.csv"
        write_csv(path, case_rows)
        paths[f"{case}_sigma_profile"] = path
    delta_path = REPORTS_DIR / "stageF_cpu_results_delta_sigma_profile.csv"
    write_csv(delta_path, delta)
    paths["delta_sigma_profile"] = delta_path
    summary = {
        "generated_at": now_iso(),
        "status": "completed",
        "interface_z_A": INTERFACE_Z_A,
        "yield_threshold_mpa": YIELD_THRESHOLD_MPA,
        "stress_conversion": "LAMMPS stress/atom virial converted as sigma_mpa = -sum(c_st)/(Lx*Ly*bin_width)*0.1; per-atom percentiles use bin_volume/count proxy.",
        "windows": ["initial", "final", "last20_mean"],
        "summary": summaries,
        "delta_summary": {
            "final_max_delta_sigma_vm_mean_mpa": max((abs(float(r["delta_sigma_vm_mean_mpa"])) for r in delta if r["window"] == "final" and r.get("delta_sigma_vm_mean_mpa") is not None), default=None),
            "last20_max_delta_sigma_vm_mean_mpa": max((abs(float(r["delta_sigma_vm_mean_mpa"])) for r in delta if r["window"] == "last20_mean" and r.get("delta_sigma_vm_mean_mpa") is not None), default=None),
            "final_max_delta_abs_sigma_zz_mean_mpa": max((abs(float(r["delta_abs_sigma_zz_mean_mpa"])) for r in delta if r["window"] == "final" and r.get("delta_abs_sigma_zz_mean_mpa") is not None), default=None),
        },
    }
    summary_path = REPORTS_DIR / "stageF_cpu_results_sigma_summary.json"
    write_json(summary_path, summary)
    paths["sigma_summary"] = summary_path
    return paths


def plot_stress_figures(stress_rows: list[dict[str, Any]], delta_rows_: list[dict[str, Any]]) -> list[str]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    files: list[str] = []

    def plot_cases(metric: str, ylabel: str, filename: str, window: str = "last20_mean") -> None:
        fig, ax = plt.subplots(figsize=(8, 5))
        for case, label in [("eps0000", "eps0000 control"), ("eps00194", "eps00194")]:
            selected = sorted([r for r in stress_rows if r["case"] == case and r["window"] == window and r.get(metric) is not None], key=lambda r: r["r_bin_center_A"])
            ax.plot([r["r_bin_center_A"] for r in selected], [r[metric] for r in selected], marker="o", linewidth=1.5, markersize=3, label=label)
        ax.axhline(YIELD_THRESHOLD_MPA, color="black", linestyle="--", linewidth=1, label="120 MPa")
        ax.set_xlabel("r from interface into Al, A")
        ax.set_ylabel(ylabel)
        ax.set_title(f"Stage F CPU {window}: {ylabel}")
        ax.grid(True, alpha=0.25)
        ax.legend()
        out = FIGURES_DIR / filename
        fig.tight_layout()
        fig.savefig(out, dpi=180)
        plt.close(fig)
        files.append(str(out.relative_to(REPO_ROOT)))

    plot_cases("sigma_vm_mean_mpa", "mean von Mises proxy, MPa", "stageF_cpu_results_sigma_vm_last20.png")
    plot_cases("abs_sigma_zz_mean_mpa", "mean |sigma_zz| proxy, MPa", "stageF_cpu_results_sigma_zz_last20.png")
    plot_cases("sigma_vm_p95_mpa", "p95 atom VM proxy, MPa", "stageF_cpu_results_sigma_vm_p95_last20.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    selected = sorted([r for r in delta_rows_ if r["window"] == "last20_mean" and r.get("delta_sigma_vm_mean_mpa") is not None], key=lambda r: r["r_bin_center_A"])
    ax.plot([r["r_bin_center_A"] for r in selected], [r["delta_sigma_vm_mean_mpa"] for r in selected], marker="o", linewidth=1.5, markersize=3, label="eps00194 - eps0000")
    ax.axhline(0.0, color="black", linewidth=1)
    ax.axhline(YIELD_THRESHOLD_MPA, color="black", linestyle="--", linewidth=1, label="+120 MPa")
    ax.axhline(-YIELD_THRESHOLD_MPA, color="black", linestyle="--", linewidth=1, label="-120 MPa")
    ax.set_xlabel("r from interface into Al, A")
    ax.set_ylabel("delta mean VM proxy, MPa")
    ax.set_title("Stage F CPU delta sigma(r), last 20%")
    ax.grid(True, alpha=0.25)
    ax.legend()
    out = FIGURES_DIR / "stageF_cpu_results_delta_sigma_vm_last20.png"
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)
    files.append(str(out.relative_to(REPO_ROOT)))

    return files


def plot_defect_figures(defect_rows: list[dict[str, Any]], delta_rows_: list[dict[str, Any]]) -> list[str]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    for metric, ylabel, filename in [
        ("other_fraction", "OTHER fraction", "stageF_cpu_results_defect_other_final.png"),
        ("hcp_fraction", "HCP fraction", "stageF_cpu_results_defect_hcp_final.png"),
        ("non_fcc_fraction", "non-FCC fraction", "stageF_cpu_results_defect_nonfcc_final.png"),
    ]:
        fig, ax = plt.subplots(figsize=(8, 5))
        for case, label in [("eps0000", "eps0000 control"), ("eps00194", "eps00194")]:
            selected = sorted([r for r in defect_rows if r["case"] == case and r["window"] == "final"], key=lambda r: r["r_bin_center_A"])
            ax.plot([r["r_bin_center_A"] for r in selected], [r[metric] for r in selected], marker="o", linewidth=1.5, markersize=3, label=label)
        ax.set_xlabel("r from interface into Al, A")
        ax.set_ylabel(ylabel)
        ax.set_title(f"Stage F CPU final CNA: {ylabel}")
        ax.grid(True, alpha=0.25)
        ax.legend()
        out = FIGURES_DIR / filename
        fig.tight_layout()
        fig.savefig(out, dpi=180)
        plt.close(fig)
        files.append(str(out.relative_to(REPO_ROOT)))

    fig, ax = plt.subplots(figsize=(8, 5))
    selected = sorted([r for r in delta_rows_ if r["window"] == "final"], key=lambda r: r["r_bin_center_A"])
    ax.plot([r["r_bin_center_A"] for r in selected], [r["delta_non_fcc_fraction"] for r in selected], marker="o", linewidth=1.5, markersize=3)
    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_xlabel("r from interface into Al, A")
    ax.set_ylabel("delta non-FCC fraction")
    ax.set_title("Stage F CPU final delta CNA: eps00194 - eps0000")
    ax.grid(True, alpha=0.25)
    out = FIGURES_DIR / "stageF_cpu_results_delta_defect_nonfcc_final.png"
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)
    files.append(str(out.relative_to(REPO_ROOT)))
    return files


def write_defect_outputs(defect_rows: list[dict[str, Any]], delta: list[dict[str, Any]], frame_summaries: list[dict[str, Any]], ovito_version: str, figure_paths: list[str]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for case in ["eps0000", "eps00194"]:
        path = REPORTS_DIR / f"stageF_cpu_results_{case}_defect_profile.csv"
        write_csv(path, [r for r in defect_rows if r["case"] == case])
        paths[f"{case}_defect_profile"] = path
    delta_path = REPORTS_DIR / "stageF_cpu_results_delta_defect_profile.csv"
    write_csv(delta_path, delta)
    paths["delta_defect_profile"] = delta_path
    summary = {
        "generated_at": now_iso(),
        "status": "completed",
        "ovito_version": ovito_version,
        "frames_analyzed": frame_summaries,
        "dmin2_status": "unavailable_not_stored_in_dump_not_computed_for_this_report",
        "interpretation_guardrail": "CNA/DXA are secondary indicators; no developed-dislocation/plasticity claim is made from short or non-persistent signals.",
        "figures": figure_paths,
    }
    path = REPORTS_DIR / "stageF_cpu_results_defect_summary.json"
    write_json(path, summary)
    paths["defect_summary"] = path
    return paths


def write_stress_report(summary: dict[str, Any], stress_figures: list[str], delta_rows_: list[dict[str, Any]]) -> Path:
    rows = summary["summary"]
    final_rows = [r for r in rows if r["window"] == "final"]
    last_rows = [r for r in rows if r["window"] == "last20_mean"]
    delta_peak = summary["delta_summary"].get("last20_max_delta_sigma_vm_mean_mpa")
    text = f"""# Stage F CPU results: sigma(r) report

Дата: {summary['generated_at']}

## Краткий вывод

CPU fallback pair дает валидный post-processing ответ на главный запрос Пшонкина: `sigma(r)` построен от плоской границы `z = {INTERFACE_Z_A} A` в Al matrix, отдельно для `eps0000` и `eps00194`, плюс baseline-subtracted delta `eps00194 - eps0000`.

Главная оговорка: это local virial stress proxy, а не калиброванное continuum-напряжение. Поэтому надежнее читать форму профиля и baseline delta, чем абсолютные p95 atom-level значения.

## Thickness checks

Final frame:

{markdown_table(['case', 'mean VM layer A', 'p95 VM layer A', '|zz| mean layer A', 'near 0-10A VM MPa', 'far 50A+ VM MPa'], [[r['case'], r['layer_mean_vm_gt_120_A'], r['layer_p95_vm_gt_120_A'], r['layer_abs_zz_mean_gt_120_A'], r['near_0_10A_sigma_vm_mean_mpa'], r['far_50A_plus_sigma_vm_mean_mpa']] for r in final_rows])}

Last 20% window:

{markdown_table(['case', 'mean VM layer A', 'p95 VM layer A', '|zz| mean layer A', 'near 0-10A VM MPa', 'far 50A+ VM MPa'], [[r['case'], r['layer_mean_vm_gt_120_A'], r['layer_p95_vm_gt_120_A'], r['layer_abs_zz_mean_gt_120_A'], r['near_0_10A_sigma_vm_mean_mpa'], r['far_50A_plus_sigma_vm_mean_mpa']] for r in last_rows])}

Peak absolute baseline delta in last-20%-mean `sigma_vm_mean`: `{fmt(delta_peak)} MPa`.

## Что можно сказать Пшонкину

- `sigma(r)` построен в нужной геометрии: `r=0` на interface, `+Z` в Al matrix.
- Слой относительно `120 MPa` есть по local virial proxy, но p95 atom-level proxy шумный; cutoff нельзя превращать в точную физическую длину без оговорки.
- Baseline delta CPU-only показывает изменение поля напряжений от eigenstrain, без смешивания CPU/GPU.

## Figures

{chr(10).join(f'- `{p}`' for p in stress_figures)}

## Files

- `docs/reports/stageF_cpu_results_eps0000_sigma_profile.csv`
- `docs/reports/stageF_cpu_results_eps00194_sigma_profile.csv`
- `docs/reports/stageF_cpu_results_delta_sigma_profile.csv`
- `docs/reports/stageF_cpu_results_sigma_summary.json`
"""
    path = REPORTS_DIR / "stageF_cpu_results_sigma_report_ru.md"
    write_text(path, text)
    return path


def write_plasticity_report(defect_summary: dict[str, Any], defect_figures: list[str]) -> Path:
    frame_summaries = defect_summary["frames_analyzed"]
    text = f"""# Stage F CPU results: defect/plasticity report

Дата: {defect_summary['generated_at']}

## Краткий вывод

CNA/DXA post-processing выполнен через OVITO `{defect_summary['ovito_version']}` для `step 0` и `step 50000` по обеим CPU cases. Анализ ограничен Al matrix (`type=1`, `z >= {INTERFACE_Z_A} A`) и теми же `r`-bins.

`Dmin2` не заявлен: это свойство не было сохранено в dump, а в этом отчете не вводилась отдельная reference-strain процедура.

## Frame summary

{markdown_table(['case', 'step', 'matrix atoms', 'HCP', 'OTHER', 'non-FCC', 'DXA segments', 'DXA line A'], [[r['case'], r['step'], r['matrix_atoms'], r['hcp_atoms'], r['other_atoms'], r['non_fcc_atoms'], r['dislocation_segments'], r['dislocation_line_length_A']] for r in frame_summaries])}

## Интерпретация

CNA/OTHER около interface и свободной поверхности трактуется как локальное нарушение решетки/топологии. Сам по себе такой сигнал не равен доказанной пластической зоне. DXA line length в финале, если появляется, должен читаться только вместе с устойчивостью во времени; текущий defect block имеет `step 0` и `step 50000`, поэтому не доказывает persistent dislocation dynamics.

## Figures

{chr(10).join(f'- `{p}`' for p in defect_figures)}

## Files

- `docs/reports/stageF_cpu_results_eps0000_defect_profile.csv`
- `docs/reports/stageF_cpu_results_eps00194_defect_profile.csv`
- `docs/reports/stageF_cpu_results_delta_defect_profile.csv`
- `docs/reports/stageF_cpu_results_defect_summary.json`
"""
    path = REPORTS_DIR / "stageF_cpu_results_plasticity_report_ru.md"
    write_text(path, text)
    return path


def write_residual_check(stress_summary: dict[str, Any], defect_summary: dict[str, Any], delta_defect: list[dict[str, Any]]) -> tuple[Path, Path, dict[str, Any]]:
    final_dxa = [r for r in defect_summary["frames_analyzed"] if r["step"] == FINAL_STEP]
    final_delta_nonfcc = max((abs(float(r["delta_non_fcc_fraction"])) for r in delta_defect if r["window"] == "final" and r.get("delta_non_fcc_fraction") is not None), default=0.0)
    final_delta_other = max((abs(float(r["delta_other_fraction"])) for r in delta_defect if r["window"] == "final" and r.get("delta_other_fraction") is not None), default=0.0)
    max_dxa_line = max((float(r["dislocation_line_length_A"]) for r in final_dxa), default=0.0)
    verdict = "not_confirmed"
    if max_dxa_line > 50.0 or final_delta_nonfcc > 0.05:
        verdict = "possible_local_lattice_disturbance_not_persistent_plasticity"
    data = {
        "generated_at": now_iso(),
        "status": "completed",
        "verdict": verdict,
        "max_final_dxa_line_length_A": max_dxa_line,
        "max_abs_final_delta_nonfcc_fraction": final_delta_nonfcc,
        "max_abs_final_delta_other_fraction": final_delta_other,
        "stress_delta_last20_max_vm_mean_mpa": stress_summary["delta_summary"].get("last20_max_delta_sigma_vm_mean_mpa"),
        "reasoning": [
            "Stress transfer is present as a virial proxy, but stress alone is not residual plasticity.",
            "CNA/DXA final comparison does not establish a persistent dislocation network.",
            "Dmin2 was not available from stored dump fields and is not claimed.",
        ],
    }
    json_path = REPORTS_DIR / "stageF_cpu_results_residual_plasticity_check.json"
    md_path = REPORTS_DIR / "stageF_cpu_results_residual_plasticity_check_ru.md"
    write_json(json_path, data)
    text = f"""# Stage F CPU results: residual plasticity check

Дата: {data['generated_at']}

Verdict: `{data['verdict']}`.

Stress transfer is visible in `sigma(r)`, but residual plasticity is not confirmed by the available final CNA/DXA evidence. The strongest final baseline delta in non-FCC fraction is `{fmt(final_delta_nonfcc)}`; max final DXA line length is `{fmt(max_dxa_line)} A`.

This report intentionally avoids claiming developed dislocation behavior or persistent plastic deformation from a local/short structural signal.
"""
    write_text(md_path, text)
    return md_path, json_path, data


def source_map(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    materials = REPO_ROOT / "pshonkin_materials_ishodniki"
    data = {
        "prompt": str(PROMPT_PATH),
        "physicist_transcript": str(materials / "Phonkin_discussion_m4a.txt"),
        "visual_sketches": [str(p) for p in sorted(materials.glob("visual*.jpg"))],
        "cpu_setup": str(SETUP_JSON),
        "cpu_worker_status": str(STATUS_JSON),
        "production_status": str(PRODUCTION_STATUS_JSON),
        "production_root": str(PRODUCTION_ROOT),
        "previous_alignment": str(REPORTS_DIR / "stageF_physics_meeting_alignment_ru.md"),
        "previous_boundary_stress_decay": str(REPORTS_DIR / "stageF_boundary_stress_decay_report_ru.md"),
    }
    if extra:
        data.update(extra)
    return data


def write_criteria_map(stress_summary: dict[str, Any], residual: dict[str, Any]) -> Path:
    criteria = [
        ["CPU pair completed clean", "yes", "Both eps0000/eps00194 production50k returncode 0, max step 50000."],
        ["No CPU/GPU mixing", "yes", "Delta uses CPU fallback pair only."],
        ["r=0 on Fe4Al13/Al interface", "yes", f"F0 planar interface `z={INTERFACE_Z_A} A`, +Z into Al matrix."],
        ["Al matrix only", "yes", "`type=1` and `z>=interface_z`."],
        ["sigma(r) vs 120 MPa", "yes", "Mean VM, p95 VM, |sigma_zz| metrics exported."],
        ["Baseline-subtracted delta", "yes", "`eps00194 - eps0000` CSV exported."],
        ["Final + last 20% window", "yes", "`step 50000` and `40000..50000` time-averaged stress profiles."],
        ["CNA/DXA defect check", "partial", "OVITO CNA/DXA on step 0 and final; Dmin2 unavailable."],
        ["Persistent plasticity claim", "no", f"Residual verdict: `{residual['verdict']}`."],
        ["Physical report to Pshonkin", "yes", "Russian reports and meeting brief generated."],
    ]
    text = f"""# Stage F CPU results: Pshonkin criteria map

Дата: {stress_summary['generated_at']}

{markdown_table(['criterion', 'status', 'evidence'], criteria)}

## Guardrails

- Не утверждать, что стабильная дислокация доказана.
- Не превращать atom-level virial p95 в точный continuum cutoff без оговорки.
- Не смешивать CPU и GPU lanes в одном delta pair.
- Не считать GPU blocker физическим blocker для уже завершенной CPU пары.

## Source Map

```json
{json.dumps(source_map(), indent=2, ensure_ascii=False)}
```
"""
    path = REPORTS_DIR / "stageF_cpu_results_pshonkin_criteria_map_ru.md"
    write_text(path, text)
    return path


def write_pshonkin_report(stress_summary: dict[str, Any], defect_summary: dict[str, Any], residual: dict[str, Any], stress_figures: list[str], defect_figures: list[str]) -> Path:
    last = {r["case"]: r for r in stress_summary["summary"] if r["window"] == "last20_mean"}
    text = f"""# Stage F CPU results: report for Pshonkin criteria

Дата: {stress_summary['generated_at']}

## Answer

Завершенная CPU fallback pair пригодна как физический ответ на текущий запрос: построен `sigma(r)` от плоской границы Fe4Al13/Al в Al matrix, выполнено сравнение `eps00194` против `eps0000`, и результат проверен относительно `sigma_y = {YIELD_THRESHOLD_MPA} MPa`.

При этом остаточная пластичность не подтверждена: verdict residual-check = `{residual['verdict']}`. Корректная формулировка: есть передача/перераспределение local virial stress proxy около interface; устойчивую дислокационную пластическую зону по этим данным заявлять нельзя.

## Last 20% stress summary

{markdown_table(['case', 'mean VM layer A', 'p95 VM layer A', 'near 0-10A VM MPa', 'far 50A+ VM MPa'], [[case, row['layer_mean_vm_gt_120_A'], row['layer_p95_vm_gt_120_A'], row['near_0_10A_sigma_vm_mean_mpa'], row['far_50A_plus_sigma_vm_mean_mpa']] for case, row in last.items()])}

## Defect/plasticity status

{markdown_table(['case', 'step', 'HCP', 'OTHER', 'DXA segments', 'DXA line A'], [[r['case'], r['step'], r['hcp_atoms'], r['other_atoms'], r['dislocation_segments'], r['dislocation_line_length_A']] for r in defect_summary['frames_analyzed']])}

`Dmin2` не использовался, потому что это поле не сохранено в CPU dump, а отдельный reference-strain pipeline в этом анализе не вводился.

## Figures

{chr(10).join(f'- `{p}`' for p in stress_figures + defect_figures)}

## Source Map

```json
{json.dumps(source_map(), indent=2, ensure_ascii=False)}
```
"""
    path = REPORTS_DIR / "stageF_cpu_results_pshonkin_report_ru.md"
    write_text(path, text)
    return path


def write_meeting_brief(stress_summary: dict[str, Any], residual: dict[str, Any]) -> Path:
    delta_peak = stress_summary["delta_summary"].get("last20_max_delta_sigma_vm_mean_mpa")
    text = f"""# Stage F CPU results: meeting brief

Дата: {stress_summary['generated_at']}

- CPU pair завершена clean: `eps0000` и `eps00194`, 50k steps, `p p f`, zhi=200 A.
- `sigma(r)` построен от interface `z={INTERFACE_Z_A} A` в Al matrix.
- Last-20%-mean peak baseline delta по mean VM proxy: `{fmt(delta_peak)} MPa`.
- Порог `120 MPa` используется как ориентир stress layer, но absolute virial MPa не надо продавать как точный continuum cutoff.
- Остаточная пластичность: `{residual['verdict']}`.
- Безопасная формулировка: stress transfer/local lattice disturbance near interface; persistent dislocation/plastic zone не доказана.
"""
    path = REPORTS_DIR / "stageF_cpu_results_pshonkin_meeting_brief_ru.md"
    write_text(path, text)
    return path


def write_next_step_decision(stress_summary: dict[str, Any], residual: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    data = {
        "generated_at": now_iso(),
        "decision": "use_completed_cpu_pair_for_pshonkin_report_do_not_launch_new_production_now",
        "next_step": "If stronger plasticity evidence is required, run a separate post-processing task for Dmin2/atomic-strain reference handling or a planned longer boundary-patch run; do not treat GPU recovery as required for this CPU physics report.",
        "do_not_do": [
            "do not launch eps005, F1, F0_300A, or new production under this task",
            "do not mix CPU and GPU in the same delta pair",
            "do not claim persistent dislocation/plasticity from these CPU outputs",
        ],
        "stress_delta_last20_max_vm_mean_mpa": stress_summary["delta_summary"].get("last20_max_delta_sigma_vm_mean_mpa"),
        "residual_plasticity_verdict": residual["verdict"],
    }
    json_path = REPORTS_DIR / "stageF_cpu_results_next_step_decision.json"
    md_path = REPORTS_DIR / "stageF_cpu_results_next_step_decision_ru.md"
    write_json(json_path, data)
    text = f"""# Stage F CPU results: next-step decision

Дата: {data['generated_at']}

Decision: `{data['decision']}`.

Следующий шаг: {data['next_step']}

Запуски новой production в этом анализе не нужны. GPU recovery остается технической задачей ускорения/воспроизводимости, но не блокирует физический отчет по уже завершенной CPU pair.
"""
    write_text(md_path, text)
    return md_path, json_path, data


def write_agent_report(outputs: dict[str, Any], stress_summary: dict[str, Any], residual: dict[str, Any]) -> Path:
    output_lines = []
    for value in outputs.values():
        if isinstance(value, Path):
            output_lines.append(f"- `{value.relative_to(REPO_ROOT) if value.is_relative_to(REPO_ROOT) else value}`")
        elif isinstance(value, list):
            for item in value:
                output_lines.append(f"- `{item}`")
    text = f"""# Agent report: Stage F CPU results Pshonkin analysis

Date: {now_iso()}

Completed post-processing only. No LAMMPS production, GPU repair, raw dump deletion, restart deletion, git commit, push, merge, or deploy was performed.

## Result

- CPU pair: completed clean, 50k steps each.
- Interface: F0 planar, `r=0` at `z={INTERFACE_Z_A} A`, +Z into Al matrix.
- Stress delta last-20%-mean peak VM proxy: `{fmt(stress_summary['delta_summary'].get('last20_max_delta_sigma_vm_mean_mpa'))} MPa`.
- Residual plasticity verdict: `{residual['verdict']}`.
- Safe interpretation: stress transfer/local lattice disturbance; no persistent dislocation/plastic-zone claim.

## Outputs

{chr(10).join(output_lines)}
"""
    path = REPO_ROOT / "agent_report_stageF_cpu_results_pshonkin_analysis.md"
    write_text(path, text)
    return path


def analyze(production_root: Path) -> dict[str, Any]:
    setup = read_json(SETUP_JSON)
    status = read_json(STATUS_JSON)
    production_status = read_json(PRODUCTION_STATUS_JSON, {})
    specs = case_specs(production_root)

    for spec in specs.values():
        for path in [spec.production_dir, spec.dump_path, spec.log_path, spec.input_path, spec.command_path]:
            if not path.exists():
                raise FileNotFoundError(path)

    steps_by_case = {key: scan_dump_steps(spec.dump_path) for key, spec in specs.items()}
    wanted = {0, FINAL_STEP, *range(LAST_WINDOW_START_STEP, FINAL_STEP + 1, 1000)}
    frames_by_case: dict[str, list[FrameData]] = {}
    for key, spec in specs.items():
        frames: list[FrameData] = []
        print(f"[stageF-cpu] reading stress frames for {key}", flush=True)
        for step, columns, bounds, array in iter_dump_frames(spec.dump_path, wanted):
            frames.append(frame_from_raw(spec, step, columns, bounds, array))
        missing = sorted(wanted - {f.step for f in frames})
        if missing:
            raise RuntimeError(f"Missing requested frames for {key}: {missing}")
        frames_by_case[key] = sorted(frames, key=lambda f: f.step)

    bins = bin_edges(max(max_al_r(frames) for frames in frames_by_case.values()))
    thermo = {key: parse_thermo_log(spec.log_path) for key, spec in specs.items()}

    raw_stress_rows: list[dict[str, Any]] = []
    for key, frames in frames_by_case.items():
        for frame in frames:
            window = "initial" if frame.step == 0 else ("final" if frame.step == FINAL_STEP else "last20_frame")
            raw_stress_rows.extend(stress_profile_for_frame(frame, bins, thermo[key].get(frame.step), window))

    stress_rows = [r for r in raw_stress_rows if r["window"] in {"initial", "final"}]
    for key in specs:
        members = [r for r in raw_stress_rows if r["case"] == key and r["window"] == "last20_frame"]
        stress_rows.extend(average_window_rows(members, key, bins, "last20_mean"))

    delta = delta_rows(stress_rows, "initial", bins) + delta_rows(stress_rows, "final", bins) + delta_rows(stress_rows, "last20_mean", bins)
    stress_summaries = [profile_summary(stress_rows, case, window) for case in specs for window in ["initial", "final", "last20_mean"]]

    verification_md, verification_json, verification = write_production_verification(specs, setup, status)
    inventory_md, inventory_json, inventory = write_inventory(specs, steps_by_case, setup, status)
    stress_paths = write_stress_outputs(stress_rows, delta, stress_summaries)
    stress_summary = read_json(stress_paths["sigma_summary"])
    stress_figures = plot_stress_figures(stress_rows, delta)
    stress_report = write_stress_report(stress_summary, stress_figures, delta)

    ovito_ok, ovito_version = ovito_available()
    defect_rows: list[dict[str, Any]] = []
    defect_frame_summaries: list[dict[str, Any]] = []
    defect_figures: list[str] = []
    if ovito_ok:
        for key, spec in specs.items():
            steps = steps_by_case[key]
            for step in [0, FINAL_STEP]:
                print(f"[stageF-cpu] OVITO CNA/DXA for {key} step {step}", flush=True)
                rows, frame_summary = defect_profile_for_frame(spec, step, steps.index(step), bins)
                defect_rows.extend(rows)
                defect_frame_summaries.append(frame_summary)
        delta_defects = delta_defect_rows(defect_rows, "initial", bins) + delta_defect_rows(defect_rows, "final", bins)
        defect_figures = plot_defect_figures(defect_rows, delta_defects)
        defect_paths = write_defect_outputs(defect_rows, delta_defects, defect_frame_summaries, ovito_version, defect_figures)
        defect_summary = read_json(defect_paths["defect_summary"])
    else:
        delta_defects = []
        defect_summary = {
            "generated_at": now_iso(),
            "status": "blocked",
            "ovito_version": ovito_version,
            "frames_analyzed": [],
            "dmin2_status": "unavailable",
            "figures": [],
        }
        defect_paths = {}
        write_json(REPORTS_DIR / "stageF_cpu_results_defect_summary.json", defect_summary)

    plasticity_report = write_plasticity_report(defect_summary, defect_figures)
    residual_md, residual_json, residual = write_residual_check(stress_summary, defect_summary, delta_defects)
    criteria_map = write_criteria_map(stress_summary, residual)
    pshonkin_report = write_pshonkin_report(stress_summary, defect_summary, residual, stress_figures, defect_figures)
    meeting_brief = write_meeting_brief(stress_summary, residual)
    decision_md, decision_json, decision = write_next_step_decision(stress_summary, residual)

    outputs: dict[str, Any] = {
        "production_verification_md": verification_md,
        "production_verification_json": verification_json,
        "inventory_md": inventory_md,
        "inventory_json": inventory_json,
        "stress_report": stress_report,
        "stress_summary": stress_paths["sigma_summary"],
        "plasticity_report": plasticity_report,
        "defect_summary": REPORTS_DIR / "stageF_cpu_results_defect_summary.json",
        "residual_md": residual_md,
        "residual_json": residual_json,
        "criteria_map": criteria_map,
        "pshonkin_report": pshonkin_report,
        "meeting_brief": meeting_brief,
        "decision_md": decision_md,
        "decision_json": decision_json,
        "stress_figures": stress_figures,
        "defect_figures": defect_figures,
    }
    outputs.update(stress_paths)
    outputs.update(defect_paths)
    agent_report = write_agent_report(outputs, stress_summary, residual)
    outputs["agent_report"] = agent_report

    result = {
        "status": "completed",
        "generated_at": now_iso(),
        "production_root": str(production_root),
        "verification": verification,
        "inventory": inventory,
        "stress_summary": stress_summary,
        "defect_summary": defect_summary,
        "residual": residual,
        "decision": decision,
        "outputs": {key: str(value) for key, value in outputs.items() if isinstance(value, Path)},
        "stress_figures": stress_figures,
        "defect_figures": defect_figures,
        "source_map": source_map(),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-root", type=Path, default=PRODUCTION_ROOT)
    args = parser.parse_args(argv)
    try:
        result = analyze(args.production_root)
    except Exception as exc:
        error = {
            "status": "failed",
            "generated_at": now_iso(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        write_json(REPORTS_DIR / "stageF_cpu_results_analysis_failure.json", error)
        raise
    print(json.dumps({"status": result["status"], "outputs": result["outputs"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
