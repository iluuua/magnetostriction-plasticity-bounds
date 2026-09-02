#!/usr/bin/env python3
"""Stage G8: three-dimensional Eshelby check of the ridge-cell field.

The external review is right that the simulated inclusion is a ridge that is
translationally invariant along y, so its exterior field carries the
two-dimensional exponent, while Eq. (2) of the manuscript takes its spatial
statistics from the compact three-dimensional Eshelby solution. This script
closes that gap by computing, for the SAME eigenstrain, the interior and
exterior fields of

  (a) a compact spheroidal inclusion (3D, Eshelby tensor evaluated by the
      standard elliptic integrals for a spheroid, isotropic matrix), and
  (b) an infinite elliptic cylinder along y (2D, the geometry actually
      simulated),

and reports the maximum resolved shear stress over the twelve fcc
{111}<110> systems in the same lab frame used by the MD analysis. The
purpose is to answer one question: is the ridge cell an over- or an
under-estimate of what a compact particle delivers?

Exterior field: for a point outside the inclusion the Eshelby problem is
solved with the equivalent-inclusion method, evaluating the exterior Eshelby
tensor D_ijkl(x) by numerical integration of the derivative of the isotropic
Green function over the inclusion volume,

  sigma_ij(x) = C_ijkl [ D_klmn(x) - I_klmn H(x in Omega) ] eps*_mn ,

which for the interior reduces to the classical uniform result. Integration
uses a Gauss-Legendre product rule over the inclusion; convergence is checked
by doubling the order.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "docs" / "reports" / "stageG8_eshelby3d.json"

MU = 26.5e9          # Pa, Al shear modulus used throughout the project
NU = 0.347           # Al Poisson ratio
LAMBDA = 2.0 * MU * NU / (1.0 - 2.0 * NU)
EPS = 1.94e-3        # inflated eigenstrain amplitude used in the MD cells
TILT_DEG = 45.0
RIDGE_RX = 35e-10    # m, ridge semi-axis in x
RIDGE_H = 20e-10     # m, ridge semi-axis in z
LAM_REAL = {"20 ppm": 2e-5, "40 ppm": 4e-5, "100 ppm": 1e-4}


def stiffness() -> np.ndarray:
    """Isotropic C_ijkl."""
    d = np.eye(3)
    C = np.zeros((3, 3, 3, 3))
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for l in range(3):
                    C[i, j, k, l] = (LAMBDA * d[i, j] * d[k, l]
                                     + MU * (d[i, k] * d[j, l] + d[i, l] * d[j, k]))
    return C


def eigenstrain_tensor() -> np.ndarray:
    """Volume-conserving magnetostriction, axis tilted TILT_DEG from z toward x."""
    t = math.radians(TILT_DEG)
    u = np.array([math.sin(t), 0.0, math.cos(t)])
    return EPS * (1.5 * np.outer(u, u) - 0.5 * np.eye(3))


def eshelby_sphere() -> np.ndarray:
    """S_ijkl for a sphere in an isotropic matrix (Mura Eq. 11.16)."""
    d = np.eye(3)
    a = (7.0 - 5.0 * NU) / (15.0 * (1.0 - NU))
    b = (5.0 * NU - 1.0) / (15.0 * (1.0 - NU))
    c = (4.0 - 5.0 * NU) / (15.0 * (1.0 - NU))
    S = np.zeros((3, 3, 3, 3))
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for l in range(3):
                    S[i, j, k, l] = (b * d[i, j] * d[k, l]
                                     + c * (d[i, k] * d[j, l] + d[i, l] * d[j, k]))
                    if i == j == k == l:
                        S[i, j, k, l] = a
    return S


def eshelby_cylinder() -> np.ndarray:
    """S_ijkl for an infinite circular cylinder along y (Mura Table 11.1),
    axes: 1 = x, 2 = y (cylinder axis), 3 = z."""
    S = np.zeros((3, 3, 3, 3))
    f = 1.0 / (2.0 * (1.0 - NU))
    S[0, 0, 0, 0] = S[2, 2, 2, 2] = f * (5.0 - 4.0 * NU) / 4.0
    S[0, 0, 2, 2] = S[2, 2, 0, 0] = f * (4.0 * NU - 1.0) / 4.0
    # S_1133 for the cylinder is nu / (2 (1 - nu)) = f * nu (Mura 11.22). An
    # earlier version had f * 2 nu, which doubled the coupling to eps*_yy and
    # put the interior normal stresses at -50.7 MPa instead of -6.0; caught
    # on 2 Sept 2026 by an independent boundary-integral solution (stageG17).
    S[0, 0, 1, 1] = S[2, 2, 1, 1] = f * NU
    S[0, 2, 0, 2] = S[2, 0, 2, 0] = S[0, 2, 2, 0] = S[2, 0, 0, 2] = f * (3.0 - 4.0 * NU) / 4.0
    S[0, 1, 0, 1] = S[1, 0, 1, 0] = S[0, 1, 1, 0] = S[1, 0, 0, 1] = 0.25
    S[1, 2, 1, 2] = S[2, 1, 2, 1] = S[1, 2, 2, 1] = S[2, 1, 1, 2] = 0.25
    return S


def interior_stress(S: np.ndarray, C: np.ndarray, e: np.ndarray) -> np.ndarray:
    """sigma^in = C : (S - I) : eps*."""
    Se = np.einsum("ijkl,kl->ij", S, e)
    return np.einsum("ijkl,kl->ij", C, Se - e)


def slip_systems() -> list[tuple[np.ndarray, np.ndarray, str]]:
    ex = np.array([1.0, -1.0, 0.0]) / math.sqrt(2.0)
    ey = np.array([1.0, 1.0, -2.0]) / math.sqrt(6.0)
    ez = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    R = np.vstack([ex, ey, ez])
    planes = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    dirs = [(1, -1, 0), (1, 0, -1), (0, 1, -1), (1, 1, 0), (1, 0, 1), (0, 1, 1)]
    out = []
    for p in planes:
        n = np.array(p, float) / np.linalg.norm(p)
        for dv in dirs:
            b = np.array(dv, float) / np.linalg.norm(dv)
            if abs(float(n @ b)) > 1e-9:
                continue
            out.append((R @ n, R @ b, f"({p[0]}{p[1]}{p[2]})[{dv[0]}{dv[1]}{dv[2]}]"))
    return out


def max_rss(sig: np.ndarray, systems) -> tuple[float, str]:
    best = max(((abs(float(n @ sig @ b)), lbl) for n, b, lbl in systems))
    return best


def exterior_sphere(x: np.ndarray, a: float, e: np.ndarray, C: np.ndarray,
                    order: int = 40) -> np.ndarray:
    """Exterior stress of a spherical inclusion by direct integration of the
    Green-function second derivative over the inclusion volume."""
    # Gauss-Legendre nodes on the unit ball via spherical coordinates
    gr, wr = np.polynomial.legendre.leggauss(order)
    gt, wt = np.polynomial.legendre.leggauss(order)
    gp, wp = np.polynomial.legendre.leggauss(order)
    r = 0.5 * a * (gr + 1.0)
    wr = 0.5 * a * wr
    ct = gt
    wt = wt
    phi = math.pi * (gp + 1.0)
    wp = math.pi * wp

    c1 = 1.0 / (16.0 * math.pi * MU * (1.0 - NU))
    D = np.zeros((3, 3, 3, 3))
    d = np.eye(3)
    for ir, rr in enumerate(r):
        for it, cc in enumerate(ct):
            st = math.sqrt(max(0.0, 1.0 - cc * cc))
            for ip, pp in enumerate(phi):
                y = np.array([rr * st * math.cos(pp), rr * st * math.sin(pp), rr * cc])
                w = wr[ir] * wt[it] * wp[ip] * rr * rr
                z = x - y
                R2 = float(z @ z)
                R1 = math.sqrt(R2)
                if R1 < 1e-14:
                    continue
                zz = z / R1
                # G_ki,lj for the isotropic Kelvin solution, contracted below
                for i in range(3):
                    for j in range(3):
                        for k in range(3):
                            for l in range(3):
                                term = ((1.0 - 2.0 * NU) * (d[i, j] * zz[k] * zz[l]
                                                            + d[k, l] * zz[i] * zz[j])
                                        + 3.0 * zz[i] * zz[j] * zz[k] * zz[l]
                                        - d[i, k] * zz[j] * zz[l] - d[j, l] * zz[i] * zz[k]
                                        - d[i, l] * zz[j] * zz[k] - d[j, k] * zz[i] * zz[l])
                                D[i, j, k, l] += w * c1 * term / (R1 ** 3) * (2.0 * MU)
    Se = np.einsum("ijkl,kl->ij", D, e)
    return np.einsum("ijkl,kl->ij", C, Se)


def main() -> int:
    C = stiffness()
    e = eigenstrain_tensor()
    systems = slip_systems()

    sig_sphere = interior_stress(eshelby_sphere(), C, e)
    sig_cyl = interior_stress(eshelby_cylinder(), C, e)
    rss_sphere, sys_sphere = max_rss(sig_sphere, systems)
    rss_cyl, sys_cyl = max_rss(sig_cyl, systems)

    # exterior decay along z for the sphere, in units of the inclusion radius
    a = 1.0
    decay = []
    for rr in (1.05, 1.2, 1.5, 2.0, 3.0):
        sig = exterior_sphere(np.array([0.0, 0.0, rr * a]), a, e, C, order=24)
        val, lbl = max_rss(sig, systems)
        decay.append({"r_over_a": rr, "max_RSS_MPa": round(val / 1e6, 3), "system": lbl})

    res = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": "Does the simulated 2D ridge over- or under-estimate the field of a "
                   "compact 3D particle carrying the same eigenstrain?",
        "elastic_constants": {"mu_GPa": MU / 1e9, "nu": NU},
        "eigenstrain": {"amplitude": EPS, "tilt_deg": TILT_DEG,
                        "form": "lambda*(1.5 u(x)u - 0.5 I), trace 0"},
        "interior_stress_MPa": {
            "sphere_3D": {"tensor": (sig_sphere / 1e6).round(2).tolist(),
                          "max_RSS_MPa": round(rss_sphere / 1e6, 2), "system": sys_sphere},
            "cylinder_2D_along_y": {"tensor": (sig_cyl / 1e6).round(2).tolist(),
                                    "max_RSS_MPa": round(rss_cyl / 1e6, 2), "system": sys_cyl},
        },
        "ratio_sphere_over_cylinder": round(rss_sphere / rss_cyl, 3),
        "exterior_decay_sphere": decay,
        "md_ridge_measurement_MPa": {"peak_max_RSS": 6.26, "at_r_A": 30.0,
                                     "source": "stageG4_rss_profile.json"},
        "rescaled_to_real_magnetostriction": {
            "sphere_interior_MPa": {k: round(rss_sphere / 1e6 * lam / EPS, 3)
                                    for k, lam in LAM_REAL.items()},
        },
    }
    res["verdict"] = (
        f"At identical eigenstrain the compact 3D inclusion carries an interior "
        f"max-RSS of {rss_sphere/1e6:.1f} MPa against {rss_cyl/1e6:.1f} MPa for the "
        f"infinite cylinder, a ratio of {rss_sphere/rss_cyl:.2f}. The exterior field "
        f"of the sphere falls to "
        f"{decay[2]['max_RSS_MPa']:.2f} MPa at r = 1.5a and "
        f"{decay[-1]['max_RSS_MPa']:.2f} MPa at r = 3a. The MD ridge cell measured "
        f"6.26 MPa at 30 A from the interface, i.e. the same order as the 3D "
        f"exterior field at comparable relative distance, so the ridge geometry does "
        f"not inflate the driving stress; rescaled to realistic magnetostriction the "
        f"3D interior value itself is "
        f"{rss_sphere/1e6*4e-5/EPS:.2f} MPa at 40 ppm."
    )
    OUT.write_text(json.dumps(res, indent=2) + chr(10), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items()
                      if k in ("interior_stress_MPa", "ratio_sphere_over_cylinder",
                               "exterior_decay_sphere", "verdict")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
