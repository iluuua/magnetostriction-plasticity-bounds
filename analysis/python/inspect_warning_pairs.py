#!/usr/bin/env python3
"""Inspect short Al-Fe warning pairs and track them through a LAMMPS trajectory."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
TRIAL_DIR = ROOT / "lammps/02_interface_relax/trial_001"
DEFAULT_DATA = TRIAL_DIR / "data.interface_nvt_300k_long"
DEFAULT_DUMP = TRIAL_DIR / "dump.interface_nvt_300k_long.lammpstrj"
DEFAULT_METADATA = ROOT / "structures/interface/flat_interface/trial_001/interface_metadata.json"
DEFAULT_WARNING_JSON = TRIAL_DIR / "warning_pairs_long_nvt.json"
DEFAULT_DISTANCE_CSV = ROOT / "results/tables/interface_trial_001_warning_pair_distance_over_time.csv"
DEFAULT_NEIGHBOR_CSV = ROOT / "results/tables/interface_trial_001_warning_pair_neighborhood.csv"
DEFAULT_DISTANCE_PNG = ROOT / "results/figures/interface_trial_001_warning_pair_distance_over_time.png"
HARD_OVERLAP_A = 1.8
WARNING_AL_FE_A = 2.1
NEIGHBOR_RADIUS_A = 4.0


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

    atoms: dict[int, dict[str, Any]] = {}
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
        atoms[atom_id] = {"id": atom_id, "type": atom_type, "position": np.array([x, y, z], dtype=float)}

    if n_atoms_header is not None and len(atoms) != n_atoms_header:
        raise ValueError(f"Expected {n_atoms_header} atoms, parsed {len(atoms)} atoms from {path}")
    return {"box": box, "atoms": atoms}


def reconstruct_triclinic_box(bounds: list[tuple[float, float, float]]) -> dict[str, float]:
    xlo_bound, xhi_bound, xy = bounds[0]
    ylo_bound, yhi_bound, xz = bounds[1]
    zlo_bound, zhi_bound, yz = bounds[2]
    return {
        "xlo": xlo_bound - min(0.0, xy, xz, xy + xz),
        "xhi": xhi_bound - max(0.0, xy, xz, xy + xz),
        "ylo": ylo_bound - min(0.0, yz),
        "yhi": yhi_bound - max(0.0, yz),
        "zlo": zlo_bound,
        "zhi": zhi_bound,
        "xy": xy,
        "xz": xz,
        "yz": yz,
    }


def read_dump_frames(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(errors="replace").splitlines()
    frames: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("ITEM: TIMESTEP"):
            index += 1
            continue
        timestep = int(lines[index + 1].strip())
        n_atoms = int(lines[index + 3].strip())
        bounds = []
        for offset in [5, 6, 7]:
            values = [float(value) for value in lines[index + offset].split()]
            if len(values) == 2:
                values.append(0.0)
            bounds.append((values[0], values[1], values[2]))
        box = reconstruct_triclinic_box(bounds)
        columns = lines[index + 8].split()[2:]
        atoms: dict[int, dict[str, Any]] = {}
        index += 9
        for _ in range(n_atoms):
            values = lines[index].split()
            row = dict(zip(columns, values))
            atom_id = int(row["id"])
            atoms[atom_id] = {
                "id": atom_id,
                "type": int(row["type"]),
                "position": np.array([float(row["x"]), float(row["y"]), float(row["z"])], dtype=float),
            }
            index += 1
        frames.append({"timestep": timestep, "box": box, "atoms": atoms})
    if not frames:
        raise ValueError(f"No frames found in {path}")
    return frames


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


def min_image_delta(pos_i: np.ndarray, pos_j: np.ndarray, box: dict[str, float]) -> np.ndarray:
    h_matrix = box_matrix(box)
    h_inverse = np.linalg.inv(h_matrix)
    delta = pos_j - pos_i
    frac = h_inverse @ delta
    frac[0] -= round(float(frac[0]))
    frac[1] -= round(float(frac[1]))
    return h_matrix @ frac


def distance(pos_i: np.ndarray, pos_j: np.ndarray, box: dict[str, float]) -> float:
    return float(np.linalg.norm(min_image_delta(pos_i, pos_j, box)))


def species(atom_type: int) -> str:
    return {1: "Al", 2: "Fe"}.get(atom_type, f"type{atom_type}")


def assign_phases(atoms: dict[int, dict[str, Any]], al_slab_atoms: int) -> None:
    for atom in atoms.values():
        atom["phase"] = "Al_slab" if atom["id"] <= al_slab_atoms else "Fe4Al13_slab"


def classify_pair(atom_i: dict[str, Any], atom_j: dict[str, Any]) -> str:
    if atom_i["phase"] != atom_j["phase"]:
        return "cross-slab interface pair"
    if atom_i["phase"] == "Fe4Al13_slab":
        return "internal Fe4Al13 pair"
    if atom_i["phase"] == "Al_slab":
        return "internal Al slab pair"
    return "unknown"


def find_warning_pairs(parsed: dict[str, Any], al_slab_atoms: int, threshold_a: float) -> list[dict[str, Any]]:
    atoms = parsed["atoms"]
    assign_phases(atoms, al_slab_atoms)
    atom_list = [atoms[atom_id] for atom_id in sorted(atoms)]
    warnings: list[dict[str, Any]] = []
    for index, atom_i in enumerate(atom_list[:-1]):
        for atom_j in atom_list[index + 1 :]:
            if {atom_i["type"], atom_j["type"]} != {1, 2}:
                continue
            dist = distance(atom_i["position"], atom_j["position"], parsed["box"])
            if dist < threshold_a:
                warnings.append(
                    {
                        "atom_i": atom_i["id"],
                        "atom_j": atom_j["id"],
                        "type_i": atom_i["type"],
                        "type_j": atom_j["type"],
                        "species_i": species(atom_i["type"]),
                        "species_j": species(atom_j["type"]),
                        "phase_i": atom_i["phase"],
                        "phase_j": atom_j["phase"],
                        "classification": classify_pair(atom_i, atom_j),
                        "distance_A": dist,
                        "coords_i_A": atom_i["position"].tolist(),
                        "coords_j_A": atom_j["position"].tolist(),
                    }
                )
    return sorted(warnings, key=lambda item: item["distance_A"])


def summarize_time_series(distances: list[float]) -> dict[str, Any]:
    diffs = [b - a for a, b in zip(distances, distances[1:])]
    below_warning = [value < WARNING_AL_FE_A for value in distances]
    below_hard = [value < HARD_OVERLAP_A for value in distances]
    monotonic_decrease = all(diff <= 1e-8 for diff in diffs)
    last5 = below_warning[-5:] if len(below_warning) >= 5 else below_warning
    if all(last5) and len(last5) >= 3:
        contact_type = "stable late short contact"
    elif sum(below_warning) <= max(2, math.ceil(0.25 * len(below_warning))):
        contact_type = "transient fluctuation"
    else:
        contact_type = "intermittent short contact"
    return {
        "min_distance_A": min(distances),
        "max_distance_A": max(distances),
        "mean_distance_A": float(np.mean(distances)),
        "std_distance_A": float(np.std(distances, ddof=1)) if len(distances) > 1 else 0.0,
        "frames_below_2p1_A": int(sum(below_warning)),
        "frames_below_1p8_A": int(sum(below_hard)),
        "monotonically_decreases": monotonic_decrease,
        "contact_type": contact_type,
    }


def track_pairs(frames: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for pair_index, pair in enumerate(warnings, start=1):
        atom_i = int(pair["atom_i"])
        atom_j = int(pair["atom_j"])
        distances = []
        for frame in frames:
            dist = distance(frame["atoms"][atom_i]["position"], frame["atoms"][atom_j]["position"], frame["box"])
            distances.append(dist)
            rows.append(
                {
                    "pair_index": pair_index,
                    "timestep": frame["timestep"],
                    "atom_i": atom_i,
                    "atom_j": atom_j,
                    "classification": pair["classification"],
                    "distance_A": dist,
                    "below_2p1_A": dist < WARNING_AL_FE_A,
                    "below_1p8_A": dist < HARD_OVERLAP_A,
                }
            )
        summary = summarize_time_series(distances)
        summary.update(
            {
                "pair_index": pair_index,
                "atom_i": atom_i,
                "atom_j": atom_j,
                "classification": pair["classification"],
            }
        )
        summaries.append(summary)
    return rows, summaries


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_distance_plot(path: Path, rows: list[dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(8, 4.5))
    pair_indices = sorted({int(row["pair_index"]) for row in rows})
    for pair_index in pair_indices:
        pair_rows = [row for row in rows if int(row["pair_index"]) == pair_index]
        axis.plot(
            [row["timestep"] for row in pair_rows],
            [row["distance_A"] for row in pair_rows],
            marker="o",
            label=f"pair {pair_index}: {pair_rows[0]['atom_i']}-{pair_rows[0]['atom_j']}",
        )
    axis.axhline(WARNING_AL_FE_A, color="tab:orange", linestyle="--", label="2.1 A warning")
    axis.axhline(HARD_OVERLAP_A, color="tab:red", linestyle="--", label="1.8 A hard")
    axis.set_xlabel("Timestep")
    axis.set_ylabel("Al-Fe distance, A")
    axis.set_title("trial_001 warning pair distance over long NVT")
    axis.grid(True, alpha=0.3)
    axis.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def neighborhood_rows(parsed: dict[str, Any], warnings: list[dict[str, Any]], radius_a: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    atoms = parsed["atoms"]
    box = parsed["box"]
    for pair_index, pair in enumerate(warnings, start=1):
        atom_i = atoms[int(pair["atom_i"])]
        atom_j = atoms[int(pair["atom_j"])]
        pair_delta = min_image_delta(atom_i["position"], atom_j["position"], box)
        center = atom_i["position"] + 0.5 * pair_delta
        for atom in atoms.values():
            d_center = distance(center, atom["position"], box)
            if d_center <= radius_a:
                rows.append(
                    {
                        "pair_index": pair_index,
                        "neighbor_atom_id": atom["id"],
                        "type": atom["type"],
                        "species": species(atom["type"]),
                        "phase": atom["phase"],
                        "x_A": atom["position"][0],
                        "y_A": atom["position"][1],
                        "z_A": atom["position"][2],
                        "distance_to_pair_center_A": d_center,
                        "distance_to_atom_i_A": distance(atom_i["position"], atom["position"], box),
                        "distance_to_atom_j_A": distance(atom_j["position"], atom["position"], box),
                    }
                )
    return sorted(rows, key=lambda row: (row["pair_index"], row["distance_to_pair_center_A"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--dump", type=Path, default=DEFAULT_DUMP)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--warning-json", type=Path, default=DEFAULT_WARNING_JSON)
    parser.add_argument("--distance-csv", type=Path, default=DEFAULT_DISTANCE_CSV)
    parser.add_argument("--neighborhood-csv", type=Path, default=DEFAULT_NEIGHBOR_CSV)
    parser.add_argument("--distance-png", type=Path, default=DEFAULT_DISTANCE_PNG)
    parser.add_argument("--warning-threshold-a", type=float, default=WARNING_AL_FE_A)
    parser.add_argument("--neighborhood-radius-a", type=float, default=NEIGHBOR_RADIUS_A)
    args = parser.parse_args()

    metadata = json.loads(args.metadata.read_text())
    al_slab_atoms = int(metadata["actual_atoms"]["Al_slab_atoms"])
    parsed = parse_lammps_data(args.data)
    warnings = find_warning_pairs(parsed, al_slab_atoms, args.warning_threshold_a)
    frames = read_dump_frames(args.dump)
    distance_rows, pair_summaries = track_pairs(frames, warnings) if warnings else ([], [])
    neighbors = neighborhood_rows(parsed, warnings, args.neighborhood_radius_a) if warnings else []

    write_csv(args.distance_csv, distance_rows)
    write_csv(args.neighborhood_csv, neighbors)
    if distance_rows:
        write_distance_plot(args.distance_png, distance_rows)

    summary = {
        "data": str(args.data),
        "dump": str(args.dump),
        "metadata": str(args.metadata),
        "warning_threshold_A": args.warning_threshold_a,
        "hard_overlap_threshold_A": HARD_OVERLAP_A,
        "neighborhood_radius_A": args.neighborhood_radius_a,
        "n_warning_pairs": len(warnings),
        "warning_pairs": warnings,
        "trajectory_frame_count": len(frames),
        "pair_time_summaries": pair_summaries,
        "distance_csv": str(args.distance_csv),
        "distance_png": str(args.distance_png) if distance_rows else None,
        "neighborhood_csv": str(args.neighborhood_csv),
        "verdict": "no_warning_pairs" if not warnings else None,
    }
    if pair_summaries:
        first = pair_summaries[0]
        if warnings[0]["classification"] == "cross-slab interface pair" or first["contact_type"] == "stable late short contact":
            verdict = "block_loading_and_refine_geometry"
        elif warnings[0]["classification"] == "internal Fe4Al13 pair" and first["frames_below_1p8_A"] == 0:
            verdict = "warning_to_monitor_not_loading_blocker"
        else:
            verdict = "warning_requires_review"
        summary["verdict"] = verdict

    args.warning_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"warning pairs: {len(warnings)}")
    for pair in warnings:
        print(
            f"{pair['atom_i']}-{pair['atom_j']} {pair['species_i']}-{pair['species_j']} "
            f"{pair['classification']} d={pair['distance_A']:.6f} A"
        )
    for item in pair_summaries:
        print(f"time summary: {item}")
    print(f"json: {args.warning_json}")
    print(f"distance csv: {args.distance_csv}")
    print(f"neighborhood csv: {args.neighborhood_csv}")
    if distance_rows:
        print(f"distance png: {args.distance_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
