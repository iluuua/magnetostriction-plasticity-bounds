#!/usr/bin/env python3
"""Calculate per-atom loading forces for interface trial_001 templates.

This script only prepares numbers for future controlled loading. It does not run
LAMMPS and does not create any loaded trajectory.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "lammps/02_interface_relax/trial_001/data.interface_nvt_300k_long"
DEFAULT_METADATA = ROOT / "structures/interface/flat_interface/trial_001/interface_metadata.json"
DEFAULT_OUTPUT_CSV = ROOT / "results/tables/interface_trial_001_loading_force_table.csv"
DEFAULT_INTERFACE_Z_A = 40.16445
DEFAULT_REGION_WIDTH_A = 8.0
DEFAULT_SIGMAS_MPA = [0.0, 60.0, 120.0, 147.0, 200.0]
EV_PER_ANGSTROM_TO_NEWTON = 1.602176634e-9


@dataclass
class Atom:
    atom_id: int
    atom_type: int
    x: float
    y: float
    z: float
    phase: str = ""


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
        atoms.append(Atom(atom_id=atom_id, atom_type=atom_type, x=x, y=y, z=z))

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


def assign_phases(atoms: list[Atom], metadata: dict[str, Any]) -> str:
    al_slab_atoms = int(metadata.get("actual_atoms", {}).get("Al_slab_atoms", 0))
    if al_slab_atoms <= 0:
        raise ValueError("metadata actual_atoms.Al_slab_atoms is required")
    for atom in atoms:
        atom.phase = "Al_slab" if atom.atom_id <= al_slab_atoms else "Fe4Al13_slab"
    return f"atom_id<=Al_slab_atoms ({al_slab_atoms})"


def region_atoms(atoms: list[Atom], phase: str, zlo: float, zhi: float) -> list[Atom]:
    return [atom for atom in atoms if atom.phase == phase and zlo <= atom.z <= zhi]


def count_types(atoms: list[Atom]) -> dict[str, int]:
    return {
        "Al_type_1": sum(1 for atom in atoms if atom.atom_type == 1),
        "Fe_type_2": sum(1 for atom in atoms if atom.atom_type == 2),
    }


def force_row(
    sigma_mpa: float,
    area_A2: float,
    target_atoms: int,
    target_counts: dict[str, int],
    monitor_atoms: int,
    interface_z: float,
    region_width: float,
) -> dict[str, Any]:
    sigma_pa = sigma_mpa * 1.0e6
    area_m2 = area_A2 * 1.0e-20
    f_total_n = sigma_pa * area_m2
    f_atom_n = f_total_n / target_atoms
    f_atom_eva = f_atom_n / EV_PER_ANGSTROM_TO_NEWTON
    return {
        "scenario": f"stress_{int(round(sigma_mpa)):03d}mpa",
        "sigma_MPa": sigma_mpa,
        "interface_area_A2": area_A2,
        "interface_area_nm2": area_A2 * 0.01,
        "target_region": "Fe4Al13_slab near interface",
        "target_zlo_A": interface_z,
        "target_zhi_A": interface_z + region_width,
        "target_atoms": target_atoms,
        "target_Al_type_1_atoms": target_counts["Al_type_1"],
        "target_Fe_type_2_atoms": target_counts["Fe_type_2"],
        "monitor_region": "Al_slab near interface",
        "monitor_zlo_A": interface_z - region_width,
        "monitor_zhi_A": interface_z,
        "monitor_atoms": monitor_atoms,
        "F_total_N": f_total_n,
        "F_atom_N": f_atom_n,
        "F_atom_eV_per_A": f_atom_eva,
        "compression_addforce_z_eV_per_A": -f_atom_eva,
        "tension_addforce_z_eV_per_A": f_atom_eva,
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scenario",
        "sigma_MPa",
        "interface_area_A2",
        "interface_area_nm2",
        "target_region",
        "target_zlo_A",
        "target_zhi_A",
        "target_atoms",
        "target_Al_type_1_atoms",
        "target_Fe_type_2_atoms",
        "monitor_region",
        "monitor_zlo_A",
        "monitor_zhi_A",
        "monitor_atoms",
        "F_total_N",
        "F_atom_N",
        "F_atom_eV_per_A",
        "compression_addforce_z_eV_per_A",
        "tension_addforce_z_eV_per_A",
        "phase_assignment",
        "data_file",
        "metadata_file",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    parsed = parse_lammps_data(args.data)
    metadata = json.loads(args.metadata.read_text())
    phase_assignment = assign_phases(parsed["atoms"], metadata)
    area_A2 = in_plane_area_A2(parsed["box"])

    target = region_atoms(
        parsed["atoms"],
        "Fe4Al13_slab",
        args.interface_z,
        args.interface_z + args.region_width,
    )
    monitor = region_atoms(
        parsed["atoms"],
        "Al_slab",
        args.interface_z - args.region_width,
        args.interface_z,
    )
    if not target:
        raise ValueError("Target loading region has zero atoms")

    target_counts = count_types(target)
    rows = [
        force_row(
            sigma_mpa=sigma,
            area_A2=area_A2,
            target_atoms=len(target),
            target_counts=target_counts,
            monitor_atoms=len(monitor),
            interface_z=args.interface_z,
            region_width=args.region_width,
        )
        for sigma in args.sigmas
    ]
    for row in rows:
        row["phase_assignment"] = phase_assignment
        row["data_file"] = str(args.data)
        row["metadata_file"] = str(args.metadata)

    write_csv(rows, args.output_csv)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--interface-z", type=float, default=DEFAULT_INTERFACE_Z_A)
    parser.add_argument("--region-width", type=float, default=DEFAULT_REGION_WIDTH_A)
    parser.add_argument("--sigmas", type=float, nargs="+", default=DEFAULT_SIGMAS_MPA)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    args = parser.parse_args()

    rows = run(args)
    print(f"data: {args.data}")
    print(f"metadata: {args.metadata}")
    print(f"interface_z_A: {args.interface_z}")
    print(f"region_width_A: {args.region_width}")
    print(f"output_csv: {args.output_csv}")
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
