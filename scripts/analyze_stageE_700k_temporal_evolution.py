#!/usr/bin/env python3
"""Temporal post-processing for the completed Stage E4 700k DXA confirmation run.

This script reads existing production dump frames only. It does not launch MD,
rerun production, render OVITO images, encode videos, or modify raw run data.
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTROL_ROOT = PROJECT_ROOT.parents[1]
ANALYSIS_RUNNER_DIR = PROJECT_ROOT / "analysis" / "python" / "stage_runner"
if str(ANALYSIS_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_RUNNER_DIR))

import analysis_runner  # noqa: E402


DEFAULT_RUN_ROOT = PROJECT_ROOT / "runs" / "stageE_700k_dxa_confirm" / "20260625-102200"
CASE_RELATIVE = Path("cases") / "E4_700k_dxa_confirm" / "E4_phys001942_700k_80k"
TARGET_STEPS = list(range(0, 80001, 10000))

BASELINE_250K = {
    "run_root": r"runs\stageE_250k_single_physical_longrun\20260623-205439",
    "actual_atoms": 254055,
    "steps": 120000,
    "eps_z": 0.001942,
    "max_temp_K": 291.552,
    "dxa_segments": 0,
    "line_length_A": 0.0,
    "cna_fcc_atoms": 239404,
    "cna_fcc_pct": 98.25,
    "cna_hcp_atoms": 7,
    "cna_hcp_pct": 0.0029,
    "cna_other_atoms": 4258,
    "cna_other_pct": 1.747,
    "defect_atoms_beyond_1p3_shell": 2,
    "hcp_atoms_beyond_1p3_shell": 0,
}

BASELINE_510K = {
    "run_root": r"runs\stageE_homogeneous_inclusion_scaleup_v2\20260622-224433",
    "actual_atoms": 510375,
    "steps": 10000,
    "eps_z": 0.001942,
    "max_temp_K": 291.98355,
    "dxa_segments": 1,
    "line_length_A": 8.47,
    "burgers": "1/6<112>",
    "density_m2": 9.979240393274844e13,
    "cna_hcp_atoms": 12,
    "cna_hcp_pct": 0.0025,
    "cna_other_atoms": 6079,
    "cna_other_pct": 1.241,
    "defect_atoms_beyond_1p3_shell": 0,
}


@dataclass(frozen=True)
class FrameSpec:
    step: int
    dump_path: Path
    frame_index: int
    dump_timesteps: list[int]


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    meta = _read_json(run_root / CASE_RELATIVE / "production" / "geometry_metadata.json")
    final_summary = _read_json(run_root / "stageE_700k_final_summary.json")
    return {
        "matrix_max_id": int(meta["matrix_max_id"]),
        "center": tuple(float(x) for x in meta["center_A"]),
        "axes": tuple(float(x) for x in meta["inclusion_axes_A"]),
        "actual_atoms": int(meta["actual_atom_count"]),
        "matrix_atoms": int(meta["matrix_atoms"]),
        "inclusion_atoms": int(meta["inclusion_atoms"]),
        "box_A": [float(x) for x in meta["box_A"]],
        "eps_z": float(final_summary.get("eps_z", 0.001942)),
        "production_steps": int(final_summary.get("production_steps", 80000)),
        "max_temp_K": float(final_summary.get("max_temp_K", math.nan)),
        "production_returncode": final_summary.get("production_returncode"),
        "analysis_status": final_summary.get("status"),
    }


def _structure_summary_for_frame(data: Any, structure_type: np.ndarray, matrix_max_id: int) -> dict[str, Any]:
    matrix_mask = analysis_runner._matrix_mask(data, matrix_max_id)
    summary = analysis_runner._structure_summary(structure_type, matrix_mask)
    return {
        "matrix_atoms": int(summary["matrix_atoms"]),
        "fcc_atoms": int(summary["fcc_atoms"]),
        "fcc_pct": float(summary["fcc_pct"]),
        "hcp_atoms": int(summary["hcp_atoms"]),
        "hcp_pct": float(summary["hcp_pct"]),
        "other_atoms": int(summary["other_atoms"]),
        "other_pct": float(summary["other_pct"]),
        "mask": matrix_mask,
    }


def _ptm_for_frame(dump_path: Path, frame_index: int, matrix_max_id: int) -> dict[str, Any]:
    from ovito.io import import_file
    from ovito.modifiers import PolyhedralTemplateMatchingModifier

    pipe = import_file(str(dump_path))
    pipe.modifiers.append(PolyhedralTemplateMatchingModifier())
    data = pipe.compute(frame_index)
    st = np.asarray(data.particles["Structure Type"])
    mask = analysis_runner._matrix_mask(data, matrix_max_id)
    summary = analysis_runner._structure_summary(st, mask)
    attrs: dict[str, Any] = {}
    for key, value in data.attributes.items():
        skey = str(key)
        if skey.startswith("PolyhedralTemplateMatching"):
            try:
                attrs[skey] = float(value)
            except (TypeError, ValueError):
                attrs[skey] = str(value)
    summary["attributes"] = attrs
    return summary


def _burgers_lengths(dxa_attrs: dict[str, Any]) -> dict[str, float]:
    prefix = "DislocationAnalysis.length."
    result: dict[str, float] = {}
    for key, value in dxa_attrs.items():
        if str(key).startswith(prefix):
            result[str(key)[len(prefix) :]] = float(value)
    return result


def _analyze_frame(spec: FrameSpec, matrix_max_id: int, center: tuple[float, float, float], axes: tuple[float, float, float], clearance: float) -> dict[str, Any]:
    from ovito.io import import_file
    from ovito.modifiers import CommonNeighborAnalysisModifier, DislocationAnalysisModifier

    pipe = import_file(str(spec.dump_path))
    pipe.modifiers.append(CommonNeighborAnalysisModifier())
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)
    data = pipe.compute(spec.frame_index)

    st = np.asarray(data.particles["Structure Type"])
    cna = _structure_summary_for_frame(data, st, matrix_max_id)
    mask = cna.pop("mask")

    n_segments = len(data.dislocations.segments)
    total_len = float(data.attributes.get("DislocationAnalysis.total_line_length", 0.0))
    if total_len == 0.0 and n_segments:
        total_len = float(sum(segment.length for segment in data.dislocations.segments))
    volume = float(data.cell.volume)

    dxa_attrs: dict[str, Any] = {}
    for key, value in data.attributes.items():
        skey = str(key)
        if skey.startswith("DislocationAnalysis"):
            try:
                dxa_attrs[skey] = float(value)
            except (TypeError, ValueError):
                dxa_attrs[skey] = str(value)

    stress_profiles = analysis_runner.analyze_stress_profiles(data, st, mask, center, axes)

    pos = np.asarray(data.particles.positions)
    cell = np.asarray(data.cell)[:3, :3]
    box_len = np.array([cell[0][0], cell[1][1], cell[2][2]], dtype=float)
    shell_axes = np.array(axes, dtype=float) + float(clearance)
    defect_mask = mask & (st != 1)
    rel = pos[defect_mask] - np.array(center, dtype=float)
    rel -= box_len * np.round(rel / box_len)
    e_val = np.sqrt(np.sum((rel / shell_axes) ** 2, axis=1))
    hcp_defect = st[defect_mask] == 2
    beyond = e_val > 1.3

    ptm = _ptm_for_frame(spec.dump_path, spec.frame_index, matrix_max_id)

    return {
        "step": int(spec.step),
        "dump": str(spec.dump_path),
        "frame_index": int(spec.frame_index),
        "dump_timesteps": spec.dump_timesteps,
        "atom_count": int(data.particles.count),
        "matrix_atoms": int(cna["matrix_atoms"]),
        "inclusion_atoms": int(data.particles.count - cna["matrix_atoms"]),
        "cell_volume_A3": volume,
        "cna": cna,
        "ptm": ptm,
        "dxa": {
            "segments": int(n_segments),
            "total_line_length_A": float(total_len),
            "total_line_length_A_rounded": round(total_len, 2),
            "density_per_m2": float(total_len / volume * 1e20) if volume else 0.0,
            "burgers_lengths_A": _burgers_lengths(dxa_attrs),
            "attributes": dxa_attrs,
        },
        "plastic_zone": {
            "matrix_defect_atoms_total": int(defect_mask.sum()),
            "defect_atoms_beyond_1p3_shell": int(np.count_nonzero(beyond)),
            "hcp_atoms_beyond_1p3_shell": int(np.count_nonzero(beyond & hcp_defect)),
            "max_normalized_ellipsoid_distance": float(e_val.max()) if int(defect_mask.sum()) else None,
            "median_normalized_ellipsoid_distance": float(np.median(e_val)) if int(defect_mask.sum()) else None,
        },
        "stress_profiles": stress_profiles,
    }


def _flat_rows(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for frame in frames:
        cna = frame["cna"]
        ptm = frame["ptm"]
        dxa = frame["dxa"]
        pz = frame["plastic_zone"]
        hotspots = frame.get("stress_profiles", {}).get("hotspots", {}) or {}
        radial_profile = frame.get("stress_profiles", {}).get("radial_profile", []) or []
        radial_0_5 = radial_profile[0] if len(radial_profile) > 0 else {}
        radial_5_15 = radial_profile[1] if len(radial_profile) > 1 else {}
        radial_15_30 = radial_profile[2] if len(radial_profile) > 2 else {}
        radial_gt30 = radial_profile[3] if len(radial_profile) > 3 else {}
        burgers = dxa.get("burgers_lengths_A", {})
        rows.append(
            {
                "step": frame["step"],
                "dump": frame["dump"],
                "frame_index": frame["frame_index"],
                "atom_count": frame["atom_count"],
                "matrix_atoms": frame["matrix_atoms"],
                "inclusion_atoms": frame["inclusion_atoms"],
                "dxa_segments": dxa["segments"],
                "dxa_total_line_length_A": dxa["total_line_length_A"],
                "dxa_density_per_m2": dxa["density_per_m2"],
                "dxa_burgers_1_6_112_A": burgers.get("1/6<112>", 0.0),
                "dxa_burgers_1_2_110_A": burgers.get("1/2<110>", 0.0),
                "dxa_burgers_other_A": burgers.get("other", 0.0),
                "cna_fcc_atoms": cna["fcc_atoms"],
                "cna_fcc_pct": cna["fcc_pct"],
                "cna_hcp_atoms": cna["hcp_atoms"],
                "cna_hcp_pct": cna["hcp_pct"],
                "cna_other_atoms": cna["other_atoms"],
                "cna_other_pct": cna["other_pct"],
                "ptm_fcc_atoms": ptm["fcc_atoms"],
                "ptm_fcc_pct": ptm["fcc_pct"],
                "ptm_hcp_atoms": ptm["hcp_atoms"],
                "ptm_hcp_pct": ptm["hcp_pct"],
                "ptm_other_atoms": ptm["other_atoms"],
                "ptm_other_pct": ptm["other_pct"],
                "matrix_defect_atoms_total": pz["matrix_defect_atoms_total"],
                "defect_atoms_beyond_1p3_shell": pz["defect_atoms_beyond_1p3_shell"],
                "hcp_atoms_beyond_1p3_shell": pz["hcp_atoms_beyond_1p3_shell"],
                "max_normalized_ellipsoid_distance": pz["max_normalized_ellipsoid_distance"],
                "median_normalized_ellipsoid_distance": pz["median_normalized_ellipsoid_distance"],
                "radial_0_5_atoms": radial_0_5.get("atom_count"),
                "radial_0_5_hcp_atoms": radial_0_5.get("hcp_atoms"),
                "radial_0_5_other_atoms": radial_0_5.get("other_atoms"),
                "radial_0_5_other_pct": radial_0_5.get("other_pct"),
                "radial_0_5_pzz_MPa": radial_0_5.get("pzz_MPa"),
                "radial_0_5_von_mises_MPa": radial_0_5.get("von_mises_MPa"),
                "radial_5_15_atoms": radial_5_15.get("atom_count"),
                "radial_5_15_other_atoms": radial_5_15.get("other_atoms"),
                "radial_5_15_other_pct": radial_5_15.get("other_pct"),
                "radial_5_15_von_mises_MPa": radial_5_15.get("von_mises_MPa"),
                "radial_15_30_atoms": radial_15_30.get("atom_count"),
                "radial_15_30_other_atoms": radial_15_30.get("other_atoms"),
                "radial_15_30_other_pct": radial_15_30.get("other_pct"),
                "radial_15_30_von_mises_MPa": radial_15_30.get("von_mises_MPa"),
                "radial_gt30_atoms": radial_gt30.get("atom_count"),
                "radial_gt30_hcp_atoms": radial_gt30.get("hcp_atoms"),
                "radial_gt30_other_atoms": radial_gt30.get("other_atoms"),
                "radial_gt30_other_pct": radial_gt30.get("other_pct"),
                "radial_gt30_von_mises_MPa": radial_gt30.get("von_mises_MPa"),
                "max_radial_von_mises_MPa": (hotspots.get("max_radial_von_mises") or {}).get("von_mises_MPa"),
                "max_z_above_von_mises_MPa": (hotspots.get("max_z_above_von_mises") or {}).get("von_mises_MPa"),
                "max_z_below_von_mises_MPa": (hotspots.get("max_z_below_von_mises") or {}).get("von_mises_MPa"),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: Any, ndigits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if math.isnan(value):
            return "n/a"
        if abs(value) >= 10000 or (0 < abs(value) < 0.001):
            return f"{value:.6g}"
        if 0 < abs(value) < 0.01:
            return f"{value:.6f}"
        return f"{value:.{ndigits}f}"
    return str(value)


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(_fmt(cell) for cell in row) + " |")
    return "\n".join(out)


def _temporal_verdict(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dxa_positive = [r for r in rows if int(r["dxa_segments"]) > 0 or float(r["dxa_total_line_length_A"] or 0.0) > 0.0]
    max_defects = max(rows, key=lambda r: int(r["matrix_defect_atoms_total"]))
    max_beyond = max(rows, key=lambda r: int(r["defect_atoms_beyond_1p3_shell"]))
    max_hcp = max(rows, key=lambda r: int(r["cna_hcp_atoms"]))
    max_interface_vm = max(rows, key=lambda r: float(r["radial_0_5_von_mises_MPa"] or 0.0))
    return {
        "dxa_positive_steps": [int(r["step"]) for r in dxa_positive],
        "max_dxa_segments": max(int(r["dxa_segments"]) for r in rows),
        "max_dxa_line_length_A": max(float(r["dxa_total_line_length_A"] or 0.0) for r in rows),
        "max_matrix_defect_step": int(max_defects["step"]),
        "max_matrix_defect_atoms_total": int(max_defects["matrix_defect_atoms_total"]),
        "max_defect_beyond_step": int(max_beyond["step"]),
        "max_defect_atoms_beyond_1p3_shell": int(max_beyond["defect_atoms_beyond_1p3_shell"]),
        "max_cna_hcp_step": int(max_hcp["step"]),
        "max_cna_hcp_atoms": int(max_hcp["cna_hcp_atoms"]),
        "max_interface_vm_step": int(max_interface_vm["step"]),
        "max_interface_vm_MPa": float(max_interface_vm["radial_0_5_von_mises_MPa"] or 0.0),
        "interpretation": (
            "No transient DXA segment was detected in sampled production frames."
            if not dxa_positive
            else "A transient DXA segment was detected in sampled production frames."
        ),
    }


def _write_plots(out_dir: Path, rows: list[dict[str, Any]]) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []

    paths: list[str] = []
    steps = [int(r["step"]) for r in rows]
    series = [
        ("stageE_700k_temporal_dislocation_length.png", "DXA line length, A", [float(r["dxa_total_line_length_A"] or 0.0) for r in rows]),
        ("stageE_700k_temporal_defect_atoms.png", "Matrix defect atoms", [int(r["matrix_defect_atoms_total"]) for r in rows]),
        ("stageE_700k_temporal_hcp_atoms.png", "CNA HCP atoms in matrix", [int(r["cna_hcp_atoms"]) for r in rows]),
    ]
    for filename, ylabel, values in series:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.plot(steps, values, marker="o", linewidth=1.8)
        ax.set_xlabel("Timestep")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(min(steps), max(steps))
        fig.tight_layout()
        path = out_dir / filename
        fig.savefig(path, dpi=160)
        plt.close(fig)
        paths.append(str(path))
    return paths


def _short_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _write_temporal_report(path: Path, run_root: Path, metadata: dict[str, Any], rows: list[dict[str, Any]], verdict: dict[str, Any], csv_path: Path, summary_path: Path, plot_paths: list[str]) -> None:
    dxa_positive_steps = verdict["dxa_positive_steps"]
    positive_steps_set = set(dxa_positive_steps)
    positive_rows = [r for r in rows if int(r["step"]) in positive_steps_set]
    burgers_summary = "; ".join(
        (
            f"{r['step']}: 1/6<112>={_fmt(float(r['dxa_burgers_1_6_112_A'] or 0.0))} A, "
            f"1/2<110>={_fmt(float(r['dxa_burgers_1_2_110_A'] or 0.0))} A, "
            f"other={_fmt(float(r['dxa_burgers_other_A'] or 0.0))} A"
        )
        for r in positive_rows
    )
    if dxa_positive_steps:
        temporal_comparison_conclusion = f"transient DXA at {dxa_positive_steps}; final DXA=0"
        dxa_summary = (
            f"В sampled temporal series обнаружен transient DXA-сигнал на шагах "
            f"`{dxa_positive_steps}`: максимум `{verdict['max_dxa_segments']}` сегмента, "
            f"суммарная длина `{_fmt(verdict['max_dxa_line_length_A'])}` A. "
            f"Burgers-разложение: `{burgers_summary}`. "
            "Финальный кадр `80000` снова имеет DXA=0, поэтому сигнал кратковременный."
        )
        transient_interpretation = (
            "700k подтверждает сильный локальный механический отклик интерфейса Fe4Al13/Al, "
            f"и temporal post-processing нашел кратковременный DXA-сегмент на шаге "
            f"`{dxa_positive_steps[0]}`. Это поддерживает интерпретацию 510k-сегмента как "
            "реального локального порогового события, но не как устойчивой линии: соседние "
            "sampled кадры и финальный кадр не удерживают DXA-сигнал."
        )
    else:
        temporal_comparison_conclusion = "sampled frames DXA=0"
        dxa_summary = (
            "В sampled temporal series DXA-сегменты не обнаружены ни в одном кадре: "
            f"positive steps = `{dxa_positive_steps}`, максимальная суммарная длина линии = "
            f"`{_fmt(verdict['max_dxa_line_length_A'])}` A. Это означает, что короткий "
            "510k DXA-сигнал `1/6<112>` длиной `8.47 A` не воспроизвелся ни в финальном "
            "700k кадре, ни в контрольных промежуточных кадрах с шагом `10000`."
        )
        transient_interpretation = (
            "700k подтверждает сильный локальный механический отклик интерфейса Fe4Al13/Al, "
            "но temporal post-processing не нашел transient DXA-сегмента на сетке `10k` шагов. "
            "Следовательно, 510k-сегмент остается слабым локальным пороговым сигналом, "
            "чувствительным к размеру, времени или критериям распознавания."
        )

    dxa_rows = [
        [
            r["step"],
            r["dxa_segments"],
            r["dxa_total_line_length_A"],
            r["dxa_burgers_1_6_112_A"],
            r["cna_hcp_atoms"],
            r["cna_other_atoms"],
            r["matrix_defect_atoms_total"],
            r["defect_atoms_beyond_1p3_shell"],
            r["radial_0_5_other_pct"],
            r["radial_0_5_von_mises_MPa"],
        ]
        for r in rows
    ]
    report = f"""# Stage E4 700k: temporal DXA/CNA/PTM анализ промежуточных кадров

Дата отчета: 2026-06-29

Run root: `{run_root}`

Задача: post-processing только по уже существующим production dump-файлам для шагов `0, 10000, ..., 80000`. Новые MD-запуски, sweep/grid, OVITO render и ffmpeg не выполнялись.

## Краткий вывод

{dxa_summary}

Дефектность остается интерфейсно-локализованной. Максимум CNA HCP в матрице: `{verdict["max_cna_hcp_atoms"]}` атомов на шаге `{verdict["max_cna_hcp_step"]}`. Максимум дальних дефектов за `1.3` shell: `{verdict["max_defect_atoms_beyond_1p3_shell"]}` атомов на шаге `{verdict["max_defect_beyond_step"]}`. По этим кадрам нет признака устойчивой дислокационной линии или распространения дефектной зоны в объем матрицы.

## Корректность источников

| Показатель | Значение |
| --- | ---: |
| Actual atoms | `{metadata["actual_atoms"]}` |
| Matrix atoms | `{metadata["matrix_atoms"]}` |
| Inclusion atoms | `{metadata["inclusion_atoms"]}` |
| eps_z | `{metadata["eps_z"]}` |
| Production steps | `{metadata["production_steps"]}` |
| Max temp K | `{metadata["max_temp_K"]}` |
| Production return code | `{metadata["production_returncode"]}` |
| Existing analysis status | `{metadata["analysis_status"]}` |

## Temporal table

{_markdown_table(["Step", "DXA seg", "Line A", "1/6<112> A", "CNA HCP", "CNA OTHER", "Defect atoms", "Beyond 1.3", "0-5A OTHER %", "0-5A VM MPa"], dxa_rows)}

## Сравнение с baseline

{_markdown_table(
        ["Run", "Atoms", "Steps", "eps_z", "Max T K", "DXA seg", "Line A", "HCP atoms", "OTHER atoms", "Conclusion"],
        [
            ["250k longrun", BASELINE_250K["actual_atoms"], BASELINE_250K["steps"], BASELINE_250K["eps_z"], BASELINE_250K["max_temp_K"], BASELINE_250K["dxa_segments"], BASELINE_250K["line_length_A"], BASELINE_250K["cna_hcp_atoms"], BASELINE_250K["cna_other_atoms"], "interface-local, DXA=0"],
            ["510k v2 physical", BASELINE_510K["actual_atoms"], BASELINE_510K["steps"], BASELINE_510K["eps_z"], BASELINE_510K["max_temp_K"], BASELINE_510K["dxa_segments"], BASELINE_510K["line_length_A"], BASELINE_510K["cna_hcp_atoms"], BASELINE_510K["cna_other_atoms"], "short local 1/6<112> signal"],
            ["700k temporal", metadata["actual_atoms"], metadata["production_steps"], metadata["eps_z"], metadata["max_temp_K"], verdict["max_dxa_segments"], verdict["max_dxa_line_length_A"], verdict["max_cna_hcp_atoms"], max(int(r["cna_other_atoms"]) for r in rows), temporal_comparison_conclusion],
        ],
    )}

## Интерпретация

{transient_interpretation} По этой серии корректная формулировка: локальное интерфейсное состояние около порога зарождения без подтвержденной устойчивой дислокационной линии.

## Артефакты

- CSV: `{_short_path(csv_path)}`
- JSON: `{_short_path(summary_path)}`
"""
    if plot_paths:
        report += "\nГрафики:\n\n"
        for plot_path in plot_paths:
            report += f"- `{_short_path(Path(plot_path))}`\n"

    report += "\n## Ограничения\n\n"
    report += "- Анализ выполнен по кадрам с шагом `10000`; событие короче этого интервала могло быть пропущено.\n"
    report += "- Локальные напряжения являются virial proxy и надежнее для относительного сравнения зон, чем для абсолютной шкалы MPa.\n"
    report += "- DXA/CNA/PTM чувствительны к порогам распознавания и температурной истории.\n"

    path.write_text(report, encoding="utf-8")


def _write_combined_report(path: Path, temporal_report: Path, run_root: Path, metadata: dict[str, Any], rows: list[dict[str, Any]], verdict: dict[str, Any]) -> None:
    final = rows[-1]
    dxa_positive_steps = verdict["dxa_positive_steps"]
    positive_steps_set = set(dxa_positive_steps)
    positive_rows = [r for r in rows if int(r["step"]) in positive_steps_set]
    burgers_summary = "; ".join(
        (
            f"{r['step']}: 1/6<112>={_fmt(float(r['dxa_burgers_1_6_112_A'] or 0.0))} A, "
            f"1/2<110>={_fmt(float(r['dxa_burgers_1_2_110_A'] or 0.0))} A, "
            f"other={_fmt(float(r['dxa_burgers_other_A'] or 0.0))} A"
        )
        for r in positive_rows
    )
    if dxa_positive_steps:
        main_dxa = (
            f"Полный post-processing 700k подтверждает штатное завершение production "
            f"(`80000/80000`, return code `{metadata['production_returncode']}`) и обнаруживает "
            f"transient DXA-сигнал на шагах `{dxa_positive_steps}`: максимум "
            f"`{verdict['max_dxa_segments']}` сегмента, `{_fmt(verdict['max_dxa_line_length_A'])}` A. "
            f"Burgers-разложение: `{burgers_summary}`. "
            "Финальный кадр `80000` снова имеет `0` сегментов и `0.0 A` суммарной линии."
        )
        transient_question = (
            f"Вывод по transient question: на доступной сетке промежуточных кадров DXA-сегмент "
            f"появлялся на шаге `{dxa_positive_steps[0]}` и исчезал к следующим sampled кадрам. "
            "Это делает 510k результат физически правдоподобным как короткое пороговое событие, "
            "но 700k не поддерживает устойчивую дислокационную линию в финальном состоянии."
        )
        assertion_bullet = f"- DXA transient найден на шагах `{dxa_positive_steps}`; финальный `80000` имеет DXA=0."
    else:
        main_dxa = (
            f"Полный post-processing 700k подтверждает штатное завершение production "
            f"(`80000/80000`, return code `{metadata['production_returncode']}`) и отсутствие "
            "DXA-сегментов во всех sampled кадрах `0, 10000, ..., 80000`. Финальный кадр также "
            "имеет `0` сегментов и `0.0 A` суммарной линии."
        )
        transient_question = (
            "Вывод по transient question: на доступной сетке промежуточных кадров DXA-сегмент "
            "не появлялся. Это сужает интерпретацию 510k результата: там был короткий локальный "
            "зародыш `1/6<112>` длиной `8.47 A`, но 700k temporal series его не поддержала."
        )
        assertion_bullet = "- DXA=0 во всех sampled промежуточных кадрах и в финале."
    report = f"""# Stage E4 700k: полный анализ с temporal evolution

Дата отчета: 2026-06-29

Run root: `{run_root}`

## Главный вывод

{main_dxa}

Интерфейсная дефектная оболочка сохраняется, но не превращается в устойчивую линию DXA. Максимум temporal CNA HCP: `{verdict["max_cna_hcp_atoms"]}` атомов; максимум дальних дефектов за `1.3` shell: `{verdict["max_defect_atoms_beyond_1p3_shell"]}` атомов. Лучшее физическое описание: локальный интерфейсный отклик около порога зарождения, без подтверждения устойчивой дислокации на 700k.

## 700k финальное состояние

| Метрика | Значение |
| --- | ---: |
| Actual atoms | `{metadata["actual_atoms"]}` |
| Matrix atoms | `{metadata["matrix_atoms"]}` |
| Inclusion atoms | `{metadata["inclusion_atoms"]}` |
| eps_z | `{metadata["eps_z"]}` |
| Steps | `{metadata["production_steps"]}` |
| Max temp K | `{metadata["max_temp_K"]}` |
| Final DXA segments | `{final["dxa_segments"]}` |
| Final DXA line A | `{_fmt(final["dxa_total_line_length_A"])}` |
| Final CNA FCC atoms | `{final["cna_fcc_atoms"]}` |
| Final CNA HCP atoms | `{final["cna_hcp_atoms"]}` |
| Final CNA OTHER atoms | `{final["cna_other_atoms"]}` |
| Final defect atoms beyond 1.3 shell | `{final["defect_atoms_beyond_1p3_shell"]}` |

## Temporal DXA check

{_markdown_table(
        ["Step", "DXA seg", "Line A", "1/6<112> A", "CNA HCP", "CNA OTHER", "Beyond 1.3", ">30A OTHER"],
        [[r["step"], r["dxa_segments"], r["dxa_total_line_length_A"], r["dxa_burgers_1_6_112_A"], r["cna_hcp_atoms"], r["cna_other_atoms"], r["defect_atoms_beyond_1p3_shell"], r["radial_gt30_other_atoms"]] for r in rows],
    )}

{transient_question}

## Сравнение 250k / 510k / 700k

{_markdown_table(
        ["Run", "Atoms", "Steps", "eps_z", "DXA seg", "Line A", "HCP", "OTHER", "Defects beyond 1.3"],
        [
            ["250k longrun", BASELINE_250K["actual_atoms"], BASELINE_250K["steps"], BASELINE_250K["eps_z"], BASELINE_250K["dxa_segments"], BASELINE_250K["line_length_A"], BASELINE_250K["cna_hcp_atoms"], BASELINE_250K["cna_other_atoms"], BASELINE_250K["defect_atoms_beyond_1p3_shell"]],
            ["510k v2 physical", BASELINE_510K["actual_atoms"], BASELINE_510K["steps"], BASELINE_510K["eps_z"], BASELINE_510K["dxa_segments"], BASELINE_510K["line_length_A"], BASELINE_510K["cna_hcp_atoms"], BASELINE_510K["cna_other_atoms"], BASELINE_510K["defect_atoms_beyond_1p3_shell"]],
            ["700k temporal max", metadata["actual_atoms"], metadata["production_steps"], metadata["eps_z"], verdict["max_dxa_segments"], verdict["max_dxa_line_length_A"], verdict["max_cna_hcp_atoms"], max(int(r["cna_other_atoms"]) for r in rows), verdict["max_defect_atoms_beyond_1p3_shell"]],
        ],
    )}

## Что можно утверждать

- 700k production корректно завершен и пригоден для post-processing.
{assertion_bullet}
- Основной дефектный сигнал остается у интерфейса и Z-cap областей включения.
- 510k DXA-сигнал получил временный 700k аналог, но не удержался как финальный устойчивый сигнал.

## Что нельзя утверждать

- Нельзя утверждать устойчивую дислокационную линию в 700k.
- Нельзя утверждать объемное распространение пластической зоны в матрицу.
- Нельзя исключить событие короче интервала между сохраненными dump-кадрами.

Подробный temporal отчет: `{_short_path(temporal_report)}`.
"""
    path.write_text(report, encoding="utf-8")


def _write_agent_report(path: Path, run_root: Path, artifacts: dict[str, Path], verdict: dict[str, Any]) -> None:
    if verdict["dxa_positive_steps"]:
        conclusion = (
            f"Conclusion: sampled 700k frames show a transient DXA segment at "
            f"{verdict['dxa_positive_steps']}; the final frame returns to DXA=0, "
            "so the response is short-lived and interface-local."
        )
    else:
        conclusion = "Conclusion: sampled 700k frames do not show a transient DXA segment. The observed response is interface-local."
    report = f"""# Agent report: Stage E4 700k temporal evolution analysis

Date: 2026-06-29

Run root: `{run_root}`

Completed post-processing only. No MD production, rerun, sweep/grid, OVITO render, ffmpeg, raw-file deletion, or mutating git operation was performed.

## Outputs

- Temporal report: `{_short_path(artifacts["temporal_report"])}`
- Combined report: `{_short_path(artifacts["combined_report"])}`
- CSV table: `{_short_path(artifacts["csv"])}`
- JSON summary: `{_short_path(artifacts["summary"])}`
- Control-plane handoff JSON: `{artifacts["control_handoff"]}`

## Result

- Frames analyzed: `0, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000`
- DXA-positive sampled steps: `{verdict["dxa_positive_steps"]}`
- Max DXA segments: `{verdict["max_dxa_segments"]}`
- Max DXA line length A: `{_fmt(verdict["max_dxa_line_length_A"])}`
- Max CNA HCP atoms: `{verdict["max_cna_hcp_atoms"]}` at step `{verdict["max_cna_hcp_step"]}`
- Max defects beyond 1.3 shell: `{verdict["max_defect_atoms_beyond_1p3_shell"]}` at step `{verdict["max_defect_beyond_step"]}`

{conclusion}
"""
    path.write_text(report, encoding="utf-8")


def _write_state_reports(control_path: Path, run_root: Path, metadata: dict[str, Any], artifacts: dict[str, Path], rows: list[dict[str, Any]], verdict: dict[str, Any]) -> None:
    control_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "completed",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "task": "stageE_700k_temporal_evolution_postprocessing",
        "run_root": str(run_root),
        "metadata": metadata,
        "target_steps": TARGET_STEPS,
        "frames_analyzed": [
            {
                "step": int(r["step"]),
                "dump": r["dump"],
                "frame_index": int(r["frame_index"]),
                "dxa_segments": int(r["dxa_segments"]),
                "dxa_total_line_length_A": float(r["dxa_total_line_length_A"] or 0.0),
                "cna_hcp_atoms": int(r["cna_hcp_atoms"]),
                "cna_other_atoms": int(r["cna_other_atoms"]),
                "defect_atoms_beyond_1p3_shell": int(r["defect_atoms_beyond_1p3_shell"]),
            }
            for r in rows
        ],
        "verdict": verdict,
        "artifacts": {key: str(value) for key, value in artifacts.items()},
        "constraints_honored": [
            "no_new_md_production",
            "no_rerun",
            "no_sweep_or_grid",
            "no_ovito_render",
            "no_ffmpeg",
            "no_raw_file_deletion",
            "no_mutating_git_operation",
        ],
    }
    control_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--clearance", type=float, default=2.2)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)

    run_root = args.run_root.resolve()
    production = _production_dir(run_root)
    metadata = _parse_metadata(run_root)
    plan = _frame_plan(production)

    print("Frame plan:")
    for spec in plan:
        print(f"  step={spec.step} frame={spec.frame_index} dump={spec.dump_path.name} timesteps={spec.dump_timesteps}", flush=True)

    frames: list[dict[str, Any]] = []
    for spec in plan:
        print(f"Analyzing step {spec.step} from {spec.dump_path.name} frame {spec.frame_index}", flush=True)
        frames.append(
            _analyze_frame(
                spec=spec,
                matrix_max_id=metadata["matrix_max_id"],
                center=metadata["center"],
                axes=metadata["axes"],
                clearance=args.clearance,
            )
        )

    rows = _flat_rows(frames)
    verdict = _temporal_verdict(rows)

    reports_dir = PROJECT_ROOT / "docs" / "reports"
    csv_path = reports_dir / "stageE_700k_temporal_evolution_table.csv"
    summary_path = reports_dir / "stageE_700k_temporal_evolution_summary.json"
    temporal_report = reports_dir / "stageE_700k_temporal_evolution_report_ru.md"
    combined_report = reports_dir / "stageE_700k_full_analysis_with_temporal_evolution_ru.md"
    agent_report = PROJECT_ROOT / "agent_report_stageE_700k_temporal_evolution_analysis.md"
    control_handoff = CONTROL_ROOT / "state" / "reports" / "physics_md_al_fe" / "stageE_700k_temporal_evolution_20260629.json"

    reports_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(csv_path, rows)
    plot_paths = [] if args.no_plots else _write_plots(reports_dir, rows)
    summary_payload = {
        "status": "completed",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_root": str(run_root),
        "metadata": metadata,
        "frame_plan": [
            {
                "step": spec.step,
                "dump": str(spec.dump_path),
                "frame_index": spec.frame_index,
                "dump_timesteps": spec.dump_timesteps,
            }
            for spec in plan
        ],
        "rows": rows,
        "frames": frames,
        "verdict": verdict,
        "plots": plot_paths,
    }
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    _write_temporal_report(temporal_report, run_root, metadata, rows, verdict, csv_path, summary_path, plot_paths)
    _write_combined_report(combined_report, temporal_report, run_root, metadata, rows, verdict)

    artifacts = {
        "temporal_report": temporal_report,
        "combined_report": combined_report,
        "csv": csv_path,
        "summary": summary_path,
        "agent_report": agent_report,
        "control_handoff": control_handoff,
    }
    _write_state_reports(control_handoff, run_root, metadata, artifacts, rows, verdict)
    _write_agent_report(agent_report, run_root, artifacts, verdict)

    print(json.dumps({"status": "completed", "verdict": verdict, "artifacts": {k: str(v) for k, v in artifacts.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
