#!/usr/bin/env python3
"""What the aluminium next to the held inclusion does: strain, stress and density.

From the static pair (in.static_pair dumps ref, plus, minus) the linear part of the
response, (plus - minus)/2, is analysed per matrix atom:

  atomic strain   least-squares displacement gradient over the neighbours within
                  3.2 A in the reference cell (the twelve nearest in fcc), symmetrised;
  stress check    the per-atom virial stress against C : (atomic strain) with the
                  cubic constants of the potential, as a regression slope in 1 A shells
                  of distance d from the inclusion surface: 1 means the atoms carry
                  the stress of bulk aluminium for their strain, less than 1 means the
                  layer is more compliant than bulk;
  density         number of matrix atoms in 0.5 A shells around the inclusion centre,
                  relative to bulk aluminium (1 / 16.6075 A^3);
  cavity          the volume left for the inclusion, V_box - N_Al * 16.6075 A^3,
                  as an equivalent radius, against the inclusion radius.

    python analysis/python/embedded_interface.py --dir runs/.../static --n-al 114374 \
        --out docs/reports/embedded_interface.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

import embedded_inclusion_continuum as C
import embedded_inclusion_field as F

OMEGA = 16.6075


def atomic_strain(pos: np.ndarray, u: np.ndarray, box: np.ndarray, sel: np.ndarray,
                  cutoff: float = 3.2) -> np.ndarray:
    """Symmetric displacement gradient per selected atom (N_sel, 3, 3)."""
    tree = cKDTree(np.mod(pos, box), boxsize=box)
    idx = np.flatnonzero(sel)
    out = np.full((len(idx), 3, 3), np.nan)
    for k, i in enumerate(idx):
        nb = [j for j in tree.query_ball_point(np.mod(pos[i], box), cutoff) if j != i]
        if len(nb) < 6:
            continue
        dx = pos[nb] - pos[i]
        dx -= box * np.round(dx / box)
        du = u[nb] - u[i]
        G = np.linalg.lstsq(dx, du, rcond=None)[0].T          # du = G dx
        out[k] = 0.5 * (G + G.T)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--n-al", type=int, required=True)
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--dmax", type=float, default=30.0)
    ap.add_argument("--elastic", type=Path,
                    default=Path(__file__).resolve().parents[2] / "docs/reports/meam_elastic_constants.json")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    ids, pos0, s_ref, box = F.read_dump(a.dir / "ref.static.lammpstrj")
    _, pos_p, s_p, _ = F.read_dump(a.dir / "plus.static.lammpstrj")
    _, pos_m, s_m, _ = F.read_dump(a.dir / "minus.static.lammpstrj")
    matrix = ids <= a.n_al
    centre = pos0[~matrix].mean(axis=0)
    g = F.Geometry(pos0, centre, box, a.radius)
    dp = pos_p - pos0
    dp -= box * np.round(dp / box)
    dm = pos_m - pos0
    dm -= box * np.round(dm / box)
    u = (dp - dm) / 2
    sig = F.tensor((s_p - s_m) / 2) * F.TO_MPA                  # MPa, tension positive

    el = json.loads(a.elastic.read_text(encoding="utf-8"))["Al"]
    Cs = C.cubic_in_cell_frame(el["C11"] * 1e9, el["C12"] * 1e9, el["C44"] * 1e9) / 1e6   # MPa
    sel = matrix & (g.d < a.dmax)
    eps = atomic_strain(pos0, u, box, sel)
    pred = np.einsum("ijkl,pkl->pij", Cs, eps)
    vir = sig[sel]
    d = g.d[sel]
    ok = ~np.isnan(eps[:, 0, 0])

    def dev(t):
        return t - np.trace(t, axis1=-2, axis2=-1)[:, None, None] / 3 * np.eye(3)

    rows = []
    for lo in np.arange(0.0, a.dmax, 1.0):
        m = ok & (d >= lo) & (d < lo + 1.0)
        if m.sum() < 30:
            continue
        x, y = pred[m].reshape(-1), vir[m].reshape(-1)
        xd, yd = dev(pred[m]).reshape(-1), dev(vir[m]).reshape(-1)
        rows.append({"d_from_A": float(lo), "n": int(m.sum()),
                     "virial_over_C_eps": float(x @ y / (x @ x)),
                     "deviatoric_virial_over_C_eps": float(xd @ yd / (xd @ xd)),
                     "correlation": float(np.corrcoef(x, y)[0, 1])})

    r = np.linalg.norm(((pos0 - centre + box / 2) % box) - box / 2, axis=1)
    dens = []
    for lo in np.arange(a.radius - 1.0, a.radius + 8.0, 0.5):
        m = matrix & (r >= lo) & (r < lo + 0.5)
        vol = 4.0 / 3.0 * np.pi * ((lo + 0.5) ** 3 - lo ** 3)
        dens.append({"r_from_A": float(lo), "relative_density": float(m.sum() * OMEGA / vol)})
    inc_r = r[~matrix]
    v_cav = float(np.prod(box) - matrix.sum() * OMEGA)
    res = {"dir": str(a.dir).replace("\\", "/"), "radius_A": a.radius,
           "stress_vs_atomic_strain": rows, "density": dens,
           "inclusion_outer_radius_A": float(inc_r.max()),
           "inclusion_moment_radius_A": float(np.sqrt(5.0 / 3.0 * np.mean(inc_r ** 2))),
           "cavity_volume_A3": v_cav,
           "cavity_equivalent_radius_A": float((3.0 * v_cav / (4.0 * np.pi)) ** (1.0 / 3.0)),
           "cavity_over_inclusion_volume": float(v_cav / (4.0 / 3.0 * np.pi * a.radius ** 3))}
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for q in rows:
        print("d %4.1f-%-4.1f n %5d  virial / C:eps %.3f  (deviatoric %.3f, corr %.3f)" % (
            q["d_from_A"], q["d_from_A"] + 1, q["n"], q["virial_over_C_eps"],
            q["deviatoric_virial_over_C_eps"], q["correlation"]))
    print("density:", [(q["r_from_A"], round(q["relative_density"], 2)) for q in dens])
    print("cavity radius %.2f A, cavity / inclusion volume %.3f, inclusion outer radius %.2f A" % (
        res["cavity_equivalent_radius_A"], res["cavity_over_inclusion_volume"], res["inclusion_outer_radius_A"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
