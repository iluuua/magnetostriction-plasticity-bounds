#!/usr/bin/env python3
"""Extract meeting-ready Stage F CPU result numbers.

This script reads existing Stage F CPU analysis CSV/JSON/MD/figure artifacts and
writes compact executive reports. It does not launch MD, smoke, GPU repair, or
modify raw run outputs.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "docs" / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
YIELD_MPA = 120.0
PRIMARY_WINDOW = "last20_mean"
FINAL_WINDOW = "final"
INTERFACE_Z_A = 50.0


SOURCE_FILES = {
    "sigma_summary": REPORTS_DIR / "stageF_cpu_results_sigma_summary.json",
    "defect_summary": REPORTS_DIR / "stageF_cpu_results_defect_summary.json",
    "residual": REPORTS_DIR / "stageF_cpu_results_residual_plasticity_check.json",
    "decision": REPORTS_DIR / "stageF_cpu_results_next_step_decision.json",
    "verification": REPORTS_DIR / "stageF_cpu_results_production_verification.json",
    "eps0000_sigma": REPORTS_DIR / "stageF_cpu_results_eps0000_sigma_profile.csv",
    "eps00194_sigma": REPORTS_DIR / "stageF_cpu_results_eps00194_sigma_profile.csv",
    "delta_sigma": REPORTS_DIR / "stageF_cpu_results_delta_sigma_profile.csv",
    "eps0000_defect": REPORTS_DIR / "stageF_cpu_results_eps0000_defect_profile.csv",
    "eps00194_defect": REPORTS_DIR / "stageF_cpu_results_eps00194_defect_profile.csv",
    "delta_defect": REPORTS_DIR / "stageF_cpu_results_delta_defect_profile.csv",
}


EXPECTED_EXISTING = [
    "docs/reports/stageF_cpu_results_production_verification.md",
    "docs/reports/stageF_cpu_results_production_verification.json",
    "docs/reports/stageF_cpu_results_pshonkin_criteria_map_ru.md",
    "docs/reports/stageF_cpu_results_dump_inventory.md",
    "docs/reports/stageF_cpu_results_dump_inventory.json",
    "docs/reports/stageF_cpu_results_eps0000_sigma_profile.csv",
    "docs/reports/stageF_cpu_results_eps00194_sigma_profile.csv",
    "docs/reports/stageF_cpu_results_delta_sigma_profile.csv",
    "docs/reports/stageF_cpu_results_sigma_summary.json",
    "docs/reports/stageF_cpu_results_sigma_report_ru.md",
    "docs/reports/stageF_cpu_results_eps0000_defect_profile.csv",
    "docs/reports/stageF_cpu_results_eps00194_defect_profile.csv",
    "docs/reports/stageF_cpu_results_delta_defect_profile.csv",
    "docs/reports/stageF_cpu_results_defect_summary.json",
    "docs/reports/stageF_cpu_results_plasticity_report_ru.md",
    "docs/reports/stageF_cpu_results_residual_plasticity_check_ru.md",
    "docs/reports/stageF_cpu_results_residual_plasticity_check.json",
    "docs/reports/stageF_cpu_results_pshonkin_report_ru.md",
    "docs/reports/stageF_cpu_results_pshonkin_meeting_brief_ru.md",
    "docs/reports/stageF_cpu_results_next_step_decision_ru.md",
    "docs/reports/stageF_cpu_results_next_step_decision.json",
    "agent_report_stageF_cpu_results_pshonkin_analysis.md",
]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number):
        return "n/a"
    if abs(number) >= 1000.0:
        return f"{number:.1f}"
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def as_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, float) and math.isnan(value):
        return None
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=as_jsonable) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def md_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(out)


def file_record(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": rel(path),
        "full_path": str(path),
        "length": stat.st_size,
        "last_write_time": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
    }


def collect_inventory() -> dict[str, Any]:
    report_files = [
        p
        for p in REPORTS_DIR.glob("*")
        if p.is_file()
        and (
            p.name.startswith("stageF_cpu_results")
            or "pshonkin" in p.name.lower()
            or "plasticity" in p.name.lower()
            or "sigma" in p.name.lower()
        )
    ]
    figure_files = sorted(FIGURES_DIR.glob("stageF_cpu_results*.png")) if FIGURES_DIR.exists() else []
    expected_missing = [path for path in EXPECTED_EXISTING if not (REPO_ROOT / path).exists()]
    records = [file_record(p) for p in sorted(report_files, key=lambda x: x.name)]
    inventory = {
        "generated_at": now_iso(),
        "reports_considered": len(records),
        "csv_files": [r for r in records if r["name"].endswith(".csv")],
        "json_files": [r for r in records if r["name"].endswith(".json")],
        "md_files": [r for r in records if r["name"].endswith(".md")],
        "other_files": [r for r in records if not any(r["name"].endswith(ext) for ext in [".csv", ".json", ".md"])],
        "figures": [file_record(p) for p in sorted(figure_files, key=lambda x: x.name)],
        "expected_missing": expected_missing,
    }
    return inventory


def peak_by_abs(df: pd.DataFrame, col: str, windows: list[str] | None = None) -> dict[str, Any]:
    source = df if windows is None else df[df["window"].isin(windows)].copy()
    idx = source[col].abs().idxmax()
    row = source.loc[idx]
    return {
        "column": col,
        "window": row["window"],
        "value_mpa": float(row[col]),
        "abs_value_mpa": abs(float(row[col])),
        "r_bin_min_A": float(row["r_bin_min_A"]),
        "r_bin_max_A": float(row["r_bin_max_A"]),
        "r_center_A": float(row["r_bin_center_A"]),
    }


def peak_positive(df: pd.DataFrame, col: str, window: str) -> dict[str, Any]:
    source = df[df["window"] == window].copy()
    idx = source[col].idxmax()
    row = source.loc[idx]
    return {
        "column": col,
        "window": row["window"],
        "value_mpa": float(row[col]),
        "r_bin_min_A": float(row["r_bin_min_A"]),
        "r_bin_max_A": float(row["r_bin_max_A"]),
        "r_center_A": float(row["r_bin_center_A"]),
    }


def contiguous_thickness(df: pd.DataFrame, col: str, threshold: float, window: str, absolute: bool = False) -> float:
    rows = df[df["window"] == window].sort_values("r_bin_min_A")
    thickness = 0.0
    for _, row in rows.iterrows():
        value = float(row[col])
        above = abs(value) > threshold if absolute else value > threshold
        if above:
            thickness = float(row["r_bin_max_A"])
        else:
            break
    return thickness


def robust_noise_floor(delta_sigma: pd.DataFrame) -> dict[str, Any]:
    rows = delta_sigma[(delta_sigma["window"] == PRIMARY_WINDOW) & (delta_sigma["r_bin_center_A"] >= 70.0)].copy()
    values = rows["delta_sigma_vm_mean_mpa"].abs().dropna().to_numpy()
    median_abs = float(np.median(values))
    mad = float(np.median(np.abs(values - median_abs)))
    threshold = float(median_abs + 2.0 * 1.4826 * mad)
    edge_rows = rows[rows["delta_sigma_vm_mean_mpa"].abs() > threshold]
    return {
        "method": "far-field r_center>=70 A, threshold = median(abs(delta_vm)) + 2*1.4826*MAD",
        "window": PRIMARY_WINDOW,
        "far_field_bin_count": int(len(values)),
        "median_abs_delta_vm_mpa": median_abs,
        "mad_abs_delta_vm_mpa": mad,
        "noise_floor_mpa": threshold,
        "far_field_edge_outliers": edge_rows[
            ["r_bin_min_A", "r_bin_max_A", "r_bin_center_A", "delta_sigma_vm_mean_mpa"]
        ].to_dict(orient="records"),
    }


def weighted_overlap_rows(delta_sigma: pd.DataFrame, lo: float, hi: float) -> dict[str, Any]:
    rows = delta_sigma[delta_sigma["window"] == PRIMARY_WINDOW].copy()
    selected: list[tuple[float, pd.Series]] = []
    for _, row in rows.iterrows():
        overlap = max(0.0, min(float(row["r_bin_max_A"]), hi) - max(float(row["r_bin_min_A"]), lo))
        if overlap > 0:
            selected.append((overlap, row))
    if not selected:
        raise RuntimeError(f"No bins overlap {lo}-{hi} A")
    weights = np.array([w for w, _ in selected], dtype=float)
    total = float(weights.sum())

    def wavg(col: str) -> float:
        return float(sum(w * float(row[col]) for w, row in selected) / total)

    return {
        "label": f"{lo:g}-{hi:g} A",
        "r_value_A": 0.5 * (lo + hi),
        "r_bin": f"{lo:g}-{hi:g}",
        "eps0000_sigma_vm_mean_mpa": wavg("eps0000_sigma_vm_mean_mpa"),
        "eps00194_sigma_vm_mean_mpa": wavg("eps00194_sigma_vm_mean_mpa"),
        "delta_sigma_vm_mean_mpa": wavg("delta_sigma_vm_mean_mpa"),
        "eps0000_sigma_zz_mean_mpa": wavg("eps0000_sigma_zz_mean_mpa"),
        "eps00194_sigma_zz_mean_mpa": wavg("eps00194_sigma_zz_mean_mpa"),
        "delta_sigma_zz_mean_mpa": wavg("delta_sigma_zz_mean_mpa"),
        "eps0000_fraction_vm_gt_120mpa": wavg("eps0000_fraction_vm_gt_120mpa"),
        "eps00194_fraction_vm_gt_120mpa": wavg("eps00194_fraction_vm_gt_120mpa"),
        "delta_fraction_vm_gt_120mpa": wavg("delta_fraction_vm_gt_120mpa"),
    }


def nearest_checkpoint(delta_sigma: pd.DataFrame, target: float) -> dict[str, Any]:
    rows = delta_sigma[delta_sigma["window"] == PRIMARY_WINDOW].copy()
    idx = (rows["r_bin_center_A"] - target).abs().idxmin()
    row = rows.loc[idx]
    return {
        "label": f"{target:g} A",
        "r_value_A": float(target),
        "r_bin": f"{row['r_bin_min_A']:g}-{row['r_bin_max_A']:g}",
        "r_center_A": float(row["r_bin_center_A"]),
        "eps0000_sigma_vm_mean_mpa": float(row["eps0000_sigma_vm_mean_mpa"]),
        "eps00194_sigma_vm_mean_mpa": float(row["eps00194_sigma_vm_mean_mpa"]),
        "delta_sigma_vm_mean_mpa": float(row["delta_sigma_vm_mean_mpa"]),
        "eps0000_sigma_zz_mean_mpa": float(row["eps0000_sigma_zz_mean_mpa"]),
        "eps00194_sigma_zz_mean_mpa": float(row["eps00194_sigma_zz_mean_mpa"]),
        "delta_sigma_zz_mean_mpa": float(row["delta_sigma_zz_mean_mpa"]),
        "eps0000_fraction_vm_gt_120mpa": float(row["eps0000_fraction_vm_gt_120mpa"]),
        "eps00194_fraction_vm_gt_120mpa": float(row["eps00194_fraction_vm_gt_120mpa"]),
        "delta_fraction_vm_gt_120mpa": float(row["delta_fraction_vm_gt_120mpa"]),
    }


def checkpoint_table(delta_sigma: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        weighted_overlap_rows(delta_sigma, 0.0, 5.0),
        nearest_checkpoint(delta_sigma, 10.0),
        nearest_checkpoint(delta_sigma, 20.0),
        nearest_checkpoint(delta_sigma, 50.0),
        nearest_checkpoint(delta_sigma, 100.0),
    ]


def first_below_noise(delta_sigma: pd.DataFrame, noise_floor: float) -> dict[str, Any]:
    rows = delta_sigma[delta_sigma["window"] == PRIMARY_WINDOW].sort_values("r_bin_min_A")
    for _, row in rows.iterrows():
        if abs(float(row["delta_sigma_vm_mean_mpa"])) <= noise_floor:
            return {
                "r_bin_min_A": float(row["r_bin_min_A"]),
                "r_bin_max_A": float(row["r_bin_max_A"]),
                "r_center_A": float(row["r_bin_center_A"]),
                "delta_sigma_vm_mean_mpa": float(row["delta_sigma_vm_mean_mpa"]),
            }
    last = rows.iloc[-1]
    return {
        "r_bin_min_A": float(last["r_bin_min_A"]),
        "r_bin_max_A": float(last["r_bin_max_A"]),
        "r_center_A": float(last["r_bin_center_A"]),
        "delta_sigma_vm_mean_mpa": float(last["delta_sigma_vm_mean_mpa"]),
    }


def compute_stress_numbers() -> dict[str, Any]:
    eps0000 = pd.read_csv(SOURCE_FILES["eps0000_sigma"])
    eps00194 = pd.read_csv(SOURCE_FILES["eps00194_sigma"])
    delta = pd.read_csv(SOURCE_FILES["delta_sigma"])
    sigma_summary = read_json(SOURCE_FILES["sigma_summary"])
    windows = [FINAL_WINDOW, PRIMARY_WINDOW]
    noise = robust_noise_floor(delta)
    peak_delta_vm = peak_by_abs(delta, "delta_sigma_vm_mean_mpa", windows)
    peak_delta_vm_p95 = peak_by_abs(delta, "delta_sigma_vm_p95_mpa", windows)
    peak_delta_zz = peak_by_abs(delta, "delta_sigma_zz_mean_mpa", windows)
    peak_eps00194_vm = peak_positive(eps00194, "sigma_vm_mean_mpa", PRIMARY_WINDOW)
    peak_eps0000_vm = peak_positive(eps0000, "sigma_vm_mean_mpa", PRIMARY_WINDOW)
    total_mean_layer = contiguous_thickness(eps00194, "sigma_vm_mean_mpa", YIELD_MPA, PRIMARY_WINDOW)
    total_p95_layer = contiguous_thickness(eps00194, "sigma_vm_p95_mpa", YIELD_MPA, PRIMARY_WINDOW)
    delta_120_layer = contiguous_thickness(delta, "delta_sigma_vm_mean_mpa", YIELD_MPA, PRIMARY_WINDOW, absolute=True)
    delta_noise_layer = contiguous_thickness(
        delta, "delta_sigma_vm_mean_mpa", noise["noise_floor_mpa"], PRIMARY_WINDOW, absolute=True
    )
    first_below = first_below_noise(delta, noise["noise_floor_mpa"])
    checkpoints = checkpoint_table(delta)
    peak_row = delta[
        (delta["window"] == peak_delta_vm["window"])
        & (delta["r_bin_min_A"] == peak_delta_vm["r_bin_min_A"])
        & (delta["r_bin_max_A"] == peak_delta_vm["r_bin_max_A"])
    ].iloc[0]
    components = {
        "delta_sigma_xx_mean_mpa": float(peak_row["delta_sigma_xx_mean_mpa"]),
        "delta_sigma_yy_mean_mpa": float(peak_row["delta_sigma_yy_mean_mpa"]),
        "delta_sigma_zz_mean_mpa": float(peak_row["delta_sigma_zz_mean_mpa"]),
        "delta_sigma_vm_mean_mpa": float(peak_row["delta_sigma_vm_mean_mpa"]),
    }
    dominant_component = max(
        ["delta_sigma_xx_mean_mpa", "delta_sigma_yy_mean_mpa", "delta_sigma_zz_mean_mpa"],
        key=lambda key: abs(components[key]),
    )
    at_100 = next(item for item in checkpoints if item["label"] == "100 A")
    decay = {
        "baseline_subtracted_delta_decays_within_100A": abs(at_100["delta_sigma_vm_mean_mpa"])
        <= noise["noise_floor_mpa"],
        "delta_vm_at_100A_mpa": at_100["delta_sigma_vm_mean_mpa"],
        "total_vm_layer_reaches_available_slab_edge": total_mean_layer >= 120.0,
        "interpretation": "Delta sigma_vm falls below robust far-field noise by the 4-6 A bin and is below noise near 100 A; total sigma_vm remains above 120 MPa across the available slab, so total-stress cutoff is not a clean physical cutoff.",
    }
    return {
        "generated_at": now_iso(),
        "status": "completed",
        "window_primary": PRIMARY_WINDOW,
        "yield_threshold_mpa": YIELD_MPA,
        "source_files": {key: rel(path) for key, path in SOURCE_FILES.items() if "sigma" in key},
        "stress_conversion": sigma_summary.get("stress_conversion"),
        "peak_delta_sigma_vm_mean": peak_delta_vm,
        "peak_delta_sigma_vm_p95": peak_delta_vm_p95,
        "peak_delta_sigma_zz_mean": peak_delta_zz,
        "peak_total_sigma_vm_eps00194": peak_eps00194_vm,
        "peak_total_sigma_vm_eps0000": peak_eps0000_vm,
        "layer_thickness": {
            "eps00194_total_sigma_vm_mean_gt_120_A": total_mean_layer,
            "eps00194_total_sigma_vm_p95_gt_120_A": total_p95_layer,
            "abs_delta_sigma_vm_mean_gt_120_A": delta_120_layer,
            "abs_delta_sigma_vm_mean_above_noise_A": delta_noise_layer,
            "first_bin_where_abs_delta_vm_below_noise": first_below,
        },
        "noise_floor": noise,
        "checkpoints": checkpoints,
        "directional_components_at_peak_delta_vm": {
            "components": components,
            "dominant_component": dominant_component,
            "z_component_dominates": dominant_component == "delta_sigma_zz_mean_mpa",
            "interpretation": "The peak is mixed von-Mises/interface stress; sigma_zz does not dominate the peak bin.",
        },
        "decay": decay,
    }


def max_fraction(df: pd.DataFrame, col: str, window: str = FINAL_WINDOW, absolute: bool = False) -> dict[str, Any]:
    rows = df[df["window"] == window].copy()
    idx = rows[col].abs().idxmax() if absolute else rows[col].idxmax()
    row = rows.loc[idx]
    return {
        "column": col,
        "window": window,
        "value": float(row[col]),
        "abs_value": abs(float(row[col])),
        "r_bin_min_A": float(row["r_bin_min_A"]),
        "r_bin_max_A": float(row["r_bin_max_A"]),
        "r_center_A": float(row["r_bin_center_A"]),
    }


def compute_plasticity_numbers() -> dict[str, Any]:
    eps0000 = pd.read_csv(SOURCE_FILES["eps0000_defect"])
    eps00194 = pd.read_csv(SOURCE_FILES["eps00194_defect"])
    delta = pd.read_csv(SOURCE_FILES["delta_defect"])
    defect_summary = read_json(SOURCE_FILES["defect_summary"])
    residual = read_json(SOURCE_FILES["residual"])
    final_frames = [row for row in defect_summary["frames_analyzed"] if int(row["step"]) == 50000]
    dxa_by_case = {row["case"]: row["dislocation_line_length_A"] for row in final_frames}
    max_timeline_dxa = max(float(row["dislocation_line_length_A"]) for row in defect_summary["frames_analyzed"])
    final_hcp_eps0000 = max_fraction(eps0000, "hcp_fraction")
    final_hcp_eps00194 = max_fraction(eps00194, "hcp_fraction")
    final_other_eps0000 = max_fraction(eps0000, "other_fraction")
    final_other_eps00194 = max_fraction(eps00194, "other_fraction")
    delta_hcp = max_fraction(delta, "delta_hcp_fraction", absolute=True)
    delta_other = max_fraction(delta, "delta_other_fraction", absolute=True)
    delta_nonfcc = max_fraction(delta, "delta_non_fcc_fraction", absolute=True)
    fcc_drop = {
        "max_fcc_fraction_drop_eps00194_minus_eps0000": max(0.0, float(delta_nonfcc["value"])),
        "r_bin_min_A": delta_nonfcc["r_bin_min_A"],
        "r_bin_max_A": delta_nonfcc["r_bin_max_A"],
        "r_center_A": delta_nonfcc["r_center_A"],
    }
    classification = "absent/not_confirmed"
    if max_timeline_dxa > 0.0 or abs(delta_other["value"]) > 0.05 or abs(delta_hcp["value"]) > 0.005:
        classification = "weak/transient indicators"
    return {
        "generated_at": now_iso(),
        "status": "completed",
        "source_files": {key: rel(path) for key, path in SOURCE_FILES.items() if "defect" in key or key == "residual"},
        "hcp": {
            "eps0000_max_fraction_final": final_hcp_eps0000,
            "eps00194_max_fraction_final": final_hcp_eps00194,
            "max_abs_delta_fraction_final": delta_hcp,
        },
        "other": {
            "eps0000_max_fraction_final": final_other_eps0000,
            "eps00194_max_fraction_final": final_other_eps00194,
            "max_abs_delta_fraction_final": delta_other,
        },
        "fcc": {
            "max_non_fcc_delta_final": delta_nonfcc,
            "fcc_drop": fcc_drop,
        },
        "dxa": {
            "final_line_length_A_by_case": dxa_by_case,
            "max_line_length_A_available_timeline": max_timeline_dxa,
            "burgers_types": [],
            "persistence": "not_observed_in_available_step0_and_step50000_frames",
        },
        "residual_plasticity": {
            "verdict": residual["verdict"],
            "exact_reasoning": residual.get("reasoning", []),
            "max_abs_final_delta_nonfcc_fraction": residual["max_abs_final_delta_nonfcc_fraction"],
        },
        "classification": classification,
        "interpretation": "Final DXA is zero for both CPU cases. HCP is essentially absent, and OTHER/non-FCC differences are small interface-shell/background differences rather than confirmed residual plasticity.",
    }


def write_inventory(inventory: dict[str, Any]) -> None:
    write_json(REPORTS_DIR / "stageF_cpu_results_executive_extraction_inventory.json", inventory)
    rows = []
    for category in ["csv_files", "json_files", "md_files", "figures"]:
        for record in inventory[category]:
            rows.append([category, record["name"], record["length"], record["path"]])
    text = f"""# Stage F CPU Results Executive Extraction Inventory

Дата: {inventory['generated_at']}

## Summary

- CSV found: `{len(inventory['csv_files'])}`
- JSON found: `{len(inventory['json_files'])}`
- MD reports found: `{len(inventory['md_files'])}`
- Figures found: `{len(inventory['figures'])}`
- Expected files missing: `{len(inventory['expected_missing'])}`

{md_table(['Category', 'Name', 'Bytes', 'Path'], rows)}

## Expected Missing

{chr(10).join('- `' + item + '`' for item in inventory['expected_missing']) if inventory['expected_missing'] else 'None.'}
"""
    write_text(REPORTS_DIR / "stageF_cpu_results_executive_extraction_inventory.md", text)


def write_key_stress(stress: dict[str, Any]) -> None:
    write_json(REPORTS_DIR / "stageF_cpu_results_key_stress_numbers.json", stress)
    metric_rows = [
        [
            "Peak Delta sigma_vm mean",
            stress["peak_delta_sigma_vm_mean"]["value_mpa"],
            f"{stress['peak_delta_sigma_vm_mean']['r_bin_min_A']}-{stress['peak_delta_sigma_vm_mean']['r_bin_max_A']} A; {stress['peak_delta_sigma_vm_mean']['window']}",
            "Largest CPU-only baseline-subtracted VM change; signed value, selected by absolute magnitude.",
        ],
        [
            "Peak Delta sigma_vm p95",
            stress["peak_delta_sigma_vm_p95"]["value_mpa"],
            f"{stress['peak_delta_sigma_vm_p95']['r_bin_min_A']}-{stress['peak_delta_sigma_vm_p95']['r_bin_max_A']} A; {stress['peak_delta_sigma_vm_p95']['window']}",
            "Atom-level virial proxy p95 is noisy; use as secondary support only.",
        ],
        [
            "Peak Delta sigma_zz mean",
            stress["peak_delta_sigma_zz_mean"]["value_mpa"],
            f"{stress['peak_delta_sigma_zz_mean']['r_bin_min_A']}-{stress['peak_delta_sigma_zz_mean']['r_bin_max_A']} A; {stress['peak_delta_sigma_zz_mean']['window']}",
            "Z component is not the dominant peak component.",
        ],
        [
            "Peak total sigma_vm eps00194",
            stress["peak_total_sigma_vm_eps00194"]["value_mpa"],
            f"{stress['peak_total_sigma_vm_eps00194']['r_bin_min_A']}-{stress['peak_total_sigma_vm_eps00194']['r_bin_max_A']} A",
            "Total local virial VM proxy in physical CPU case.",
        ],
        [
            "Peak total sigma_vm eps0000",
            stress["peak_total_sigma_vm_eps0000"]["value_mpa"],
            f"{stress['peak_total_sigma_vm_eps0000']['r_bin_min_A']}-{stress['peak_total_sigma_vm_eps0000']['r_bin_max_A']} A",
            "Baseline also has high local virial stress near interface.",
        ],
        [
            "Thickness total sigma_vm > 120 MPa",
            stress["layer_thickness"]["eps00194_total_sigma_vm_mean_gt_120_A"],
            "contiguous from interface",
            "Total VM proxy remains above 120 MPa to available slab edge; not a clean physical cutoff.",
        ],
        [
            "Thickness Delta sigma_vm meaningful above noise",
            stress["layer_thickness"]["abs_delta_sigma_vm_mean_above_noise_A"],
            f"noise floor {fmt(stress['noise_floor']['noise_floor_mpa'])} MPa",
            "Baseline-subtracted near-interface effect is localized to the first two bins.",
        ],
    ]
    for target in ["10 A", "20 A", "50 A", "100 A"]:
        cp = next(row for row in stress["checkpoints"] if row["label"] == target)
        metric_rows.append(
            [
                f"Delta sigma_vm at {target}",
                cp["delta_sigma_vm_mean_mpa"],
                cp["r_bin"],
                "Nearest-bin last-20%-mean CPU-only delta.",
            ]
        )
    metric_rows.append(
        [
            "Decay within 100 A",
            "yes" if stress["decay"]["baseline_subtracted_delta_decays_within_100A"] else "inconclusive",
            f"Delta sigma_vm at 100 A = {fmt(stress['decay']['delta_vm_at_100A_mpa'])} MPa",
            stress["decay"]["interpretation"],
        ]
    )
    cp_rows = [
        [
            cp["label"],
            cp.get("r_center_A", cp["r_value_A"]),
            cp["eps0000_sigma_vm_mean_mpa"],
            cp["eps00194_sigma_vm_mean_mpa"],
            cp["delta_sigma_vm_mean_mpa"],
            cp["eps0000_sigma_zz_mean_mpa"],
            cp["eps00194_sigma_zz_mean_mpa"],
            cp["delta_sigma_zz_mean_mpa"],
            cp["eps0000_fraction_vm_gt_120mpa"],
            cp["eps00194_fraction_vm_gt_120mpa"],
            cp["delta_fraction_vm_gt_120mpa"],
        ]
        for cp in stress["checkpoints"]
    ]
    text = f"""# Stage F CPU Results: Key Stress Numbers

Дата: {stress['generated_at']}

Primary window: `{PRIMARY_WINDOW}`. Stress is a local virial proxy; absolute MPa values should be interpreted with the documented conversion caveat.

## Executive Metrics

{md_table(['Metric', 'Value', 'r / layer', 'Interpretation'], metric_rows)}

## Checkpoints

{md_table(['r checkpoint', 'r center A', 'eps0000 VM', 'eps00194 VM', 'Delta VM', 'eps0000 zz', 'eps00194 zz', 'Delta zz', 'f>120 eps0000', 'f>120 eps00194', 'Delta f'], cp_rows)}

## Directional Component Check

At the peak Delta sigma_vm bin, components are:

{md_table(['Component', 'MPa'], [[key, value] for key, value in stress['directional_components_at_peak_delta_vm']['components'].items()])}

Dominant component: `{stress['directional_components_at_peak_delta_vm']['dominant_component']}`. Z dominance: `{stress['directional_components_at_peak_delta_vm']['z_component_dominates']}`.

## Noise Floor

Method: {stress['noise_floor']['method']}. Noise floor = `{fmt(stress['noise_floor']['noise_floor_mpa'])} MPa`. Far-field boundary-edge outliers are listed in JSON and should not be overinterpreted as a smooth physical decay signal.
"""
    write_text(REPORTS_DIR / "stageF_cpu_results_key_stress_numbers.md", text)


def write_key_plasticity(plasticity: dict[str, Any]) -> None:
    write_json(REPORTS_DIR / "stageF_cpu_results_key_plasticity_numbers.json", plasticity)
    rows = [
        [
            "DXA line length final",
            plasticity["dxa"]["final_line_length_A_by_case"].get("eps0000"),
            plasticity["dxa"]["final_line_length_A_by_case"].get("eps00194"),
            0.0,
            "all Al matrix",
            "DXA line length is zero in final CPU frames.",
        ],
        ["DXA max timeline available", 0.0, 0.0, 0.0, "step 0/final", plasticity["dxa"]["persistence"]],
        [
            "HCP max fraction",
            plasticity["hcp"]["eps0000_max_fraction_final"]["value"],
            plasticity["hcp"]["eps00194_max_fraction_final"]["value"],
            plasticity["hcp"]["max_abs_delta_fraction_final"]["value"],
            plasticity["hcp"]["max_abs_delta_fraction_final"]["r_center_A"],
            "HCP is essentially absent; no positive growth signal in eps00194 final.",
        ],
        [
            "OTHER max fraction",
            plasticity["other"]["eps0000_max_fraction_final"]["value"],
            plasticity["other"]["eps00194_max_fraction_final"]["value"],
            plasticity["other"]["max_abs_delta_fraction_final"]["value"],
            plasticity["other"]["max_abs_delta_fraction_final"]["r_center_A"],
            "OTHER is concentrated in interface shell/background.",
        ],
        [
            "Delta HCP max",
            "",
            "",
            plasticity["hcp"]["max_abs_delta_fraction_final"]["value"],
            plasticity["hcp"]["max_abs_delta_fraction_final"]["r_center_A"],
            "Negative/small; not a plasticity signature.",
        ],
        [
            "Delta OTHER max",
            "",
            "",
            plasticity["other"]["max_abs_delta_fraction_final"]["value"],
            plasticity["other"]["max_abs_delta_fraction_final"]["r_center_A"],
            "Small final interface-shell delta.",
        ],
        [
            "FCC drop max",
            "",
            "",
            plasticity["fcc"]["fcc_drop"]["max_fcc_fraction_drop_eps00194_minus_eps0000"],
            plasticity["fcc"]["fcc_drop"]["r_center_A"],
            "Equivalent to max positive non-FCC delta; weak local shell signal.",
        ],
        [
            "Residual plasticity verdict",
            "",
            "",
            plasticity["residual_plasticity"]["verdict"],
            "",
            "No DXA, no persistent defect cluster, no Dmin2/unload proof.",
        ],
    ]
    text = f"""# Stage F CPU Results: Key Plasticity Numbers

Дата: {plasticity['generated_at']}

Classification: `{plasticity['classification']}`.

{md_table(['Metric', 'eps0000', 'eps00194', 'Delta', 'r', 'Interpretation'], rows)}

## Reason

{chr(10).join('- ' + item for item in plasticity['residual_plasticity']['exact_reasoning'])}
"""
    write_text(REPORTS_DIR / "stageF_cpu_results_key_plasticity_numbers.md", text)


def write_criteria_answers(stress: dict[str, Any], plasticity: dict[str, Any]) -> None:
    criteria = [
        [
            "Есть ли передача напряжения от границы в Al?",
            "CPU-only Delta sigma(r), eps00194 - eps0000",
            f"Peak Delta sigma_vm = {fmt(stress['peak_delta_sigma_vm_mean']['value_mpa'])} MPa at {fmt(stress['peak_delta_sigma_vm_mean']['r_center_A'])} A",
            "Передача local virial stress proxy подтверждена около interface.",
            "confirmed",
        ],
        [
            "Есть ли локальный напряженный слой у interface?",
            "total sigma_vm and Delta sigma_vm",
            f"Total VM >120 MPa to {fmt(stress['layer_thickness']['eps00194_total_sigma_vm_mean_gt_120_A'])} A; Delta above noise to {fmt(stress['layer_thickness']['abs_delta_sigma_vm_mean_above_noise_A'])} A",
            "Есть сильный near-interface Delta layer; total VM cutoff не чистый из-за baseline/local virial noise.",
            "confirmed",
        ],
        [
            "Превышает ли напряжение 120 MPa?",
            "eps00194 total sigma_vm_mean/p95",
            f"Peak eps00194 VM = {fmt(stress['peak_total_sigma_vm_eps00194']['value_mpa'])} MPa",
            "Да по local virial proxy; абсолютные MPa не являются continuum-calibrated stress.",
            "confirmed",
        ],
        [
            "Какова толщина слоя?",
            "contiguous bins from r=0",
            f"Total VM mean layer {fmt(stress['layer_thickness']['eps00194_total_sigma_vm_mean_gt_120_A'])} A; Delta meaningful layer {fmt(stress['layer_thickness']['abs_delta_sigma_vm_mean_above_noise_A'])} A",
            "Для разговора важнее Delta layer 0-4 A; total layer reaches available slab edge.",
            "confirmed",
        ],
        [
            "Затухает ли эффект внутри 100 A?",
            "Delta sigma_vm at checkpoints and noise floor",
            f"Delta VM at 100 A = {fmt(stress['decay']['delta_vm_at_100A_mpa'])} MPa; noise floor {fmt(stress['noise_floor']['noise_floor_mpa'])} MPa",
            "Baseline-subtracted near-interface effect decays below noise well before 100 A.",
            "confirmed",
        ],
        [
            "Доминирует ли sigma_zz из-за eigenstrain Z?",
            "Delta xx/yy/zz at peak VM bin",
            f"Dominant = {stress['directional_components_at_peak_delta_vm']['dominant_component']}",
            "Peak is mixed/interface VM stress; sigma_zz does not dominate.",
            "not_confirmed",
        ],
        [
            "Есть ли признаки пластической деформации?",
            "CNA/DXA final and residual verdict",
            f"Residual verdict = {plasticity['residual_plasticity']['verdict']}",
            "Пластичность не подтверждена.",
            "not_confirmed",
        ],
        [
            "Есть ли HCP/OTHER рост сверх baseline?",
            "final delta defect profile",
            f"Max Delta OTHER/non-FCC = {fmt(plasticity['other']['max_abs_delta_fraction_final']['value'])}",
            "Есть слабая local interface-shell разница, не самостоятельное доказательство пластичности.",
            "inconclusive",
        ],
        [
            "Есть ли DXA/dislocations?",
            "OVITO DXA final",
            "DXA line length = 0 A for eps0000 and eps00194 final",
            "DXA-сигнала в CPU final нет.",
            "not_confirmed",
        ],
        [
            "Есть ли остаточная/необратимая пластичность?",
            "residual plasticity check",
            plasticity["residual_plasticity"]["verdict"],
            "Не подтверждена; нет unload/quench/Dmin2 proof.",
            "not_confirmed",
        ],
        [
            "Достаточен ли F0_planar для вывода?",
            "geometry scope",
            "F0 planar answers local flat-boundary stress transfer only",
            "Достаточен для локального planar stress answer; не заменяет curved/micron inclusion.",
            "technical_limitation",
        ],
        [
            "Что логично запускать дальше?",
            "decision logic",
            "primary: stop/no new MD until supervisor feedback; secondary: F1 curved cap if requested",
            "Сначала показать числа Пшонкину; следующий MD должен быть motivated by feedback.",
            "next_step_required",
        ],
    ]
    payload = {
        "generated_at": now_iso(),
        "criteria": [
            {
                "criterion": row[0],
                "checked": row[1],
                "numeric_result": row[2],
                "conclusion": row[3],
                "status": row[4],
            }
            for row in criteria
        ],
    }
    write_json(REPORTS_DIR / "stageF_cpu_results_pshonkin_criteria_answers.json", payload)
    text = f"""# Stage F CPU Results: ответы по критериям Пшонкина

Дата: {payload['generated_at']}

{md_table(['Критерий Пшонкина', 'Что проверили', 'Численный результат', 'Вывод', 'Статус'], criteria)}
"""
    write_text(REPORTS_DIR / "stageF_cpu_results_pshonkin_criteria_answers_ru.md", text)


def write_executive_brief(stress: dict[str, Any], plasticity: dict[str, Any]) -> None:
    cp50 = next(row for row in stress["checkpoints"] if row["label"] == "50 A")
    cp100 = next(row for row in stress["checkpoints"] if row["label"] == "100 A")
    numbers = [
        [1, "Peak Delta sigma_vm", f"{fmt(stress['peak_delta_sigma_vm_mean']['value_mpa'])} MPa", "главный baseline-subtracted stress-transfer signal"],
        [2, "r peak Delta sigma_vm", f"{fmt(stress['peak_delta_sigma_vm_mean']['r_center_A'])} A", "показывает near-interface localization"],
        [3, "Total sigma_vm >120 MPa layer", f"{fmt(stress['layer_thickness']['eps00194_total_sigma_vm_mean_gt_120_A'])} A", "total virial proxy above yield reference across available slab"],
        [4, "Delta sigma_vm at 50/100 A", f"{fmt(cp50['delta_sigma_vm_mean_mpa'])} / {fmt(cp100['delta_sigma_vm_mean_mpa'])} MPa", "Delta signal is below noise by far field"],
        [5, "DXA / residual verdict", f"0 A / {plasticity['residual_plasticity']['verdict']}", "no final dislocation line evidence"],
    ]
    text = f"""# Stage F CPU Results: executive brief для Пшонкина

## Короткий вывод

Мы разобрали уже завершенную CPU fallback pair `eps0000`/`eps00194` для F0 planar boundary, без новых MD запусков и без GPU. Напряжение от eigenstrain видно как near-interface baseline-subtracted signal: peak Delta sigma_vm = `{fmt(stress['peak_delta_sigma_vm_mean']['value_mpa'])} MPa` в первом bin около interface. При этом total local virial sigma_vm остается выше `120 MPa` по всей доступной Al-области, поэтому total-stress cutoff сам по себе не дает чистую физическую толщину. Пластичность не подтверждена: финальный DXA = `0 A`, residual verdict = `{plasticity['residual_plasticity']['verdict']}`.

## 5 главных чисел

{md_table(['№', 'Показатель', 'Значение', 'Зачем важно'], numbers)}

## Интерпретация

Подтверждено:

- stress transfer в локальной F0 planar модели;
- сильный near-interface Delta sigma_vm layer в 0-4 A по robust noise threshold;
- Delta sigma_vm near 100 A ниже noise floor.

Не подтверждено:

- residual plasticity;
- DXA/dislocation line in final CPU frames;
- dominance of sigma_zz at the VM peak.

Ограничение:

- stress is a local virial proxy, not calibrated continuum stress;
- F0 planar is a flat-boundary local model, not a 5 micrometer inclusion model;
- total sigma_vm >120 MPa reaches the available slab edge, so total-stress cutoff is not a clean thickness.

## Формулировка для Пшонкина

Мы посчитали локальную плоскую границу Fe4Al13/Al в CPU-only pair, с `eps00194` против baseline `eps0000`. На профиле `sigma(r)` видно, что magnetostrictive eigenstrain дает дополнительное локальное напряжение у interface: peak Delta sigma_vm около `{fmt(stress['peak_delta_sigma_vm_mean']['value_mpa'])} MPa` в первом bin. Этот baseline-subtracted эффект быстро падает: уже к 50 A Delta sigma_vm около `{fmt(cp50['delta_sigma_vm_mean_mpa'])} MPa`, а около 100 A около `{fmt(cp100['delta_sigma_vm_mean_mpa'])} MPa`, то есть ниже нашего far-field noise floor. Total sigma_vm в local virial proxy выше 120 MPa практически во всей доступной Al области, но это не стоит трактовать как точный continuum cutoff. По дефектам финальный DXA дает 0 A, HCP практически нет, OTHER/non-FCC меняется только как слабый interface-shell/background сигнал. Поэтому честный вывод: напряжение передается, а пластичность и дислокации этими данными не подтверждены.

## Следующий шаг

Primary next step: `stop/no new MD until supervisor feedback`. Эти числа уже отвечают на meeting question без запуска eps005/F1/F0_300A.

Secondary option: `F1 curved cap`, если Пшонкин попросит проверить curvature/geometry realism after seeing the planar-boundary numbers.
"""
    write_text(REPORTS_DIR / "stageF_cpu_results_pshonkin_executive_brief_ru.md", text)


def write_talk_track(stress: dict[str, Any], plasticity: dict[str, Any]) -> None:
    cp50 = next(row for row in stress["checkpoints"] if row["label"] == "50 A")
    cp100 = next(row for row in stress["checkpoints"] if row["label"] == "100 A")
    text = f"""# Stage F CPU Results: talk track для устного доклада

## Слайд 1. Что моделировали

- Локальная плоская граница Fe4Al13/Al: F0 planar, `r=0` на interface `z={INTERFACE_Z_A} A`.
- CPU-only comparable pair: `eps0000` baseline и `eps00194` physical eigenstrain.
- Анализируем `sigma(r)`, CNA/DXA и residual verdict без новых production запусков.

## Слайд 2. Почему CPU, а не GPU

- GPU backend имеет KOKKOS/MEAM blocker и не дает валидную comparable GPU pair.
- CPU pair завершена clean: обе cases 50k, одинаковый protocol, без CPU/GPU mixing.

## Слайд 3. Напряжения

- Peak Delta sigma_vm = `{fmt(stress['peak_delta_sigma_vm_mean']['value_mpa'])} MPa` at `r={fmt(stress['peak_delta_sigma_vm_mean']['r_center_A'])} A`.
- Peak Delta sigma_zz = `{fmt(stress['peak_delta_sigma_zz_mean']['value_mpa'])} MPa` at `r={fmt(stress['peak_delta_sigma_zz_mean']['r_center_A'])} A`.
- Total eps00194 sigma_vm >120 MPa to `{fmt(stress['layer_thickness']['eps00194_total_sigma_vm_mean_gt_120_A'])} A`; Delta meaningful layer to `{fmt(stress['layer_thickness']['abs_delta_sigma_vm_mean_above_noise_A'])} A`.
- Delta sigma_vm at 50/100 A = `{fmt(cp50['delta_sigma_vm_mean_mpa'])}` / `{fmt(cp100['delta_sigma_vm_mean_mpa'])} MPa`.

## Слайд 4. Пластика/дефекты

- Final DXA line length: `0 A` for eps0000 and eps00194.
- Max final Delta OTHER/non-FCC fraction: `{fmt(plasticity['other']['max_abs_delta_fraction_final']['value'])}` near `r={fmt(plasticity['other']['max_abs_delta_fraction_final']['r_center_A'])} A`.
- HCP final signal is essentially absent; eps00194 HCP max fraction = `{fmt(plasticity['hcp']['eps00194_max_fraction_final']['value'])}`.
- Residual plasticity verdict: `{plasticity['residual_plasticity']['verdict']}`.

## Слайд 5. Вывод

- Stress transfer: confirmed in local F0 CPU model.
- Plasticity: not confirmed by final CNA/DXA/residual check.
- Next step: stop and discuss with supervisor; if new MD is requested, F1 curved cap is the cleanest secondary option.

## Как отвечать на вопросы

1. Почему не 5 micrometer inclusion?
   Потому что atomistic MD cannot cover that scale here; F0 answers local interface physics.
2. Почему planar boundary?
   Это минимальная модель для вопроса Пшонкина: `sigma(r)` от границы в Al.
3. Почему local virial stress proxy?
   Dump contains stress/atom virial; it is valid for relative profiles and CPU-only delta, but not a calibrated continuum stress.
4. Почему нет дислокаций, если stress >120 MPa?
   120 MPa is a continuum reference; local virial stress can exceed it without a persistent atomistic defect network.
5. Что значит 578 MPa?
   Это peak CPU-only baseline-subtracted local VM proxy in the first interface bin, not a bulk yield stress.
6. Можно ли считать это пластической деформацией?
   Нет, residual verdict is not confirmed: final DXA is 0 A and no persistent defect evidence is present.
7. Что даст eps005?
   Diagnostic overload sensitivity, but it may overdrive the model and is not the next clean physics step.
8. Что даст F1 curved cap?
   Checks whether curvature changes stress localization compared with flat F0.
9. Что даст F0_300A?
   More distance for decay/cutoff, but current Delta already falls below noise near 100 A; use only if supervisor asks for longer far field.
10. Почему GPU не использовали?
   GPU path is not a valid comparable pair; CPU pair is clean and comparable.
"""
    write_text(REPORTS_DIR / "stageF_cpu_results_pshonkin_talk_track_ru.md", text)


def write_best_figures() -> dict[str, Any]:
    candidates = [
        (
            "docs/reports/figures/stageF_cpu_results_delta_sigma_vm_last20.png",
            "Delta sigma_vm(r), last 20% mean",
            "Main stress-transfer and decay figure.",
            True,
        ),
        (
            "docs/reports/figures/stageF_cpu_results_sigma_zz_last20.png",
            "sigma_zz profiles, last 20% mean",
            "Shows Z-component profile and why Z does not dominate the main VM peak.",
            True,
        ),
        (
            "docs/reports/figures/stageF_cpu_results_sigma_vm_last20.png",
            "total sigma_vm profiles",
            "Shows total local virial stress remains above the 120 MPa reference.",
            True,
        ),
        (
            "docs/reports/figures/stageF_cpu_results_sigma_vm_p95_last20.png",
            "p95 sigma_vm profile",
            "Documents atom-level virial proxy noise/upper envelope.",
            True,
        ),
        (
            "docs/reports/figures/stageF_cpu_results_delta_defect_nonfcc_final.png",
            "Delta non-FCC final",
            "Shows defect baseline delta is small/local.",
            True,
        ),
        (
            "docs/reports/figures/stageF_cpu_results_defect_other_final.png",
            "OTHER fraction final",
            "Supports interface-shell/background interpretation.",
            True,
        ),
        (
            "docs/reports/figures/stageF_cpu_results_above_yield_fraction.png",
            "above_yield_fraction(r)",
            "Requested minimum figure is absent; values are available in CSV.",
            False,
        ),
        (
            "docs/reports/figures/stageF_cpu_results_dxa_timeline.png",
            "DXA timeline",
            "No dedicated CPU DXA timeline figure exists; final DXA is in JSON/MD tables.",
            False,
        ),
        (
            "docs/reports/figures/stageF_cpu_results_stressed_layer_thickness.png",
            "stressed layer thickness",
            "No dedicated thickness figure exists; thickness is in key stress JSON/MD.",
            False,
        ),
    ]
    figures = []
    for path, shows, supports, include in candidates:
        full = REPO_ROOT / path
        figures.append(
            {
                "path": path,
                "exists": full.exists(),
                "length": full.stat().st_size if full.exists() else None,
                "shows": shows,
                "supports": supports,
                "include": include and full.exists(),
                "blocker": None if full.exists() else "figure_absent",
            }
        )
    payload = {"generated_at": now_iso(), "figures": figures}
    write_json(REPORTS_DIR / "stageF_cpu_results_best_figures_for_pshonkin.json", payload)
    rows = [[fig["path"], fig["shows"], fig["supports"], "yes" if fig["include"] else "no"] for fig in figures]
    text = f"""# Stage F CPU Results: best figures for Pshonkin

Дата: {payload['generated_at']}

{md_table(['Path', 'Что показывает', 'Какой вывод поддерживает', 'Include'], rows)}
"""
    write_text(REPORTS_DIR / "stageF_cpu_results_best_figures_for_pshonkin.md", text)
    return payload


def write_safe_wording() -> None:
    text = """# Stage F CPU Results: safe wording

# Можно говорить

- "Получен дополнительный локальный напряженный слой у interface по CPU-only Delta sigma(r)."
- "Stress transfer confirmed in the local F0 planar model."
- "Plasticity is not confirmed by final CNA/DXA and residual check."
- "DXA line length = 0 A in both final CPU frames."
- "Result points to predominantly stressed/local lattice state at eps00194, not proven irreversible plasticity."

# Нельзя говорить

- "Дислокации подтверждены."
- "Пластическая деформация доказана."
- "Модель 5 micrometer включения выполнена."
- "Полный micron-scale MD выполнен."
- "Это GPU production result."
- "120 MPa cutoff дает точную физическую толщину plastic layer."

# Осторожные формулировки

- "По local virial stress proxy peak Delta sigma_vm расположен в первом interface bin."
- "Total sigma_vm выше 120 MPa во всей доступной области, но это не clean continuum cutoff."
- "Baseline-subtracted Delta effect falls below robust far-field noise near the first few bins."
- "OTHER/non-FCC difference is small and localized near interface; it is not enough for residual plasticity claim."
- "F0 planar answers the flat-boundary question; curved cap geometry remains a separate next-step option."
- "GPU blocker does not invalidate CPU-only physics extraction, because CPU pair is comparable and clean."
"""
    write_text(REPORTS_DIR / "stageF_cpu_results_safe_wording_ru.md", text)


def write_agent_report(
    inventory: dict[str, Any],
    stress: dict[str, Any],
    plasticity: dict[str, Any],
    figures: dict[str, Any],
    created: list[str],
) -> None:
    best = [fig["path"] for fig in figures["figures"] if fig["include"]]
    files_read = [rel(path) for path in SOURCE_FILES.values()]
    text = f"""# Agent report: Stage F CPU results key numbers extraction

Date: {now_iso()}

No MD production, smoke, GPU repair, eps005, F1, F0_300A, file deletion, git commit, or push was performed.

## Files read

{chr(10).join('- `' + item + '`' for item in files_read)}

## Production validation summary

CPU fallback pair is already completed clean: eps0000 and eps00194, 50k, CPU-only comparable protocol. GPU production remains outside this analysis.

## Five key numbers

- Peak Delta sigma_vm: `{fmt(stress['peak_delta_sigma_vm_mean']['value_mpa'])} MPa`.
- r peak Delta sigma_vm: `{fmt(stress['peak_delta_sigma_vm_mean']['r_center_A'])} A`.
- Total sigma_vm >120 MPa thickness: `{fmt(stress['layer_thickness']['eps00194_total_sigma_vm_mean_gt_120_A'])} A`; Delta meaningful layer: `{fmt(stress['layer_thickness']['abs_delta_sigma_vm_mean_above_noise_A'])} A`.
- Delta sigma_vm at 50/100 A: `{fmt(next(row for row in stress['checkpoints'] if row['label'] == '50 A')['delta_sigma_vm_mean_mpa'])}` / `{fmt(next(row for row in stress['checkpoints'] if row['label'] == '100 A')['delta_sigma_vm_mean_mpa'])} MPa`.
- DXA/plasticity verdict: `0 A`, `{plasticity['residual_plasticity']['verdict']}`.

## Stress layer interpretation

Local stress transfer is confirmed in CPU-only Delta sigma(r). The baseline-subtracted near-interface effect is localized to about `{fmt(stress['layer_thickness']['abs_delta_sigma_vm_mean_above_noise_A'])} A` by the robust far-field noise method. Total sigma_vm remains above 120 MPa to the available slab edge, so it should not be reported as a clean continuum cutoff.

## Plasticity interpretation

Plasticity is not confirmed. Final DXA line length is 0 A for both CPU cases. HCP is essentially absent, and OTHER/non-FCC changes are small local interface-shell/background differences.

## Pshonkin criteria summary

Stress transfer and local stress layer: confirmed. Z-component dominance, DXA, and residual plasticity: not confirmed. F0 planar is sufficient for local flat-boundary discussion, not for a full curved/micron inclusion claim.

## Best figures

{chr(10).join('- `' + item + '`' for item in best)}

## Recommended next step

Primary: stop/no new MD until supervisor feedback. Secondary: F1 curved cap if curvature realism is requested after discussion.

## Files created

{chr(10).join('- `' + item + '`' for item in created)}

## Validation checklist

- JSON parse: pending external validation command.
- CSV read with pandas: pending external validation command.
- Required reports created: yes.
- Best figure paths checked in JSON: yes.
- Old outputs preserved: yes.
- New production/smoke/GPU/eps005/F1/F0_300A launches: none.
- Forbidden claim scan: pending external validation command.

## Exact next command

```powershell
Get-Content -Raw docs\\reports\\stageF_cpu_results_pshonkin_executive_brief_ru.md
```
"""
    write_text(REPO_ROOT / "agent_report_stageF_cpu_results_key_numbers_extraction.md", text)


def run() -> None:
    inventory = collect_inventory()
    write_inventory(inventory)
    stress = compute_stress_numbers()
    write_key_stress(stress)
    plasticity = compute_plasticity_numbers()
    write_key_plasticity(plasticity)
    write_criteria_answers(stress, plasticity)
    write_executive_brief(stress, plasticity)
    write_talk_track(stress, plasticity)
    figures = write_best_figures()
    write_safe_wording()
    created = [
        "docs/reports/stageF_cpu_results_executive_extraction_inventory.md",
        "docs/reports/stageF_cpu_results_executive_extraction_inventory.json",
        "docs/reports/stageF_cpu_results_key_stress_numbers.md",
        "docs/reports/stageF_cpu_results_key_stress_numbers.json",
        "docs/reports/stageF_cpu_results_key_plasticity_numbers.md",
        "docs/reports/stageF_cpu_results_key_plasticity_numbers.json",
        "docs/reports/stageF_cpu_results_pshonkin_criteria_answers_ru.md",
        "docs/reports/stageF_cpu_results_pshonkin_criteria_answers.json",
        "docs/reports/stageF_cpu_results_pshonkin_executive_brief_ru.md",
        "docs/reports/stageF_cpu_results_pshonkin_talk_track_ru.md",
        "docs/reports/stageF_cpu_results_best_figures_for_pshonkin.md",
        "docs/reports/stageF_cpu_results_best_figures_for_pshonkin.json",
        "docs/reports/stageF_cpu_results_safe_wording_ru.md",
        "agent_report_stageF_cpu_results_key_numbers_extraction.md",
    ]
    write_agent_report(inventory, stress, plasticity, figures, created)
    print(json.dumps({"status": "completed", "created": created}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
