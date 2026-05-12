#!/usr/bin/env python3
"""Convert an interface stress to total and per-atom force."""

from __future__ import annotations

import argparse
import json


EV_PER_ANGSTROM_TO_NEWTON = 1.602176634e-9


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sigma_mpa", type=float)
    parser.add_argument("area_nm2", type=float)
    parser.add_argument("n_atoms", type=int)
    args = parser.parse_args()

    if args.area_nm2 <= 0:
        raise ValueError("area_nm2 must be positive")
    if args.n_atoms <= 0:
        raise ValueError("n_atoms must be positive")

    sigma_pa = args.sigma_mpa * 1.0e6
    area_m2 = args.area_nm2 * 1.0e-18
    f_total_n = sigma_pa * area_m2
    f_atom_n = f_total_n / args.n_atoms
    f_atom_ev_per_a = f_atom_n / EV_PER_ANGSTROM_TO_NEWTON

    result = {
        "sigma_mpa": args.sigma_mpa,
        "area_nm2": args.area_nm2,
        "n_atoms": args.n_atoms,
        "F_total_N": f_total_n,
        "F_atom_N": f_atom_n,
        "F_atom_eV_per_A": f_atom_ev_per_a,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
