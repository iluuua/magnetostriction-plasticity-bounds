#!/usr/bin/env python3
"""Convert Al13Fe4 CIF/POSCAR structure to LAMMPS atomic data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ase.io import write
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.io.cif import CifParser
from pymatgen.io.vasp import Poscar


SPECIES_TO_TYPE = {"Al": 1, "Fe": 2}


def load_structure(path: Path) -> Structure:
    suffix = path.suffix.lower()
    if suffix == ".cif":
        return CifParser(str(path), occupancy_tolerance=1.0).parse_structures(primitive=False)[0]
    return Structure.from_file(str(path))


def validate_composition(structure: Structure) -> None:
    amounts = structure.composition.get_el_amt_dict()
    species = set(amounts)
    if species != set(SPECIES_TO_TYPE):
        raise ValueError(f"Expected only Al and Fe, got {sorted(species)}")
    al = amounts["Al"]
    fe = amounts["Fe"]
    if abs(al / fe - 13 / 4) > 1e-8:
        raise ValueError(f"Expected Al:Fe = 13:4, got Al={al:g}, Fe={fe:g}")


def cell_metadata(structure: Structure) -> dict[str, object]:
    lattice = structure.lattice
    return {
        "matrix_angstrom": [[float(x) for x in row] for row in lattice.matrix],
        "lengths_angstrom": [float(x) for x in lattice.abc],
        "angles_degree": [float(x) for x in lattice.angles],
        "volume_angstrom3": float(lattice.volume),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("structures/raw/Al13Fe4/al13fe4.cif"),
        help="Input CIF or POSCAR path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("structures/converted/Al13Fe4/al13fe4.data"),
        help="Output LAMMPS data path.",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("structures/converted/Al13Fe4/al13fe4_metadata.json"),
        help="Output metadata JSON path.",
    )
    parser.add_argument(
        "--poscar",
        type=Path,
        default=Path("structures/raw/Al13Fe4/POSCAR"),
        help="Optional POSCAR copy written from the parsed structure.",
    )
    args = parser.parse_args()

    structure = load_structure(args.input)
    validate_composition(structure)

    atoms = AseAtomsAdaptor.get_atoms(structure)
    atoms.pbc = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write(
        args.output,
        atoms,
        format="lammps-data",
        atom_style="atomic",
        specorder=["Al", "Fe"],
        masses=True,
    )

    args.poscar.parent.mkdir(parents=True, exist_ok=True)
    Poscar(structure).write_file(str(args.poscar))

    metadata = {
        "source": str(args.input),
        "formula": structure.composition.reduced_formula,
        "full_formula": structure.composition.formula,
        "n_atoms": len(structure),
        "cell": cell_metadata(structure),
        "species_to_lammps_type": SPECIES_TO_TYPE,
    }
    args.metadata.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    print(f"input: {args.input}")
    print(f"output: {args.output}")
    print(f"metadata: {args.metadata}")
    print(f"formula: {metadata['formula']} ({metadata['full_formula']})")
    print(f"n_atoms: {metadata['n_atoms']}")
    print(f"cell lengths [A]: {metadata['cell']['lengths_angstrom']}")
    print(f"cell angles [deg]: {metadata['cell']['angles_degree']}")
    print(f"types: {SPECIES_TO_TYPE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
