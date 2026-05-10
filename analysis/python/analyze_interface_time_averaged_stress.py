#!/usr/bin/env python3
"""Compute time-averaged unloaded local stress profile for interface trial_001."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
TRIAL_DIR = ROOT / "lammps/02_interface_relax/trial_001"
DEFAULT_DUMP = TRIAL_DIR / "dump.interface_nvt_300k_long_stress.lammpstrj"
DEFAULT_METADATA = ROOT / "structures/interface/flat_interface/trial_001/interface_metadata.json"
DEFAULT_PREVIOUS = ROOT / "results/tables/interface_trial_001_unloaded_stress_profile.csv"
DEFAULT_CSV = ROOT / "results/tables/interface_trial_001_time_averaged_stress_profile.csv"
DEFAULT_JSON = TRIAL_DIR / "interface_time_averaged_stress_summary.json"
DEFAULT_PNG = ROOT / "results/figures/interface_trial_001_time_averaged_stress_profile.png"
BAR_TO_GPA = 1.0e-4


def reconstruct_triclinic_box(bounds: list[tuple[float, float, float]]) -> dict[str, float]:
    xlo_bound, xhi_bound, xy = bounds[0]
    ylo_bound, yhi_bound, xz = bounds[1]
    zlo_bound, zhi_bound, yz = bounds[2]
    xlo = xlo_bound - min(0.0, xy, xz, xy + xz)
    xhi = xhi_bound - max(0.0, xy, xz, xy + xz)
    ylo = ylo_bound - min(0.0, yz)
    yhi = yhi_bound - max(0.0, yz)
    return {
        "xlo": xlo,
        "xhi": xhi,
        "ylo": ylo,
        "yhi": yhi,
        "zlo": zlo_bound,
        "zhi": zhi_bound,
        "xy": xy,
        "xz": xz,
        "yz": yz,
    }


def inplane_area(box: dict[str, float]) -> float:
    lx = box["xhi"] - box["xlo"]
    ly = box["yhi"] - box["ylo"]
    xy = box["xy"]
    a = np.array([lx, 0.0, 0.0])
    b = np.array([xy, ly, 0.0])
    return float(np.linalg.norm(np.cross(a, b)))


def read_stress_dump(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(errors="replace").splitlines()
    frames: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("ITEM: TIMESTEP"):
            index += 1
            continue
        timestep = int(lines[index + 1].strip())
        if not lines[index + 2].startswith("ITEM: NUMBER OF ATOMS"):
            raise ValueError(f"Malformed dump near line {index}: missing NUMBER OF ATOMS")
        n_atoms = int(lines[index + 3].strip())
        if not lines[index + 4].startswith("ITEM: BOX BOUNDS"):
            raise ValueError(f"Malformed dump near line {index}: missing BOX BOUNDS")
        bounds = []
        for offset in [5, 6, 7]:
            parts = [float(value) for value in lines[index + offset].split()]
            if len(parts) != 3:
                raise ValueError(f"Expected triclinic BOX BOUNDS with 3 values, got: {lines[index + offset]}")
            bounds.append((parts[0], parts[1], parts[2]))
        box = reconstruct_triclinic_box(bounds)
        atoms_header = lines[index + 8]
        if not atoms_header.startswith("ITEM: ATOMS"):
            raise ValueError(f"Malformed dump near line {index}: missing ATOMS")
        columns = atoms_header.split()[2:]
        atoms = []
        index += 9
        for _ in range(n_atoms):
            parts = lines[index].split()
            row = dict(zip(columns, parts))
            atoms.append(
                {
                    "id": int(row["id"]),
                    "type": int(row["type"]),
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "z": float(row["z"]),
                    "pe_atom_eV": float(row["c_pe_atom"]),
                    "stress": np.array(
                        [
                            float(row["c_stress_atom[1]"]),
                            float(row["c_stress_atom[2]"]),
                            float(row["c_stress_atom[3]"]),
                            float(row["c_stress_atom[4]"]),
                            float(row["c_stress_atom[5]"]),
                            float(row["c_stress_atom[6]"]),
                        ],
                        dtype=float,
                    ),
                }
            )
            index += 1
        frames.append({"timestep": timestep, "box": box, "atoms": atoms})
    if not frames:
        raise ValueError(f"No frames found in {path}")
    return frames


def mean(values: list[float]) -> float:
    return float(statistics.fmean(values)) if values else math.nan


def stdev(values: list[float]) -> float:
    return float(statistics.stdev(values)) if len(values) > 1 else 0.0


def read_previous_single_frame(path: Path) -> dict[float, dict[str, float]]:
    if not path.exists():
        return {}
    with path.open() as handle:
        rows = {}
        for row in csv.DictReader(handle):
            rows[float(row["z_center_A"])] = {
                "hydrostatic_GPa": float(row["hydrostatic_GPa"]),
                "sigma_zz_GPa": float(row["sigma_zz_GPa"]),
            }
        return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def summarize_time_average(
    stress_dump: Path,
    metadata_path: Path,
    output_csv: Path,
    output_json: Path,
    output_png: Path,
    previous_single_frame_csv: Path,
    bin_width_a: float,
) -> dict[str, Any]:
    metadata = json.loads(metadata_path.read_text())
    al_slab_atoms = int(metadata["actual_atoms"]["Al_slab_atoms"])
    frames = read_stress_dump(stress_dump)
    all_z = [atom["z"] for frame in frames for atom in frame["atoms"]]
    z_min = math.floor(min(all_z) / bin_width_a) * bin_width_a
    z_max = math.ceil(max(all_z) / bin_width_a) * bin_width_a
    n_bins = max(1, int(math.ceil((z_max - z_min) / bin_width_a)))
    previous = read_previous_single_frame(previous_single_frame_csv)

    bin_samples: dict[int, list[dict[str, float]]] = defaultdict(list)
    for frame in frames:
        area = inplane_area(frame["box"])
        volume = area * bin_width_a
        per_bin: dict[int, dict[str, Any]] = {}
        for atom in frame["atoms"]:
            bin_index = int(math.floor((atom["z"] - z_min) / bin_width_a))
            bin_index = min(max(bin_index, 0), n_bins - 1)
            entry = per_bin.setdefault(
                bin_index,
                {
                    "atom_count": 0,
                    "Al_type_1": 0,
                    "Fe_type_2": 0,
                    "Al_slab_atoms": 0,
                    "Fe4Al13_slab_atoms": 0,
                    "stress": np.zeros(6, dtype=float),
                    "pe": [],
                },
            )
            entry["atom_count"] += 1
            if atom["type"] == 1:
                entry["Al_type_1"] += 1
            elif atom["type"] == 2:
                entry["Fe_type_2"] += 1
            if atom["id"] <= al_slab_atoms:
                entry["Al_slab_atoms"] += 1
            else:
                entry["Fe4Al13_slab_atoms"] += 1
            entry["stress"] += atom["stress"]
            entry["pe"].append(atom["pe_atom_eV"])

        for bin_index, entry in per_bin.items():
            summed = entry["stress"]
            normal = -summed[:3] / volume * BAR_TO_GPA
            shear = -summed[3:] / volume * BAR_TO_GPA
            bin_samples[bin_index].append(
                {
                    "atom_count": float(entry["atom_count"]),
                    "Al_type_1": float(entry["Al_type_1"]),
                    "Fe_type_2": float(entry["Fe_type_2"]),
                    "Al_slab_atoms": float(entry["Al_slab_atoms"]),
                    "Fe4Al13_slab_atoms": float(entry["Fe4Al13_slab_atoms"]),
                    "sigma_xx_GPa": float(normal[0]),
                    "sigma_yy_GPa": float(normal[1]),
                    "sigma_zz_GPa": float(normal[2]),
                    "sigma_xy_GPa": float(shear[0]),
                    "sigma_xz_GPa": float(shear[1]),
                    "sigma_yz_GPa": float(shear[2]),
                    "hydrostatic_GPa": float(np.mean(normal)),
                    "mean_pe_atom_eV": mean(entry["pe"]),
                }
            )

    rows: list[dict[str, Any]] = []
    for bin_index in sorted(bin_samples):
        samples = bin_samples[bin_index]
        z_lo = z_min + bin_index * bin_width_a
        z_hi = z_lo + bin_width_a
        z_center = 0.5 * (z_lo + z_hi)
        row: dict[str, Any] = {
            "bin_index": bin_index,
            "z_lo_A": z_lo,
            "z_hi_A": z_hi,
            "z_center_A": z_center,
            "frames_present": len(samples),
        }
        for key in [
            "atom_count",
            "Al_type_1",
            "Fe_type_2",
            "Al_slab_atoms",
            "Fe4Al13_slab_atoms",
            "sigma_xx_GPa",
            "sigma_yy_GPa",
            "sigma_zz_GPa",
            "sigma_xy_GPa",
            "sigma_xz_GPa",
            "sigma_yz_GPa",
            "hydrostatic_GPa",
            "mean_pe_atom_eV",
        ]:
            values = [float(sample[key]) for sample in samples]
            row[f"{key}_mean"] = mean(values)
            row[f"{key}_std"] = stdev(values)
        previous_row = previous.get(z_center)
        row["single_frame_hydrostatic_GPa"] = previous_row["hydrostatic_GPa"] if previous_row else ""
        row["single_frame_sigma_zz_GPa"] = previous_row["sigma_zz_GPa"] if previous_row else ""
        if previous_row:
            row["delta_hydrostatic_vs_single_GPa"] = row["hydrostatic_GPa_mean"] - previous_row["hydrostatic_GPa"]
            row["delta_sigma_zz_vs_single_GPa"] = row["sigma_zz_GPa_mean"] - previous_row["sigma_zz_GPa"]
        else:
            row["delta_hydrostatic_vs_single_GPa"] = ""
            row["delta_sigma_zz_vs_single_GPa"] = ""
        rows.append(row)

    write_csv(output_csv, rows)

    al_z_max = float(max(atom["z"] for frame in frames for atom in frame["atoms"] if atom["id"] <= al_slab_atoms))
    fe_z_min = float(min(atom["z"] for frame in frames for atom in frame["atoms"] if atom["id"] > al_slab_atoms))
    interface_z = 0.5 * (al_z_max + fe_z_min)
    interface_al_row = max((row for row in rows if row["z_center_A"] <= interface_z), key=lambda row: row["z_center_A"])
    interface_fe_row = min((row for row in rows if row["z_center_A"] >= interface_z), key=lambda row: row["z_center_A"])
    max_abs_hydro = max(rows, key=lambda row: abs(float(row["hydrostatic_GPa_mean"])))

    summary = {
        "stress_dump": str(stress_dump),
        "metadata": str(metadata_path),
        "output_csv": str(output_csv),
        "output_png": str(output_png),
        "previous_single_frame_csv": str(previous_single_frame_csv),
        "frame_count": len(frames),
        "timesteps": [frame["timestep"] for frame in frames],
        "bin_width_A": bin_width_a,
        "z_min_A": z_min,
        "z_max_A": z_max,
        "interface_z_A": interface_z,
        "Al_slab_atoms": al_slab_atoms,
        "total_atoms_per_frame": len(frames[0]["atoms"]),
        "interface_near_bins": {
            "Al_side": interface_al_row,
            "Fe4Al13_side": interface_fe_row,
        },
        "highest_abs_hydrostatic_bin": max_abs_hydro,
        "notes": [
            "This is an unloaded baseline; no 120 MPa, fix addforce, stress scenario, or NPT was used.",
            "Stress is a virial proxy from compute stress/atom NULL virial.",
            "Bin volume is in-plane cell area times 5 A bin width; free-surface bins are approximate.",
            "Values are not claimed as experimentally validated absolute stresses.",
        ],
    }
    output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    import matplotlib.pyplot as plt

    z = [row["z_center_A"] for row in rows]
    hydro = [row["hydrostatic_GPa_mean"] for row in rows]
    hydro_std = [row["hydrostatic_GPa_std"] for row in rows]
    sigma_zz = [row["sigma_zz_GPa_mean"] for row in rows]
    sigma_zz_std = [row["sigma_zz_GPa_std"] for row in rows]
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(8, 4.5))
    axis.errorbar(z, hydro, yerr=hydro_std, marker="o", capsize=2, label="hydrostatic mean")
    axis.errorbar(z, sigma_zz, yerr=sigma_zz_std, marker="s", capsize=2, label="sigma_zz mean")
    axis.axvline(interface_z, color="black", linestyle="--", linewidth=1, label="interface")
    axis.set_xlabel("z, A")
    axis.set_ylabel("Time-averaged stress proxy, GPa")
    axis.set_title("trial_001 unloaded time-averaged local stress")
    axis.grid(True, alpha=0.3)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output_png, dpi=180)
    plt.close(fig)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stress-dump", type=Path, default=DEFAULT_DUMP)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--previous-single-frame-csv", type=Path, default=DEFAULT_PREVIOUS)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-png", type=Path, default=DEFAULT_PNG)
    parser.add_argument("--bin-width-a", type=float, default=5.0)
    args = parser.parse_args()

    summary = summarize_time_average(
        stress_dump=args.stress_dump,
        metadata_path=args.metadata,
        output_csv=args.output_csv,
        output_json=args.output_json,
        output_png=args.output_png,
        previous_single_frame_csv=args.previous_single_frame_csv,
        bin_width_a=args.bin_width_a,
    )
    print(f"frames: {summary['frame_count']}")
    print(f"interface z A: {summary['interface_z_A']}")
    print(f"Al-side interface bin: {summary['interface_near_bins']['Al_side']}")
    print(f"Fe-side interface bin: {summary['interface_near_bins']['Fe4Al13_side']}")
    print(f"highest abs hydrostatic bin: {summary['highest_abs_hydrostatic_bin']}")
    print(f"csv: {args.output_csv}")
    print(f"json: {args.output_json}")
    print(f"png: {args.output_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
