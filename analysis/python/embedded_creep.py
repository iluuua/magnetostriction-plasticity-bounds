#!/usr/bin/env python3
"""Creep-rate increase predicted from the full stress field of the inclusion.

Model (as in stageG5_two_scale_bridge.py). A dislocation segment passes its
obstacles by thermal activation; a local shear stress tau speeds the forward
jumps by exp(V* tau / kT) and slows the backward ones by exp(-V* tau / kT), so
a population with both signs of bias moves faster on average by the factor
cosh(V* tau / kT) (Kocks, Argon and Ashby 1975; Caillard and Martin 2003).
The relative rate increase of a material with inclusion volume fraction f is
the volume average of cosh - 1 over the matrix:

    H = (f / V_p) * integral over r > R of < cosh(V* tau_s(x) / kT) - 1 > dV

The old scalar version assumes tau = tau_m (R/r)^3 for one amplitude tau_m,
which gives H = f x0 * integral_0^x0 (cosh u - 1)/u^2 du, x0 = V* tau_m / kT.
Here tau_s(x) is the resolved shear stress of the computed field on each of
the twelve {111}<110> systems at x, and < > averages over the systems:
  crystal   the twelve systems of the MD crystal orientation
  grains    the twelve systems of 64 random grain orientations (polycrystal)
  max       the largest of the twelve at every point (upper bound)

The field is the isolated-sphere solution for the given strain (the MD field
agrees with it outside the first few angstroms; see embedded_inclusion_field.py).
It is scale free, so H does not depend on R. f = 0.00246, T = 300 K.

    python analysis/python/embedded_creep.py --out docs/reports/embedded_creep.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedded_inclusion_continuum as C  # noqa: E402
import stageG5_two_scale_bridge as G5  # noqa: E402

KT = G5.KT_300
B3 = G5.B3
F_VOL = G5.F_VOL
TARGET = G5.TARGET


def random_rotations(n: int, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    q = rng.normal(size=(n, 4))
    q /= np.linalg.norm(q, axis=1)[:, None]
    w, x, y, z = q.T
    return np.stack([
        np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], -1),
        np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], -1),
        np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], -1)], 1)


def field_samples(radius: float, eps: float):
    """Stress (MPa) on a spherical grid r in (R, 30R), with volume weights / V_p."""
    e_s = C.transformation_strain(C.strain_given(eps))
    u = np.linspace(0, 1, 121)[1:]                       # r = R / u^(1/3): uniform in 1/r^3
    r = radius / np.cbrt(u)
    r = r[r < 30 * radius]
    nt, nph = 48, 48
    ct, wt = np.polynomial.legendre.leggauss(nt)
    ph = (np.arange(nph) + 0.5) * 2 * np.pi / nph
    rr, cc, pp = np.meshgrid(r, ct, ph, indexing="ij")
    st = np.sqrt(1 - cc ** 2)
    pts = np.stack([rr * cc, rr * st * np.cos(pp), rr * st * np.sin(pp)], -1).reshape(-1, 3)
    sig = C.stress_from_strain(C.exterior_strain(pts, np.zeros(3), radius, e_s)) / 1e6
    # dV / V_p: r^2 dr from the 1/r^3 map, dr = (R/3) u^-4/3 du with du = 1/120
    dr = (radius / 3) * np.cbrt(u[:len(r)]) ** -4 * (1 / 120)
    w = (rr ** 2 * dr[:, None, None] * wt[None, :, None] * (2 * np.pi / nph)).reshape(-1)
    return sig, w / (4 / 3 * math.pi * radius ** 3)


def resolved(sig: np.ndarray, systems) -> np.ndarray:
    return np.stack([np.einsum("pij,i,j->p", sig, n, b) for n, b in systems], -1)


def h_of(vstar_b3: float, tau_mpa: np.ndarray, w: np.ndarray, how: str) -> float:
    x = vstar_b3 * B3 * tau_mpa * 1e6 / KT
    if how == "max":
        g = np.cosh(np.max(np.abs(x), axis=-1)) - 1
    else:
        g = (np.cosh(x) - 1).mean(axis=-1)
    return F_VOL * float(np.sum(g * w))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eps", type=float, default=1.94e-3)
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    sig, w = field_samples(a.radius, a.eps)
    base = C.slip_systems()
    tau = {"crystal": resolved(sig, [(n, b) for n, b, _ in base])}
    rots = random_rotations(64)
    tau["grains"] = np.concatenate([resolved(sig, [(Q @ n, Q @ b) for n, b, _ in base]) for Q in rots], -1)
    tau["max"] = tau["crystal"]

    vgrid = np.array([10, 15, 19, 25, 30, 40, 50, 60, 70, 85, 100, 120, 142], float)
    res = {"inputs": {"eps": a.eps, "f": F_VOL, "T_K": 300.0, "b3_m3": B3,
                      "field": "isolated sphere, given strain eps*diag(1,-1/2,-1/2), isotropic Al"},
           "vstar_b3": vgrid.tolist(),
           "required_amplitude_MPa": [G5.required_sigma(v) / 1e6 for v in vgrid],
           "H": {}, "vstar_for_target_b3": {}, "effective_amplitude_MPa": {}}
    for how in ("crystal", "grains", "max"):
        hs = [h_of(v, tau[how], w, how) for v in vgrid]
        res["H"][how] = hs
        f = lambda v: math.log(h_of(v, tau[how], w, how) / TARGET)
        res["vstar_for_target_b3"][how] = brentq(f, 1.0, 400.0)
        # amplitude of the old r^-3 model that gives the same H at each V*
        eff = []
        for v, hv in zip(vgrid, hs):
            top = 600.0 * KT / (v * B3 * 1e6)            # keeps cosh below overflow
            if hv <= 1e-12 or G5.enhancement(top * 1e6, v) < hv:
                eff.append(None)
                continue
            eff.append(brentq(lambda s: G5.enhancement(s * 1e6, v) - hv, 1e-3, top))
        res["effective_amplitude_MPa"][how] = eff
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for how in res["H"]:
        print("%-8s V* for +25%%: %.1f b^3 | H at 70 b^3 = %.3g | effective amplitude at 19/70/142 b^3: %s"
              % (how, res["vstar_for_target_b3"][how], res["H"][how][8],
                 ", ".join("-" if res["effective_amplitude_MPa"][how][i] is None else "%.1f" % res["effective_amplitude_MPa"][how][i] for i in (2, 8, 12))))
    print("required amplitude (old r^-3 model) at 19/70/142 b^3:",
          ", ".join("%.1f" % res["required_amplitude_MPa"][i] for i in (2, 8, 12)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
