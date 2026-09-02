#!/usr/bin/env python3
"""Stage G17: the continuum-elastic field of the ridge itself.

The manuscript compares the atomistic ridge with an Eshelby sphere and an
infinite cylinder because those have closed forms. A reviewer will ask for
the prediction for the geometry actually simulated. This computes it.

A uniform eigenstrain eps* inside a region Omega of an infinite isotropic
plane-strain solid is equivalent to a surface force density f = +sigma* . n on
the boundary of Omega (inside Omega the eigenstress sigma* is then subtracted), with sigma* = lambda tr(eps*) I + 2 mu eps* the eigenstress
(here tr eps* = 0, so sigma* = 2 mu eps*). The stress anywhere is then the
boundary integral of the two-dimensional Kelvin solution. For the ridge the
region is the half-ellipse of the cross-section (semi-axes 35 A along x and
20 A along z, translationally invariant along y); the strained support slab
beneath it, being an infinite uniform layer, radiates nothing (its two faces
cancel), so the ridge-only field IS the exterior field.

Validation is built in: a circular cylinder must reproduce the uniform
interior stress of the Eshelby solution recorded in stageG8_eshelby3d.json,
and the traction integral around a point force must return the force.

Output: Delta sigma_xz and RSS_max on the vertical through the crest and
averaged over the cell width, as a function of height above the crest, in
the same 4 A bins as the atomistic profile.
"""
from __future__ import annotations

import io
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "docs" / "reports"
MU, NU = 26.5e9, 0.347                      # Al, as in stageG8
EPS = 1.94e-3
TILT = math.radians(45.0)
RX, RZ = 35.0, 20.0                         # ridge semi-axes, A
LX = 154.64                                 # unified cell width, for the x-average
BIN = 4.0


def eigenstrain() -> np.ndarray:
    u = np.array([math.sin(TILT), 0.0, math.cos(TILT)])
    return EPS * (1.5 * np.outer(u, u) - 0.5 * np.eye(3))


def kelvin_stress(x, z, fx, fz):
    """Plane-strain stress at (x, z) from a line force (fx, fz) per unit length
    at the origin. Returns (sxx, szz, sxz). Sign checked by force balance below."""
    r2 = x * x + z * z
    pref = -1.0 / (4 * math.pi * (1 - NU) * r2)
    a = 1 - 2 * NU
    # sigma_ij = pref * [ a (d_ik x_j + d_jk x_i - d_ij x_k) + 2 x_i x_j x_k / r2 ] F_k
    def s(i, j, xi, xj):
        tot = 0.0
        for xk, fk in ((x, fx), (z, fz)):
            dik = 1.0 if (i == 0 and xk is x) or (i == 1 and xk is z) else 0.0
            djk = 1.0 if (j == 0 and xk is x) or (j == 1 and xk is z) else 0.0
            dij = 1.0 if i == j else 0.0
            tot += (a * (dik * xj + djk * xi - dij * xk) + 2 * xi * xj * xk / r2) * fk
        return pref * tot
    return s(0, 0, x, x), s(1, 1, z, z), s(0, 1, x, z)


def check_force_balance() -> float:
    """Integrate traction of a unit force over a circle: must give -F (the
    material outside pulls back on the disk with -F)."""
    th = np.linspace(0, 2 * math.pi, 4001)[:-1]
    R = 1.0
    fx_tot = fz_tot = 0.0
    for t in th:
        x, z = R * math.cos(t), R * math.sin(t)
        nx, nz = math.cos(t), math.sin(t)
        sxx, szz, sxz = kelvin_stress(x, z, 1.0, 0.0)
        fx_tot += (sxx * nx + sxz * nz) * R * (2 * math.pi / len(th))
        fz_tot += (sxz * nx + szz * nz) * R * (2 * math.pi / len(th))
    return fx_tot   # expect -1


def boundary(kind: str, n: int):
    """Closed boundary as (x, z, nx, nz, ds) arrays, outward normals."""
    pts = []
    if kind == "circle":
        R = 30.0
        for t in np.linspace(0, 2 * math.pi, n, endpoint=False):
            pts.append((R * math.cos(t), R * math.sin(t), math.cos(t), math.sin(t), 2 * math.pi * R / n))
    elif kind == "half_ellipse":
        # arc from (-RX,0) over (0,RZ) to (RX,0), then the flat base back
        m = n // 2
        for t in np.linspace(0, math.pi, m, endpoint=False):
            x, z = RX * math.cos(t), RZ * math.sin(t)
            tx, tz = -RX * math.sin(t), RZ * math.cos(t)      # tangent
            L = math.hypot(tx, tz)
            nx, nz = tz / L, -tx / L                           # outward for CCW
            if nz < 0: nx, nz = -nx, -nz
            pts.append((x, z, nx, nz, L * math.pi / m))
        for x in np.linspace(RX, -RX, m, endpoint=False):
            pts.append((x, 0.0, 0.0, -1.0, 2 * RX / m))
    return np.array(pts)


def field(kind: str, xo, zo, n=4000):
    """Stress at (xo, zo) from the eigenstrained region. Origin at the region's
    reference point: circle centre, or the base centre of the half-ellipse."""
    e = eigenstrain()
    s_star = 2 * MU * e                                  # tr(eps*) = 0
    b = boundary(kind, n)
    sxx = szz = sxz = 0.0
    for (x, z, nx, nz, ds) in b:
        # equivalent surface force density f = +sigma* . n  (f = -div(sigma* theta_Omega))
        tx = (s_star[0, 0] * nx + s_star[0, 2] * nz)
        tz = (s_star[2, 0] * nx + s_star[2, 2] * nz)
        a, c, d = kelvin_stress(xo - x, zo - z, tx * ds, tz * ds)
        sxx += a; szz += c; sxz += d
    return sxx, szz, sxz


def rss_max_2d(sxx, szz, sxz, syy):
    """Max resolved shear over the twelve fcc systems in the lab frame, for a
    stress tensor with in-plane components and the plane-strain sigma_yy."""
    import itertools
    ex = np.array([1, -1, 0]) / math.sqrt(2); ey = np.array([1, 1, -2]) / math.sqrt(6); ez = np.array([1, 1, 1]) / math.sqrt(3)
    R = np.vstack([ex, ey, ez])
    S = np.array([[sxx, 0, sxz], [0, syy, 0], [sxz, 0, szz]])
    best = 0.0
    for p in ((1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)):
        nn = R @ (np.array(p, float) / math.sqrt(3))
        for dd in ((1, -1, 0), (1, 0, -1), (0, 1, -1), (1, 1, 0), (1, 0, 1), (0, 1, 1)):
            bb = np.array(dd, float) / math.sqrt(2)
            if abs(float(np.array(p) @ np.array(dd))) > 1e-9: continue
            best = max(best, abs(float(nn @ S @ (R @ bb))))
    return best


def main() -> int:
    fb = check_force_balance()
    e = eigenstrain()
    # --- validation: circular cylinder interior vs stageG8 -----------------
    g8 = json.loads(io.open(REPORTS / "stageG8_eshelby3d.json", encoding="utf-8").read())
    ref = np.array(g8["interior_stress_MPa"]["cylinder_2D_along_y"]["tensor"])
    s_star = 2 * MU * e
    sxx, szz, sxz = field("circle", 3.0, 4.0)
    sxx, szz, sxz = sxx - s_star[0, 0], szz - s_star[2, 2], sxz - s_star[0, 2]
    sxx2, szz2, sxz2 = field("circle", -12.0, 7.0)
    sxx2, szz2, sxz2 = sxx2 - s_star[0, 0], szz2 - s_star[2, 2], sxz2 - s_star[0, 2]
    # independent hand calculation with Mura's cylinder tensor
    S11 = (5 - 4 * NU) / (8 * (1 - NU)); S13 = (4 * NU - 1) / (8 * (1 - NU)); S12 = NU / (2 * (1 - NU)); S55 = (3 - 4 * NU) / (8 * (1 - NU))
    lam = 2 * MU * NU / (1 - 2 * NU)
    ecx = S11 * e[0, 0] + S13 * e[2, 2] + S12 * e[1, 1]
    ecz = S11 * e[2, 2] + S13 * e[0, 0] + S12 * e[1, 1]
    ecxz = 2 * S55 * e[0, 2]
    exx, ezz, eyy, exz = ecx - e[0, 0], ecz - e[2, 2], -e[1, 1], ecxz - e[0, 2]
    tr = exx + eyy + ezz
    mura = [round((lam * tr + 2 * MU * exx) / 1e6, 2), round((lam * tr + 2 * MU * ezz) / 1e6, 2),
            round(2 * MU * exz / 1e6, 2), round((lam * tr + 2 * MU * eyy) / 1e6, 2)]
    rigid_factor_shear = 1.0 / (2 * S55)
    val = {"force_balance_expect_minus1": round(fb, 5),
           "circle_interior_MPa_at_(3,4)": [round(sxx / 1e6, 2), round(szz / 1e6, 2), round(sxz / 1e6, 2)],
           "circle_interior_MPa_at_(-12,7)": [round(sxx2 / 1e6, 2), round(szz2 / 1e6, 2), round(sxz2 / 1e6, 2)],
           "mura_hand_cylinder_interior_MPa_xx_zz_xz_yy": mura,
           "stageG8_cylinder_interior_MPa": [round(ref[0, 0], 2), round(ref[2, 2], 2), round(ref[0, 2], 2)],
           "rigid_inclusion_factor_for_shear": round(rigid_factor_shear, 3),
           "note": "a rigid inclusion holding the same strain (the tethered atomistic case) "
                   "radiates 1/(2 S_xzxz) times the homogeneous field in shear"}
    # sigma_yy in plane strain for the interior: nu (sxx+szz) - E eps*_yy  (not needed for validation)

    # --- the ridge: profile above the crest ---------------------------------
    rows = []
    zs = np.arange(BIN / 2, 120, BIN)
    xs = np.linspace(-LX / 2, LX / 2, 121)
    xs_old = np.linspace(-108.82 / 2, 108.82 / 2, 85)
    xs_axis = np.linspace(-10.0, 10.0, 21)
    for dz in zs:
        zo = RZ + dz                                   # height above the crest
        # on the vertical through the crest
        a, c, d = field("half_ellipse", 0.0, zo)
        syy = NU * (a + c) - 2 * MU * e[1, 1] * 0.0    # exterior: no eigenstrain, syy = nu (sxx+szz)
        syy = NU * (a + c)
        rss_line = rss_max_2d(a, c, d, syy)
        # averaged over the cell width at that height, as the atomistic bins do
        def avg(grid):
            acc = np.zeros(3)
            for xo in grid:
                acc += np.array(field("half_ellipse", xo, zo, n=1200))
            return acc / len(grid)
        a2, c2, d2 = avg(xs)
        a3, c3, d3 = avg(xs_old)
        a4, c4, d4 = avg(xs_axis)
        rows.append({"d_A": float(dz), "r_A": float(RZ + dz + 20.0),
                     "x_avg_108A": {"sxz_MPa": round(d3 / 1e6, 3), "RSS_max_MPa": round(rss_max_2d(a3, c3, d3, NU * (a3 + c3)) / 1e6, 3)},
                     "axis_window_20A": {"sxz_MPa": round(d4 / 1e6, 3), "RSS_max_MPa": round(rss_max_2d(a4, c4, d4, NU * (a4 + c4)) / 1e6, 3)},
                     "on_axis": {"sxz_MPa": round(d / 1e6, 3), "sxx_MPa": round(a / 1e6, 3),
                                 "szz_MPa": round(c / 1e6, 3), "RSS_max_MPa": round(rss_line / 1e6, 3)},
                     "x_averaged": {"sxz_MPa": round(d2 / 1e6, 3), "sxx_MPa": round(a2 / 1e6, 3),
                                    "szz_MPa": round(c2 / 1e6, 3),
                                    "RSS_max_MPa": round(rss_max_2d(a2, c2, d2, NU * (a2 + c2)) / 1e6, 3)}})
    out = {"created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "method": "2D plane-strain Kelvin boundary integral of the eigenstress traction "
                     "-sigma*.n over the half-elliptic ridge cross-section in an infinite "
                     "isotropic medium; slab omitted (an infinite uniform layer radiates nothing)",
           "elastic_constants": {"mu_GPa": MU / 1e9, "nu": NU}, "eigenstrain": EPS, "tilt_deg": 45.0,
           "ridge_semi_axes_A": [RX, RZ], "cell_width_A": LX,
           "validation": val, "profile": rows}
    (REPORTS / "stageG17_ridge_continuum.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("force balance (expect -1):", round(fb, 4))
    print("circle interior (sxx, szz, sxz) MPa at two points:", val["circle_interior_MPa_at_(3,4)"], val["circle_interior_MPa_at_(-12,7)"])
    print("Mura tensor by hand (xx, zz, xz, yy)    :", val["mura_hand_cylinder_interior_MPa_xx_zz_xz_yy"])
    print("stageG8 cylinder interior (xx, zz, xz)   :", val["stageG8_cylinder_interior_MPa"])
    print("rigid-inclusion factor (shear):", val["rigid_inclusion_factor_for_shear"])
    print("\nridge exterior above the crest:")
    print("  d(A)  sxz on-axis  sxz |x|<10  sxz avg108  sxz avg155   (homogeneous Eshelby; rigid x%.2f)" % val["rigid_inclusion_factor_for_shear"])
    for r in rows[:12]:
        print("  %4.0f  %10.2f  %10.2f  %10.2f  %10.2f" % (r["d_A"], r["on_axis"]["sxz_MPa"], r["axis_window_20A"]["sxz_MPa"],
                                                       r["x_avg_108A"]["sxz_MPa"], r["x_averaged"]["sxz_MPa"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
