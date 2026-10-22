#!/usr/bin/env python3
"""Where is the edge dislocation in the relaxed slabs, and did the field move it?

Runs OVITO's dislocation analysis (DXA, FCC) on relaxed slab dumps written by
lammps/embedded_inclusion/in.disl_relax (ctl: sphere unstrained; fld: sphere
given +eps; rev: strain removed again) and reports for each:

  - the segments lying on the glide plane (|z - z_glide| < 6 A) and longer than
    half the line length: the two Shockley partials of the edge dislocation,
    with the mean x of each, their mean (the core) and the spread of x along the
    line (bowing);
  - every other segment, with its distance from the sphere surface.

The answer to "does the field move the dislocation, and does it come back" is
the core shift fld - ctl and rev - ctl, compared with the lattice period b/2.
The exit status is 0 when the control state is clean (exactly two glide-plane
partials, no other segment farther than 5 A from the sphere surface), which the
queue uses as the condition for the loading ramps.

    python analysis/python/embedded_disl_states.py --dir runs/.../disl --meta slab_metadata.json \
        --states ctl fld rev --out states.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HALF_B = 2.863782 / 2


def analyse(path: Path, meta: dict) -> dict:
    from ovito.io import import_file
    from ovito.modifiers import DislocationAnalysisModifier
    pipe = import_file(str(path))
    pipe.source.data.cell_.pbc = (True, True, False)
    pipe.modifiers.append(DislocationAnalysisModifier(
        input_crystal_structure=DislocationAnalysisModifier.Lattice.FCC))
    d = pipe.compute()
    ly = float(d.cell[1][1])
    lx = float(d.cell[0][0])
    zg = meta["z_glide_A"]
    sph = meta.get("sphere")
    c = np.array(sph["centre_A"]) if sph else None
    partials, other = [], []
    for s in d.dislocations.segments:
        p = np.asarray(s.points)
        z = float(p[:, 2].mean())
        if abs(z - zg) < 6.0 and s.length > 0.5 * ly:
            # unwrap x along the line before averaging
            x = np.unwrap(p[:, 0] / lx * 2 * np.pi) * lx / (2 * np.pi)
            partials.append({"x_mean_A": float(np.mean(x) % lx), "x_spread_A": float(np.ptp(x)),
                             "z_mean_A": z, "length_A": float(s.length),
                             "burgers": [round(float(v), 4) for v in s.true_burgers_vector]})
        else:
            dist = None
            if c is not None:
                r = p - c
                r[:, :2] -= np.array([lx, ly]) * np.round(r[:, :2] / np.array([lx, ly]))
                dist = float(np.linalg.norm(r, axis=1).min() - sph["radius_A"])
            other.append({"length_A": round(float(s.length), 2), "z_mean_A": round(z, 2),
                          "min_distance_from_sphere_surface_A": None if dist is None else round(dist, 2)})
    core = None
    if len(partials) == 2:
        xs = sorted(q["x_mean_A"] for q in partials)
        if xs[1] - xs[0] > lx / 2:                     # the pair straddles the boundary
            xs = [xs[1], xs[0] + lx]
        core = float(np.mean(xs) % lx)
    return {"file": path.name, "partials": partials, "core_x_A": core,
            "splitting_A": None if core is None else float(abs(partials[0]["x_mean_A"] - partials[1]["x_mean_A"])),
            "other_segments": other}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--meta", type=Path, required=True)
    ap.add_argument("--states", nargs="+", default=["ctl", "fld", "rev"])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    meta = json.loads(a.meta.read_text(encoding="utf-8"))
    lx = meta["box_A"][0]
    res = {"z_glide_A": meta["z_glide_A"], "half_b_A": HALF_B, "states": {}}
    for s in a.states:
        p = a.dir / f"{s}.relaxed.lammpstrj"
        if p.exists():
            res["states"][s] = analyse(p, meta)
    st = res["states"]
    if "ctl" in st and st["ctl"]["core_x_A"] is not None:
        x0 = st["ctl"]["core_x_A"]
        if meta.get("sphere"):
            res["ctl_core_minus_sphere_x_A"] = float((x0 - meta["sphere"]["centre_A"][0] + lx / 2) % lx - lx / 2)
        for s in ("fld", "rev"):
            if s in st and st[s]["core_x_A"] is not None:
                dx = (st[s]["core_x_A"] - x0 + lx / 2) % lx - lx / 2
                res[f"core_shift_{s}_minus_ctl_A"] = float(dx)
                res[f"core_shift_{s}_minus_ctl_in_half_b"] = float(dx / HALF_B)
    ctl = st.get("ctl")
    clean = bool(ctl and len(ctl["partials"]) == 2 and all(
        o["min_distance_from_sphere_surface_A"] is not None and o["min_distance_from_sphere_surface_A"] <= 5.0
        for o in ctl["other_segments"]))
    res["control_clean"] = clean
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "states"}, indent=1))
    for s, r in st.items():
        print("%-4s core %s A, partials %d, other segments %d" % (
            s, "%.2f" % r["core_x_A"] if r["core_x_A"] is not None else "-", len(r["partials"]),
            len(r["other_segments"])))
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
