#!/usr/bin/env python3
"""Aluminium slab with one edge dislocation, optionally with the Al13Fe4 sphere.

Geometry (Osetsky-Bacon type). Periodic along x = [1-10] (glide direction) and
y = [11-2] (dislocation line); finite along z = [111], with rigid blocks of
BLOCK_LAYERS (111) layers at the bottom and at the top. The glide plane lies
between two (111) layers; the dislocation is an edge 1/2[1-10] line along y.

The extra half-plane is put entirely into the upper half: the lower half, which
holds the inclusion, has NX columns at the natural spacing (zero far-field
strain where the inclusion sits), the upper half has NX + 1 columns over the same
length (uniform compression 1/(NX+1) along x, which exerts no glide force on a
line with b along x on a plane normal to z). The upper layers are spaced wider
by the plane-strain Poisson expansion of that compression, so the slab starts
close to zero sigma_zz. The relative registry of the halves is shifted so that
the half-period mismatch, where the core forms, lies at x0.

With --sphere the Al13Fe4 sphere (as in scripts/build_embedded_inclusion.py) is
carved into the lower half, centred at x0 + Lx/2, at height HS below the glide
plane; Al atoms within 2.2 A of it are removed.

Atom IDs: matrix first (1..N_AL), inclusion after. Types 1 Al, 2 Fe, 3 Mg, 4 Si.
Groups for the inputs are written to the metadata (z bounds of the blocks).

    python scripts/build_embedded_dislocation.py --ny 4 --out structures/embedded_inclusion/slab_peierls
    python scripts/build_embedded_dislocation.py --ny 25 --sphere --out structures/embedded_inclusion/slab_sphere_R25
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_embedded_inclusion as B  # noqa: E402

PX, PY, D111 = B.PX, B.PY, B.D111
NU = 0.344
BLOCK_LAYERS = 3


def layer_sites(n_cols: int, lx: float, ny: int, k: int, z: float, shift: float) -> np.ndarray:
    """One (111) layer: n_cols columns over lx, two-site basis, ABC offset in y."""
    p = lx / n_cols
    ly = ny * PY
    off = (k % 3) * PY / 3.0
    i, j = np.meshgrid(np.arange(n_cols), np.arange(ny), indexing="ij")
    out = []
    for sx, sy in ((0.0, 0.0), (p / 2.0, PY / 2.0)):
        x = (i.ravel() * p + sx + shift) % lx
        y = (j.ravel() * PY + sy + off) % ly
        out.append(np.column_stack([x, y, np.full(x.size, z)]))
    return np.vstack(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nx", type=int, default=44)
    ap.add_argument("--ny", type=int, default=25)
    ap.add_argument("--below", type=float, default=22.0, help="Al below the sphere, above the bottom block, A")
    ap.add_argument("--clear", type=float, default=12.0, help="glide plane above the sphere top, A")
    ap.add_argument("--above", type=float, default=24.0, help="Al above the glide plane below the top block, A")
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--sphere", action="store_true")
    ap.add_argument("--sphere-dx", type=float, default=None,
                    help="sphere centre this far ahead of the core along x, A (default half the cell)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    lx, ly = a.nx * PX, a.ny * PY
    block = BLOCK_LAYERS * D111
    # lower half: bottom block, Al below the sphere, the sphere, the clearance
    n_low = int(math.ceil((block + a.below + 2 * a.radius + a.clear) / D111))
    n_low += (-n_low) % 3                              # whole ABC repeats below the glide plane
    n_up = int(math.ceil((a.above + block) / D111))
    eps_up = -1.0 / (a.nx + 1)                         # compression of the upper half along x
    dz_up = D111 * (1.0 - NU / (1.0 - NU) * eps_up)    # plane-strain Poisson expansion
    x0 = lx / 4.0                                      # core position; the sphere goes to x0 + dx
    dx = lx / 2.0 if a.sphere_dx is None else a.sphere_dx

    sites, half = [], []
    z = 0.5 * D111
    for k in range(n_low):
        sites.append(layer_sites(a.nx, lx, a.ny, k, z, 0.0))
        half.append(np.zeros(len(sites[-1]), int))
        z += D111
    z_glide = z - 0.5 * D111
    # registry: upper column j sits at j*lx/(nx+1) + s, lower column j at j*PX, so the
    # offset of column j is s - j*dp with dp = PX - lx/(nx+1). The core forms where
    # the halves are half a period out of registry, s - j*dp = PX/2; put that at x0.
    dp = PX - lx / (a.nx + 1)
    shift = PX / 2.0 + (x0 / PX) * dp
    z = z_glide + 0.5 * dz_up
    for k in range(n_low, n_low + n_up):
        sites.append(layer_sites(a.nx + 1, lx, a.ny, k, z, shift))
        half.append(np.ones(len(sites[-1]), int))
        z += dz_up
    z_top = z - 0.5 * dz_up + 0.5 * D111
    al = np.vstack(sites)
    half = np.concatenate(half)

    meta = {"created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "builder": "scripts/build_embedded_dislocation.py",
            "box_A": [lx, ly, z_top], "periods": {"nx": a.nx, "ny": a.ny},
            "layers": {"lower": n_low, "upper": n_up, "block": BLOCK_LAYERS},
            "upper_compression_x": eps_up, "upper_layer_spacing_A": dz_up,
            "z_glide_A": z_glide, "x_core_initial_A": x0,
            "z_bottom_block_top_A": block, "z_top_block_bottom_A": z_top - block - 0.5 * D111,
            "burgers_A": PX, "sphere": None}
    inc, inc_t = np.zeros((0, 3)), np.zeros(0, int)
    if a.sphere:
        zc = z_glide - a.clear - a.radius
        centre = np.array([(x0 + dx) % lx, ly / 2, zc])
        inc, inc_t, info = B.carve_inclusion("sphere", a.radius, centre, lx, ly, None)
        box3 = np.array([lx, ly, 1e6])                 # no z periodicity for the clearance
        d = B.pbc_nearest(al, inc, box3)
        inside = np.sum((al - centre) ** 2, axis=1) <= a.radius ** 2
        keep = (d >= B.CLEARANCE_A) & ~inside
        al, half = al[keep], half[keep]
        meta["sphere"] = {"centre_A": centre.tolist(), "radius_A": a.radius, "ahead_of_core_A": dx, **info,
                          "matrix_removed": int((~keep).sum())}
    pos = np.vstack([al, inc])
    types = np.concatenate([np.ones(len(al), int), inc_t])
    a.out.mkdir(parents=True, exist_ok=True)
    name = a.out.name
    box = np.array([lx, ly, z_top])
    # write with a little vacuum margin in z handled by the input (boundary p p f)
    B.write_data(a.out / f"data.{name}", pos, types, box,
                 f"Al slab with one edge dislocation{' and an Al13Fe4 sphere' if a.sphere else ''}; "
                 f"matrix IDs 1..{len(al)}")
    meta.update({"n_atoms": int(len(pos)), "N_AL": int(len(al)), "n_inclusion": int(len(inc)),
                 "n_upper_half_atoms": int(half.sum())})
    (a.out / f"{name}_metadata.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("box_A", "layers", "z_glide_A", "x_core_initial_A",
                                            "n_atoms", "N_AL", "n_inclusion")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
