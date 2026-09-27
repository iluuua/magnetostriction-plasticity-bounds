#!/usr/bin/env python3
"""Fit retained inclusion strain between paired LAMMPS snapshots.

Atom IDs establish correspondence. Fe coordinates (angstroms) define the
affine fit x - mean(x) = F (X - mean(X)); the dimensionless Green strain is
E = (F.T F - I) / 2. Its projection onto the imposed strain gives eta.
JSON contains subset tensors and formal least-squares errors, not a spread
over independent simulations. The default pair uses a tethered inclusion.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import TextIO

import numpy as np
from _g4clean import (
    CONTROL,
    FIELD,
    DumpFrame,
    file_provenance,
    open_text,
    read_snapshot,
    resolve_dump,
    source_dir,
    validate_pair,
)

REPO = Path(__file__).resolve().parents[2]
EPS_NOM = 1.94e-3
TILT_DEG = 45.0
Z_SUP, RIDGE_H, RIDGE_RX = 20.0, 20.0, 35.0


def eigenstrain_tensor() -> np.ndarray:
    """Trace-free imposed strain, amplitude 0.00194, tilted 45 degrees from z."""
    t = math.radians(TILT_DEG)
    u = np.array([math.sin(t), 0.0, math.cos(t)])
    return EPS_NOM * (1.5 * np.outer(u, u) - 0.5 * np.eye(3))


def load(path: TextIO):
    """Return sorted IDs, types, coordinates, Lx and Ly (legacy API)."""
    frame = read_snapshot(path)
    lengths = frame.bounds[:, 1] - frame.bounds[:, 0]
    return frame.ids, frame.types, frame.positions, lengths[0], lengths[1]


def affine_fit(X: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Least-squares F with x - x_bar = F (X - X_bar)."""
    dX = X - X.mean(axis=0)
    dx = x - x.mean(axis=0)
    return np.linalg.solve(dX.T @ dX, dX.T @ dx).T


def green(F: np.ndarray) -> np.ndarray:
    """Return the dimensionless Green strain of a deformation gradient."""
    return 0.5 * (F.T @ F - np.eye(3))


def retention(control: DumpFrame, field: DumpFrame, n_al: int | None = None) -> dict:
    """Fit Fe subsets in a fixed box with minimum-image x/y displacements.

    The covariance uses pooled residual variance over 3N - 12 degrees of
    freedom and the small-strain linear projection used in the paper.
    Spatial correlations and simulation-to-simulation variation are excluded.
    """
    validate_pair(control, field)
    ty_c, X, x = control.types, control.positions, field.positions
    lx, ly = (control.bounds[:, 1] - control.bounds[:, 0])[:2]

    # This correspondence assumes displacements smaller than half a box length.
    d = x - X
    for k, L in ((0, lx), (1, ly)):
        d[:, k] -= np.round(d[:, k] / L) * L
    x = X + d

    eps = eigenstrain_tensor()
    eps_norm2 = float(np.sum(eps * eps))
    cx = float(control.bounds[0].mean())

    fe = ty_c == 2
    if n_al is not None and np.any(fe & (control.ids <= n_al)):
        raise ValueError("Fe atoms occur within the specified matrix ID range")
    zc = X[:, 2]
    inside_ridge = (np.abs(X[:, 0] - cx) < RIDGE_RX) & (zc >= Z_SUP)
    subsets = {
        "whole_inclusion_Fe_sublattice": fe,
        "support_slab_only_z_lt_18": fe & (zc < 18.0),
        "ridge_only_z_gt_22": fe & (zc > 22.0) & inside_ridge,
        "ridge_interior_z22_34_x_within_25": (
            fe & (zc > 22.0) & (zc < 34.0) & (np.abs(X[:, 0] - cx) < 25.0)
        ),
    }

    out = {}
    for name, m in subsets.items():
        n = int(m.sum())
        if n < 30:
            out[name] = {"n_atoms": n, "note": "too few atoms to fit"}
            continue
        dX = X[m] - X[m].mean(axis=0)
        dx = x[m] - x[m].mean(axis=0)
        G = dX.T @ dX
        F = np.linalg.solve(G, dX.T @ dx).T
        E = green(F)
        eta = float(np.sum(E * eps) / eps_norm2)
        resid = dx - dX @ F.T
        # formal least-squares standard error: the three rows of F are separate
        # regressions on the common centred design matrix, s^2 pooled over
        # 3N - 12 degrees of freedom (nine for F, three for the centroid)
        s2 = float((resid**2).sum() / (3 * n - 12))
        C = np.linalg.inv(G)
        W = eps / eps_norm2
        var = float(
            sum(
                W[a, b] * W[a, bb] * s2 * C[b, bb]
                for a in range(3)
                for b in range(3)
                for bb in range(3)
            )
        )
        out[name] = {
            "n_atoms": n,
            "F_minus_I": np.round(F - np.eye(3), 6).tolist(),
            "E_res": np.round(E, 6).tolist(),
            "eta_retained_fraction": round(eta, 4),
            "eta_standard_error": round(math.sqrt(var), 4),
            "E_res_norm": round(float(math.sqrt(np.sum(E * E))), 6),
            "eps_star_norm": round(float(math.sqrt(eps_norm2)), 6),
            "rms_nonaffine_A": round(float(np.sqrt((resid**2).sum(axis=1).mean())), 4),
        }

    ridge = out["ridge_only_z_gt_22"]
    if "eta_retained_fraction" not in ridge:
        raise ValueError("Too few Fe atoms in the ridge to estimate retention")
    eta_main = ridge["eta_retained_fraction"]
    se_main = ridge["eta_standard_error"]
    res = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "quantity": "Projection of the fitted Fe-sublattice strain onto the imposed strain",
        "method": "best-fit affine map between minimised control and minimised field "
        "on the Fe sublattice; E_res = 0.5(F^T F - I); eta = (E_res:eps*)/(eps*:eps*)",
        "eigenstrain_nominal": EPS_NOM,
        "eigenstrain_tensor": np.round(eigenstrain_tensor(), 8).tolist(),
        "subsets": out,
        "eta_used_for_rescaling": eta_main,
        "eta_used_for_rescaling_se": se_main,
        "eta_note": (
            "Legacy rescaling keys report the ridge subset (z > 22 A). "
            "Eta is a projection diagnostic and does not calibrate the stress field."
        ),
        "error_definition": (
            "formal least-squares standard error, Cov(f_alpha) = "
            "s^2 (Xc^T Xc)^-1 per row with s^2 pooled over 3N-12 "
            "degrees of freedom, propagated linearly to eta; not a "
            "bootstrap and not a spread over seeds"
        ),
        "atom_correspondence": "validated identical atom IDs and types in both snapshots",
        "box_bounds_A": control.bounds.tolist(),
        "snapshot_steps": {"control": control.timestep, "field": field.timestep},
        "matrix_id_limit": n_al,
        "pbc": "minimum image applied to the x and y displacement components before fitting",
        "components_table_1e3": {
            k: {
                "N": v["n_atoms"],
                "Exx": round(v["E_res"][0][0] * 1e3, 3),
                "Eyy": round(v["E_res"][1][1] * 1e3, 3),
                "Ezz": round(v["E_res"][2][2] * 1e3, 3),
                "Exz": round(v["E_res"][0][2] * 1e3, 3),
                "eta": v["eta_retained_fraction"],
                "se": v["eta_standard_error"],
            }
            for k, v in out.items()
            if "eta_retained_fraction" in v
        },
        "nominal_1e3": {
            "Exx": round(eigenstrain_tensor()[0][0] * 1e3, 3),
            "Eyy": round(eigenstrain_tensor()[1][1] * 1e3, 3),
            "Ezz": round(eigenstrain_tensor()[2][2] * 1e3, 3),
            "Exz": round(eigenstrain_tensor()[0][2] * 1e3, 3),
        },
        "interpretation": (
            "A coordinate-strain fit measures the retained deformation. "
            "Boundary constraints and convergence must be established from "
            "the simulation inputs and logs, not inferred from eta."
        ),
    }
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, help="directory containing the curated pair")
    ap.add_argument("--control", type=Path)
    ap.add_argument("--field", type=Path)
    ap.add_argument(
        "--out", type=Path, default=REPO / "docs/reports/stageG12_eigenstrain_retention.json"
    )
    ap.add_argument("--n-al", type=int, help="optional matrix ID limit, checked against Fe IDs")
    ap.add_argument(
        "--protocol", choices=("held", "free", "unspecified"), help="constraint provenance"
    )
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    if bool(args.control) != bool(args.field):
        ap.error("--control and --field must be supplied together")
    src = source_dir(args.src)
    paths = {
        "control": resolve_dump(args.control or src / CONTROL),
        "field": resolve_dump(args.field or src / FIELD),
    }
    with open_text(paths["control"]) as stream:
        control = read_snapshot(stream)
    with open_text(paths["field"]) as stream:
        field = read_snapshot(stream)
    res = retention(control, field, args.n_al)
    res["inputs"] = {key: file_provenance(path) for key, path in paths.items()}
    res["constraint_protocol"] = args.protocol or ("held" if not args.control else "unspecified")
    if args.label:
        res["label"] = args.label
    p = args.out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res, indent=2) + chr(10), encoding="utf-8")

    eps = eigenstrain_tensor()
    print(f"Nominal eps* = {EPS_NOM:.3e}, norm = {np.linalg.norm(eps):.4e}")
    for k, v in res["subsets"].items():
        if "eta_retained_fraction" in v:
            print(
                f"{k:<36} N={v['n_atoms']:6d} eta = {v['eta_retained_fraction']:+.4f} "
                f"+- {v['eta_standard_error']:.4f}, nonaffine RMS = {v['rms_nonaffine_A']:.3f} A"
            )
    print()
    print("E_res of the ridge (x1e3):")
    print(np.round(np.array(res["subsets"]["ridge_only_z_gt_22"]["E_res"]) * 1e3, 4))
    print("eps* (x1e3):")
    print(np.round(eigenstrain_tensor() * 1e3, 4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
