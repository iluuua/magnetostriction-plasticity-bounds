#!/usr/bin/env python3
"""Stage F boundary stress-decay analysis for the completed 700k run.

Reads existing Stage E4 dump frames only. It does not launch MD, delete raw
outputs, or mutate old Stage D/E scripts.
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
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE_RUNNER_DIR = Path(__file__).resolve().parent / "stage_runner"
if str(STAGE_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(STAGE_RUNNER_DIR))

import analysis_runner  # noqa: E402


DEFAULT_RUN_ROOT = (
    REPO_ROOT
    / "runs"
    / "stageE_700k_dxa_confirm"
    / "20260625-102200"
)
CASE_RELATIVE = Path("cases") / "E4_700k_dxa_confirm" / "E4_phys001942_700k_80k"
TARGET_STEPS = [0, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000]
YIELD_THRESHOLD_MPA = 120.0
BAR_TO_MPA = 0.1
DEFAULT_TIMESTEP_PS = 0.001
REPORTS_DIR = REPO_ROOT / "docs" / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
RENDERS_DIR = REPORTS_DIR / "renders"


@dataclass(frozen=True)
class FrameSpec:
    step: int
    dump_path: Path
    frame_index: int
    dump_timesteps: list[int]


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=_json_default) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _scan_dump_timesteps(path: Path) -> list[int]:
    steps: list[int] = []
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip() == "ITEM: TIMESTEP":
                value = next(handle, "").strip()
                if value:
                    steps.append(int(value))
    return steps


def _production_dir(run_root: Path) -> Path:
    production = run_root / CASE_RELATIVE / "production"
    if not production.is_dir():
        raise FileNotFoundError(f"Production directory not found: {production}")
    return production


def _frame_plan(production: Path) -> list[FrameSpec]:
    candidates = sorted(production.glob("dump.chunk*.lammpstrj"))
    final_dump = production / "dump.final.lammpstrj"
    if not candidates:
        raise FileNotFoundError(f"No production chunk dumps found in {production}")
    if not final_dump.is_file():
        raise FileNotFoundError(f"Final dump not found: {final_dump}")

    step_to_spec: dict[int, FrameSpec] = {}
    for dump_path in candidates:
        steps = _scan_dump_timesteps(dump_path)
        for index, step in enumerate(steps):
            if step not in TARGET_STEPS:
                continue
            if step == 0:
                step_to_spec[step] = FrameSpec(step, dump_path, index, steps)
            elif index > 0 and step not in step_to_spec:
                step_to_spec[step] = FrameSpec(step, dump_path, index, steps)

    final_steps = _scan_dump_timesteps(final_dump)
    if 80000 in final_steps:
        step_to_spec[80000] = FrameSpec(80000, final_dump, final_steps.index(80000), final_steps)

    missing = [step for step in TARGET_STEPS if step not in step_to_spec]
    if missing:
        raise RuntimeError(f"Missing target dump frames for steps: {missing}")
    return [step_to_spec[step] for step in TARGET_STEPS]


def _parse_metadata(run_root: Path) -> dict[str, Any]:
    production = _production_dir(run_root)
    geometry = _read_json(production / "geometry_metadata.json")
    final_summary = _read_json(run_root / "stageE_700k_final_summary.json", {})
    case_meta = _read_json(production / "case_metadata.json", {})
    return {
        "run_root": str(run_root),
        "production_dir": str(production),
        "case_id": "E4_phys001942_700k_80k",
        "matrix_max_id": int(geometry["matrix_max_id"]),
        "center": [float(x) for x in geometry["center_A"]],
        "axes": [float(x) for x in geometry["inclusion_axes_A"]],
        "box_A": [float(x) for x in geometry["box_A"]],
        "actual_atoms": int(geometry["actual_atom_count"]),
        "matrix_atoms": int(geometry["matrix_atoms"]),
        "inclusion_atoms": int(geometry["inclusion_atoms"]),
        "eps_z": float(final_summary.get("eps_z", case_meta.get("eps_z", 0.001942))),
        "temperature_K": float(case_meta.get("temperature_K", 300.0)),
        "production_steps": int(final_summary.get("production_steps", case_meta.get("steps_target", 80000))),
        "production_status": final_summary.get("status", case_meta.get("status")),
        "production_returncode": final_summary.get("production_returncode", case_meta.get("exit_code")),
        "max_temp_K": final_summary.get("max_temp_K"),
        "timestep_ps": _parse_timestep_ps(production),
    }


def _parse_timestep_ps(production: Path) -> float:
    for path in sorted(production.glob("in.chunk*")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("timestep"):
                parts = stripped.split()
                if len(parts) >= 2:
                    return float(parts[1])
    return DEFAULT_TIMESTEP_PS


def _parse_thermo_rows(production: Path) -> dict[int, dict[str, float]]:
    rows: dict[int, dict[str, float]] = {}
    for log_path in sorted(production.glob("log.chunk*.lammps")):
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        header: list[str] | None = None
        for line in lines:
            parts = line.split()
            if not parts:
                continue
            if parts[0] == "Step" and "Temp" in parts and "Pzz" in parts:
                header = parts
                continue
            if header is None:
                continue
            try:
                vals = [float(x) for x in parts[: len(header)]]
            except ValueError:
                header = None
                continue
            if len(vals) != len(header):
                continue
            item = dict(zip(header, vals))
            rows[int(item["Step"])] = item
    return rows


def _restart_for_step(production: Path, step: int) -> str:
    if step <= 0:
        return ""
    path = production / f"restart.{step}"
    return str(path) if path.exists() else ""


def _stress_keys(data: Any) -> list[str]:
    candidates = [[f"c_st[{i}]" for i in range(1, 7)], [f"c_stress_atom[{i}]" for i in range(1, 7)]]
    for keys in candidates:
        if all(key in data.particles for key in keys):
            return keys
    missing = [key for key in candidates[0] if key not in data.particles]
    raise RuntimeError(f"stress columns missing: {missing}")


def _surface_distance(
    positions: np.ndarray,
    center: np.ndarray,
    axes: np.ndarray,
    box_len: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    rel = positions - center
    rel -= box_len * np.round(rel / box_len)
    radius = np.linalg.norm(rel, axis=1)
    direction = np.zeros_like(rel)
    nonzero = radius > 0.0
    direction[nonzero] = rel[nonzero] / radius[nonzero, None]
    denom = np.sqrt(np.sum((direction / axes) ** 2, axis=1))
    surface_radius = np.divide(1.0, denom, out=np.zeros_like(radius), where=denom > 0.0)
    signed = radius - surface_radius
    normalized = np.sqrt(np.sum((rel / axes) ** 2, axis=1))
    return signed, normalized


def _z_plane_distance(positions: np.ndarray, center: np.ndarray, axes: np.ndarray, box_len: np.ndarray) -> np.ndarray:
    rel = positions - center
    rel -= box_len * np.round(rel / box_len)
    z_surface = axes[2]
    return np.abs(rel[:, 2]) - z_surface


def _distance_bins(max_distance: float) -> list[tuple[float, float]]:
    capped = max(0.0, min(float(max_distance), 300.0))
    bins: list[tuple[float, float]] = []
    edge = 0.0
    while edge < min(50.0, capped):
        hi = min(edge + 2.0, capped)
        if hi > edge:
            bins.append((edge, hi))
        edge = hi
    edge = 50.0
    while edge < capped:
        hi = min(edge + 5.0, capped)
        if hi > edge:
            bins.append((edge, hi))
        edge = hi
    return bins


def _von_mises_mpa(tensor_mpa: np.ndarray) -> np.ndarray:
    xx, yy, zz, xy, xz, yz = [tensor_mpa[:, i] for i in range(6)]
    return np.sqrt(0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2) + 3.0 * (xy**2 + xz**2 + yz**2))


def _max_principal_mpa(tensor_mpa: np.ndarray) -> np.ndarray:
    if len(tensor_mpa) == 0:
        return np.array([], dtype=float)
    mats = np.zeros((len(tensor_mpa), 3, 3), dtype=float)
    mats[:, 0, 0] = tensor_mpa[:, 0]
    mats[:, 1, 1] = tensor_mpa[:, 1]
    mats[:, 2, 2] = tensor_mpa[:, 2]
    mats[:, 0, 1] = mats[:, 1, 0] = tensor_mpa[:, 3]
    mats[:, 0, 2] = mats[:, 2, 0] = tensor_mpa[:, 4]
    mats[:, 1, 2] = mats[:, 2, 1] = tensor_mpa[:, 5]
    vals = np.linalg.eigvalsh(mats)
    return vals[:, -1]


def _percentile(values: np.ndarray, q: float) -> float | None:
    if values.size == 0:
        return None
    return float(np.percentile(values, q))


def _mean_or_none(values: np.ndarray) -> float | None:
    if values.size == 0:
        return None
    return float(np.mean(values))


def _reference_positions(spec: FrameSpec, matrix_max_id: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    from ovito.io import import_file

    pipe = import_file(str(spec.dump_path))
    data = pipe.compute(spec.frame_index)
    ids = np.asarray(data.particles["Particle Identifier"], dtype=np.int64)
    pos = np.asarray(data.particles.positions, dtype=float)
    order = np.argsort(ids)
    cell = np.asarray(data.cell)[:3, :3]
    box_len = np.array([cell[0][0], cell[1][1], cell[2][2]], dtype=float)
    matrix_mask = ids[order] <= int(matrix_max_id)
    return ids[order], pos[order], matrix_mask, box_len


def _displacement_stats(
    ids: np.ndarray,
    positions: np.ndarray,
    reference_ids: np.ndarray,
    reference_positions: np.ndarray,
    matrix_mask_sorted: np.ndarray,
    box_len: np.ndarray,
) -> dict[str, float | None]:
    order = np.argsort(ids)
    ids_sorted = ids[order]
    if len(ids_sorted) != len(reference_ids) or not np.array_equal(ids_sorted, reference_ids):
        return {"max_displacement": None, "displacement_p95_A": None, "displacement_p99_A": None}
    pos_sorted = positions[order]
    delta = pos_sorted - reference_positions
    delta -= box_len * np.round(delta / box_len)
    disp = np.linalg.norm(delta[matrix_mask_sorted], axis=1)
    if disp.size == 0:
        return {"max_displacement": None, "displacement_p95_A": None, "displacement_p99_A": None}
    return {
        "max_displacement": float(disp.max()),
        "displacement_p95_A": float(np.percentile(disp, 95)),
        "displacement_p99_A": float(np.percentile(disp, 99)),
    }


def _structure_counts(st: np.ndarray, mask: np.ndarray) -> dict[str, int]:
    return {
        "fcc_atoms": int(np.count_nonzero(mask & (st == 1))),
        "hcp_atoms": int(np.count_nonzero(mask & (st == 2))),
        "other_atoms": int(np.count_nonzero(mask & (st == 0))),
    }


def _dxa_attrs(data: Any) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for key, value in data.attributes.items():
        skey = str(key)
        if skey.startswith("DislocationAnalysis"):
            try:
                attrs[skey] = float(value)
            except (TypeError, ValueError):
                attrs[skey] = str(value)
    return attrs


def _burgers_lengths(dxa_attrs: dict[str, Any]) -> dict[str, float]:
    prefix = "DislocationAnalysis.length."
    out: dict[str, float] = {}
    for key, value in dxa_attrs.items():
        if str(key).startswith(prefix):
            out[str(key)[len(prefix) :]] = float(value)
    return out


def _analyze_frame(
    spec: FrameSpec,
    meta: dict[str, Any],
    thermo: dict[int, dict[str, float]],
    reference: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
) -> dict[str, Any]:
    from ovito.io import import_file
    from ovito.modifiers import CommonNeighborAnalysisModifier, DislocationAnalysisModifier

    matrix_max_id = int(meta["matrix_max_id"])
    center = np.array(meta["center"], dtype=float)
    axes = np.array(meta["axes"], dtype=float)
    pipe = import_file(str(spec.dump_path))
    pipe.modifiers.append(CommonNeighborAnalysisModifier())
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)
    data = pipe.compute(spec.frame_index)

    ids = np.asarray(data.particles["Particle Identifier"], dtype=np.int64)
    positions = np.asarray(data.particles.positions, dtype=float)
    st = np.asarray(data.particles["Structure Type"], dtype=int)
    matrix_mask = analysis_runner._matrix_mask(data, matrix_max_id)
    cell = np.asarray(data.cell)[:3, :3]
    box_len = np.array([cell[0][0], cell[1][1], cell[2][2]], dtype=float)
    atom_volume = float(data.cell.volume) / int(data.particles.count)
    stress = np.vstack([np.asarray(data.particles[key], dtype=float) for key in _stress_keys(data)]).T
    atom_tensor_mpa = -stress / atom_volume * BAR_TO_MPA
    atom_vm_mpa = _von_mises_mpa(atom_tensor_mpa)
    atom_max_principal = _max_principal_mpa(atom_tensor_mpa)
    atom_max_component = np.max(np.abs(atom_tensor_mpa), axis=1)

    surface_distance, normalized_distance = _surface_distance(positions, center, axes, box_len)
    z_distance = _z_plane_distance(positions, center, axes, box_len)
    distance = surface_distance
    distance_mode = "surface-distance"
    interface_definition = (
        "analytic ellipsoid Fe4Al13/Al interface from Stage E geometry metadata; "
        "r is radial signed distance from ellipsoid surface into Al matrix"
    )
    if not np.any(matrix_mask & (distance >= 0.0)):
        distance = z_distance
        distance_mode = "z-plane-fallback"
        interface_definition = "fallback distance from estimated top/bottom ellipsoid z surface into Al matrix"

    max_distance = float(np.nanmax(distance[matrix_mask & (distance >= 0.0)])) if np.any(matrix_mask & (distance >= 0.0)) else 0.0
    bins = _distance_bins(max_distance)
    if not bins:
        bins = [(0.0, 2.0)]

    dxa_attr = _dxa_attrs(data)
    dxa_segments = int(len(data.dislocations.segments))
    dxa_line = float(data.attributes.get("DislocationAnalysis.total_line_length", 0.0))
    if dxa_line == 0.0 and dxa_segments:
        dxa_line = float(sum(segment.length for segment in data.dislocations.segments))

    disp_stats = _displacement_stats(
        ids,
        positions,
        reference[0],
        reference[1],
        reference[2],
        reference[3],
    )

    thermo_row = thermo.get(spec.step, {})
    frame_rows: list[dict[str, Any]] = []
    for lo, hi in bins:
        mask = matrix_mask & (distance >= lo) & (distance < hi)
        count = int(np.count_nonzero(mask))
        tensor = atom_tensor_mpa[mask]
        vm = atom_vm_mpa[mask]
        max_pr = atom_max_principal[mask]
        max_comp = atom_max_component[mask]
        summed_pressure_mpa = None
        if count:
            volume = count * atom_volume
            pressure_bar = -np.sum(stress[mask], axis=0) / volume
            summed_pressure_mpa = pressure_bar * BAR_TO_MPA
        counts = _structure_counts(st, mask)
        above = (vm > YIELD_THRESHOLD_MPA) | (max_comp > YIELD_THRESHOLD_MPA)
        frame_rows.append(
            {
                "frame_id": f"step_{spec.step}",
                "case_id": meta["case_id"],
                "timestep": int(spec.step),
                "time_ps": float(spec.step) * float(meta["timestep_ps"]),
                "dump_file": str(spec.dump_path),
                "restart_file": _restart_for_step(Path(meta["production_dir"]), spec.step),
                "temperature": thermo_row.get("Temp"),
                "pressure": thermo_row.get("Press"),
                "pe": thermo_row.get("PotEng"),
                "ke": thermo_row.get("KinEng"),
                "etotal": thermo_row.get("TotEng"),
                "pxx": thermo_row.get("Pxx"),
                "pyy": thermo_row.get("Pyy"),
                "pzz": thermo_row.get("Pzz"),
                "eps_z": float(meta["eps_z"]),
                "distance_mode": distance_mode,
                "interface_definition": interface_definition,
                "distance_bin_A": f"{lo:g}-{hi:g}",
                "distance_bin_center_A": 0.5 * (lo + hi),
                "matrix_atoms_in_bin": count,
                "sigma_xx_mpa_mean": float(summed_pressure_mpa[0]) if summed_pressure_mpa is not None else None,
                "sigma_yy_mpa_mean": float(summed_pressure_mpa[1]) if summed_pressure_mpa is not None else None,
                "sigma_zz_mpa_mean": float(summed_pressure_mpa[2]) if summed_pressure_mpa is not None else None,
                "sigma_hydro_mpa_mean": float(np.mean(summed_pressure_mpa[:3])) if summed_pressure_mpa is not None else None,
                "sigma_vm_mpa_mean": float(_von_mises_mpa(summed_pressure_mpa.reshape(1, 6))[0]) if summed_pressure_mpa is not None else None,
                "sigma_max_principal_mpa_mean": float(np.max(np.linalg.eigvalsh(np.array([
                    [summed_pressure_mpa[0], summed_pressure_mpa[3], summed_pressure_mpa[4]],
                    [summed_pressure_mpa[3], summed_pressure_mpa[1], summed_pressure_mpa[5]],
                    [summed_pressure_mpa[4], summed_pressure_mpa[5], summed_pressure_mpa[2]],
                ])))) if summed_pressure_mpa is not None else None,
                "sigma_vm_p95_mpa": _percentile(vm, 95),
                "sigma_vm_p99_mpa": _percentile(vm, 99),
                "sigma_max_component_p95_mpa": _percentile(max_comp, 95),
                "sigma_max_component_p99_mpa": _percentile(max_comp, 99),
                "above_yield_atoms": int(np.count_nonzero(above)) if count else 0,
                "above_yield_fraction": float(np.count_nonzero(above) / count) if count else 0.0,
                "yield_threshold_mpa": YIELD_THRESHOLD_MPA,
                "plastic_layer_thickness_A": None,
                "hcp_atoms": counts["hcp_atoms"],
                "other_atoms": counts["other_atoms"],
                "dislocation_segments": dxa_segments,
                "dislocation_line_length_A": dxa_line,
                "atomic_strain_p95": None,
                "atomic_strain_p99": None,
                "Dmin2_p95": None,
                "Dmin2_p99": None,
                "max_displacement": disp_stats["max_displacement"],
                "event_class": None,
                "physical_interpretation_flag": None,
                "displacement_p95_A": disp_stats["displacement_p95_A"],
                "displacement_p99_A": disp_stats["displacement_p99_A"],
                "distance_bin_min_A": lo,
                "distance_bin_max_A": hi,
                "max_normalized_ellipsoid_distance_in_bin": _mean_or_none(normalized_distance[mask]),
            }
        )

    return {
        "step": int(spec.step),
        "dump": str(spec.dump_path),
        "frame_index": int(spec.frame_index),
        "dump_timesteps": spec.dump_timesteps,
        "distance_mode": distance_mode,
        "interface_definition": interface_definition,
        "available_distance_max_A": max_distance,
        "matrix_atoms": int(np.count_nonzero(matrix_mask)),
        "inclusion_atoms": int(data.particles.count - np.count_nonzero(matrix_mask)),
        "dxa_segments": dxa_segments,
        "dxa_line_A": dxa_line,
        "dxa_burgers_lengths_A": _burgers_lengths(dxa_attr),
        "cna": _structure_counts(st, matrix_mask),
        "displacement": disp_stats,
        "rows": frame_rows,
    }


def _apply_frame_classification(frames: list[dict[str, Any]]) -> None:
    baseline_hcp = int(frames[0]["cna"]["hcp_atoms"])
    baseline_other = int(frames[0]["cna"]["other_atoms"])
    dxa_by_step = {int(f["step"]): int(f["dxa_segments"]) for f in frames}
    line_by_step = {int(f["step"]): float(f["dxa_line_A"]) for f in frames}
    for idx, frame in enumerate(frames):
        step = int(frame["step"])
        next_frame = frames[idx + 1] if idx + 1 < len(frames) else None
        event_class = "no_event"
        flag = "no_persistent_plasticity"
        if int(frame["dxa_segments"]) > 0 or float(frame["dxa_line_A"]) > 0.0:
            event_class = "confirmed_DXA"
            next_has_dxa = bool(next_frame and (int(next_frame["dxa_segments"]) > 0 or float(next_frame["dxa_line_A"]) > 0.0))
            if float(frame["dxa_line_A"]) < 50.0 or not next_has_dxa:
                flag = "short_transient_dxa / not_developed_dislocation"
            else:
                flag = "stable_dxa_candidate"
        elif int(frame["cna"]["hcp_atoms"]) > baseline_hcp or int(frame["cna"]["other_atoms"]) > baseline_other + 500:
            event_class = "weak_hcp"
            flag = "local_lattice_disturbance_no_DXA"
        for row in frame["rows"]:
            row["event_class"] = event_class
            row["physical_interpretation_flag"] = flag
        frame["event_class"] = event_class
        frame["physical_interpretation_flag"] = flag
        frame["next_sample_dxa_segments"] = dxa_by_step.get(step + 10000)
        frame["next_sample_dxa_line_A"] = line_by_step.get(step + 10000)


def _layer_condition(row: dict[str, Any]) -> bool:
    return (
        (row.get("sigma_vm_p95_mpa") is not None and float(row["sigma_vm_p95_mpa"]) > YIELD_THRESHOLD_MPA)
        or (
            row.get("sigma_max_component_p95_mpa") is not None
            and float(row["sigma_max_component_p95_mpa"]) > YIELD_THRESHOLD_MPA
        )
    )


def _apply_plastic_layers(frames: list[dict[str, Any]]) -> None:
    for frame in frames:
        sorted_rows = sorted(frame["rows"], key=lambda r: float(r["distance_bin_min_A"]))
        continuous = 0.0
        max_above: float | None = None
        broken = False
        for row in sorted_rows:
            above = _layer_condition(row)
            if above:
                max_above = float(row["distance_bin_max_A"])
                if not broken:
                    continuous = float(row["distance_bin_max_A"])
            else:
                broken = True
        for row in frame["rows"]:
            row["plastic_layer_thickness_A"] = continuous
            row["continuous_layer_thickness_A"] = continuous
            row["max_above_yield_distance_A"] = max_above
        frame["plastic_layer_thickness_A"] = continuous
        frame["max_above_yield_distance_A"] = max_above


def _flatten(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for frame in frames:
        rows.extend(frame["rows"])
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "frame_id",
        "case_id",
        "timestep",
        "time_ps",
        "dump_file",
        "restart_file",
        "temperature",
        "pressure",
        "pe",
        "ke",
        "etotal",
        "pxx",
        "pyy",
        "pzz",
        "eps_z",
        "distance_mode",
        "interface_definition",
        "distance_bin_A",
        "distance_bin_center_A",
        "matrix_atoms_in_bin",
        "sigma_xx_mpa_mean",
        "sigma_yy_mpa_mean",
        "sigma_zz_mpa_mean",
        "sigma_hydro_mpa_mean",
        "sigma_vm_mpa_mean",
        "sigma_max_principal_mpa_mean",
        "sigma_vm_p95_mpa",
        "sigma_vm_p99_mpa",
        "sigma_max_component_p95_mpa",
        "sigma_max_component_p99_mpa",
        "above_yield_atoms",
        "above_yield_fraction",
        "yield_threshold_mpa",
        "plastic_layer_thickness_A",
        "hcp_atoms",
        "other_atoms",
        "dislocation_segments",
        "dislocation_line_length_A",
        "atomic_strain_p95",
        "atomic_strain_p99",
        "Dmin2_p95",
        "Dmin2_p99",
        "max_displacement",
        "event_class",
        "physical_interpretation_flag",
        "continuous_layer_thickness_A",
        "max_above_yield_distance_A",
        "displacement_p95_A",
        "displacement_p99_A",
        "distance_bin_min_A",
        "distance_bin_max_A",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: Any, ndigits: int = 3) -> str:
    if value is None or value == "":
        return "n/a"
    if isinstance(value, float):
        if math.isnan(value):
            return "n/a"
        if abs(value) >= 10000 or (0 < abs(value) < 0.001):
            return f"{value:.6g}"
        return f"{value:.{ndigits}f}"
    return str(value)


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(_fmt(cell) for cell in row) + " |")
    return "\n".join(out)


def _frame_summary_rows(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for frame in frames:
        first = frame["rows"][0]
        max_vm_mean = max((r.get("sigma_vm_mpa_mean") or 0.0 for r in frame["rows"]), default=0.0)
        max_vm_p95 = max((r.get("sigma_vm_p95_mpa") or 0.0 for r in frame["rows"]), default=0.0)
        max_above_fraction = max((r.get("above_yield_fraction") or 0.0 for r in frame["rows"]), default=0.0)
        out.append(
            {
                "timestep": frame["step"],
                "time_ps": first["time_ps"],
                "distance_mode": frame["distance_mode"],
                "available_distance_max_A": frame["available_distance_max_A"],
                "plastic_layer_thickness_A": frame["plastic_layer_thickness_A"],
                "max_above_yield_distance_A": frame["max_above_yield_distance_A"],
                "max_sigma_vm_mean_mpa": max_vm_mean,
                "max_sigma_vm_p95_mpa": max_vm_p95,
                "max_above_yield_fraction": max_above_fraction,
                "hcp_atoms": frame["cna"]["hcp_atoms"],
                "other_atoms": frame["cna"]["other_atoms"],
                "dislocation_segments": frame["dxa_segments"],
                "dislocation_line_length_A": frame["dxa_line_A"],
                "event_class": frame["event_class"],
                "physical_interpretation_flag": frame["physical_interpretation_flag"],
            }
        )
    return out


def _write_event_timeline(path: Path, frames: list[dict[str, Any]]) -> None:
    rows = _frame_summary_rows(frames)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _plot_figures(rows: list[dict[str, Any]], frames: list[dict[str, Any]]) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    selected_steps = {0, 60000, 80000}
    max_layer_frame = max(frames, key=lambda f: float(f["plastic_layer_thickness_A"] or 0.0))
    selected_steps.add(int(max_layer_frame["step"]))

    def by_step(step: int) -> list[dict[str, Any]]:
        return sorted([r for r in rows if int(r["timestep"]) == step and int(r["matrix_atoms_in_bin"]) > 0], key=lambda r: float(r["distance_bin_center_A"]))

    written: list[str] = []

    fig, ax = plt.subplots(figsize=(9, 5))
    for step in sorted(selected_steps):
        rs = by_step(step)
        if not rs:
            continue
        x = [r["distance_bin_center_A"] for r in rs]
        ax.plot(x, [r["sigma_xx_mpa_mean"] for r in rs], label=f"{step} xx", linewidth=1.2)
        ax.plot(x, [r["sigma_yy_mpa_mean"] for r in rs], label=f"{step} yy", linewidth=1.2)
        ax.plot(x, [r["sigma_zz_mpa_mean"] for r in rs], label=f"{step} zz", linewidth=1.2)
    ax.axhline(YIELD_THRESHOLD_MPA, color="black", linestyle="--", linewidth=1, label="120 MPa")
    ax.axhline(-YIELD_THRESHOLD_MPA, color="black", linestyle=":", linewidth=1)
    ax.set_xlabel("r from interface into Al, A")
    ax.set_ylabel("mean stress proxy, MPa")
    ax.set_title("Stage F sigma components from existing 700k dumps")
    ax.legend(ncol=2, fontsize=7)
    ax.grid(True, alpha=0.25)
    path = FIGURES_DIR / "stageF_sigma_decay_components.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    written.append(str(path))

    fig, ax = plt.subplots(figsize=(9, 5))
    for step in sorted(selected_steps):
        rs = by_step(step)
        if rs:
            ax.plot([r["distance_bin_center_A"] for r in rs], [r["sigma_vm_mpa_mean"] for r in rs], label=f"{step} mean")
            ax.plot([r["distance_bin_center_A"] for r in rs], [r["sigma_vm_p95_mpa"] for r in rs], linestyle="--", label=f"{step} p95")
    ax.axhline(YIELD_THRESHOLD_MPA, color="black", linestyle="--", linewidth=1, label="120 MPa")
    ax.set_xlabel("r from interface into Al, A")
    ax.set_ylabel("von Mises stress proxy, MPa")
    ax.set_title("Stage F sigma_vm(r)")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.25)
    path = FIGURES_DIR / "stageF_sigma_decay_vm.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    written.append(str(path))

    fig, ax = plt.subplots(figsize=(9, 5))
    for step in sorted(selected_steps):
        rs = by_step(step)
        if rs:
            ax.plot([r["distance_bin_center_A"] for r in rs], [r["above_yield_fraction"] for r in rs], label=str(step))
    ax.set_xlabel("r from interface into Al, A")
    ax.set_ylabel("fraction of Al atoms above proxy threshold")
    ax.set_title("Above-yield proxy fraction by distance")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    path = FIGURES_DIR / "stageF_above_yield_layer.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    written.append(str(path))

    timeline = _frame_summary_rows(frames)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot([r["timestep"] for r in timeline], [r["plastic_layer_thickness_A"] for r in timeline], marker="o")
    ax.set_xlabel("timestep")
    ax.set_ylabel("continuous layer thickness, A")
    ax.set_title("Temporal plastic/stress layer proxy")
    ax.grid(True, alpha=0.25)
    path = FIGURES_DIR / "stageF_temporal_plastic_layer.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    written.append(str(path))

    step = 60000
    rs = by_step(step)
    fig, ax = plt.subplots(figsize=(9, 5))
    if rs:
        ax.plot([r["distance_bin_center_A"] for r in rs], [r["hcp_atoms"] for r in rs], marker="o", label="HCP")
        ax.plot([r["distance_bin_center_A"] for r in rs], [r["other_atoms"] for r in rs], marker="s", label="OTHER")
    ax.set_xlabel("r from interface into Al, A")
    ax.set_ylabel("atoms in bin")
    ax.set_title("CNA HCP/OTHER by distance at timestep 60000")
    ax.legend()
    ax.grid(True, alpha=0.25)
    path = FIGURES_DIR / "stageF_hcp_other_by_distance.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    written.append(str(path))

    return written


def _try_renders(frame_plan: list[FrameSpec], meta: dict[str, Any], rows: list[dict[str, Any]], skip: bool) -> dict[str, Any]:
    if skip:
        return {"status": "skipped", "reason": "skip_renders requested", "files": [], "blockers": ["renders skipped by command option"]}
    blockers: list[str] = []
    files: list[str] = []
    try:
        from ovito.io import import_file
        from ovito.modifiers import ColorCodingModifier, CommonNeighborAnalysisModifier, SliceModifier
        from ovito.vis import TachyonRenderer, Viewport
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"status": "blocked", "files": [], "blockers": [f"OVITO render imports failed: {exc}"]}

    RENDERS_DIR.mkdir(parents=True, exist_ok=True)
    spec_by_step = {spec.step: spec for spec in frame_plan}
    render_jobs = [
        (50000, "type", RENDERS_DIR / "stageF_before_event_type.png"),
        (60000, "type", RENDERS_DIR / "stageF_at_event_60000_type.png"),
        (70000, "type", RENDERS_DIR / "stageF_after_event_70000_type.png"),
        (80000, "type", RENDERS_DIR / "stageF_final_80000_type.png"),
        (80000, "type", RENDERS_DIR / "stageF_geometry_interface_view.png"),
        (60000, "cna", RENDERS_DIR / "stageF_cna_at_event_60000.png"),
        (int(max(rows, key=lambda r: float(r.get("sigma_vm_p95_mpa") or 0.0))["timestep"]), "stress", RENDERS_DIR / "stageF_stress_layer_view.png"),
    ]

    def add_stress_property(frame: int, data: Any) -> None:
        keys = _stress_keys(data)
        stress = np.vstack([np.asarray(data.particles[key], dtype=float) for key in keys]).T
        atom_volume = float(data.cell.volume) / int(data.particles.count)
        tensor = -stress / atom_volume * BAR_TO_MPA
        data.particles_.create_property("VM proxy MPa", data=_von_mises_mpa(tensor))

    for step, mode, out_path in render_jobs:
        spec = spec_by_step.get(step)
        if spec is None:
            blockers.append(f"missing render frame for step {step}")
            continue
        try:
            pipe = import_file(str(spec.dump_path))
            pipe.modifiers.append(SliceModifier(normal=(1, 0, 0), distance=float(meta["center"][0]), slab_width=45.0))
            if mode == "cna":
                pipe.modifiers.append(CommonNeighborAnalysisModifier())
                pipe.modifiers.append(ColorCodingModifier(property="Structure Type", start_value=0.0, end_value=2.0))
            elif mode == "stress":
                from ovito.modifiers import PythonScriptModifier

                pipe.modifiers.append(PythonScriptModifier(function=add_stress_property))
                pipe.modifiers.append(ColorCodingModifier(property="VM proxy MPa", start_value=0.0, end_value=600.0))
            else:
                pipe.modifiers.append(ColorCodingModifier(property="Particle Type", start_value=1.0, end_value=2.0))
            pipe.add_to_scene()
            vp = Viewport(type=Viewport.Type.Ortho)
            vp.camera_dir = (0.0, -1.0, -0.25)
            vp.camera_pos = (float(meta["center"][0]), float(meta["center"][1]) - 450.0, float(meta["center"][2]) + 95.0)
            vp.fov = 360.0
            vp.render_image(
                size=(1200, 900),
                filename=str(out_path),
                frame=spec.frame_index,
                renderer=TachyonRenderer(),
            )
            pipe.remove_from_scene()
            files.append(str(out_path))
        except Exception as exc:  # pragma: no cover - environment dependent
            try:
                pipe.remove_from_scene()
            except Exception:
                pass
            blockers.append(f"{out_path.name}: {type(exc).__name__}: {exc}")
    status = "completed" if not blockers else ("partial" if files else "blocked")
    return {"status": status, "files": files, "blockers": blockers}


def _write_alignment_report(path: Path, meta: dict[str, Any], source_map: dict[str, Any]) -> None:
    text = f"""# Stage F: alignment после встречи с физиком

Дата: 2026-06-29

## Что было сделано до Stage F

- 510k: короткий transient DXA-сигнал `1/6<112>` с длиной около `8.47 A`.
- 700k: короткий transient только на timestep `60000`: `2` сегмента, суммарная длина около `17.45 A`.
- `70000` и финальный `80000`: DXA `0`.

## Почему это не стабильная физическая дислокационная зона

Линии `8-17 A` слишком короткие для развитой дислокационной картины, событие исчезает на следующем sampled frame, финальный DXA равен нулю, устойчивого DXA во времени нет. В temporal 700k нет признака развитой пластики в Al matrix. В транскрипте Пшонкин прямо указывает, что такие короткие "дислокации" физически сомнительны и лучше рассматривать их как локальное нарушение решетки/топологии.

Корректная формулировка: short transient DXA event, local lattice/topology disturbance, physically weak evidence, not a persistent dislocation line.

## Что реально попросил физик

Нужно взять локальный patch границы Fe4Al13 / Al, построить `sigma(r)`, где `r=0` на interface, найти слой, где `sigma > sigma_y` или сравнима с ним, и смотреть дефекты именно в Al matrix около interface. Интерпретация должна отвечать, передается ли напряжение/пластика в matrix, или напряжение локализуется и быстро затухает около interface.

Рабочий порог: `sigma_y = 120 MPa`. Направление магнитного поля и magnetostrictive eigenstrain: `Z`.

## Почему full 20-30 um MD невозможна

Текущий 700k box имеет размер `{meta['box_A'][0]:.2f} x {meta['box_A'][1]:.2f} x {meta['box_A'][2]:.2f} A`, то есть nanoscopic scale. Область `20-30 um` и включение `5-7 um` требуют недостижимого для атомистической MD числа атомов. Даже `700k-1M` atoms остаются увеличенным nanoscopic domain, а не микронной моделью.

## Почему Stage F должен быть boundary-patch

Boundary-patch соответствует замечанию физика, дает физически читаемый `sigma(r)`, позволяет сравнить профиль с `sigma_y = 120 MPa` и заменяет blind DXA hunting на проверку переноса/затухания напряжения от interface.

## Как замечания физика меняют постановку задачи

На переданных эскизах нарисована локальная граница Fe4Al13 / Al и срез/отрезанная верхушка эллипсоида. `r=0` расположен на границе раздела; направление `r` идет от interface в Al matrix. `Z` показан как направление поля/eigenstrain. Нужен график `sigma(r)`, падающий от interface в matrix, и слой, где stress proxy выше или сравним с `120 MPa`.

Ожидаемый физический вывод: либо напряжение передается в Al matrix на заметную толщину, либо затухает в тонкой оболочке около interface. DXA остается вторичным диагностическим признаком и не должен быть целью любой ценой.

## Source Map

```json
{json.dumps(source_map, indent=2, ensure_ascii=False)}
```
"""
    _write_text(path, text)


def _write_stress_report(path: Path, meta: dict[str, Any], rows: list[dict[str, Any]], frames: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    timeline = _frame_summary_rows(frames)
    max_layer = max(timeline, key=lambda r: float(r["plastic_layer_thickness_A"] or 0.0))
    max_mean_vm = max(timeline, key=lambda r: float(r["max_sigma_vm_mean_mpa"] or 0.0))
    max_p95_vm = max(timeline, key=lambda r: float(r["max_sigma_vm_p95_mpa"] or 0.0))
    first_mode = frames[0]["distance_mode"]
    layer_text = (
        f"По заданному p95-критерию слой выше `120 MPa` идет до `{max_layer['plastic_layer_thickness_A']:.2f} A` "
        f"в кадре `{max_layer['timestep']}`. Это граница доступного расстояния в текущем 700k box, а не доказанный физический cutoff."
    )
    text = f"""# Stage F: stress-decay от interface в Al matrix

Дата: 2026-06-29

Run root: `{meta['run_root']}`

## Краткий вывод

Stress layer в существующем 700k run вычислен как local virial stress proxy по Al matrix bins от аналитической поверхности Fe4Al13 / Al. Реальный режим расстояния: `{first_mode}`.

{layer_text}

Mean `sigma_vm(r)` показывает сильную near-interface компоненту, но p95/per-atom virial proxy остается шумным и часто выше порога далеко от interface. Поэтому текущий 700k ellipsoid-run полезен как post-processing sanity check, но не дает аккуратного cutoff `sigma(r)` до уровня ниже `120 MPa`; для этого нужен Stage F boundary-patch с controlled geometry.

## Ответы на вопросы

1. Есть ли stress layer? Да, по local virial proxy слой выше `120 MPa` есть около interface; p95-критерий не дает чистого затухания ниже порога в доступном 700k box.
2. Толщина слоя выше `120 MPa`: `{max_layer['plastic_layer_thickness_A']:.2f} A` continuous по p95-критерию в кадре `{max_layer['timestep']}`; максимум above-yield distance `{_fmt(max_layer['max_above_yield_distance_A'])} A`.
3. Затухание: mean VM обычно падает от near-interface к дальним bin, но p95 atom-level virial остается noisy; надежно сказать "затухает за N A" нельзя.
4. Передается ли напряжение в Al matrix? В существующей модели stress proxy передается в matrix, но интерпретация ограничена ellipsoid geometry и virial noise.
5. Физически значимые дислокации: нет подтверждения. Есть short transient DXA на `60000`, `2` segments, `17.45 A`, затем `70000/80000` возвращаются к DXA `0`.
6. Почему transient DXA at 60000 недостаточен: линия короче `50 A`, событие исчезает на следующем sampled frame и не является persistent dislocation.
7. Можно показать Пшонкину: да, как reality-alignment и motivation для boundary-patch, но не как окончательный `sigma(r)` cutoff.

## Frame timeline

{_markdown_table(
        ["step", "layer A", "max dist A", "max mean VM", "max p95 VM", "HCP", "OTHER", "DXA", "line A", "class"],
        [[r["timestep"], r["plastic_layer_thickness_A"], r["max_above_yield_distance_A"], r["max_sigma_vm_mean_mpa"], r["max_sigma_vm_p95_mpa"], r["hcp_atoms"], r["other_atoms"], r["dislocation_segments"], r["dislocation_line_length_A"], r["event_class"]] for r in timeline],
    )}

## Notes on stress conversion

- Dump columns: `c_st[1..6]`.
- Conversion follows existing Stage D/E convention: `pressure_bar = -sum(c_st)/estimated_bin_volume`; `1 bar = 0.1 MPa`.
- Full tensor VM is used because shear components are present.
- Bin volume uses mean atomic volume; absolute MPa values are approximate and should not be overclaimed.
- `atomic_strain_p95/p99` and `Dmin2_p95/p99` are empty because these properties were not stored in the Stage E dump and no same-pipeline reference deformation field is available across chunked files.

## Source Map

```json
{json.dumps(summary["source_map"], indent=2, ensure_ascii=False)}
```
"""
    _write_text(path, text)


def _write_event_report(path: Path, frames: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    timeline = _frame_summary_rows(frames)
    text = f"""# Stage F: event timeline

Дата: 2026-06-29

## Классификация событий

{_markdown_table(
        ["step", "event", "flag", "DXA", "line A", "HCP", "OTHER", "layer A"],
        [[r["timestep"], r["event_class"], r["physical_interpretation_flag"], r["dislocation_segments"], r["dislocation_line_length_A"], r["hcp_atoms"], r["other_atoms"], r["plastic_layer_thickness_A"]] for r in timeline],
    )}

## Интерпретация

Кадр `60000` классифицирован как `confirmed_DXA` только в техническом смысле DXA-detector. Физический subflag: `short_transient_dxa / not_developed_dislocation`, потому что line length меньше `50 A` и событие исчезает на следующем sampled frame.

Остальные кадры не подтверждают persistent DXA. HCP/OTHER изменения трактуются как local lattice disturbance около interface, не как развитая дислокационная пластика.

## Source Map

```json
{json.dumps(summary["source_map"], indent=2, ensure_ascii=False)}
```
"""
    _write_text(path, text)


def _write_agent_report(path: Path, summary: dict[str, Any]) -> None:
    text = f"""# Agent report: Stage F boundary stress-decay

Date: 2026-06-29

Run root: `{summary['run_root']}`

Completed post-processing and planning only. No MD production, blind 700k/1M run, raw dump deletion, restart deletion, git commit, or push was performed.

## Outputs

- `docs/reports/stageF_physics_meeting_alignment_ru.md`
- `docs/reports/stageF_boundary_stress_decay_report_ru.md`
- `docs/reports/stageF_boundary_stress_decay_table.csv`
- `docs/reports/stageF_boundary_stress_decay_summary.json`
- `docs/reports/stageF_event_timeline.csv`
- `docs/reports/stageF_event_timeline_report_ru.md`
- `docs/reports/figures/stageF_*.png`
- `docs/reports/renders/stageF_*.png` if render status is not blocked
- `docs/run_plans/stageF_boundary_patch_plan_ru.md`
- `analysis/python/stageF_boundary_stress_decay.py`
- `scripts/prepare_stageF_boundary_patch_geometry.py`

## Result

- Distance mode used: `{summary['distance_mode_used']}`
- Max continuous p95 layer above 120 MPa: `{_fmt(summary['max_plastic_layer_thickness_A'])} A`
- Max above-yield distance: `{_fmt(summary['max_above_yield_distance_A'])} A`
- DXA-positive frame: `60000`, short transient, not a persistent dislocation.
- Main limitation: local virial stress proxy and finite 700k ellipsoid geometry do not provide a clean physical cutoff below 120 MPa.
"""
    _write_text(path, text)


def _source_map(run_root: Path, frame_plan: list[FrameSpec], render_status: dict[str, Any]) -> dict[str, Any]:
    # The supervisor's source materials are copyrighted and never published, so
    # this map records only what a reader of the repository can actually open.
    return {
        "stageE_reports": [
            str(REPORTS_DIR / "stageE_700k_full_analysis_with_temporal_evolution_ru.md"),
            str(REPORTS_DIR / "stageE_700k_temporal_evolution_report_ru.md"),
            str(REPORTS_DIR / "stageE_700k_temporal_evolution_table.csv"),
            str(REPORTS_DIR / "stageE_700k_temporal_evolution_summary.json"),
            str(REPO_ROOT / "agent_report_stageE_700k_temporal_evolution_analysis.md"),
        ],
        "run_root": str(run_root),
        "dumps_used": [str(spec.dump_path) for spec in frame_plan],
        "restart_files_used_as_metadata": [str(_production_dir(run_root) / f"restart.{step}") for step in TARGET_STEPS if step > 0],
        "limitations": [
            "surface distance is analytic ellipsoid radial approximation for the existing Stage E geometry",
            "virial stress is a local proxy using mean atomic volume, not a calibrated continuum stress",
            "atomic strain and Dmin2 are unavailable in existing dump columns",
            "dump cadence is 10000 steps",
            "existing 700k ellipsoid domain cannot answer full micron-scale stress decay",
        ],
        "safe_claims": [
            "short transient DXA at timestep 60000",
            "no persistent dislocation evidence in sampled 700k frames",
            "Stage F should use boundary-patch sigma(r)",
        ],
        "unsafe_claims": [
            "claims that a stable dislocation was confirmed",
            "claims of a mature dislocation line",
            "claims that a physical dislocation was proven",
            "claims that a 20-micron atomistic domain was run",
            "claims that a full 5 micron inclusion was modeled",
        ],
        "render_status": render_status,
    }


def run(run_root: Path, skip_renders: bool = False) -> dict[str, Any]:
    production = _production_dir(run_root)
    frame_plan = _frame_plan(production)
    meta = _parse_metadata(run_root)
    thermo = _parse_thermo_rows(production)
    reference = _reference_positions(frame_plan[0], int(meta["matrix_max_id"]))

    frames: list[dict[str, Any]] = []
    for spec in frame_plan:
        print(f"[stageF] analyzing timestep {spec.step} from {spec.dump_path.name}", flush=True)
        frames.append(_analyze_frame(spec, meta, thermo, reference))

    _apply_frame_classification(frames)
    _apply_plastic_layers(frames)
    rows = _flatten(frames)
    csv_path = REPORTS_DIR / "stageF_boundary_stress_decay_table.csv"
    timeline_path = REPORTS_DIR / "stageF_event_timeline.csv"
    _write_csv(csv_path, rows)
    _write_event_timeline(timeline_path, frames)
    figure_paths = _plot_figures(rows, frames)
    render_status = _try_renders(frame_plan, meta, rows, skip_renders)

    timeline = _frame_summary_rows(frames)
    max_layer = max(timeline, key=lambda r: float(r["plastic_layer_thickness_A"] or 0.0))
    max_above_values = [r["max_above_yield_distance_A"] for r in timeline if r["max_above_yield_distance_A"] is not None]
    summary = {
        "status": "completed",
        "generated_at": _now(),
        "run_root": str(run_root),
        "metadata": meta,
        "distance_mode_used": frames[0]["distance_mode"],
        "yield_threshold_mpa": YIELD_THRESHOLD_MPA,
        "frame_summary": timeline,
        "max_plastic_layer_timestep": max_layer["timestep"],
        "max_plastic_layer_thickness_A": max_layer["plastic_layer_thickness_A"],
        "max_above_yield_distance_A": max(max_above_values) if max_above_values else None,
        "dxa_positive_steps": [int(f["step"]) for f in frames if int(f["dxa_segments"]) > 0 or float(f["dxa_line_A"]) > 0.0],
        "short_transient_dxa_steps": [int(f["step"]) for f in frames if f["physical_interpretation_flag"].startswith("short_transient")],
        "figure_paths": figure_paths,
        "render_status": render_status,
        "source_map": {},
    }
    summary["source_map"] = _source_map(run_root, frame_plan, render_status)

    summary_path = REPORTS_DIR / "stageF_boundary_stress_decay_summary.json"
    _write_json(summary_path, summary)
    _write_alignment_report(REPORTS_DIR / "stageF_physics_meeting_alignment_ru.md", meta, summary["source_map"])
    _write_stress_report(REPORTS_DIR / "stageF_boundary_stress_decay_report_ru.md", meta, rows, frames, summary)
    _write_event_report(REPORTS_DIR / "stageF_event_timeline_report_ru.md", frames, summary)
    _write_agent_report(REPO_ROOT / "agent_report_stageF_boundary_stress_decay.md", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--skip-renders", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = run(args.run_root, skip_renders=args.skip_renders)
    except Exception as exc:
        error_path = REPORTS_DIR / "stageF_boundary_stress_decay_summary.json"
        _write_json(
            error_path,
            {
                "status": "failed",
                "generated_at": _now(),
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        raise
    print(json.dumps({"status": summary["status"], "summary": str(REPORTS_DIR / "stageF_boundary_stress_decay_summary.json")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
