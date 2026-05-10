#!/usr/bin/env python3
"""Check minimum distances in an Al / Fe4Al13 interface LAMMPS data file."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_DATA = Path("lammps/02_interface_relax/trial_001/data.interface_nvt_300k")
DEFAULT_METADATA = Path("structures/interface/flat_interface/trial_001/interface_metadata.json")
HARD_OVERLAP_A = 1.8
AL_FE_WARNING_A = 2.1


def parse_lammps_data(path: Path) -> dict[str, Any]:
    text = path.read_text(errors="replace")
    lines = text.splitlines()
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

    atoms: list[dict[str, Any]] = []
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
            x, y, z = (float(parts[2]), float(parts[3]), float(parts[4]))
        except ValueError:
            if atoms:
                break
            continue
        atoms.append({"id": atom_id, "type": atom_type, "position": [x, y, z]})

    if n_atoms_header is not None and len(atoms) != n_atoms_header:
        raise ValueError(f"Expected {n_atoms_header} atoms, parsed {len(atoms)} atoms from {path}")

    for required in ["xlo", "xhi", "ylo", "yhi", "zlo", "zhi"]:
        if required not in box:
            raise ValueError(f"Missing box bound {required} in {path}")

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


def pair_distance(pos_i: np.ndarray, pos_j: np.ndarray, h_matrix: np.ndarray, h_inverse: np.ndarray) -> float:
    delta = pos_j - pos_i
    frac = h_inverse @ delta
    frac[0] -= round(float(frac[0]))
    frac[1] -= round(float(frac[1]))
    delta_min = h_matrix @ frac
    return float(np.linalg.norm(delta_min))


def empty_record() -> dict[str, Any]:
    return {"distance_A": math.inf}


def update_min(record: dict[str, Any], distance: float, atom_i: dict[str, Any], atom_j: dict[str, Any]) -> None:
    if distance < record["distance_A"]:
        record.update(
            {
                "distance_A": distance,
                "atom_i": atom_i["id"],
                "atom_j": atom_j["id"],
                "type_i": atom_i["type"],
                "type_j": atom_j["type"],
                "phase_i": atom_i["phase"],
                "phase_j": atom_j["phase"],
            }
        )


def finite_or_none(record: dict[str, Any]) -> dict[str, Any]:
    if math.isinf(record["distance_A"]):
        return {"distance_A": None}
    return record


def summarize_distances(data_path: Path, metadata_path: Path | None) -> dict[str, Any]:
    parsed = parse_lammps_data(data_path)
    atoms = parsed["atoms"]
    positions = np.array([atom["position"] for atom in atoms], dtype=float)
    h_matrix = box_matrix(parsed["box"])
    h_inverse = np.linalg.inv(h_matrix)

    metadata = json.loads(metadata_path.read_text()) if metadata_path and metadata_path.exists() else {}
    al_slab_atoms = int(metadata.get("actual_atoms", {}).get("Al_slab_atoms", 0))
    if al_slab_atoms > 0:
        for atom in atoms:
            atom["phase"] = "Al_slab" if atom["id"] <= al_slab_atoms else "Fe4Al13_slab"
        phase_method = f"atom_id<=Al_slab_atoms ({al_slab_atoms})"
    else:
        midpoint_z = float(np.median(positions[:, 2]))
        for atom in atoms:
            atom["phase"] = "lower_z_slab" if atom["position"][2] <= midpoint_z else "upper_z_slab"
        phase_method = f"z_median={midpoint_z:.6f}"

    records = {
        "minimum_Al_Al": empty_record(),
        "minimum_Fe_Fe": empty_record(),
        "minimum_Al_Fe": empty_record(),
        "minimum_cross_slab": empty_record(),
        "minimum_cross_slab_Al_Fe": empty_record(),
    }
    any_below_hard = 0
    al_fe_below_warning = 0
    cross_slab_below_hard = 0
    cross_slab_al_fe_below_warning = 0

    for i, atom_i in enumerate(atoms[:-1]):
        for j in range(i + 1, len(atoms)):
            atom_j = atoms[j]
            distance = pair_distance(positions[i], positions[j], h_matrix, h_inverse)
            type_pair = {atom_i["type"], atom_j["type"]}
            cross_slab = atom_i["phase"] != atom_j["phase"]

            if distance < HARD_OVERLAP_A:
                any_below_hard += 1
                if cross_slab:
                    cross_slab_below_hard += 1

            if type_pair == {1}:
                update_min(records["minimum_Al_Al"], distance, atom_i, atom_j)
            elif type_pair == {2}:
                update_min(records["minimum_Fe_Fe"], distance, atom_i, atom_j)
            elif type_pair == {1, 2}:
                update_min(records["minimum_Al_Fe"], distance, atom_i, atom_j)
                if distance < AL_FE_WARNING_A:
                    al_fe_below_warning += 1

            if cross_slab:
                update_min(records["minimum_cross_slab"], distance, atom_i, atom_j)
                if type_pair == {1, 2}:
                    update_min(records["minimum_cross_slab_Al_Fe"], distance, atom_i, atom_j)
                    if distance < AL_FE_WARNING_A:
                        cross_slab_al_fe_below_warning += 1

    return {
        "data_path": str(data_path),
        "metadata_path": str(metadata_path) if metadata_path else None,
        "total_atoms": len(atoms),
        "Al_type_1": sum(1 for atom in atoms if atom["type"] == 1),
        "Fe_type_2": sum(1 for atom in atoms if atom["type"] == 2),
        "counts_by_phase": {
            phase: sum(1 for atom in atoms if atom["phase"] == phase)
            for phase in sorted({atom["phase"] for atom in atoms})
        },
        "phase_assignment": phase_method,
        "box": parsed["box"],
        "minimum_Al_Al_distance_A": finite_or_none(records["minimum_Al_Al"]),
        "minimum_Fe_Fe_distance_A": finite_or_none(records["minimum_Fe_Fe"]),
        "minimum_Al_Fe_distance_A": finite_or_none(records["minimum_Al_Fe"]),
        "minimum_cross_slab_distance_A": finite_or_none(records["minimum_cross_slab"]),
        "minimum_cross_slab_Al_Fe_distance_A": finite_or_none(records["minimum_cross_slab_Al_Fe"]),
        "pairs_below_hard_overlap_threshold": any_below_hard,
        "Al_Fe_pairs_below_warning_threshold": al_fe_below_warning,
        "cross_slab_pairs_below_hard_overlap_threshold": cross_slab_below_hard,
        "cross_slab_Al_Fe_pairs_below_warning_threshold": cross_slab_al_fe_below_warning,
        "thresholds": {
            "hard_overlap_A": HARD_OVERLAP_A,
            "al_fe_warning_A": AL_FE_WARNING_A,
        },
        "safe_basic": any_below_hard == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_path", type=Path, nargs="?", default=DEFAULT_DATA)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--output", type=Path, help="Write JSON report to this path.")
    args = parser.parse_args()

    summary = summarize_distances(args.data_path, args.metadata)
    if args.output:
        args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    print(f"data: {args.data_path}")
    print(f"total atoms: {summary['total_atoms']}")
    print(f"Al type 1: {summary['Al_type_1']}")
    print(f"Fe type 2: {summary['Fe_type_2']}")
    print(f"phase assignment: {summary['phase_assignment']}")
    for key in [
        "minimum_Al_Al_distance_A",
        "minimum_Fe_Fe_distance_A",
        "minimum_Al_Fe_distance_A",
        "minimum_cross_slab_distance_A",
        "minimum_cross_slab_Al_Fe_distance_A",
    ]:
        print(f"{key}: {summary[key]['distance_A']}")
    print(f"pairs below 1.8 A: {summary['pairs_below_hard_overlap_threshold']}")
    print(f"Al-Fe pairs below 2.1 A: {summary['Al_Fe_pairs_below_warning_threshold']}")
    print(f"safe_basic: {summary['safe_basic']}")
    if args.output:
        print(f"json: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
