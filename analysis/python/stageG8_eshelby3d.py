#!/usr/bin/env python3
"""Compare spherical and circular-cylinder eigenstrain fields in isotropic Al.

Both inclusions have the matrix stiffness in an infinite elastic medium.
Interior stress uses Eshelby tensors; exterior sphere stress uses a product
Gauss-Legendre volume quadrature (default CLI order 24). No automatic
quadrature-convergence study is implied. Functions use Pa and consistent
length units; JSON reports MPa and r/a. The tethered atomistic ridge has
different geometry and constraints, so this comparison is not a bound.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
from _g4clean import file_provenance

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "docs" / "reports" / "stageG8_eshelby3d.json"

MU = 26.5e9  # Pa, Al shear modulus used throughout the project
NU = 0.347  # Al Poisson ratio
LAMBDA = 2.0 * MU * NU / (1.0 - 2.0 * NU)
EPS = 1.94e-3  # eigenstrain amplitude of the MD cells (0.194 %, the strain of the 147 MPa estimate)
TILT_DEG = 45.0
RIDGE_RX = 35e-10  # m, ridge semi-axis in x
RIDGE_H = 20e-10  # m, ridge semi-axis in z
LAM_REAL = {"20 ppm": 2e-5, "40 ppm": 4e-5, "100 ppm": 1e-4}


def stiffness() -> np.ndarray:
    """Isotropic C_ijkl."""
    d = np.eye(3)
    C = np.zeros((3, 3, 3, 3))
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for ell in range(3):
                    C[i, j, k, ell] = LAMBDA * d[i, j] * d[k, ell] + MU * (
                        d[i, k] * d[j, ell] + d[i, ell] * d[j, k]
                    )
    return C


def eigenstrain_tensor() -> np.ndarray:
    """Trace-free small eigenstrain, tilted TILT_DEG from z toward x."""
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
                for ell in range(3):
                    S[i, j, k, ell] = b * d[i, j] * d[k, ell] + c * (
                        d[i, k] * d[j, ell] + d[i, ell] * d[j, k]
                    )
                    if i == j == k == ell:
                        S[i, j, k, ell] = a
    return S


def eshelby_cylinder() -> np.ndarray:
    """S_ijkl for an infinite circular cylinder along y (Mura Table 11.1),
    axes: 1 = x, 2 = y (cylinder axis), 3 = z."""
    S = np.zeros((3, 3, 3, 3))
    f = 1.0 / (2.0 * (1.0 - NU))
    S[0, 0, 0, 0] = S[2, 2, 2, 2] = f * (5.0 - 4.0 * NU) / 4.0
    S[0, 0, 2, 2] = S[2, 2, 0, 0] = f * (4.0 * NU - 1.0) / 4.0
    # Coupling from axial eigenstrain to the two transverse normal strains.
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
    """Twelve FCC systems in the x=[1-10], y=[11-2], z=[111] frame."""
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
    """Maximum absolute resolved shear and its plane/direction label."""
    best = max(((abs(float(n @ sig @ b)), lbl) for n, b, lbl in systems))
    return best


def exterior_sphere(
    x: np.ndarray, a: float, e: np.ndarray, C: np.ndarray, order: int = 40
) -> np.ndarray:
    """Return sphere exterior stress [Pa]; x and radius a use the same units."""
    if a <= 0 or np.linalg.norm(x) <= a or order < 2:
        raise ValueError("Exterior quadrature requires |x| > a > 0 and order >= 2")
    # Gauss-Legendre nodes on the unit ball via spherical coordinates
    gr, wr = np.polynomial.legendre.leggauss(order)
    gt, wt = np.polynomial.legendre.leggauss(order)
    gp, wp = np.polynomial.legendre.leggauss(order)
    r = 0.5 * a * (gr + 1.0)
    wr = 0.5 * a * wr
    ct = gt
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
                            for ell in range(3):
                                term = (
                                    (1.0 - 2.0 * NU)
                                    * (d[i, j] * zz[k] * zz[ell] + d[k, ell] * zz[i] * zz[j])
                                    + 3.0 * zz[i] * zz[j] * zz[k] * zz[ell]
                                    - d[i, k] * zz[j] * zz[ell]
                                    - d[j, ell] * zz[i] * zz[k]
                                    - d[i, ell] * zz[j] * zz[k]
                                    - d[j, k] * zz[i] * zz[ell]
                                )
                                D[i, j, k, ell] += w * c1 * term / (R1**3) * (2.0 * MU)
    Se = np.einsum("ijkl,kl->ij", D, e)
    return np.einsum("ijkl,kl->ij", C, Se)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument(
        "--profile", type=Path, default=REPO_ROOT / "docs/reports/stageG10_field_profile.json"
    )
    parser.add_argument("--order", type=int, default=24, help="quadrature order per coordinate")
    args = parser.parse_args()
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
        sig = exterior_sphere(np.array([0.0, 0.0, rr * a]), a, e, C, order=args.order)
        val, lbl = max_rss(sig, systems)
        decay.append({"r_over_a": rr, "max_RSS_MPa": round(val / 1e6, 3), "system": lbl})

    md_peak = {"source": str(args.profile)}
    g10 = args.profile
    if g10.exists():
        d10 = json.loads(g10.read_text(encoding="utf-8"))
        md_peak["provenance"] = file_provenance(g10)
        pk = d10.get("peak", {})
        md_peak.update(
            {
                "peak_max_RSS": pk.get("max_RSS_MPa"),
                "at_r_A": pk.get("r_A"),
                "system": pk.get("system"),
                "cell": d10.get("cell"),
                "label": d10.get("label"),
            }
        )
        axis = [
            abs(x["d_sigma_xz_axis_MPa"])
            for x in d10.get("profile", [])
            if x.get("above_apex") and x.get("d_sigma_xz_axis_MPa") is not None
        ]
        md_peak["on_axis_max_abs_d_sigma_xz"] = round(max(axis), 2) if axis else None
    res = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": "Homogeneous isotropic inclusion comparison at the same nominal strain",
        "quadrature": {"order_per_coordinate": args.order, "automatic_convergence_check": False},
        "comparison_limits": (
            "Interior values are not exterior maxima; tethered MD and homogeneous "
            "eigenstrain impose different constraints"
        ),
        "elastic_constants": {"mu_GPa": MU / 1e9, "nu": NU},
        "eigenstrain": {
            "amplitude": EPS,
            "tilt_deg": TILT_DEG,
            "form": "lambda*(1.5 u(x)u - 0.5 I), trace 0",
        },
        "interior_stress_MPa": {
            "sphere_3D": {
                "tensor": (sig_sphere / 1e6).round(2).tolist(),
                "max_RSS_MPa": round(rss_sphere / 1e6, 2),
                "system": sys_sphere,
            },
            "cylinder_2D_along_y": {
                "tensor": (sig_cyl / 1e6).round(2).tolist(),
                "max_RSS_MPa": round(rss_cyl / 1e6, 2),
                "system": sys_cyl,
            },
        },
        "ratio_sphere_over_cylinder": round(rss_sphere / rss_cyl, 3),
        "exterior_decay_sphere": decay,
        "md_ridge_measurement_MPa": md_peak,
        "at_measured_FeAl_magnetostriction": {
            "note": (
                "Sensitivity values using 20-100 ppm from bulk Fe-Al comparisons; "
                "these are not measurements of the simulated Al13Fe4 phase"
            ),
            "sphere_interior_MPa": {
                k: round(rss_sphere / 1e6 * lam / EPS, 3) for k, lam in LAM_REAL.items()
            },
        },
    }
    md_txt = "No MD profile record was found"
    if md_peak.get("peak_max_RSS") is not None:
        md_txt = (
            f"The MD profile gives width-averaged max-RSS {md_peak['peak_max_RSS']:.1f} MPa "
            f"at r = {md_peak['at_r_A']:.0f} A"
        )
        if md_peak.get("on_axis_max_abs_d_sigma_xz") is not None:
            md_txt += f", and axial-window shear {md_peak['on_axis_max_abs_d_sigma_xz']:.1f} MPa"
    res["verdict"] = (
        f"At identical eigenstrain the compact 3D inclusion carries an interior "
        f"max-RSS of {rss_sphere / 1e6:.1f} MPa against {rss_cyl / 1e6:.1f} MPa for the "
        f"infinite cylinder, a ratio of {rss_sphere / rss_cyl:.2f}. The exterior field "
        f"of the sphere falls to "
        f"{decay[2]['max_RSS_MPa']:.2f} MPa at r = 1.5a and "
        f"{decay[-1]['max_RSS_MPa']:.2f} MPa at r = 3a. {md_txt}. At the largest "
        f"magnetostriction measured for bulk Fe-Al alloys (1e-4) the same sphere "
        f"would carry {rss_sphere / 1e6 * 1e-4 / EPS:.2f} MPa."
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2) + chr(10), encoding="utf-8")
    print(
        json.dumps(
            {
                k: v
                for k, v in res.items()
                if k
                in (
                    "interior_stress_MPa",
                    "ratio_sphere_over_cylinder",
                    "exterior_decay_sphere",
                    "verdict",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
