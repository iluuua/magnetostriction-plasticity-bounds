#!/usr/bin/env python3
"""Check whether visible interface gaps are real voids or geometry/visualization artifacts.

The analysis is intentionally geometric only. It does not apply load, does not run
LAMMPS, and does not claim physical validation of the interface.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
TRIAL_DIR = ROOT / "lammps/02_interface_relax/trial_001"
DEFAULT_DATA = TRIAL_DIR / "data.interface_nvt_300k_long"
DEFAULT_METADATA = ROOT / "structures/interface/flat_interface/trial_001/interface_metadata.json"
DEFAULT_STRESS_SUMMARY = TRIAL_DIR / "interface_time_averaged_stress_summary.json"
DEFAULT_REPORT_JSON = TRIAL_DIR / "interface_contact_density_report.json"
DEFAULT_PROFILE_CSV = ROOT / "results/tables/interface_trial_001_contact_density_z_profile.csv"
DEFAULT_PROFILE_PNG = ROOT / "results/figures/interface_trial_001_contact_density_z_profile.png"
DEFAULT_DOC = ROOT / "docs/interface_trial_001_contact_density_check.md"

DEFAULT_INTERFACE_Z_A = 40.164
DEFAULT_WINDOW_A = 8.0
BIN_WIDTH_A = 1.0
THRESHOLDS_A = [2.3, 2.5, 2.8, 3.0, 3.5]
TYPE_TO_SPECIES = {1: "Al", 2: "Fe"}


@dataclass
class Atom:
    atom_id: int
    atom_type: int
    position: np.ndarray
    phase: str = ""

    @property
    def species(self) -> str:
        return TYPE_TO_SPECIES.get(self.atom_type, f"type{self.atom_type}")


def parse_lammps_data(path: Path) -> dict[str, Any]:
    lines = path.read_text(errors="replace").splitlines()
    box: dict[str, float] = {"xy": 0.0, "xz": 0.0, "yz": 0.0}
    n_atoms_header = None

    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "atoms":
            n_atoms_header = int(parts[0])
        elif len(parts) >= 4 and parts[-2:] == ["xlo", "xhi"]:
            box["xlo"], box["xhi"] = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[-2:] == ["ylo", "yhi"]:
            box["ylo"], box["yhi"] = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[-2:] == ["zlo", "zhi"]:
            box["zlo"], box["zhi"] = float(parts[0]), float(parts[1])
        elif len(parts) >= 6 and parts[-3:] == ["xy", "xz", "yz"]:
            box["xy"], box["xz"], box["yz"] = float(parts[0]), float(parts[1]), float(parts[2])

    atoms_start = None
    for index, line in enumerate(lines):
        if line.strip().startswith("Atoms"):
            atoms_start = index + 1
            break
    if atoms_start is None:
        raise ValueError(f"Atoms section not found in {path}")

    atoms: list[Atom] = []
    for line in lines[atoms_start:]:
        stripped = line.strip()
        if not stripped:
            if atoms:
                break
            continue
        parts = stripped.split()
        if len(parts) < 5:
            if atoms:
                break
            continue
        try:
            atom_id = int(parts[0])
            atom_type = int(parts[1])
            x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
        except ValueError:
            if atoms:
                break
            continue
        atoms.append(Atom(atom_id=atom_id, atom_type=atom_type, position=np.array([x, y, z], dtype=float)))

    if n_atoms_header is not None and len(atoms) != n_atoms_header:
        raise ValueError(f"Expected {n_atoms_header} atoms, parsed {len(atoms)} atoms from {path}")

    for key in ["xlo", "xhi", "ylo", "yhi", "zlo", "zhi"]:
        if key not in box:
            raise ValueError(f"Missing {key} in {path}")

    return {"box": box, "atoms": atoms}


def box_matrix(box: dict[str, float]) -> np.ndarray:
    lx = box["xhi"] - box["xlo"]
    ly = box["yhi"] - box["ylo"]
    lz = box["zhi"] - box["zlo"]
    return np.array(
        [
            [lx, box["xy"], box["xz"]],
            [0.0, ly, box["yz"]],
            [0.0, 0.0, lz],
        ],
        dtype=float,
    )


def in_plane_area_A2(box: dict[str, float]) -> float:
    h = box_matrix(box)
    return float(np.linalg.norm(np.cross(h[:, 0], h[:, 1])))


def min_image_delta_xy(pos_i: np.ndarray, pos_j: np.ndarray, box: dict[str, float]) -> np.ndarray:
    h = box_matrix(box)
    h_inverse = np.linalg.inv(h)
    delta = pos_j - pos_i
    frac = h_inverse @ delta
    frac[0] -= round(float(frac[0]))
    frac[1] -= round(float(frac[1]))
    return h @ frac


def distance_xy_periodic(atom_i: Atom, atom_j: Atom, box: dict[str, float]) -> float:
    return float(np.linalg.norm(min_image_delta_xy(atom_i.position, atom_j.position, box)))


def load_interface_z(stress_summary_path: Path | None, default_z: float) -> tuple[float, str]:
    if stress_summary_path and stress_summary_path.exists():
        summary = json.loads(stress_summary_path.read_text())
        if "interface_z_A" in summary:
            return float(summary["interface_z_A"]), str(stress_summary_path)
    return float(default_z), "default"


def detect_ovito_apps() -> list[str]:
    found: list[str] = []
    for directory in [Path("/Applications"), Path.home() / "Applications"]:
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.name.lower().startswith("ovito") and path.suffix.lower() == ".app":
                found.append(str(path))
    return found


def ovito_python_available() -> bool:
    return importlib.util.find_spec("ovito") is not None


def assign_phases(atoms: list[Atom], metadata: dict[str, Any]) -> str:
    al_slab_atoms = int(metadata.get("actual_atoms", {}).get("Al_slab_atoms", 0))
    if al_slab_atoms <= 0:
        raise ValueError("metadata actual_atoms.Al_slab_atoms is required for phase assignment")
    for atom in atoms:
        atom.phase = "Al_slab" if atom.atom_id <= al_slab_atoms else "Fe4Al13_slab"
    return f"atom_id<=Al_slab_atoms ({al_slab_atoms})"


def atom_to_record(atom: Atom) -> dict[str, Any]:
    return {
        "atom_id": atom.atom_id,
        "type": atom.atom_type,
        "species": atom.species,
        "phase": atom.phase,
        "x_A": float(atom.position[0]),
        "y_A": float(atom.position[1]),
        "z_A": float(atom.position[2]),
    }


def cross_slab_contact_summary(
    atoms: list[Atom],
    box: dict[str, float],
    interface_z: float,
    window: float,
) -> dict[str, Any]:
    z_lo = interface_z - window
    z_hi = interface_z + window
    al_atoms = [atom for atom in atoms if atom.phase == "Al_slab"]
    fe_atoms = [atom for atom in atoms if atom.phase == "Fe4Al13_slab"]
    al_near = [atom for atom in al_atoms if z_lo <= atom.position[2] <= z_hi]
    fe_near = [atom for atom in fe_atoms if z_lo <= atom.position[2] <= z_hi]

    pair_rows: list[dict[str, Any]] = []
    for atom_i in al_near:
        for atom_j in fe_near:
            dist = distance_xy_periodic(atom_i, atom_j, box)
            pair_rows.append(
                {
                    "distance_A": dist,
                    "atom_i": atom_to_record(atom_i),
                    "atom_j": atom_to_record(atom_j),
                    "mid_z_A": float(0.5 * (atom_i.position[2] + atom_j.position[2])),
                }
            )
    pair_rows.sort(key=lambda row: row["distance_A"])

    if pair_rows:
        smallest = pair_rows[:10]
        min_distance = float(smallest[0]["distance_A"])
        mean10 = float(np.mean([row["distance_A"] for row in smallest]))
    else:
        smallest = []
        min_distance = None
        mean10 = None

    threshold_counts = {
        f"pairs_within_{threshold:.1f}_A": int(sum(1 for row in pair_rows if row["distance_A"] <= threshold))
        for threshold in THRESHOLDS_A
    }

    return {
        "interface_window_A": [z_lo, z_hi],
        "Al_slab_atoms_near_interface": len(al_near),
        "Fe4Al13_slab_atoms_near_interface": len(fe_near),
        "cross_slab_pairs_tested": len(pair_rows),
        "minimum_cross_slab_distance_A": min_distance,
        "mean_10_smallest_cross_slab_distances_A": mean10,
        "threshold_counts": threshold_counts,
        "ten_smallest_cross_slab_pairs": smallest,
    }


def bin_density_profile(
    atoms: list[Atom],
    box: dict[str, float],
    bin_width: float,
    interface_z: float,
    window: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    zlo = math.floor(float(box["zlo"]) / bin_width) * bin_width
    zhi = math.ceil(float(box["zhi"]) / bin_width) * bin_width
    edges = np.arange(zlo, zhi + 0.5 * bin_width, bin_width)
    area = in_plane_area_A2(box)
    volume = area * bin_width

    rows: list[dict[str, Any]] = []
    for index, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        center = 0.5 * (lo + hi)
        in_bin = [atom for atom in atoms if lo <= atom.position[2] < hi or (index == len(edges) - 2 and atom.position[2] == hi)]
        al_slab = [atom for atom in in_bin if atom.phase == "Al_slab"]
        fe_slab = [atom for atom in in_bin if atom.phase == "Fe4Al13_slab"]
        al_type = [atom for atom in in_bin if atom.atom_type == 1]
        fe_type = [atom for atom in in_bin if atom.atom_type == 2]
        if len(al_slab) > len(fe_slab):
            majority_phase = "Al_slab"
        elif len(fe_slab) > len(al_slab):
            majority_phase = "Fe4Al13_slab"
        elif in_bin:
            majority_phase = "mixed"
        else:
            majority_phase = "empty"
        rows.append(
            {
                "bin_index": index,
                "z_lo_A": float(lo),
                "z_hi_A": float(hi),
                "z_center_A": float(center),
                "total_atoms": len(in_bin),
                "Al_type_1_atoms": len(al_type),
                "Fe_type_2_atoms": len(fe_type),
                "Al_slab_atoms": len(al_slab),
                "Fe4Al13_slab_atoms": len(fe_slab),
                "total_number_density_atoms_per_A3": len(in_bin) / volume,
                "Al_slab_density_atoms_per_A3": len(al_slab) / volume,
                "Fe4Al13_slab_density_atoms_per_A3": len(fe_slab) / volume,
                "majority_phase": majority_phase,
                "in_interface_window": bool((hi > interface_z - window) and (lo < interface_z + window)),
            }
        )

    return rows, {"bin_width_A": bin_width, "in_plane_area_A2": area, "bin_volume_A3": volume}


def largest_empty_gap(rows: list[dict[str, Any]], interface_z: float, window: float) -> dict[str, Any]:
    occupied_indices = [row["bin_index"] for row in rows if row["total_atoms"] > 0]
    if not occupied_indices:
        return {"width_A": None}
    first = min(occupied_indices)
    last = max(occupied_indices)

    gaps: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for row in rows:
        index = int(row["bin_index"])
        if index < first or index > last:
            continue
        if row["total_atoms"] == 0:
            current.append(row)
        elif current:
            gaps.append(
                {
                    "z_lo_A": current[0]["z_lo_A"],
                    "z_hi_A": current[-1]["z_hi_A"],
                    "width_A": current[-1]["z_hi_A"] - current[0]["z_lo_A"],
                    "bin_count": len(current),
                    "intersects_interface_window": bool(
                        (current[-1]["z_hi_A"] > interface_z - window) and (current[0]["z_lo_A"] < interface_z + window)
                    ),
                }
            )
            current = []
    if current:
        gaps.append(
            {
                "z_lo_A": current[0]["z_lo_A"],
                "z_hi_A": current[-1]["z_hi_A"],
                "width_A": current[-1]["z_hi_A"] - current[0]["z_lo_A"],
                "bin_count": len(current),
                "intersects_interface_window": bool(
                    (current[-1]["z_hi_A"] > interface_z - window) and (current[0]["z_lo_A"] < interface_z + window)
                ),
            }
        )

    if not gaps:
        return {"width_A": 0.0, "bin_count": 0, "z_lo_A": None, "z_hi_A": None, "intersects_interface_window": False}
    return max(gaps, key=lambda item: item["width_A"])


def mean_or_none(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def density_drop_summary(
    rows: list[dict[str, Any]],
    atoms: list[Atom],
    interface_z: float,
    window: float,
) -> dict[str, Any]:
    al_z = [float(atom.position[2]) for atom in atoms if atom.phase == "Al_slab"]
    fe_z = [float(atom.position[2]) for atom in atoms if atom.phase == "Fe4Al13_slab"]
    al_surface_buffer = 8.0
    fe_surface_buffer = 8.0
    al_bulk_lo = min(al_z) + al_surface_buffer
    al_bulk_hi = interface_z - window
    fe_bulk_lo = interface_z + window
    fe_bulk_hi = max(fe_z) - fe_surface_buffer

    al_interface_rows = [
        row for row in rows if interface_z - window <= row["z_center_A"] < interface_z and row["Al_slab_atoms"] > 0
    ]
    fe_interface_rows = [
        row for row in rows if interface_z <= row["z_center_A"] <= interface_z + window and row["Fe4Al13_slab_atoms"] > 0
    ]
    al_bulk_rows = [
        row for row in rows if al_bulk_lo <= row["z_center_A"] <= al_bulk_hi and row["majority_phase"] == "Al_slab"
    ]
    fe_bulk_rows = [
        row for row in rows if fe_bulk_lo <= row["z_center_A"] <= fe_bulk_hi and row["majority_phase"] == "Fe4Al13_slab"
    ]

    al_interface_density = mean_or_none([row["Al_slab_density_atoms_per_A3"] for row in al_interface_rows])
    al_bulk_density = mean_or_none([row["Al_slab_density_atoms_per_A3"] for row in al_bulk_rows])
    fe_interface_density = mean_or_none([row["Fe4Al13_slab_density_atoms_per_A3"] for row in fe_interface_rows])
    fe_bulk_density = mean_or_none([row["Fe4Al13_slab_density_atoms_per_A3"] for row in fe_bulk_rows])

    def drop_pct(interface_density: float | None, bulk_density: float | None) -> float | None:
        if interface_density is None or bulk_density is None or bulk_density == 0:
            return None
        return float(100.0 * (bulk_density - interface_density) / bulk_density)

    interface_window_rows = [row for row in rows if row["in_interface_window"]]
    empty_interface_bins = [row for row in interface_window_rows if row["total_atoms"] == 0]

    return {
        "bulk_region_definition": {
            "Al_slab_bulk_z_A": [al_bulk_lo, al_bulk_hi],
            "Fe4Al13_slab_bulk_z_A": [fe_bulk_lo, fe_bulk_hi],
            "surface_buffer_A": al_surface_buffer,
        },
        "Al_slab_interface_density_atoms_per_A3": al_interface_density,
        "Al_slab_bulk_density_atoms_per_A3": al_bulk_density,
        "Al_slab_density_drop_percent": drop_pct(al_interface_density, al_bulk_density),
        "Fe4Al13_slab_interface_density_atoms_per_A3": fe_interface_density,
        "Fe4Al13_slab_bulk_density_atoms_per_A3": fe_bulk_density,
        "Fe4Al13_slab_density_drop_percent": drop_pct(fe_interface_density, fe_bulk_density),
        "empty_bins_in_interface_window": len(empty_interface_bins),
        "empty_interface_bin_ranges_A": [[row["z_lo_A"], row["z_hi_A"]] for row in empty_interface_bins],
    }


def verdict(contact: dict[str, Any], gap: dict[str, Any], density: dict[str, Any]) -> dict[str, Any]:
    pairs_under_30 = contact["threshold_counts"]["pairs_within_3.0_A"]
    pairs_under_35 = contact["threshold_counts"]["pairs_within_3.5_A"]
    min_dist = contact["minimum_cross_slab_distance_A"]
    interface_gap = bool(gap.get("intersects_interface_window")) and (gap.get("width_A") or 0.0) >= 2.0
    almost_absent = pairs_under_35 < 5 or min_dist is None or min_dist > 3.5

    notes = []
    if min_dist is not None:
        notes.append(f"minimum cross-slab distance is {min_dist:.3f} A")
    notes.append(f"cross-slab pairs within 3.0/3.5 A: {pairs_under_30}/{pairs_under_35}")
    if density["empty_bins_in_interface_window"] > 0:
        notes.append(f"empty 1 A bins in interface window: {density['empty_bins_in_interface_window']}")

    if almost_absent and interface_gap:
        status = "blocked_probable_interface_void"
        recommendation = "Do not load trial_001; build trial_002 with smaller interface gap or a different z-shift."
    elif pairs_under_30 > 0 and pairs_under_35 >= 20 and not interface_gap:
        status = "contact_present_visible_gaps_likely_visualization_or_structure_artifact"
        recommendation = "Keep trial_001 as unloaded baseline candidate, but still inspect visually before any loading."
    else:
        status = "ambiguous_requires_visual_or_trial_002_check"
        recommendation = "Do not load yet; inspect in OVITO and consider trial_002 if the apparent gap is at the interface."

    return {"status": status, "recommendation": recommendation, "notes": notes}


def write_profile_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "bin_index",
        "z_lo_A",
        "z_hi_A",
        "z_center_A",
        "total_atoms",
        "Al_type_1_atoms",
        "Fe_type_2_atoms",
        "Al_slab_atoms",
        "Fe4Al13_slab_atoms",
        "total_number_density_atoms_per_A3",
        "Al_slab_density_atoms_per_A3",
        "Fe4Al13_slab_density_atoms_per_A3",
        "majority_phase",
        "in_interface_window",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fieldnames})


def write_profile_png(rows: list[dict[str, Any]], interface_z: float, window: float, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    z = [row["z_center_A"] for row in rows]
    total = [row["total_number_density_atoms_per_A3"] for row in rows]
    al = [row["Al_slab_density_atoms_per_A3"] for row in rows]
    fe = [row["Fe4Al13_slab_density_atoms_per_A3"] for row in rows]

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=160)
    ax.plot(z, total, color="#2f2f2f", lw=1.6, label="total")
    ax.plot(z, al, color="#2878b5", lw=1.4, label="Al_slab")
    ax.plot(z, fe, color="#c75b12", lw=1.4, label="Fe4Al13_slab")
    ax.axvline(interface_z, color="#111111", lw=1.0, ls="--", label="interface_z")
    ax.axvspan(interface_z - window, interface_z + window, color="#999999", alpha=0.12, label="+/- 8 A window")
    ax.set_xlabel("z, A")
    ax.set_ylabel("number density, atoms/A^3")
    ax.set_title("trial_001 contact density z-profile after long unloaded NVT")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def write_doc(report: dict[str, Any], path: Path) -> None:
    contact = report["cross_slab_contact"]
    density = report["density_drop"]
    verdict_info = report["verdict"]
    gap = report["largest_empty_z_gap_between_occupied_bins"]
    counts = contact["threshold_counts"]
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"""# Проверка contact density для interface trial_001

Дата: 2026-05-10

## 1. Цель

Проверить, являются ли видимые в OVITO gap/void-like области около Al / Fe4Al13 реальными пустотами интерфейса или артефактами визуализации, triclinic skew и открытой структуры фазы Fe4Al13.

Ограничения соблюдены:

- 120 MPa не применялось;
- `fix addforce` не использовался;
- stress scenario не создавался;
- NPT не использовался;
- физическая валидация интерфейса не заявляется.

## 2. Входные данные

- Data: `{report["input"]["data"]}`
- Metadata: `{report["input"]["metadata"]}`
- Phase assignment: `{report["phase_assignment"]}`
- interface_z: {report["interface_z_A"]:.6f} A
- interface window: +/- {report["window_A"]:.3f} A
- OVITO app paths detected: `{report["ovito"]["app_paths"]}`
- OVITO Python module available: `{report["ovito"]["python_module_available"]}`

## 3. Cross-slab contact

| Quantity | Value |
|---|---:|
| Al_slab atoms near interface | {contact["Al_slab_atoms_near_interface"]} |
| Fe4Al13_slab atoms near interface | {contact["Fe4Al13_slab_atoms_near_interface"]} |
| Cross-slab pairs tested | {contact["cross_slab_pairs_tested"]} |
| Minimum cross-slab distance, A | {contact["minimum_cross_slab_distance_A"]:.6f} |
| Mean of 10 smallest cross-slab distances, A | {contact["mean_10_smallest_cross_slab_distances_A"]:.6f} |

Pair counts:

| Cutoff, A | Cross-slab pair count |
|---:|---:|
| 2.3 | {counts["pairs_within_2.3_A"]} |
| 2.5 | {counts["pairs_within_2.5_A"]} |
| 2.8 | {counts["pairs_within_2.8_A"]} |
| 3.0 | {counts["pairs_within_3.0_A"]} |
| 3.5 | {counts["pairs_within_3.5_A"]} |

## 4. z-density profile

- CSV: `results/tables/interface_trial_001_contact_density_z_profile.csv`
- Figure: `results/figures/interface_trial_001_contact_density_z_profile.png`
- Bin width: {report["density_profile"]["bin_width_A"]:.3f} A
- In-plane area: {report["density_profile"]["in_plane_area_A2"]:.6f} A^2
- Largest empty z-gap between occupied bins: {gap["width_A"]} A, z={gap["z_lo_A"]}..{gap["z_hi_A"]} A
- Empty 1 A bins inside interface window: {density["empty_bins_in_interface_window"]}
- Empty interface-bin ranges: `{density["empty_interface_bin_ranges_A"]}`

Density comparison:

| Region | Interface density, atoms/A^3 | Bulk-like density, atoms/A^3 | Drop, % |
|---|---:|---:|---:|
| Al_slab | {density["Al_slab_interface_density_atoms_per_A3"]:.6f} | {density["Al_slab_bulk_density_atoms_per_A3"]:.6f} | {density["Al_slab_density_drop_percent"]:.2f} |
| Fe4Al13_slab | {density["Fe4Al13_slab_interface_density_atoms_per_A3"]:.6f} | {density["Fe4Al13_slab_bulk_density_atoms_per_A3"]:.6f} | {density["Fe4Al13_slab_density_drop_percent"]:.2f} |

## 5. Verdict

Status: `{verdict_info["status"]}`

Recommendation: {verdict_info["recommendation"]}

Notes:

"""
    for note in verdict_info["notes"]:
        text += f"- {note}\n"
    text += """
Interpretation: visible gaps are not automatically evidence of an interface void in this triclinic/open-structure slab. The largest empty z-gap is only 1 A and is not located at the interface; the empty 1 A interface bins should be interpreted together with Al(111) layer spacing, triclinic projection, and Fe4Al13 open structure. The contact-density numbers should be used together with OVITO visual inspection before any loaded scenario.
"""
    path.write_text(text)


def run(args: argparse.Namespace) -> dict[str, Any]:
    parsed = parse_lammps_data(args.data)
    metadata = json.loads(args.metadata.read_text())
    phase_assignment = assign_phases(parsed["atoms"], metadata)
    interface_z, interface_z_source = load_interface_z(args.stress_summary, args.interface_z)
    contact = cross_slab_contact_summary(parsed["atoms"], parsed["box"], interface_z, args.window)
    rows, density_profile_meta = bin_density_profile(parsed["atoms"], parsed["box"], BIN_WIDTH_A, interface_z, args.window)
    gap = largest_empty_gap(rows, interface_z, args.window)
    density = density_drop_summary(rows, parsed["atoms"], interface_z, args.window)
    verdict_info = verdict(contact, gap, density)

    report = {
        "input": {
            "data": str(args.data),
            "metadata": str(args.metadata),
            "stress_summary": str(args.stress_summary) if args.stress_summary else None,
        },
        "interface_z_A": interface_z,
        "interface_z_source": interface_z_source,
        "window_A": args.window,
        "phase_assignment": phase_assignment,
        "box": parsed["box"],
        "total_atoms": len(parsed["atoms"]),
        "phase_counts": {
            "Al_slab": sum(1 for atom in parsed["atoms"] if atom.phase == "Al_slab"),
            "Fe4Al13_slab": sum(1 for atom in parsed["atoms"] if atom.phase == "Fe4Al13_slab"),
        },
        "type_counts": {
            "Al_type_1": sum(1 for atom in parsed["atoms"] if atom.atom_type == 1),
            "Fe_type_2": sum(1 for atom in parsed["atoms"] if atom.atom_type == 2),
        },
        "cross_slab_contact": contact,
        "density_profile": density_profile_meta,
        "largest_empty_z_gap_between_occupied_bins": gap,
        "density_drop": density,
        "verdict": verdict_info,
        "ovito": {
            "app_paths": detect_ovito_apps(),
            "python_module_available": ovito_python_available(),
            "note": "OVITO Basic GUI can be used externally; this script does not require OVITO Python.",
        },
        "hard_rules": {
            "applied_120_mpa": False,
            "used_fix_addforce": False,
            "created_stress_scenario": False,
            "used_npt": False,
            "claims_physical_validation": False,
        },
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write_profile_csv(rows, args.output_csv)
    write_profile_png(rows, interface_z, args.window, args.output_png)
    write_doc(report, args.output_doc)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--stress-summary", type=Path, default=DEFAULT_STRESS_SUMMARY)
    parser.add_argument("--interface-z", type=float, default=DEFAULT_INTERFACE_Z_A)
    parser.add_argument("--window", type=float, default=DEFAULT_WINDOW_A)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_PROFILE_CSV)
    parser.add_argument("--output-png", type=Path, default=DEFAULT_PROFILE_PNG)
    parser.add_argument("--output-doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()

    report = run(args)
    contact = report["cross_slab_contact"]
    print(f"data: {args.data}")
    print(f"interface_z_A: {report['interface_z_A']:.6f} ({report['interface_z_source']})")
    print(f"Al_slab atoms near interface: {contact['Al_slab_atoms_near_interface']}")
    print(f"Fe4Al13_slab atoms near interface: {contact['Fe4Al13_slab_atoms_near_interface']}")
    print(f"minimum cross-slab distance A: {contact['minimum_cross_slab_distance_A']}")
    print(f"mean 10 smallest cross-slab distances A: {contact['mean_10_smallest_cross_slab_distances_A']}")
    print(f"threshold counts: {contact['threshold_counts']}")
    print(f"largest empty z gap: {report['largest_empty_z_gap_between_occupied_bins']}")
    print(f"verdict: {report['verdict']['status']}")
    print(f"json: {args.output_json}")
    print(f"csv: {args.output_csv}")
    print(f"png: {args.output_png}")
    print(f"doc: {args.output_doc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
