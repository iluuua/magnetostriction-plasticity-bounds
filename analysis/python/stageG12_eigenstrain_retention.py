#!/usr/bin/env python3
"""Stage G12: how much of the nominal eigenstrain survives minimisation?

The external review raised the one question that decides whether the whole
rescaling to 20-100 ppm is meaningful. Section 2.2 applies

    r -> r + eps* . (r - r_c)      (volume conserving, trace zero)

to the Fe4Al13 atoms and then minimises WITHOUT any constraint holding that
distortion. The equilibrium metric of the MEAM potential is untouched, so the
inclusion is free to relax the imposed mode back out. If it relaxes most of it
away, then "eps* = 1.94e-3" labels a perturbation that was applied, not one
that was carried, and every stress rescaled from it is referenced to the wrong
amplitude.

The retained fraction is measurable. For the inclusion atoms we fit the best
affine map between the MINIMISED control and the MINIMISED field state,

    F = argmin sum_i || (x_i - x_bar) - F (X_i - X_bar) ||^2
    E_res = 0.5 (F^T F - I)
    eta   = (E_res : eps*) / (eps* : eps*)

eta = 1 means the mode is carried in full; eta = 0 means it was relaxed away.
The Fe sublattice is used for the fit: an affine map acts on every sublattice
alike, and the Fe positions are unambiguous inclusion markers.
"""
from __future__ import annotations

import io
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
BASE = Path("C:/Users/dille/AppData/Local/Temp/claude/g4clean")
EPS_NOM = 1.94e-3
TILT_DEG = 45.0
Z_SUP, RIDGE_H, RIDGE_RX = 20.0, 20.0, 35.0


def eigenstrain_tensor() -> np.ndarray:
    t = math.radians(TILT_DEG)
    u = np.array([math.sin(t), 0.0, math.cos(t)])
    return EPS_NOM * (1.5 * np.outer(u, u) - 0.5 * np.eye(3))


def load(path: Path):
    rows, started, box = [], False, []
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        if ln.startswith("ITEM: BOX"):
            started = "box"
            continue
        if started == "box" and len(box) < 3:
            box.append([float(v) for v in ln.split()])
            continue
        if ln.startswith("ITEM: ATOMS"):
            started = True
            continue
        if started is True:
            p = ln.split()
            if len(p) >= 5:
                rows.append([float(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4])])
    a = np.array(rows)
    order = np.argsort(a[:, 0])
    a = a[order]
    lx = box[0][1] - box[0][0]
    ly = box[1][1] - box[1][0]
    return a[:, 0].astype(int), a[:, 1].astype(int), a[:, 2:5], lx, ly


def affine_fit(X: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Least-squares F with x - x_bar = F (X - X_bar)."""
    dX = X - X.mean(axis=0)
    dx = x - x.mean(axis=0)
    return np.linalg.solve(dX.T @ dX, dX.T @ dx).T


def green(F: np.ndarray) -> np.ndarray:
    return 0.5 * (F.T @ F - np.eye(3))


def main() -> int:
    ids_c, ty_c, X, lx, ly = load(BASE / "G4_tilted_eps0000_clean.gate.lammpstrj")
    ids_f, ty_f, x, _, _ = load(BASE / "G4_tilted_eps00194_clean.gate.lammpstrj")
    assert np.array_equal(ids_c, ids_f) and np.array_equal(ty_c, ty_f)

    # minimum image in the periodic directions: the two minimised states differ
    # by ~0.1 A, so anything larger is a wrap, not a displacement
    d = x - X
    for k, L in ((0, lx), (1, ly)):
        d[:, k] -= np.round(d[:, k] / L) * L
    x = X + d

    eps = eigenstrain_tensor()
    eps_norm2 = float(np.sum(eps * eps))
    cx = lx / 2.0

    fe = ty_c == 2
    zc = X[:, 2]
    inside_ridge = (np.abs(X[:, 0] - cx) < RIDGE_RX) & (zc >= Z_SUP)
    subsets = {
        "whole_inclusion_Fe_sublattice": fe,
        "support_slab_only_z_lt_18": fe & (zc < 18.0),
        "ridge_only_z_gt_22": fe & (zc > 22.0) & inside_ridge,
        "ridge_interior_z22_34_x_within_25": (fe & (zc > 22.0) & (zc < 34.0)
                                              & (np.abs(X[:, 0] - cx) < 25.0)),
    }

    out = {}
    for name, m in subsets.items():
        n = int(m.sum())
        if n < 30:
            out[name] = {"n_atoms": n, "note": "too few atoms to fit"}
            continue
        F = affine_fit(X[m], x[m])
        E = green(F)
        eta = float(np.sum(E * eps) / eps_norm2)
        resid = (x[m] - x[m].mean(axis=0)) - (X[m] - X[m].mean(axis=0)) @ F.T
        out[name] = {
            "n_atoms": n,
            "F_minus_I": np.round(F - np.eye(3), 6).tolist(),
            "E_res": np.round(E, 6).tolist(),
            "eta_retained_fraction": round(eta, 4),
            "E_res_norm": round(float(math.sqrt(np.sum(E * E))), 6),
            "eps_star_norm": round(float(math.sqrt(eps_norm2)), 6),
            "rms_nonaffine_A": round(float(np.sqrt((resid ** 2).sum(axis=1).mean())), 4),
        }

    eta_main = out["ridge_interior_z22_34_x_within_25"]["eta_retained_fraction"]
    res = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "question": "Does the nominal eigenstrain survive unconstrained minimisation?",
        "method": "best-fit affine map between minimised control and minimised field "
                  "on the Fe sublattice; E_res = 0.5(F^T F - I); eta = (E_res:eps*)/(eps*:eps*)",
        "eigenstrain_nominal": EPS_NOM,
        "eigenstrain_tensor": np.round(eigenstrain_tensor(), 8).tolist(),
        "subsets": out,
        "eta_used_for_rescaling": eta_main,
        "effective_eigenstrain": round(eta_main * EPS_NOM, 8),
    }
    p = REPO / "docs" / "reports" / "stageG12_eigenstrain_retention.json"
    p.write_text(json.dumps(res, indent=2) + chr(10), encoding="utf-8")

    print("nominal eps* = %.3e, ||eps*|| = %.4e" % (EPS_NOM, math.sqrt(eps_norm2)))
    for k, v in out.items():
        if "eta_retained_fraction" in v:
            print("%-36s N=%6d  eta = %+.4f   ||E_res|| = %.3e  nonaffine rms = %.3f A"
                  % (k, v["n_atoms"], v["eta_retained_fraction"], v["E_res_norm"],
                     v["rms_nonaffine_A"]))
    print()
    print("E_res of ridge interior (x1e3):")
    print(np.round(np.array(out["ridge_interior_z22_34_x_within_25"]["E_res"]) * 1e3, 4))
    print("eps* (x1e3):")
    print(np.round(eigenstrain_tensor() * 1e3, 4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
