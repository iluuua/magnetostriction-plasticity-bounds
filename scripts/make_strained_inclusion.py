#!/usr/bin/env python3
"""Give the inclusion of a relaxed reference cell its magnetostrictive strain.

The input is the relaxed reference written by lammps/embedded_inclusion/
in.relax_control. Every inclusion atom (ID > N_AL) is moved by
u = eps . (r - r_c), where r_c is the centroid of the inclusion and

    eps = EPS * diag(1, -1/2, -1/2)

is the strain of a magnetostrictive body with the field along x: it lengthens
along x by EPS and shortens along y and z by EPS/2, so its volume is unchanged
to first order. With --inclusion-from the inclusion atoms are first put at their
positions in another data file with the same atom IDs (the reference cell), so a
larger strain can be applied to a matrix already relaxed at a smaller one, or the
strain removed again (--eps 0). By default matrix atoms are not moved. With --guess the matrix
atoms are moved by the continuum displacement of the same problem (fixed box,
cubic Al of the potential, inclusion strain held at eps; see
analysis/python/embedded_inclusion_continuum.py), so that conjugate gradients
only have to remove the atomistic deviation from it. The box is not changed.

    python scripts/make_strained_inclusion.py --control run/sphere_R25.control.data \
        --n-al 114374 --eps 1.94e-3 --out run/strained.data
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def read_data(path: Path) -> tuple[list[str], list[str], list[str], np.ndarray]:
    """Header lines, atom lines split off, trailer (Velocities etc.), box lengths."""
    lines = path.read_text(encoding="utf-8").splitlines()
    i0 = next(i for i, l in enumerate(lines) if l.strip().startswith("Atoms"))
    j = i0 + 2
    atoms = []
    while j < len(lines) and lines[j].strip():
        atoms.append(lines[j])
        j += 1
    box = []
    for l in lines[:i0]:
        p = l.split()
        if len(p) >= 4 and p[-2] in ("xlo", "ylo", "zlo"):
            box.append(float(p[1]) - float(p[0]))
    return lines[:i0 + 2], atoms, lines[j:], np.array(box)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--control", type=Path, required=True)
    ap.add_argument("--n-al", type=int, required=True, help="matrix atoms have IDs 1..N_AL")
    ap.add_argument("--eps", type=float, default=1.94e-3)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--guess", action="store_true", help="start the matrix from the continuum displacement")
    ap.add_argument("--inclusion-from", type=Path, default=None,
                    help="data file whose inclusion positions the strain is applied to")
    ap.add_argument("--radius", type=float, default=25.0, help="inclusion radius for --guess, A")
    ap.add_argument("--elastic", type=Path, default=Path(__file__).resolve().parents[1]
                    / "docs/reports/meam_elastic_constants.json")
    a = ap.parse_args()

    head, atoms, tail, box = read_data(a.control)
    rows = [l.split() for l in atoms]
    ids = np.array([int(r[0]) for r in rows])
    xyz = np.array([[float(v) for v in r[2:5]] for r in rows])
    images = [r[5:8] for r in rows]               # keep image flags if present
    inc = ids > a.n_al
    if a.inclusion_from is not None:
        _, atoms_b, _, _ = read_data(a.inclusion_from)
        base = {int(r.split()[0]): [float(v) for v in r.split()[2:5]] for r in atoms_b}
        xyz[inc] = np.array([base[i] for i in ids[inc]])
    # the inclusion sits in the middle of the box and never crosses a boundary,
    # so its centroid is the plain mean of its coordinates
    rc = xyz[inc].mean(axis=0)
    eps = a.eps * np.diag([1.0, -0.5, -0.5])
    new = xyz.copy()
    new[inc] = xyz[inc] + (xyz[inc] - rc) @ eps.T
    guess_info = None
    if a.guess:
        import sys
        from scipy.ndimage import map_coordinates
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis/python"))
        import embedded_inclusion_continuum as C
        el = json.loads(a.elastic.read_text(encoding="utf-8"))["Al"]
        Cs = C.cubic_in_cell_frame(el["C11"] * 1e9, el["C12"] * 1e9, el["C44"] * 1e9)
        u, axes, e_star, e_in = C.periodic_fft_frozen(box, rc, a.radius, eps, Cs, 1.0, displacement=True)
        h = np.array([ax[1] - ax[0] for ax in axes])
        idx = (np.mod(xyz, box) / h).T                         # fractional grid coordinates
        uc = [map_coordinates(u[i], idx[:, ~inc], order=1, mode="grid-wrap") for i in range(3)]
        u0 = [map_coordinates(u[i], (np.mod(rc, box) / h)[:, None], order=1, mode="grid-wrap")[0]
              for i in range(3)]
        new[~inc] = xyz[~inc] + np.stack(uc, axis=1) - np.array(u0)
        guess_info = {"max_matrix_displacement_A": float(np.abs(np.stack(uc, 1) - np.array(u0)).max()),
                      "fft_inclusion_strain": e_in.tolist()}
    out_atoms = []
    for r, p, im in zip(rows, new, images):
        out_atoms.append(" ".join([r[0], r[1], "%.10f" % p[0], "%.10f" % p[1], "%.10f" % p[2]] + im))
    # drop velocities: the static input minimises only
    keep_tail = []
    skip = False
    for l in tail:
        if l.strip().startswith("Velocities"):
            skip = True
            continue
        if skip and l.strip() and l.strip()[0].isalpha():
            skip = False
        if not skip:
            keep_tail.append(l)
    a.out.write_text("\n".join(head + out_atoms + keep_tail) + "\n", encoding="utf-8")
    disp = np.linalg.norm(new[inc] - xyz[inc], axis=1)
    meta = {"control": str(a.control), "inclusion_from": str(a.inclusion_from), "n_al": a.n_al, "eps": a.eps,
            "strain_tensor": eps.tolist(), "inclusion_centroid_A": rc.tolist(),
            "n_inclusion_moved": int(inc.sum()), "max_displacement_A": float(disp.max()),
            "box_A": box.tolist(), "continuum_guess": guess_info}
    a.out.with_suffix(".json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
