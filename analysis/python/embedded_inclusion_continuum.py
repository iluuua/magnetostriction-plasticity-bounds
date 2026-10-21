#!/usr/bin/env python3
"""Continuum reference for a spherical inclusion given a magnetostrictive strain.

The inclusion is given a uniform strain eps_c (elongation along the field
direction x by eps, contraction along y and z by eps/2). Outside it the
aluminium matrix is isotropic (mu = 26.5 GPa, nu = 0.347). The matrix field
around a sphere whose surface is displaced as u = eps_c . x is the Eshelby
exterior field of an equal-moduli inclusion with transformation strain
eps* = S^-1 : eps_c; the stiffness of the inclusion itself does not enter.

Two references are computed on the same lines and the same section as the MD
cell:
  isolated  closed-form exterior field of one sphere in an infinite matrix
            (Ju and Sun 1999; Mura 1987, Sect. 11)
  periodic  the same sphere repeated with the period of the MD box, solved by
            FFT with the homogeneous Green operator and zero mean stress, which
            is the condition the MD box is relaxed to

    python analysis/python/embedded_inclusion_continuum.py --box 126.0 124.0 126.3 \
        --radius 25 --out docs/reports/embedded_continuum.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

# isotropic (Voigt-Reuss-Hill) constants of Al for the MEAM potential used in the
# MD; see analysis/python/meam_elastic_constants.py
MU = 26.9e9
NU = 0.344
LAM = 2.0 * MU * NU / (1.0 - 2.0 * NU)
EPS = 1.94e-3


def strain_given(eps: float = EPS) -> np.ndarray:
    """Volume-conserving magnetostrictive strain with the field along x."""
    return eps * np.diag([1.0, -0.5, -0.5])


def stiffness() -> np.ndarray:
    d = np.eye(3)
    return (LAM * np.einsum("ij,kl->ijkl", d, d)
            + MU * (np.einsum("ik,jl->ijkl", d, d) + np.einsum("il,jk->ijkl", d, d)))


def eshelby_interior() -> np.ndarray:
    """Interior Eshelby tensor of a sphere (Mura Eq. 11.16)."""
    d = np.eye(3)
    b = (5.0 * NU - 1.0) / (15.0 * (1.0 - NU))
    c = (4.0 - 5.0 * NU) / (15.0 * (1.0 - NU))
    return b * np.einsum("ij,kl->ijkl", d, d) + c * (np.einsum("ik,jl->ijkl", d, d)
                                                     + np.einsum("il,jk->ijkl", d, d))


def transformation_strain(eps_c: np.ndarray) -> np.ndarray:
    """eps* such that the interior strain S : eps* equals eps_c."""
    S = eshelby_interior().reshape(9, 9)
    return np.linalg.lstsq(S, eps_c.reshape(9), rcond=None)[0].reshape(3, 3)


def exterior_strain(pts: np.ndarray, centre: np.ndarray, a: float, e_star: np.ndarray) -> np.ndarray:
    """Exterior strain at points |x - c| > a (Ju and Sun 1999, sphere)."""
    r = pts - centre
    R = np.linalg.norm(r, axis=1)
    n = r / R[:, None]
    p2 = (a / R) ** 2
    pre = (a / R) ** 3 / (30.0 * (1.0 - NU))
    tr = np.trace(e_star)
    ne = np.einsum("pk,kl,pl->p", n, e_star, n)               # n.e*.n
    en = np.einsum("kl,pl->pk", e_star, n)                     # e*.n
    nn = np.einsum("pi,pj->pij", n, n)
    d = np.eye(3)[None, :, :]
    out = ((3 * p2 + 10 * NU - 5)[:, None, None] * tr * d
           + 2 * (3 * p2 - 10 * NU + 5)[:, None, None] * e_star[None]
           + 15 * (1 - p2)[:, None, None] * d * ne[:, None, None]
           + 15 * (1 - 2 * NU - p2)[:, None, None] * tr * nn
           + 15 * (NU - p2)[:, None, None] * 2 * (np.einsum("pi,pj->pij", n, en)
                                                   + np.einsum("pi,pj->pij", en, n))
           + 15 * (7 * p2 - 5)[:, None, None] * ne[:, None, None] * nn)
    return pre[:, None, None] * out


def stress_from_strain(eps: np.ndarray) -> np.ndarray:
    tr = np.trace(eps, axis1=-2, axis2=-1)
    return LAM * tr[..., None, None] * np.eye(3) + 2.0 * MU * eps


def periodic_fft(box: np.ndarray, centre: np.ndarray, a: float, e_star: np.ndarray,
                 h: float = 1.0) -> tuple[np.ndarray, list[np.ndarray]]:
    """Stress field of a periodic array of equal-moduli spheres, zero mean stress."""
    n = [int(round(L / h)) for L in box]
    n = [k + (k % 2) for k in n]
    axes = [np.arange(k) * (L / k) for k, L in zip(n, box)]
    X = np.meshgrid(*axes, indexing="ij")
    dx = [((X[i] - centre[i] + box[i] / 2) % box[i]) - box[i] / 2 for i in range(3)]
    rr = np.sqrt(dx[0] ** 2 + dx[1] ** 2 + dx[2] ** 2)
    # characteristic function of the sphere, smoothed over one voxel
    chi = np.clip(0.5 - (rr - a) / h, 0.0, 1.0)
    tau = np.einsum("ijkl,kl->ij", stiffness(), e_star)        # C : e*
    chi_k = np.fft.fftn(chi)
    k = np.meshgrid(*[2 * np.pi * np.fft.fftfreq(m, d=L / m) for m, L in zip(n, box)],
                    indexing="ij")
    k2 = k[0] ** 2 + k[1] ** 2 + k[2] ** 2
    k2[0, 0, 0] = 1.0
    xi = [ki / np.sqrt(k2) for ki in k]
    # strain eps_ij = Gamma_ijkl(xi) tau_kl chi(k), isotropic Green operator
    t_xi = [sum(tau[i, j] * xi[j] for j in range(3)) for i in range(3)]   # tau . xi
    xi_t_xi = sum(xi[i] * t_xi[i] for i in range(3))
    c2 = (LAM + MU) / (MU * (LAM + 2 * MU))
    eps = np.zeros((3, 3) + tuple(n))
    for i in range(3):
        for j in range(3):
            g = (xi[i] * t_xi[j] + xi[j] * t_xi[i]) / (2 * MU) - c2 * xi[i] * xi[j] * xi_t_xi
            g[0, 0, 0] = 0.0
            eps[i, j] = np.real(np.fft.ifftn(g * chi_k))
    # zero mean stress: the macroscopic strain equals the mean transformation strain
    eps += (chi.mean() * e_star)[:, :, None, None, None]
    eps_el = eps - chi[None, None] * e_star[:, :, None, None, None]
    tr = eps_el[0, 0] + eps_el[1, 1] + eps_el[2, 2]
    sig = 2 * MU * eps_el
    for i in range(3):
        sig[i, i] += LAM * tr
    return sig, axes


def cubic_in_cell_frame(c11: float, c12: float, c44: float) -> np.ndarray:
    """Cubic stiffness (Pa) rotated to x = [1-10], y = [11-2], z = [111]."""
    d = np.eye(3)
    C0 = np.zeros((3, 3, 3, 3))
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for l in range(3):
                    if i == j == k == l:
                        C0[i, j, k, l] = c11
                    elif i == j and k == l:
                        C0[i, j, k, l] = c12
                    elif (i == k and j == l) or (i == l and j == k):
                        C0[i, j, k, l] = c44
    R = np.vstack([np.array([1.0, -1.0, 0.0]) / math.sqrt(2.0),
                   np.array([1.0, 1.0, -2.0]) / math.sqrt(6.0),
                   np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)])
    return np.einsum("ai,bj,ck,dl,ijkl->abcd", R, R, R, R, C0)


def periodic_fft_frozen(box: np.ndarray, centre: np.ndarray, a: float, e_c: np.ndarray,
                        Cs: np.ndarray, h: float = 1.0, iterations: int = 3,
                        displacement: bool = False):
    """Fixed-box (zero mean strain) periodic solution in an anisotropic medium of
    stiffness Cs, with a spherical transformation strain e* adjusted until the
    inclusion's mean strain equals the given e_c, as for the held MD inclusion.
    Returns stress (Pa, shape 3x3xNxNxN), grid axes, e* and the inclusion strain."""
    n = [int(round(L / h)) for L in box]
    n = [k + (k % 2) for k in n]
    axes = [np.arange(k) * (L / k) for k, L in zip(n, box)]
    X = np.meshgrid(*axes, indexing="ij")
    dx = [((X[i] - centre[i] + box[i] / 2) % box[i]) - box[i] / 2 for i in range(3)]
    rr = np.sqrt(dx[0] ** 2 + dx[1] ** 2 + dx[2] ** 2)
    del X, dx
    chi = np.clip(0.5 - (rr - a) / h, 0.0, 1.0)
    del rr
    chi_k = np.fft.fftn(chi)
    kk = np.meshgrid(*[2 * np.pi * np.fft.fftfreq(m, d=L / m) for m, L in zip(n, box)], indexing="ij")
    kn = np.sqrt(kk[0] ** 2 + kk[1] ** 2 + kk[2] ** 2)
    kn[0, 0, 0] = 1.0
    xi = np.stack([k / kn for k in kk], axis=-1).reshape(-1, 3)
    del kk, kn
    K = np.einsum("ijkl,pj,pl->pik", Cs, xi, xi)
    K[0] = np.eye(3)
    N = np.linalg.inv(K)
    del K
    inside = chi > 0.5

    def solve(e_star):
        tau = np.einsum("ijkl,kl->ij", Cs, e_star)
        w = np.einsum("pjk,kl,pl->pj", N, tau, xi)          # N (tau xi)
        eps = np.empty((3, 3) + tuple(n))
        for i in range(3):
            for j in range(i, 3):
                g = 0.5 * (xi[:, i] * w[:, j] + xi[:, j] * w[:, i])
                g[0] = 0.0                                   # fixed box: no mean strain
                eps[i, j] = np.real(np.fft.ifftn(g.reshape(n) * chi_k))
                eps[j, i] = eps[i, j]
        return eps

    S = eshelby_interior().reshape(9, 9)
    e_star = transformation_strain(e_c)
    for _ in range(iterations):
        eps = solve(e_star)
        e_in = eps[:, :, inside].mean(axis=-1)
        e_star = e_star + np.linalg.lstsq(S, (e_c - e_in).reshape(9), rcond=None)[0].reshape(3, 3)
    eps = solve(e_star)
    e_in = eps[:, :, inside].mean(axis=-1)
    if displacement:
        # u(k) = -i N(xi) (tau xi) chi(k) / |k|; zero mean, as the strain has
        kmag = np.sqrt(sum(k ** 2 for k in np.meshgrid(
            *[2 * np.pi * np.fft.fftfreq(m, d=L / m) for m, L in zip(n, box)], indexing="ij"))).reshape(-1)
        kmag[0] = 1.0
        tau = np.einsum("ijkl,kl->ij", Cs, e_star)
        w = np.einsum("pjk,kl,pl->pj", N, tau, xi)
        u = np.empty((3,) + tuple(n))
        for i in range(3):
            ui = -1j * w[:, i] / kmag
            ui[0] = 0.0
            u[i] = np.real(np.fft.ifftn(ui.reshape(n) * chi_k))
        return u, axes, e_star, e_in
    eps -= chi[None, None] * e_star[:, :, None, None, None]
    sig = np.einsum("ijkl,kl...->ij...", Cs, eps)
    return sig, axes, e_star, e_in



def slip_systems() -> list[tuple[np.ndarray, np.ndarray, str]]:
    ex = np.array([1.0, -1.0, 0.0]) / math.sqrt(2.0)
    ey = np.array([1.0, 1.0, -2.0]) / math.sqrt(6.0)
    ez = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    Rm = np.vstack([ex, ey, ez])
    out = []
    for p in [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]:
        nv = np.array(p, float) / np.linalg.norm(p)
        for dv in [(1, -1, 0), (1, 0, -1), (0, 1, -1), (1, 1, 0), (1, 0, 1), (0, 1, 1)]:
            bv = np.array(dv, float) / np.linalg.norm(dv)
            if abs(float(nv @ bv)) < 1e-9:
                out.append((Rm @ nv, Rm @ bv, "(%d%d%d)[%d%d%d]" % (p + dv)))
    return out


def invariants(sig: np.ndarray) -> dict[str, np.ndarray]:
    """sig: (..., 3, 3) in Pa. Returns MPa arrays."""
    s = sig / 1e6
    systems = slip_systems()
    rss = np.stack([np.einsum("...ij,i,j->...", s, nv, bv) for nv, bv, _ in systems], axis=-1)
    ev = np.linalg.eigvalsh(s)
    dev = s - np.trace(s, axis1=-2, axis2=-1)[..., None, None] / 3 * np.eye(3)
    vm = np.sqrt(1.5 * np.einsum("...ij,...ij->...", dev, dev))
    return {"sxx": s[..., 0, 0], "syy": s[..., 1, 1], "szz": s[..., 2, 2], "sxz": s[..., 0, 2],
            "rss_slip": s[..., 0, 2], "rss_max": np.max(np.abs(rss), axis=-1),
            "tau_max": (ev[..., -1] - ev[..., 0]) / 2, "von_mises": vm}


LINES = {"pole": np.array([1.0, 0.0, 0.0]), "equator": np.array([0.0, 0.0, 1.0]),
         "diagonal": np.array([1.0, 0.0, 1.0]) / math.sqrt(2.0)}


def along(sig: np.ndarray, u: np.ndarray) -> dict[str, np.ndarray]:
    """Normal stresses along and across the radius u, glide stress sigma_xz,
    von Mises; sig in Pa with shape (..., 3, 3); returns MPa."""
    s = sig / 1e6
    tvec = np.array([-u[2], 0.0, u[0]])
    dev = s - np.trace(s, axis1=-2, axis2=-1)[..., None, None] / 3 * np.eye(3)
    return {"srr": np.einsum("i,...ij,j->...", u, s, u),
            "stt": np.einsum("i,...ij,j->...", tvec, s, tvec),
            "s_axial_shear": s[..., 0, 2],
            "von_mises": np.sqrt(1.5 * np.einsum("...ij,...ij->...", dev, dev))}


def main() -> int:
    import embedded_inclusion_field as F

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--box", type=float, nargs=3, default=[126.006, 124.005, 126.267])
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--eps", type=float, default=EPS)
    ap.add_argument("--grid", type=float, default=1.0, help="FFT voxel size, A")
    ap.add_argument("--elastic", type=Path,
                    default=Path(__file__).resolve().parents[2] / "docs/reports/meam_elastic_constants.json")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    box = np.array(a.box)
    centre = box / 2
    e_c = strain_given(a.eps)
    e_s = transformation_strain(e_c)
    el = json.loads(a.elastic.read_text(encoding="utf-8"))["Al"]
    Cs = cubic_in_cell_frame(el["C11"] * 1e9, el["C12"] * 1e9, el["C44"] * 1e9)

    S = eshelby_interior()
    inner = np.einsum("ijkl,kl->ij", stiffness(), np.einsum("ijkl,kl->ij", S, e_s) - e_s)
    res = {"inputs": {"mu_GPa": MU / 1e9, "nu": NU, "eps": a.eps, "radius_A": a.radius,
                      "box_A": box.tolist(), "given_strain": e_c.tolist(),
                      "cubic_C_GPa": [el["C11"], el["C12"], el["C44"]],
                      "isolated": "closed form, isotropic Al, infinite matrix",
                      "periodic": "FFT, cubic Al of the MEAM potential, the MD box, fixed box "
                                  "(zero mean strain), inclusion strain held at the given value"},
           "isolated_interior_stress_MPa": (inner / 1e6).round(3).tolist(),
           "isolated": {}, "periodic": {}}

    # isolated sphere: exact values on rays in the xz plane at the window centres
    for name, (deg, _) in F.DIRECTIONS.items():
        u = np.array([math.cos(math.radians(deg)), 0.0, math.sin(math.radians(deg))])
        rr = np.concatenate([a.radius + np.arange(0.25, min(box) / 2 - a.radius, 0.5),
                             np.geomspace(min(box) / 2, 10 * a.radius, 80)])
        sig = stress_from_strain(exterior_strain(centre + rr[:, None] * u, centre, a.radius, e_s))
        g = F.Geometry(centre + rr[:, None] * u, centre, box * 100, a.radius)
        comp = F.components(sig / 1e6, g, np.arange(len(rr)))
        res["isolated"][name] = {"d_A": (rr - a.radius).round(4).tolist(),
                                 **{k: np.round(v, 4).tolist() for k, v in comp.items()}}

    # periodic, fixed box: same windows and shells as the MD analysis
    sig, axes, e_star, e_in = periodic_fft_frozen(box, centre, a.radius, e_c, Cs, a.grid)
    res["inputs"]["periodic_transformation_strain"] = e_star.tolist()
    res["inputs"]["periodic_inclusion_strain"] = e_in.tolist()
    X = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    tens = np.moveaxis(sig, (0, 1), (-2, -1)).reshape(-1, 3, 3) / 1e6
    g = F.Geometry(X, centre, box, a.radius)
    outside = g.d > 0.5 * a.grid
    dmax = float(min(box) / 2 - a.radius)
    for name, sel in F.selections(g.theta, outside).items():
        res["periodic"][name] = F.shell_profile(tens, g, sel, dmax)
    res["periodic_mean_matrix_MPa"] = dict(zip(["xx", "yy", "zz", "xy", "xz", "yz"],
        [float(tens[outside][:, i, j].mean()) for i, j in ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))]))
    # section y = y_c for the map figure
    jy = int(round(centre[1] / (axes[1][1] - axes[1][0])))
    sec = sig[:, :, :, jy, :] / 1e6
    dev = sec - np.trace(sec)[None, None] / 3 * np.eye(3)[:, :, None, None]
    res["section_xz"] = {"x_A": (axes[0] - centre[0]).tolist(), "z_A": (axes[2] - centre[2]).tolist(),
                         "sxx": np.round(sec[0, 0], 3).tolist(), "szz": np.round(sec[2, 2], 3).tolist(),
                         "sxz": np.round(sec[0, 2], 3).tolist(),
                         "von_mises": np.round(np.sqrt(1.5 * np.einsum("ij...,ij...->...", dev, dev)), 3).tolist()}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res) + "\n", encoding="utf-8")
    for name in F.DIRECTIONS:
        I, P = res["isolated"][name], res["periodic"][name]
        k = min(range(len(I["d_A"])), key=lambda q: abs(I["d_A"][q] - 5.0))
        q = min(P, key=lambda r: abs(r["d_A"] - 5.0))
        print("%-9s d=5 A  isolated: srr %7.1f shear %6.1f vm %6.1f | periodic: srr %7.1f shear %6.1f vm %6.1f"
              % (name, I["srr"][k], I["s_axial_shear"][k], I["von_mises"][k],
                 q["srr"], q["s_axial_shear"], q["von_mises"]))
    print("periodic mean over the matrix (MPa):", {k: round(v, 2) for k, v in res["periodic_mean_matrix_MPa"].items()})
    print("isolated interior stress (MPa):", res["isolated_interior_stress_MPa"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
