#!/usr/bin/env python3
"""Stress added in the aluminium matrix by the strain of an embedded inclusion.

Reads the static dumps written by lammps/embedded_inclusion/in.static_pair for
the reference cell and for the cell whose inclusion was given the strain
+eps (and optionally -eps), all built from one relaxed reference, so atom IDs
match. For every matrix atom the stress difference strained minus reference is
formed from the per-atom virial divided by the atomic volume of aluminium.
Sign convention of mechanics: tension positive.

The strain is symmetric about the field direction x, so the added field is
(up to the weak elastic anisotropy of Al) symmetric about the x axis through
the inclusion centre. Coordinates: s = x - x_c along the field, rho the
distance from the axis, r the distance from the centre, theta the angle from
+x. Results:

  profiles  against the distance d = r - R from the surface, in 2 A shells,
            within a cone of 10 degrees about +-x ("pole", along the field),
            a band of 10 degrees about the plane s = 0 ("equator", across the
            field) and a band of 7.5 degrees about theta = 45 deg ("diagonal");
            each gives sigma_rr, sigma_tt (normal stresses along and across the
            radius), the von Mises equivalent stress and the glide stress
            sigma_xz of the (111)[1-10] system, which in the xz plane equals the
            axial shear sigma_s,rho (signed with s z)
  axisym    the same quantities on a (|s|, rho) grid of 2 A, from all atoms;
            the xz map is read off it (sigma_xz = sigma_s,rho sign(s z))
  section   a true xz section from atoms with |y - y_c| < 4 A, 4 A pixels
  mean      the difference averaged over all matrix atoms (box check)
  linear    with --minus: (d(+eps) - d(-eps))/2 and the nonlinear remainder
            (d(+eps) + d(-eps))/2, per shell along the three directions

    python analysis/python/embedded_inclusion_field.py --control ctl.static.lammpstrj \
        --strained plus.static.lammpstrj [--minus minus.static.lammpstrj] \
        --n-al 114374 --radius 25 --out docs/reports/embedded_field.json
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import math
from pathlib import Path

import numpy as np

AL_A = 4.05
OMEGA_AL = AL_A ** 3 / 4.0          # 16.61 A^3, atomic volume of fcc Al
TO_MPA = 0.1 / OMEGA_AL             # bar*A^3 per atom -> MPa
SHELL_A = 2.0
POLE_DEG, EQUATOR_DEG, BAND_DEG = 10.0, 10.0, 7.5
# angles from the field axis; the glide stress sigma_xz has its two lobes near
# 25 and 67 degrees (it changes sign near 52 degrees) and vanishes on the axes
DIRECTIONS = {"pole": (0.0, POLE_DEG), "lobe25": (25.0, BAND_DEG), "diagonal": (45.0, BAND_DEG),
              "lobe67": (67.0, BAND_DEG), "equator": (90.0, EQUATOR_DEG)}


def selections(theta: np.ndarray, base: np.ndarray) -> dict[str, np.ndarray]:
    """Atoms (or grid points) within each angular window, theta from the nearer pole."""
    return {k: base & (np.abs(theta - c) <= w) for k, (c, w) in DIRECTIONS.items()}


def read_dump(path: Path):
    """ids, positions (box origin removed), stress*volume (xx yy zz xy xz yz), box."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        lines = f.read().splitlines()
    n = int(lines[lines.index("ITEM: NUMBER OF ATOMS") + 1])
    j = next(k for k, l in enumerate(lines) if l.startswith("ITEM: BOX BOUNDS"))
    lo = np.array([float(lines[j + 1 + k].split()[0]) for k in range(3)])
    hi = np.array([float(lines[j + 1 + k].split()[1]) for k in range(3)])
    a = next(k for k, l in enumerate(lines) if l.startswith("ITEM: ATOMS"))
    data = np.loadtxt(io.StringIO("\n".join(lines[a + 1:a + 1 + n])))
    data = data[np.argsort(data[:, 0])]
    return data[:, 0].astype(int), data[:, 2:5] - lo, data[:, 5:11], hi - lo


def tensor(s6: np.ndarray) -> np.ndarray:
    t = np.empty((len(s6), 3, 3))
    t[:, 0, 0], t[:, 1, 1], t[:, 2, 2] = s6[:, 0], s6[:, 1], s6[:, 2]
    t[:, 0, 1] = t[:, 1, 0] = s6[:, 3]
    t[:, 0, 2] = t[:, 2, 0] = s6[:, 4]
    t[:, 1, 2] = t[:, 2, 1] = s6[:, 5]
    return t


def von_mises(t: np.ndarray) -> np.ndarray:
    dev = t - np.trace(t, axis1=-2, axis2=-1)[..., None, None] / 3 * np.eye(3)
    return np.sqrt(1.5 * np.einsum("...ij,...ij->...", dev, dev))


class Geometry:
    """Per-atom local frames about the inclusion axis (x through the centre)."""

    def __init__(self, pos: np.ndarray, centre: np.ndarray, box: np.ndarray, radius: float):
        r = pos - centre
        r -= box * np.round(r / box)
        self.s = r[:, 0]
        self.rho = np.hypot(r[:, 1], r[:, 2])
        self.r = np.linalg.norm(r, axis=1)
        self.d = self.r - radius
        self.theta = np.degrees(np.arccos(np.clip(np.abs(self.s) / np.maximum(self.r, 1e-9), 0, 1)))
        self.n = r / np.maximum(self.r, 1e-9)[:, None]               # radial unit vector
        # unit vector of increasing theta in the (s, rho) half-plane of each atom
        e_rho = np.zeros_like(r)
        e_rho[:, 1:] = r[:, 1:] / np.maximum(self.rho, 1e-9)[:, None]
        sgn = np.sign(self.s) + (self.s == 0)
        self.t = (np.cos(np.radians(self.theta))[:, None] * e_rho
                  - np.sin(np.radians(self.theta))[:, None] * np.array([1.0, 0, 0]) * sgn[:, None])
        self.e_rho = e_rho
        self.sgn_s = sgn
        self.sgn_sz = np.sign(r[:, 0] * r[:, 2])
        self.y = r[:, 1]
        self.z = r[:, 2]


def components(t: np.ndarray, g: Geometry, idx: np.ndarray) -> dict[str, np.ndarray]:
    """sigma_rr, sigma_tt, axial shear sigma_s,rho (signed with s) and von Mises."""
    n, tt, er = g.n[idx], g.t[idx], g.e_rho[idx]
    ex = np.array([1.0, 0, 0])
    return {"srr": np.einsum("pi,pij,pj->p", n, t, n),
            "stt": np.einsum("pi,pij,pj->p", tt, t, tt),
            "s_axial_shear": np.einsum("i,pij,pj->p", ex, t, er) * g.sgn_s[idx],
            "von_mises": von_mises(t)}


def shell_profile(t: np.ndarray, g: Geometry, sel: np.ndarray, dmax: float) -> list[dict]:
    rows = []
    for lo in np.arange(0.0, dmax, SHELL_A):
        idx = np.flatnonzero(sel & (g.d >= lo) & (g.d < lo + SHELL_A))
        if len(idx) < 4:
            continue
        comp = components(t[idx], g, idx)
        mean_t = t[idx].mean(axis=0)
        row = {"d_A": float(lo + SHELL_A / 2), "n_atoms": int(len(idx)),
               "von_mises_of_mean": float(von_mises(mean_t[None])[0])}
        for k, v in comp.items():
            row[k] = float(v.mean())
            row[k + "_sem"] = float(v.std(ddof=1) / math.sqrt(len(v)))
        rows.append(row)
    return rows


GLIDE_HEIGHTS_A = (3.0, 5.0, 10.0, 15.0, 20.0)


def glide_planes(x: np.ndarray, z: np.ndarray, sxz: np.ndarray, radius: float,
                 lx: float, keep: np.ndarray, slab: float = 2.0, bin_a: float = 2.0) -> dict:
    """sigma_xz averaged along y (the line of an edge dislocation) on horizontal
    planes at height h above the top of the inclusion, against x - x_c.
    x, z are coordinates relative to the inclusion centre (minimum image)."""
    out = {}
    nb = int(lx // bin_a)
    edges = (np.arange(nb + 1) - nb / 2) * bin_a
    for h in GLIDE_HEIGHTS_A:
        sel = keep & (np.abs(z - (radius + h)) < slab)
        k = np.digitize(x[sel], edges) - 1
        ok = (k >= 0) & (k < nb)
        cnt = np.bincount(k[ok], minlength=nb)
        tot = np.bincount(k[ok], weights=sxz[sel][ok], minlength=nb)
        mean = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)
        out["%g" % h] = {"x_A": ((edges[:-1] + edges[1:]) / 2).tolist(),
                         "line_average_MPa": np.where(np.isnan(mean), None, np.round(mean, 4)).tolist(),
                         "n_atoms": cnt.tolist(),
                         "local_max_abs_MPa": float(np.max(np.abs(sxz[sel]))) if sel.any() else None}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--control", type=Path, required=True)
    ap.add_argument("--strained", type=Path, required=True)
    ap.add_argument("--minus", type=Path, default=None)
    ap.add_argument("--n-al", type=int, required=True)
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--label", default="")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    ids, pos, s0, box = read_dump(a.control)
    ids1, _, s1, box1 = read_dump(a.strained)
    if not np.array_equal(ids, ids1):
        raise SystemExit("reference and strained dumps hold different atoms")
    matrix = ids <= a.n_al
    centre = pos[~matrix].mean(axis=0)
    r_eff = (3 * int((~matrix).sum()) * (1489.3 / 102) / (4 * math.pi)) ** (1 / 3)
    g = Geometry(pos, centre, box, a.radius)
    dif = tensor(s1 - s0) * TO_MPA
    ref = tensor(s0) * TO_MPA
    dmax = float(min(box) / 2 - a.radius)

    sels = selections(g.theta, matrix)
    res = {
        "label": a.label, "control": str(a.control), "strained": str(a.strained),
        "minus": str(a.minus) if a.minus else None, "n_al": a.n_al, "radius_A": a.radius,
        "box_reference_A": box.tolist(), "box_strained_A": box1.tolist(),
        "centre_A": centre.tolist(), "effective_radius_A": r_eff,
        "convention": "mechanics, tension positive; per-atom virial / %.2f A^3" % OMEGA_AL,
        "directions_deg_from_field_axis": {k: {"centre": c, "half_width": w}
                                           for k, (c, w) in DIRECTIONS.items()},
        "mean_difference_matrix_MPa": dict(zip(["xx", "yy", "zz", "xy", "xz", "yz"],
                                               (s1 - s0)[matrix].mean(axis=0) * TO_MPA)),
        "profiles": {}, "reference_von_mises_profile": {},
    }
    for name, sel in sels.items():
        res["profiles"][name] = shell_profile(dif, g, sel, dmax)
        res["reference_von_mises_profile"][name] = [
            {"d_A": q["d_A"], "von_mises": q["von_mises"]} for q in shell_profile(ref, g, sel, dmax)]

    # line-averaged glide stress on planes above the inclusion (edge line along y)
    res["glide_planes"] = glide_planes(g.s, g.z, dif[:, 0, 2], a.radius, box[0], matrix & (g.d > 0))

    # axisymmetric map on (|s|, rho)
    h = 2.0
    ns, nr = int(dmax // h) + int(a.radius // h) + 1, int(dmax // h) + int(a.radius // h) + 1
    isq = np.floor(np.abs(g.s) / h).astype(int)
    irh = np.floor(g.rho / h).astype(int)
    ok = matrix & (g.d > 0) & (isq < ns) & (irh < nr)
    comp = components(dif[ok], g, np.flatnonzero(ok))
    sxx = dif[ok, 0, 0]
    srho = np.einsum("pi,pij,pj->p", g.e_rho[ok], dif[ok], g.e_rho[ok])
    key = isq[ok] * nr + irh[ok]
    maps = {k: np.full((ns, nr), np.nan) for k in ("sxx", "s_rho_rho", "s_axial_shear", "von_mises", "srr")}
    count = np.bincount(key, minlength=ns * nr).reshape(ns, nr)
    for k, v in (("sxx", sxx), ("s_rho_rho", srho), ("s_axial_shear", comp["s_axial_shear"]),
                 ("von_mises", comp["von_mises"]), ("srr", comp["srr"])):
        tot = np.bincount(key, weights=v, minlength=ns * nr).reshape(ns, nr)
        maps[k] = np.where(count >= 4, tot / np.maximum(count, 1), np.nan)
    res["axisym"] = {"cell_A": h, "s_centres_A": ((np.arange(ns) + 0.5) * h).tolist(),
                     "rho_centres_A": ((np.arange(nr) + 0.5) * h).tolist(),
                     "n_atoms": count.tolist(),
                     **{k: np.where(np.isnan(v), None, np.round(v, 3)).tolist() for k, v in maps.items()}}

    # true section |y| < 4 A
    p = 4.0
    slab = matrix & (np.abs(g.y) < 4.0) & (g.d > 0)
    nx, nz = int(box[0] // p), int(box[2] // p)
    ix = np.floor((g.s[slab] + nx * p / 2) / p).astype(int)
    iz = np.floor((g.z[slab] + nz * p / 2) / p).astype(int)
    good = (ix >= 0) & (ix < nx) & (iz >= 0) & (iz < nz)
    key = ix[good] * nz + iz[good]
    cnt = np.bincount(key, minlength=nx * nz).reshape(nx, nz)
    sec = {}
    for k, v in (("sxx", dif[slab][good, 0, 0]), ("szz", dif[slab][good, 2, 2]),
                 ("sxz", dif[slab][good, 0, 2]), ("von_mises", von_mises(dif[slab][good]))):
        tot = np.bincount(key, weights=v, minlength=nx * nz).reshape(nx, nz)
        sec[k] = np.where(cnt >= 3, tot / np.maximum(cnt, 1), np.nan)
    res["section_xz"] = {"pixel_A": p, "x_centres_A": ((np.arange(nx) + 0.5) * p - nx * p / 2).tolist(),
                         "z_centres_A": ((np.arange(nz) + 0.5) * p - nz * p / 2).tolist(),
                         "n_atoms": cnt.tolist(),
                         **{k: np.where(np.isnan(v), None, np.round(v, 3)).tolist() for k, v in sec.items()}}

    if a.minus:
        ids2, _, s2, _ = read_dump(a.minus)
        if not np.array_equal(ids, ids2):
            raise SystemExit("reference and -eps dumps hold different atoms")
        dm = tensor(s2 - s0) * TO_MPA
        lin, non = (dif - dm) / 2, (dif + dm) / 2
        res["linear"] = {name: shell_profile(lin, g, sel, dmax) for name, sel in sels.items()}
        res["nonlinear"] = {name: shell_profile(non, g, sel, dmax) for name, sel in sels.items()}

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res) + "\n", encoding="utf-8")
    print("mean difference over the matrix, MPa:",
          {k: round(float(v), 3) for k, v in res["mean_difference_matrix_MPa"].items()})
    for name, rows in res["profiles"].items():
        print("%-8s " % name + " | ".join("d=%.0f srr %.1f stt %.1f shear %.1f vm %.1f n=%d"
                                          % (q["d_A"], q["srr"], q["stt"], q["s_axial_shear"],
                                             q["von_mises"], q["n_atoms"]) for q in rows[1:12:3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
