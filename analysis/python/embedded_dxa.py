#!/usr/bin/env python3
"""Does the given strain of the inclusion create defects in the aluminium matrix?

For each static configuration (reference, +eps, -eps) the script runs OVITO's
adaptive common neighbour analysis on the matrix atoms and its dislocation
analysis (DXA, FCC), once with the inclusion atoms kept and once with them
removed (the inclusion is then a cavity with a free surface, so the interface
cannot be read as a defect network). Reported per configuration:

  - matrix atoms that are not FCC, in shells of distance d from the sphere
    surface (d < 3 A, 3-6 A, > 6 A);
  - every DXA segment: length, Burgers vector, centre, distance from the surface.

A segment shorter than the cell period is not by itself a dislocation; segments
that appear in the same place in the reference cell are interface artefacts of
the construction, not an effect of the strain.

    python analysis/python/embedded_dxa.py --dir runs/.../static --n-al 114374 \
        --radius 25 --out runs/.../static/dxa.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

STRUCT = {0: "other", 1: "FCC", 2: "HCP", 3: "BCC", 4: "ICO"}


def analyse(path: Path, n_al: int, radius: float, drop_inclusion: bool) -> dict:
    from ovito.io import import_file
    from ovito.modifiers import (CommonNeighborAnalysisModifier, DislocationAnalysisModifier,
                                 ExpressionSelectionModifier, DeleteSelectedModifier)
    kw = {"atom_style": "atomic"} if path.name.startswith("data.") or path.suffix == ".data" else {}
    pipe = import_file(str(path), **kw)
    pipe.source.data.cell_.pbc = (True, True, True)
    if drop_inclusion:
        pipe.modifiers.append(ExpressionSelectionModifier(expression="ParticleIdentifier > %d" % n_al))
        pipe.modifiers.append(DeleteSelectedModifier())
    pipe.modifiers.append(CommonNeighborAnalysisModifier())
    pipe.modifiers.append(DislocationAnalysisModifier(
        input_crystal_structure=DislocationAnalysisModifier.Lattice.FCC))
    d = pipe.compute()
    ids = np.asarray(d.particles["Particle Identifier"])
    pos = np.asarray(d.particles.positions)
    st = np.asarray(d.particles["Structure Type"])
    cell = np.asarray(d.cell)[:3, :3].diagonal()
    origin = np.asarray(d.cell)[:3, 3]
    full = import_file(str(path), **kw).compute()
    fid = np.asarray(full.particles["Particle Identifier"])
    fpos = np.asarray(full.particles.positions)
    centre = fpos[fid > n_al].mean(axis=0)

    def dist(p):
        r = p - centre
        r -= cell * np.round(r / cell)
        return np.linalg.norm(r, axis=-1) - radius

    mat = ids <= n_al
    dm = dist(pos[mat])
    shells = {}
    for name, lo, hi in (("d<3", -1e9, 3.0), ("3<=d<6", 3.0, 6.0), ("d>=6", 6.0, 1e9)):
        m = (dm >= lo) & (dm < hi)
        counts = {STRUCT.get(k, str(k)): int(np.sum(st[mat][m] == k)) for k in np.unique(st[mat][m])}
        shells[name] = {"n_atoms": int(m.sum()), "by_structure": counts}
    segs = []
    for s in d.dislocations.segments:
        pts = np.asarray(s.points)
        c = pts.mean(axis=0)
        segs.append({"length_A": round(float(s.length), 2),
                     "burgers": [round(float(v), 4) for v in s.true_burgers_vector],
                     "centre_A": (c - origin).round(2).tolist(),
                     "distance_from_surface_A": round(float(dist(c[None, :])[0]), 2)})
    return {"file": path.name, "inclusion_removed": drop_inclusion,
            "matrix_shells": shells, "n_segments": len(segs),
            "total_length_A": round(sum(s["length_A"] for s in segs), 2), "segments": segs}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--cases", nargs="*", default=["ref", "plus", "minus"])
    ap.add_argument("--suffix", default="static.lammpstrj")
    ap.add_argument("--n-al", type=int, required=True)
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    res = {"dir": str(a.dir), "radius_A": a.radius, "cases": {}}
    for case in a.cases:
        path = a.dir / f"{case}.{a.suffix}"
        if not path.exists():
            continue
        res["cases"][case] = [analyse(path, a.n_al, a.radius, drop) for drop in (False, True)]
        for r in res["cases"][case]:
            far = r["matrix_shells"]["d>=6"]
            print("%-6s inclusion %-7s  segments %d (%.1f A)  matrix d>=6 A non-FCC %d of %d" % (
                case, "removed" if r["inclusion_removed"] else "kept", r["n_segments"], r["total_length_A"],
                far["n_atoms"] - far["by_structure"].get("FCC", 0), far["n_atoms"]))
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
