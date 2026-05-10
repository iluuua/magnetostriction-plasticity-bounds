#!/usr/bin/env python3
"""Analyze unloaded interface stress and strain proxies after NVT."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRIAL_DIR = ROOT / "lammps/02_interface_relax/trial_001"
DEFAULT_METADATA = ROOT / "structures/interface/flat_interface/trial_001/interface_metadata.json"
BAR_TO_GPA = 1.0e-4


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
        raise ValueError(f"Atoms section not found: {path}")

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


def inplane_area(box: dict[str, float]) -> float:
    h_matrix = box_matrix(box)
    return float(np.linalg.norm(np.cross(h_matrix[:, 0], h_matrix[:, 1])))


def min_image_delta(pos_i: np.ndarray, pos_j: np.ndarray, h_matrix: np.ndarray, h_inverse: np.ndarray) -> np.ndarray:
    delta = pos_j - pos_i
    frac = h_inverse @ delta
    frac[0] -= round(float(frac[0]))
    frac[1] -= round(float(frac[1]))
    return h_matrix @ frac


def parse_stress_dump(path: Path) -> dict[int, dict[str, Any]]:
    lines = path.read_text(errors="replace").splitlines()
    atoms: dict[int, dict[str, Any]] = {}
    index = 0
    columns: list[str] | None = None
    while index < len(lines):
        if lines[index].startswith("ITEM: ATOMS"):
            columns = lines[index].split()[2:]
            index += 1
            break
        index += 1
    if columns is None:
        raise ValueError(f"ITEM: ATOMS section not found in {path}")

    for line in lines[index:]:
        if line.startswith("ITEM:"):
            break
        parts = line.split()
        if len(parts) != len(columns):
            continue
        row = dict(zip(columns, parts))
        atom_id = int(row["id"])
        atoms[atom_id] = {
            "id": atom_id,
            "type": int(row["type"]),
            "position": np.array([float(row["x"]), float(row["y"]), float(row["z"])], dtype=float),
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
    return atoms


def assign_phases(atoms: dict[int, dict[str, Any]], metadata_path: Path) -> None:
    metadata = json.loads(metadata_path.read_text())
    al_slab_atoms = int(metadata["actual_atoms"]["Al_slab_atoms"])
    for atom in atoms.values():
        atom["phase"] = "Al_slab" if atom["id"] <= al_slab_atoms else "Fe4Al13_slab"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def mean_or_none(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def max_or_none(values: list[float]) -> float | None:
    return float(np.max(values)) if values else None


def local_strain_proxies(
    reference_atoms: dict[int, dict[str, Any]],
    current_atoms: dict[int, dict[str, Any]],
    h_matrix: np.ndarray,
    h_inverse: np.ndarray,
    cutoff_a: float,
) -> dict[int, dict[str, float | int | None]]:
    ids = sorted(reference_atoms)
    ref_positions = {atom_id: reference_atoms[atom_id]["position"] for atom_id in ids}
    cur_positions = {atom_id: current_atoms[atom_id]["position"] for atom_id in ids}
    proxies: dict[int, dict[str, float | int | None]] = {}

    for atom_id in ids:
        r0_i = ref_positions[atom_id]
        r1_i = cur_positions[atom_id]
        ref_neighbors = []
        cur_neighbors = []
        for other_id in ids:
            if other_id == atom_id:
                continue
            r0 = min_image_delta(r0_i, ref_positions[other_id], h_matrix, h_inverse)
            distance = float(np.linalg.norm(r0))
            if distance <= cutoff_a:
                r1 = min_image_delta(r1_i, cur_positions[other_id], h_matrix, h_inverse)
                ref_neighbors.append(r0)
                cur_neighbors.append(r1)

        displacement = min_image_delta(r0_i, r1_i, h_matrix, h_inverse)
        result: dict[str, float | int | None] = {
            "neighbor_count": len(ref_neighbors),
            "displacement_A": float(np.linalg.norm(displacement)),
            "dx_A": float(displacement[0]),
            "dy_A": float(displacement[1]),
            "dz_A": float(displacement[2]),
            "strain_trace": None,
            "von_mises_strain_proxy": None,
            "d2min_A2": None,
        }
        if len(ref_neighbors) >= 4:
            r0_matrix = np.vstack(ref_neighbors)
            r1_matrix = np.vstack(cur_neighbors)
            deformation_t, *_ = np.linalg.lstsq(r0_matrix, r1_matrix, rcond=None)
            deformation = deformation_t.T
            strain = 0.5 * (deformation + deformation.T) - np.eye(3)
            deviatoric = strain - np.trace(strain) / 3.0 * np.eye(3)
            fitted = (deformation @ r0_matrix.T).T
            residuals = r1_matrix - fitted
            result["strain_trace"] = float(np.trace(strain))
            result["von_mises_strain_proxy"] = float(math.sqrt(2.0 / 3.0 * np.sum(deviatoric * deviatoric)))
            result["d2min_A2"] = float(np.mean(np.sum(residuals * residuals, axis=1)))
        proxies[atom_id] = result
    return proxies


def summarize(
    minimized_data: Path,
    nvt_data: Path,
    stress_dump: Path,
    metadata_path: Path,
    stress_profile_csv: Path,
    strain_profile_csv: Path,
    atom_diagnostics_csv: Path,
    output_json: Path,
    bin_width_a: float,
    neighbor_cutoff_a: float,
) -> dict[str, Any]:
    minimized = parse_lammps_data(minimized_data)
    nvt = parse_lammps_data(nvt_data)
    stress_atoms = parse_stress_dump(stress_dump)
    assign_phases(nvt["atoms"], metadata_path)
    assign_phases(stress_atoms, metadata_path)

    h_matrix = box_matrix(nvt["box"])
    h_inverse = np.linalg.inv(h_matrix)
    area = inplane_area(nvt["box"])
    z_values = [atom["position"][2] for atom in nvt["atoms"].values()]
    z_min = math.floor(min(z_values) / bin_width_a) * bin_width_a
    z_max = math.ceil(max(z_values) / bin_width_a) * bin_width_a
    n_bins = max(1, int(math.ceil((z_max - z_min) / bin_width_a)))

    strain = local_strain_proxies(minimized["atoms"], nvt["atoms"], h_matrix, h_inverse, neighbor_cutoff_a)

    atom_rows = []
    for atom_id in sorted(nvt["atoms"]):
        atom = nvt["atoms"][atom_id]
        stress = stress_atoms[atom_id]["stress"]
        sxx_bar_a3, syy_bar_a3, szz_bar_a3 = stress[:3]
        hydrostatic_raw_bar_a3 = -(sxx_bar_a3 + syy_bar_a3 + szz_bar_a3) / 3.0
        proxy = strain[atom_id]
        atom_rows.append(
            {
                "id": atom_id,
                "type": atom["type"],
                "phase": atom["phase"],
                "x_A": atom["position"][0],
                "y_A": atom["position"][1],
                "z_A": atom["position"][2],
                "pe_atom_eV": stress_atoms[atom_id]["pe_atom_eV"],
                "sxx_bar_A3": sxx_bar_a3,
                "syy_bar_A3": syy_bar_a3,
                "szz_bar_A3": szz_bar_a3,
                "sxy_bar_A3": stress[3],
                "sxz_bar_A3": stress[4],
                "syz_bar_A3": stress[5],
                "hydrostatic_raw_bar_A3": hydrostatic_raw_bar_a3,
                "displacement_A": proxy["displacement_A"],
                "dx_A": proxy["dx_A"],
                "dy_A": proxy["dy_A"],
                "dz_A": proxy["dz_A"],
                "neighbor_count": proxy["neighbor_count"],
                "strain_trace": proxy["strain_trace"],
                "von_mises_strain_proxy": proxy["von_mises_strain_proxy"],
                "d2min_A2": proxy["d2min_A2"],
            }
        )

    stress_rows: list[dict[str, Any]] = []
    strain_rows: list[dict[str, Any]] = []
    for bin_index in range(n_bins):
        z_lo = z_min + bin_index * bin_width_a
        z_hi = z_lo + bin_width_a
        bin_atom_ids = [
            atom_id
            for atom_id, atom in nvt["atoms"].items()
            if (z_lo <= atom["position"][2] < z_hi)
            or (bin_index == n_bins - 1 and z_lo <= atom["position"][2] <= z_hi)
        ]
        if not bin_atom_ids:
            continue
        volume = area * bin_width_a
        phase_counts = {
            "Al_slab": sum(1 for atom_id in bin_atom_ids if nvt["atoms"][atom_id]["phase"] == "Al_slab"),
            "Fe4Al13_slab": sum(1 for atom_id in bin_atom_ids if nvt["atoms"][atom_id]["phase"] == "Fe4Al13_slab"),
        }
        sum_stress = np.sum([stress_atoms[atom_id]["stress"] for atom_id in bin_atom_ids], axis=0)
        sigma = -sum_stress[:3] / volume * BAR_TO_GPA
        shear = -sum_stress[3:] / volume * BAR_TO_GPA
        hydro = float(np.mean(sigma))
        stress_rows.append(
            {
                "bin_index": bin_index,
                "z_lo_A": z_lo,
                "z_hi_A": z_hi,
                "z_center_A": 0.5 * (z_lo + z_hi),
                "atom_count": len(bin_atom_ids),
                "Al_slab_atoms": phase_counts["Al_slab"],
                "Fe4Al13_slab_atoms": phase_counts["Fe4Al13_slab"],
                "sigma_xx_GPa": float(sigma[0]),
                "sigma_yy_GPa": float(sigma[1]),
                "sigma_zz_GPa": float(sigma[2]),
                "sigma_xy_GPa": float(shear[0]),
                "sigma_xz_GPa": float(shear[1]),
                "sigma_yz_GPa": float(shear[2]),
                "hydrostatic_GPa": hydro,
                "mean_pe_atom_eV": mean_or_none([stress_atoms[atom_id]["pe_atom_eV"] for atom_id in bin_atom_ids]),
            }
        )

        proxy_values = [strain[atom_id] for atom_id in bin_atom_ids]
        vm_values = [float(p["von_mises_strain_proxy"]) for p in proxy_values if p["von_mises_strain_proxy"] is not None]
        trace_values = [float(p["strain_trace"]) for p in proxy_values if p["strain_trace"] is not None]
        d2_values = [float(p["d2min_A2"]) for p in proxy_values if p["d2min_A2"] is not None]
        disp_values = [float(p["displacement_A"]) for p in proxy_values]
        strain_rows.append(
            {
                "bin_index": bin_index,
                "z_lo_A": z_lo,
                "z_hi_A": z_hi,
                "z_center_A": 0.5 * (z_lo + z_hi),
                "atom_count": len(bin_atom_ids),
                "Al_slab_atoms": phase_counts["Al_slab"],
                "Fe4Al13_slab_atoms": phase_counts["Fe4Al13_slab"],
                "mean_displacement_A": mean_or_none(disp_values),
                "max_displacement_A": max_or_none(disp_values),
                "mean_dx_A": mean_or_none([float(p["dx_A"]) for p in proxy_values]),
                "mean_dy_A": mean_or_none([float(p["dy_A"]) for p in proxy_values]),
                "mean_dz_A": mean_or_none([float(p["dz_A"]) for p in proxy_values]),
                "mean_von_mises_strain_proxy": mean_or_none(vm_values),
                "max_von_mises_strain_proxy": max_or_none(vm_values),
                "mean_strain_trace": mean_or_none(trace_values),
                "mean_d2min_A2": mean_or_none(d2_values),
                "max_d2min_A2": max_or_none(d2_values),
                "atoms_with_strain_fit": len(vm_values),
            }
        )

    write_csv(stress_profile_csv, stress_rows)
    write_csv(strain_profile_csv, strain_rows)
    write_csv(atom_diagnostics_csv, atom_rows)

    al_z_max = max(atom["position"][2] for atom in nvt["atoms"].values() if atom["phase"] == "Al_slab")
    fe_z_min = min(atom["position"][2] for atom in nvt["atoms"].values() if atom["phase"] == "Fe4Al13_slab")
    interface_z = 0.5 * (al_z_max + fe_z_min)

    by_phase: dict[str, dict[str, Any]] = {}
    for phase in ["Al_slab", "Fe4Al13_slab"]:
        phase_atom_ids = [atom_id for atom_id, atom in nvt["atoms"].items() if atom["phase"] == phase]
        phase_volume = area * (max(nvt["atoms"][atom_id]["position"][2] for atom_id in phase_atom_ids) - min(nvt["atoms"][atom_id]["position"][2] for atom_id in phase_atom_ids))
        phase_stress = np.sum([stress_atoms[atom_id]["stress"] for atom_id in phase_atom_ids], axis=0)
        phase_sigma = -phase_stress[:3] / phase_volume * BAR_TO_GPA if phase_volume > 0 else np.array([math.nan] * 3)
        phase_strain = [strain[atom_id] for atom_id in phase_atom_ids]
        by_phase[phase] = {
            "atom_count": len(phase_atom_ids),
            "z_min_A": min(nvt["atoms"][atom_id]["position"][2] for atom_id in phase_atom_ids),
            "z_max_A": max(nvt["atoms"][atom_id]["position"][2] for atom_id in phase_atom_ids),
            "sigma_xx_GPa": float(phase_sigma[0]),
            "sigma_yy_GPa": float(phase_sigma[1]),
            "sigma_zz_GPa": float(phase_sigma[2]),
            "hydrostatic_GPa": float(np.mean(phase_sigma)),
            "mean_displacement_A": mean_or_none([float(p["displacement_A"]) for p in phase_strain]),
            "max_displacement_A": max_or_none([float(p["displacement_A"]) for p in phase_strain]),
            "mean_von_mises_strain_proxy": mean_or_none(
                [float(p["von_mises_strain_proxy"]) for p in phase_strain if p["von_mises_strain_proxy"] is not None]
            ),
            "mean_d2min_A2": mean_or_none([float(p["d2min_A2"]) for p in phase_strain if p["d2min_A2"] is not None]),
        }

    high_hydro = max(stress_rows, key=lambda row: abs(float(row["hydrostatic_GPa"])))
    high_strain = max(
        [row for row in strain_rows if row["mean_von_mises_strain_proxy"] is not None],
        key=lambda row: float(row["mean_von_mises_strain_proxy"]),
    )

    summary = {
        "minimized_data": str(minimized_data),
        "nvt_data": str(nvt_data),
        "stress_dump": str(stress_dump),
        "metadata": str(metadata_path),
        "stress_profile_csv": str(stress_profile_csv),
        "strain_profile_csv": str(strain_profile_csv),
        "atom_diagnostics_csv": str(atom_diagnostics_csv),
        "bin_width_A": bin_width_a,
        "neighbor_cutoff_A": neighbor_cutoff_a,
        "total_atoms": len(nvt["atoms"]),
        "Al_type_1": sum(1 for atom in nvt["atoms"].values() if atom["type"] == 1),
        "Fe_type_2": sum(1 for atom in nvt["atoms"].values() if atom["type"] == 2),
        "box": nvt["box"],
        "inplane_area_A2": area,
        "interface_z_A": interface_z,
        "Al_slab_z_max_A": al_z_max,
        "Fe4Al13_slab_z_min_A": fe_z_min,
        "phase_summary": by_phase,
        "highest_abs_hydrostatic_bin": high_hydro,
        "highest_mean_strain_proxy_bin": high_strain,
        "notes": [
            "stress/atom uses virial only; bin stresses are converted with sigma = -sum(stress_atom)/bin_volume.",
            "strain is a single-snapshot local affine proxy relative to data.interface_minimized, not an OVITO Atomic Strain result.",
            "No 120 MPa, fix addforce, NPT, or stress scenario was used.",
        ],
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimized-data", type=Path, default=DEFAULT_TRIAL_DIR / "data.interface_minimized")
    parser.add_argument("--nvt-data", type=Path, default=DEFAULT_TRIAL_DIR / "data.interface_nvt_300k")
    parser.add_argument("--stress-dump", type=Path, default=DEFAULT_TRIAL_DIR / "dump.interface_unloaded_stress_run0.lammpstrj")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--stress-profile-csv", type=Path, default=ROOT / "results/tables/interface_trial_001_unloaded_stress_profile.csv")
    parser.add_argument("--strain-profile-csv", type=Path, default=ROOT / "results/tables/interface_trial_001_unloaded_strain_profile.csv")
    parser.add_argument("--atom-diagnostics-csv", type=Path, default=ROOT / "results/tables/interface_trial_001_unloaded_atom_diagnostics.csv")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_TRIAL_DIR / "interface_unloaded_diagnostics_summary.json")
    parser.add_argument("--bin-width-a", type=float, default=5.0)
    parser.add_argument("--neighbor-cutoff-a", type=float, default=4.0)
    args = parser.parse_args()

    summary = summarize(
        minimized_data=args.minimized_data,
        nvt_data=args.nvt_data,
        stress_dump=args.stress_dump,
        metadata_path=args.metadata,
        stress_profile_csv=args.stress_profile_csv,
        strain_profile_csv=args.strain_profile_csv,
        atom_diagnostics_csv=args.atom_diagnostics_csv,
        output_json=args.output_json,
        bin_width_a=args.bin_width_a,
        neighbor_cutoff_a=args.neighbor_cutoff_a,
    )
    print(f"atoms: {summary['total_atoms']}")
    print(f"in-plane area A^2: {summary['inplane_area_A2']}")
    print(f"interface z A: {summary['interface_z_A']}")
    print("phase summary:")
    for phase, data in summary["phase_summary"].items():
        print(
            f"  {phase}: atoms={data['atom_count']} hydrostatic_GPa={data['hydrostatic_GPa']} "
            f"mean_vm_proxy={data['mean_von_mises_strain_proxy']}"
        )
    print(f"highest abs hydrostatic bin: {summary['highest_abs_hydrostatic_bin']}")
    print(f"highest mean strain proxy bin: {summary['highest_mean_strain_proxy_bin']}")
    print(f"json: {args.output_json}")
    print(f"stress csv: {args.stress_profile_csv}")
    print(f"strain csv: {args.strain_profile_csv}")
    print(f"atom csv: {args.atom_diagnostics_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
