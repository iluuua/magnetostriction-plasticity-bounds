#!/usr/bin/env python3
"""At what inclusion strain does the matrix around a real particle start to yield?

Elastic estimate for a micron-size particle, from the closed-form exterior field
of a single sphere held at the given strain eps diag(1, -1/2, -1/2) in isotropic
aluminium (embedded_inclusion_continuum.py). The field depends only on r/R and
scales linearly with eps, so for each radius the largest value over directions
gives the strain at which a criterion is first reached there:

  von Mises        sigma_eq   against the alloy yield stress 40-60 MPa
  slip, crystal    largest resolved shear on the twelve {111}<110> systems of
                   the cell orientation (x = [1-10], z = [111])
  slip, any grain  Tresca maximum shear (sigma_1 - sigma_3)/2, the upper bound
                   over grain orientations
  against the critical resolved shear stress 13-20 MPa (yield stress / 3.06).

Reported: the threshold strain at the surface (r -> R) for each criterion, and
the outer radius r_p/R of the shell above the criterion for a list of strains.
The particle is rigid in this model (its strain is prescribed), so the
thresholds are lower bounds and the shells upper bounds for a real particle.

    python analysis/python/embedded_yield.py --out docs/reports/embedded_yield.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import embedded_inclusion_continuum as C

YIELD_MPA = (40.0, 60.0)
CRSS_MPA = (13.0, 20.0)


def shell_maxima(r_over_R: np.ndarray, eps: float, n_theta: int = 91, n_phi: int = 72) -> dict:
    """Largest von Mises, crystal RSS and Tresca shear over directions at each r/R."""
    e_s = C.transformation_strain(C.strain_given(eps))
    th = np.radians(np.linspace(0.0, 180.0, n_theta))
    ph = np.radians(np.linspace(0.0, 360.0, n_phi, endpoint=False))
    T, P = np.meshgrid(th, ph, indexing="ij")
    n = np.stack([np.cos(T), np.sin(T) * np.cos(P), np.sin(T) * np.sin(P)], -1).reshape(-1, 3)
    out = {"von_mises": [], "rss_crystal": [], "tresca": []}
    for r in r_over_R:
        sig = C.stress_from_strain(C.exterior_strain(r * n, np.zeros(3), 1.0, e_s))
        inv = C.invariants(sig)
        out["von_mises"].append(float(inv["von_mises"].max()))
        out["rss_crystal"].append(float(inv["rss_max"].max()))
        out["tresca"].append(float(inv["tau_max"].max()))
    return {k: np.array(v) for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    eps0 = C.EPS
    r = 1.0 + np.concatenate([[1e-4], np.geomspace(0.002, 9.0, 160)])
    m = shell_maxima(r, eps0)
    crit = {"von_mises": YIELD_MPA, "rss_crystal": CRSS_MPA, "tresca": CRSS_MPA}
    res = {"model": "single sphere, closed-form exterior field, isotropic Al (mu 26.9 GPa, nu 0.344), "
                    "inclusion strain held (rigid particle)",
           "eps_reference": eps0, "yield_stress_MPa": YIELD_MPA, "crss_MPa": CRSS_MPA,
           "profile": {"r_over_R": r.round(5).tolist(), **{k: v.round(4).tolist() for k, v in m.items()}},
           "surface_MPa": {k: float(v[0]) for k, v in m.items()},
           "peak_MPa": {k: float(v.max()) for k, v in m.items()},
           "threshold_strain_percent": {}, "shell_outer_r_over_R": {}}
    for k, (lo, hi) in crit.items():
        peak = m[k].max()          # the first point to reach the criterion as eps grows
        res["threshold_strain_percent"][k] = [100 * eps0 * lo / peak, 100 * eps0 * hi / peak]
    strains = [0.005, 0.01, 0.02, 0.05, 0.1, 0.194, 0.3]
    for k, (lo, hi) in crit.items():
        rows = []
        for e in strains:
            s = m[k] * e / (100 * eps0)
            def outer(level):
                above = np.flatnonzero(s >= level)
                if not above.size:
                    return None
                i = above.max()
                if i + 1 >= len(r):
                    return float(r[i])
                # linear interpolation of the crossing between r[i] and r[i + 1]
                return float(r[i] + (r[i + 1] - r[i]) * (s[i] - level) / (s[i] - s[i + 1]))
            rows.append({"eps_percent": e, "r_over_R_at_low_limit": outer(lo), "r_over_R_at_high_limit": outer(hi)})
        res["shell_outer_r_over_R"][k] = rows
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("surface_MPa", "peak_MPa", "threshold_strain_percent")}, indent=1))
    for k, rows in res["shell_outer_r_over_R"].items():
        print(k, [(q["eps_percent"], q["r_over_R_at_low_limit"], q["r_over_R_at_high_limit"]) for q in rows])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
