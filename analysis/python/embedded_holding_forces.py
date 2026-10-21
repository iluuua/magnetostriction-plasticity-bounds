#!/usr/bin/env python3
"""Forces that keep the inclusion in its given shape.

in.static_pair fixes the inclusion atoms while the matrix relaxes, then
releases them and evaluates the forces once (run 0). In the strained cell those
forces push the inclusion back towards its unstrained shape: they are the
matrix pressing on it plus the inclusion's own elastic resistance. The force
needed to hold the shape is their negative, taken relative to the reference
cell (same atoms, eps = 0). In a magnetostrictive particle this is the role of
the magnetic forces.

Inclusion atoms are grouped by the polar angle theta from the field axis +x in
sectors of 15 degrees over all azimuths. Summed over a sector, the internal
forces of the inclusion cancel and the external force remains; divided by the
area of the sphere in that sector, it is a traction (MPa). Reported per sector:
the radial component (positive outward) and the component along theta.

    python analysis/python/embedded_holding_forces.py --control ref.forces.lammpstrj \
        --strained plus.forces.lammpstrj --radius 25 --out holding_forces.json
"""
from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path

import numpy as np

EV_PER_A3_TO_MPA = 160217.66
SECTOR_DEG = 15.0


def read_forces(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    n = int(lines[lines.index("ITEM: NUMBER OF ATOMS") + 1])
    a = next(k for k, l in enumerate(lines) if l.startswith("ITEM: ATOMS"))
    d = np.loadtxt(io.StringIO("\n".join(lines[a + 1:a + 1 + n])))
    d = d[np.argsort(d[:, 0])]
    return d[:, 0].astype(int), d[:, 2:5], d[:, 5:8]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--control", type=Path, required=True)
    ap.add_argument("--strained", type=Path, required=True)
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    ids, pos, f0 = read_forces(a.control)
    ids1, _, f1 = read_forces(a.strained)
    if not np.array_equal(ids, ids1):
        raise SystemExit("different atoms in the two force dumps")
    hold = -(f1 - f0)                                   # eV/A, force needed to keep the shape
    c = pos.mean(axis=0)
    r = pos - c
    rn = np.linalg.norm(r, axis=1)
    n = r / rn[:, None]
    theta = np.degrees(np.arccos(np.clip(n[:, 0], -1, 1)))
    rho = np.hypot(r[:, 1], r[:, 2])
    e_rho = np.zeros_like(r)
    e_rho[:, 1:] = r[:, 1:] / np.maximum(rho, 1e-9)[:, None]
    e_t = np.cos(np.radians(theta))[:, None] * e_rho - np.sin(np.radians(theta))[:, None] * np.array([1.0, 0, 0])
    rows = []
    for lo in np.arange(0, 180, SECTOR_DEG):
        sel = (theta >= lo) & (theta < lo + SECTOR_DEG)
        area = 2 * math.pi * a.radius ** 2 * (math.cos(math.radians(lo)) - math.cos(math.radians(lo + SECTOR_DEG)))
        # sum of vectors, then projected on the sector's mid-plane directions
        mid = math.radians(lo + SECTOR_DEG / 2)
        tot_r = float(np.sum(np.einsum("pi,pi->p", hold[sel], n[sel])))
        tot_t = float(np.sum(np.einsum("pi,pi->p", hold[sel], e_t[sel])))
        rows.append({"theta_deg": lo + SECTOR_DEG / 2, "n_atoms": int(sel.sum()),
                     "radial_MPa": tot_r / area * EV_PER_A3_TO_MPA,
                     "tangential_MPa": tot_t / area * EV_PER_A3_TO_MPA})
    net = hold.sum(axis=0)
    res = {"control": str(a.control), "strained": str(a.strained), "radius_A": a.radius,
           "sector_deg": SECTOR_DEG, "net_force_eV_per_A": net.tolist(),
           "convention": "force needed to keep the given shape; radial positive outward",
           "sectors": rows}
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for q in rows:
        print("theta %5.1f  n=%4d  radial %7.1f MPa  tangential %7.1f MPa"
              % (q["theta_deg"], q["n_atoms"], q["radial_MPa"], q["tangential_MPa"]))
    print("net force on the inclusion (should be ~0):", np.round(net, 3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
