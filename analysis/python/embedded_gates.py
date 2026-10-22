#!/usr/bin/env python3
"""Acceptance checks of the MD static pair of the embedded inclusion.

Inputs: the static dumps written by lammps/embedded_inclusion/in.static_pair
(reference, +eps, -eps, and +eps after the first CG stage). The continuum
reference is the fixed-box periodic FFT solution of the same problem
(embedded_inclusion_continuum.periodic_fft_frozen), evaluated at every atom
position. Stresses: per-atom virial / 16.61 A^3, MPa, tension positive.

  G1 convergence   field change between the two CG stages, shells r >= R+5 A
  G2 equilibrium   <dsigma_iz>(z), <dsigma_ix>(x), <dsigma_iy>(y) over planes that do
                   not cut the inclusion: flat, and equal to the continuum averages
  G3 linearity     (d(+eps) + d(-eps))/2 against d(+eps), shells r >= R+5 A
  G4 mean stress   matrix mean of the difference against the continuum mean
  G5 agreement     MD / continuum in shells R+5..R+30 A along the field (sigma_rr),
                   across it (sigma_rr) and in the lobes of sigma_xz
  kinematics       displacement of the first Al shell against eps.(r - r_c)
  events           matrix atoms whose displacement departs from the continuum
                   displacement by more than 0.1 A, in +eps (started from the
                   continuum displacement, so biased low) and in -eps (started
                   from the reference positions), and the atoms common to both

    python analysis/python/embedded_gates.py --dir runs/.../static --n-al 114374 \
        --radius 25 --out runs/.../static/gates.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import map_coordinates

sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedded_inclusion_continuum as C  # noqa: E402
import embedded_inclusion_field as F  # noqa: E402

REPORTS = Path(__file__).resolve().parents[2] / "docs" / "reports"


def sample(grid: np.ndarray, pos: np.ndarray, box: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Trilinear periodic interpolation of a (..., nx, ny, nz) grid at positions."""
    idx = (np.mod(pos, box) / h).T
    lead = grid.shape[:-3]
    flat = grid.reshape((-1,) + grid.shape[-3:])
    out = np.stack([map_coordinates(g, idx, order=1, mode="grid-wrap") for g in flat], axis=-1)
    return out.reshape((len(pos),) + lead)


def shell_means(values: np.ndarray, g: F.Geometry, sel: np.ndarray, lo: float, hi: float, w: float = 2.0):
    rows = []
    for a in np.arange(lo, hi, w):
        m = sel & (g.d >= a) & (g.d < a + w)
        if m.sum() >= 4:
            rows.append((a + w / 2, float(values[m].mean()), int(m.sum())))
    return rows


DIRS = (("pole", "srr"), ("equator", "srr"), ("lobe25", "s_axial_shear"), ("lobe67", "s_axial_shear"))


def agreement(md: dict, cont: dict, d_fit: float = 10.0, tol: float = 0.15, floor: float = 2.5,
              big: float = 5.0, dmax: float = 30.0) -> dict:
    """How the MD profiles (embedded_field.json, linear part) compare with the
    same-cell continuum (embedded_continuum.json, "periodic"), 2 A shells out to dmax.

    Directions: sigma_rr along and across the field, the axial shear in the 25 and
    67 degree lobes. The MD field is fitted as A times the continuum by least
    squares over shells d >= d_fit where the continuum is at least 3 MPa, for all
    directions together and for each one. The interface layer is the inner edge of
    the first shell from which on every shell agrees with A times the continuum to
    within tol, or floor MPa where that is smaller. Deviations after scaling are
    given where the continuum is at least big MPa."""
    src = md.get("linear") or md["profiles"]
    shells = []
    for name, key in DIRS:
        P = cont["periodic"][name]
        for r in src[name]:
            if r["d_A"] <= dmax:
                c = min(P, key=lambda q: abs(q["d_A"] - r["d_A"]))[key]
                shells.append((name, r["d_A"] - 1.0, r[key], c))

    def fit(rows):
        m = np.array([q[2] for q in rows])
        c = np.array([q[3] for q in rows])
        return float(m @ c / (c @ c))

    use = [q for q in shells if q[1] + 1.0 >= d_fit and abs(q[3]) >= 3.0]
    A = fit(use)
    per = {name: fit([q for q in use if q[0] == name]) for name, _ in DIRS}
    edges = sorted({q[1] for q in shells})
    layer = next(e for e in edges
                 if all(abs(m - A * c) <= max(tol * abs(A * c), floor) for _, e2, m, c in shells if e2 >= e))
    devs = [abs(m / (A * c) - 1) for _, e, m, c in shells if e + 1.0 >= d_fit and abs(c) >= big]
    return {"amplitude": A, "amplitude_by_direction": per, "fit_from_d_A": d_fit,
            "interface_layer_A": layer, "median_deviation_after_scaling": float(np.median(devs)),
            "max_deviation_after_scaling": float(max(devs))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--n-al", type=int, required=True)
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--eps", type=float, default=1.94e-3)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    D = a.dir
    ids, pos0, s_ref, box = F.read_dump(D / "ref.static.lammpstrj")
    _, pos_p, s_p, _ = F.read_dump(D / "plus.static.lammpstrj")
    _, _, s_p1, _ = F.read_dump(D / "plus.static1.lammpstrj")
    _, pos_m, s_m, _ = F.read_dump(D / "minus.static.lammpstrj")
    matrix = ids <= a.n_al
    centre = pos0[~matrix].mean(axis=0)
    g = F.Geometry(pos0, centre, box, a.radius)
    far = matrix & (g.d >= 5.0)
    dp = F.tensor(s_p - s_ref) * F.TO_MPA
    dm = F.tensor(s_m - s_ref) * F.TO_MPA
    dp1 = F.tensor(s_p1 - s_ref) * F.TO_MPA

    # continuum at the atom positions (fixed box, cubic MEAM Al, inclusion strain held)
    el = json.loads((REPORTS / "meam_elastic_constants.json").read_text(encoding="utf-8"))["Al"]
    Cs = C.cubic_in_cell_frame(el["C11"] * 1e9, el["C12"] * 1e9, el["C44"] * 1e9)
    e_c = C.strain_given(a.eps)
    sig, axes, _, e_in = C.periodic_fft_frozen(box, centre, a.radius, e_c, Cs, 1.0)
    u, _, _, _ = C.periodic_fft_frozen(box, centre, a.radius, e_c, Cs, 1.0, displacement=True)
    h = np.array([ax[1] - ax[0] for ax in axes])
    sc = sample(np.moveaxis(sig, (0, 1), (-5, -4)) / 1e6, pos0, box, h)      # (N, 3, 3) MPa
    uc = sample(u, pos0, box, h)
    uc -= sample(u, centre[None, :], box, h)[0]
    res = {"dir": str(D), "radius_A": a.radius, "eps": a.eps, "box_A": box.tolist(),
           "continuum_inclusion_strain_over_given": (np.diag(e_in) / np.diag(e_c)).tolist()}

    # G1: change between CG stages
    ch = np.abs(dp - dp1)[far]
    res["G1_convergence"] = {"max_shell_change_MPa": None, "median_atom_change_MPa": float(np.median(ch))}
    worst = 0.0
    for name, sel in F.selections(g.theta, far).items():
        for d_, v, n in shell_means((dp - dp1)[:, 0, 0] if name in ("pole", "equator") else (dp - dp1)[:, 0, 2] * g.sgn_s * np.sign(g.z + 1e-12),
                                    g, sel, 5.0, float(min(box) / 2 - a.radius)):
            worst = max(worst, abs(v))
    res["G1_convergence"]["max_shell_change_MPa"] = worst
    for stage in ("ref", "plus", "minus"):
        log = (D / f"log.{stage}").read_text(encoding="utf-8", errors="replace")
        fn = [float(l.split()[-1]) for l in log.splitlines() if l.startswith("CHUNK B")]
        res["G1_convergence"][f"final_fnorm_{stage}"] = fn[-1] if fn else None

    # box correction of the reference cell, from the log of in.relax_control
    ctl_log = D.parent / "log.lammps"
    if ctl_log.exists():
        lines = ctl_log.read_text(encoding="utf-8", errors="replace").splitlines()
        corr = [l.split() for l in lines if l.startswith("BOX CORRECTION")]
        after = [l.split() for l in lines if l.startswith("CHUNK B")]
        res["control_relaxation"] = {
            "far_mean_stress_before_MPa": float(corr[-1][5]) * 0.1 if corr else None,
            "box_scale": float(corr[-1][-1]) if corr else None,
            "far_mean_stress_after_MPa": float(after[-1][-1]) * 0.1 if after else None,
            "final_fnorm": float(after[-1][4]) if after else None}

    # G2: plane averages over planes that do not cut the inclusion
    g2 = {}
    for ax_i, comp in ((2, 2), (0, 0), (1, 1)):
        coord = (pos0[:, ax_i] - centre[ax_i] + box[ax_i] / 2) % box[ax_i] - box[ax_i] / 2
        planes = np.arange(-box[ax_i] / 2 + 1.0, box[ax_i] / 2, 2.0)
        md, ct = [], []
        for zc in planes:
            if abs(zc) < a.radius + 3.0:
                continue
            m = (np.abs(coord - zc) < 1.0)
            if m.sum() < 50:
                continue
            md.append(float(dp[m][:, ax_i, :].mean(axis=0)[comp]))
            ct.append(float(sc[m][:, ax_i, :].mean(axis=0)[comp]))
        g2["xyz"[ax_i] + "_planes_sigma_" + "xyz"[ax_i] + "xyz"[comp]] = {
            "md_mean": float(np.mean(md)), "md_spread": float(np.ptp(md)),
            "continuum_mean": float(np.mean(ct)), "continuum_spread": float(np.ptp(ct))}
    res["G2_equilibrium"] = g2

    # G3: symmetric part
    sym = (dp + dm) / 2
    g3 = {}
    for name, sel in F.selections(g.theta, far).items():
        k = (0, 0) if name in ("pole", "equator") else (0, 2)
        sgn = np.ones(len(g.d)) if name in ("pole", "equator") else g.sgn_s * np.sign(g.z + 1e-12)
        rows_s = shell_means(sym[:, k[0], k[1]] * sgn, g, sel, 5.0, 31.0)
        rows_p = shell_means(dp[:, k[0], k[1]] * sgn, g, sel, 5.0, 31.0)
        g3[name] = [{"d_A": d_, "symmetric_MPa": v, "plus_MPa": p} for (d_, v, _), (_, p, _) in zip(rows_s, rows_p)]
    res["G3_linearity"] = g3

    # G4: matrix mean
    res["G4_mean_stress"] = {"md": dict(zip(["xx", "yy", "zz", "xy", "xz", "yz"],
                                            [float(dp[matrix][:, i, j].mean()) for i, j in
                                             ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))])),
                             "continuum": dict(zip(["xx", "yy", "zz", "xy", "xz", "yz"],
                                                   [float(sc[matrix][:, i, j].mean()) for i, j in
                                                    ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))]))}

    # G5: MD / continuum, same atoms, same shells
    lin = (dp - dm) / 2
    comp_md = F.components(lin[far], g, np.flatnonzero(far))
    comp_ct = F.components(sc[far], g, np.flatnonzero(far))
    gf = F.Geometry(pos0[far], centre, box, a.radius)
    g5 = {}
    for name, sel in F.selections(gf.theta, np.ones(far.sum(), bool)).items():
        key = "srr" if name in ("pole", "equator") else "s_axial_shear"
        rows = []
        for lo in np.arange(5.0, 31.0, 2.0):
            m = sel & (gf.d >= lo) & (gf.d < lo + 2.0)
            if m.sum() < 4:
                continue
            vm, vc = float(comp_md[key][m].mean()), float(comp_ct[key][m].mean())
            rows.append({"d_A": lo + 1.0, "md": vm, "continuum": vc,
                         "ratio": vm / vc if abs(vc) > 1.0 else None, "n": int(m.sum())})
        g5[name] = rows
    res["G5_agreement"] = g5
    res["per_atom_rms_difference_MPa"] = {
        "sxx": float(np.sqrt(np.mean((lin[far, 0, 0] - sc[far, 0, 0]) ** 2))),
        "sxz": float(np.sqrt(np.mean((lin[far, 0, 2] - sc[far, 0, 2]) ** 2)))}

    # kinematics of the first Al shell and discrete events
    du = pos_p - pos0
    du -= box * np.round(du / box)
    shell = matrix & (g.d >= 0) & (g.d < 3.0)
    n_hat = g.n[shell]
    want = (pos0[shell] - centre) @ e_c.T
    res["interface_kinematics"] = {
        "n_atoms": int(shell.sum()),
        "radial_md_over_given": float(np.sum(np.einsum("pi,pi->p", du[shell], n_hat) * np.einsum("pi,pi->p", want, n_hat))
                                      / np.sum(np.einsum("pi,pi->p", want, n_hat) ** 2)),
        "tangential_md_over_given": float(
            np.sum(np.einsum("pi,pi->p", du[shell] - np.einsum("pi,pi->p", du[shell], n_hat)[:, None] * n_hat,
                             want - np.einsum("pi,pi->p", want, n_hat)[:, None] * n_hat))
            / np.sum(np.linalg.norm(want - np.einsum("pi,pi->p", want, n_hat)[:, None] * n_hat, axis=1) ** 2))}
    dev = np.linalg.norm(du - uc, axis=1)
    ev = matrix & (dev > 0.1)
    du_m = pos_m - pos0
    du_m -= box * np.round(du_m / box)
    ev_m = matrix & (np.linalg.norm(du_m + uc, axis=1) > 0.1)
    # linear displacement (+eps - -eps)/2 of the matrix against the continuum, by shell:
    # how much of the inclusion displacement the interface passes on
    lin_u = (du - du_m) / 2
    rows = []
    for lo in (0.0, 2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 20.0, 25.0):
        m = matrix & (g.d >= lo) & (g.d < lo + 2.0)
        nm = g.n[m]
        lr = np.einsum("pi,pi->p", lin_u[m], nm)
        cr = np.einsum("pi,pi->p", uc[m], nm)
        lt = lin_u[m] - lr[:, None] * nm
        ct = uc[m] - cr[:, None] * nm
        rows.append({"d_from_A": lo, "d_to_A": lo + 2.0, "n": int(m.sum()),
                     "radial_md_over_continuum": float(lr @ cr / (cr @ cr)),
                     "tangential_md_over_continuum": float(np.sum(lt * ct) / np.sum(ct * ct))})
    res["displacement_vs_continuum"] = rows
    res["events"] = {"n_matrix_atoms_departing_by_more_than_0.1_A": int(ev.sum()),
                     "their_distance_from_surface_A": np.round(g.d[ev], 2).tolist()[:200],
                     "minus_n_matrix_atoms_departing_by_more_than_0.1_A": int(ev_m.sum()),
                     "minus_distance_from_surface_A": np.round(g.d[ev_m], 2).tolist()[:200],
                     "n_common_to_plus_and_minus": int((ev & ev_m).sum()),
                     "max_departure_plus_A": float(dev[matrix].max()),
                     "max_departure_minus_A": float(np.linalg.norm(du_m + uc, axis=1)[matrix].max())}
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("G1_convergence", "G2_equilibrium", "G4_mean_stress",
                                          "interface_kinematics")}, indent=1))
    print("events: plus %d, minus %d, common %d" % (res["events"]["n_matrix_atoms_departing_by_more_than_0.1_A"],
          res["events"]["minus_n_matrix_atoms_departing_by_more_than_0.1_A"],
          res["events"]["n_common_to_plus_and_minus"]))
    for name, rows in g5.items():
        print("%-8s " % name + " ".join("d=%.0f %.2f" % (r["d_A"], r["ratio"]) for r in rows if r["ratio"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
