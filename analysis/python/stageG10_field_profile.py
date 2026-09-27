#!/usr/bin/env python3
"""Compute the interface stress profile from a matched pair of LAMMPS dumps.

Average the six stress/atom components on control-defined, type-1 atom sets,
then subtract strained minus control tensors. Output JSON and CSV report
stress in MPa and distance in angstroms. ``r = z - 20 A`` is height above the
flat interface plane, not distance to the nearest inclusion surface.
The conversion -S / volume is compression-positive, opposite in sign to a
tensile-positive Cauchy tensor. Absolute projections and invariants agree.
The full-width layers and the 20 A window about the ridge axis are distinct
averages. Only complete layers above the apex enter the reported peak.
"""

from __future__ import annotations

import argparse
import csv
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
REPORTS = REPO / "docs" / "reports"

V_AT = 16.6072  # A^3 per Al atom
Z_INTERFACE = 20.0  # flat Fe4Al13/Al boundary
MATRIX_ATOMS = 72532  # inclusion atoms have larger IDs in the deposited interface cells
BIN = 4.0
R_MAX = 110.0  # final published bin centre (last bin edges: 108, 112 A)
AXIS_HALF_WIDTH = 10.0
EPS_INFLATED = 1.94e-3
LAMBDA_REAL = {"20 ppm": 2e-5, "40 ppm": 4e-5, "100 ppm": 1e-4}
MU_AL = 26.5e9


def slip_systems_lab():
    """Return 12 FCC plane/direction pairs for x=[1-10], y=[11-2], z=[111]."""
    ex = np.array([1.0, -1.0, 0.0]) / math.sqrt(2.0)
    ey = np.array([1.0, 1.0, -2.0]) / math.sqrt(6.0)
    ez = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    R = np.vstack([ex, ey, ez])
    planes = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    dirs = [(1, -1, 0), (1, 0, -1), (0, 1, -1), (1, 1, 0), (1, 0, 1), (0, 1, 1)]
    out = []
    for p in planes:
        n_c = np.array(p, float) / np.linalg.norm(p)
        for d in dirs:
            b_c = np.array(d, float) / np.linalg.norm(d)
            if abs(float(n_c @ b_c)) > 1e-9:
                continue
            label = f"({p[0]}{p[1]}{p[2]})[{d[0]}{d[1]}{d[2]}]"
            out.append((R @ n_c, R @ b_c, label))
    return out


def load(path: TextIO):
    """Return types, coordinates and virials, sorted by ID (legacy API)."""
    frame = read_snapshot(path, require_stress=True)
    return frame.types, frame.positions, frame.stress


def tensor(v):
    """Expand xx, yy, zz, xy, xz, yz components to a symmetric tensor."""
    return np.array([[v[0], v[3], v[4]], [v[3], v[1], v[5]], [v[4], v[5], v[2]]])


def vm(t):
    """Von Mises stress, in the same units as the supplied stress tensor."""
    d = t - np.trace(t) / 3.0 * np.eye(3)
    return float(math.sqrt(1.5 * np.sum(d * d)))


def field_profile(
    control: DumpFrame,
    field: DumpFrame,
    r_max: float = R_MAX,
    matrix_atoms: int = MATRIX_ATOMS,
) -> dict:
    """Calculate both spatial averages using matched atom IDs and fixed bins.

    ``r_max`` sets the bin range as in the published record; a final bin can
    extend beyond it by less than 4 A. The axis centre uses the midpoint of
    the control atom x-extents to reproduce the published window exactly.
    """
    validate_pair(control, field)
    if control.stress is None or field.stress is None:
        raise ValueError("Both snapshots must contain stress/atom components")
    if not np.isfinite(r_max) or r_max <= 0:
        raise ValueError("r_max must be positive and finite")
    t_c, p_c, s_c = control.types, control.positions, control.stress
    s_f = field.stress
    inclusion = control.ids > matrix_atoms
    if not inclusion.any() or not np.array_equal(
        control.ids[~inclusion], np.arange(1, matrix_atoms + 1)
    ):
        raise ValueError("Matrix atom count must match the contiguous matrix IDs in the input")
    # Include both Al and Fe in the actual inclusion envelope, in both snapshots.
    apex_control = float(control.positions[inclusion, 2].max())
    apex_field = float(field.positions[inclusion, 2].max())
    ridge_apex = max(apex_control, apex_field)
    systems = slip_systems_lab()

    rows = []
    edges = np.arange(0.0, r_max + BIN, BIN)
    axis_center = 0.5 * float(np.max(p_c[:, 0]) + np.min(p_c[:, 0]))
    for i in range(len(edges) - 1):
        lo, hi = Z_INTERFACE + edges[i], Z_INTERFACE + edges[i + 1]
        m = (p_c[:, 2] >= lo) & (p_c[:, 2] < hi) & (t_c == 1)
        m_axis = m & (np.abs(p_c[:, 0] - axis_center) < AXIS_HALF_WIDTH)
        n = int(m.sum())
        if n < 50:
            continue
        sc = -s_c[m].mean(axis=0) / V_AT / 10.0
        sf = -s_f[m].mean(axis=0) / V_AT / 10.0
        Tc, Tf = tensor(sc), tensor(sf)
        dT = Tf - Tc
        rss = sorted(((abs(float(nn @ dT @ bb)), lbl) for nn, bb, lbl in systems), reverse=True)
        rows.append(
            {
                "r_A": round((edges[i] + edges[i + 1]) / 2, 1),
                "above_apex": bool(lo >= ridge_apex),
                "n_inclusion_al_atoms": int((m & inclusion).sum()),
                "vm_control_MPa": round(vm(Tc), 3),
                "vm_field_MPa": round(vm(Tf), 3),
                "vm_of_difference_MPa": round(vm(dT), 3),
                "diff_of_vm_MPa": round(vm(Tf) - vm(Tc), 3),
                "max_RSS_MPa": round(rss[0][0], 3),
                "system": rss[0][1],
                "d_sigma_xz_MPa": round(float(dT[0, 2]), 3),
                "d_sigma_xz_axis_MPa": (
                    round(
                        float(
                            ((-s_f[m_axis].mean(axis=0) + s_c[m_axis].mean(axis=0)) / V_AT / 10.0)[
                                4
                            ]
                        ),
                        3,
                    )
                    if m_axis.sum() >= 20
                    else None
                ),
                "n_axis": int(m_axis.sum()),
                "n_atoms": n,
            }
        )

    clean = [r for r in rows if r["above_apex"]]
    if any(row["n_inclusion_al_atoms"] for row in clean):
        raise ValueError("A retained matrix layer contains inclusion atoms")
    if not clean:
        raise ValueError("No populated bins lie entirely above the ridge apex")
    peak = max(clean, key=lambda r: r["max_RSS_MPa"])
    far = [r for r in clean if r["r_A"] > 60]
    noise_rss = float(np.mean([r["max_RSS_MPa"] for r in far])) if far else None
    noise_sd = float(np.std([r["max_RSS_MPa"] for r in far])) if far else None
    straddle = [r for r in rows if not r["above_apex"]]

    # The (111)[1-10] system resolves exactly sigma_xz in this orientation.
    assert all(r["vm_of_difference_MPa"] >= 0 and r["max_RSS_MPa"] >= 0 for r in rows)
    viol = [r["r_A"] for r in rows if r["max_RSS_MPa"] < abs(r["d_sigma_xz_MPa"]) - 1e-6]
    assert not viol, f"max RSS below |d_sigma_xz| at r = {viol}"

    res = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cell": f"Al matrix + Al13Fe4 ridge, {len(control.ids)} atoms",
        "atom_filter": "Control-selected type 1 atoms; below the apex this includes inclusion Al",
        "bin_A": BIN,
        "r_max_requested_A": r_max,
        "last_bin_edge_A": float(edges[-1]),
        "axis_window": {
            "center_x_A": axis_center,
            "width_A": 2 * AXIS_HALF_WIDTH,
            "center_definition": "midpoint of control atom x-extents",
            "selection": "abs(x - center_x) < width / 2; full y extent",
        },
        "distance_definition": "r = z - z_interface; height, not nearest-surface distance",
        "stress_definition": "-mean(c_st[1:6]) / 16.6072 A^3 / 10; MPa; field minus control",
        "stress_convention": (
            "Compression-positive pressure convention; "
            "tensile-positive Cauchy tensor has the opposite sign"
        ),
        "matrix_atom_count": matrix_atoms,
        "box_bounds_A": control.bounds.tolist(),
        "snapshot_steps": {"control": control.timestep, "field": field.timestep},
        "z_interface_A": Z_INTERFACE,
        "ridge_apex_A": ridge_apex,
        "inclusion_max_z_A": {"control": apex_control, "field": apex_field},
        "apex_definition": (
            "Maximum z over all inclusion IDs in both snapshots, including Al and Fe"
        ),
        "eigenstrain_used": EPS_INFLATED,
        "peak": peak,
        "apex_straddling_bins_excluded": straddle,
        "noise_floor_beyond_60A": {
            "mean_max_RSS_MPa": round(noise_rss, 3) if far else None,
            "std_MPa": round(noise_sd, 3) if far else None,
            "n_bins": len(far),
            "interpretation": (
                "Legacy key: spatial mean and population SD; not a calibrated noise floor"
            ),
        },
        "peak_rescaled_to_real_magnetostriction_MPa": {
            k: round(peak["max_RSS_MPa"] * lam / EPS_INFLATED, 4) for k, lam in LAMBDA_REAL.items()
        },
        "sigma_char_2_mu_lambda_MPa": {
            k: round(2 * MU_AL * lam / 1e6, 3) for k, lam in LAMBDA_REAL.items()
        },
        "profile": rows,
    }
    res["rescaling_note"] = (
        "Linear-amplitude comparisons only; a measured retention "
        "fraction does not establish a magnetostriction calibration"
    )
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, help="directory containing the curated pair")
    ap.add_argument("--control", type=Path, help="control snapshot, plain or gzip")
    ap.add_argument("--field", type=Path, help="strained snapshot, plain or gzip")
    ap.add_argument("--out", type=Path, default=REPORTS / "stageG10_field_profile.json")
    ap.add_argument("--r-max", type=float, default=R_MAX, help="profile range in A (default: 110)")
    ap.add_argument(
        "--matrix-atoms",
        type=int,
        default=MATRIX_ATOMS,
        help="number of contiguous matrix atom IDs, before inclusion IDs",
    )
    ap.add_argument("--label", default="", help="description stored in the record")
    args = ap.parse_args()
    if bool(args.control) != bool(args.field):
        ap.error("--control and --field must be supplied together")
    src = source_dir(args.src)
    paths = {
        "control": resolve_dump(args.control or src / CONTROL),
        "field": resolve_dump(args.field or src / FIELD),
    }
    with open_text(paths["control"]) as stream:
        control = read_snapshot(stream, require_stress=True)
    with open_text(paths["field"]) as stream:
        field = read_snapshot(stream, require_stress=True)
    res = field_profile(control, field, args.r_max, args.matrix_atoms)
    res["inputs"] = {key: file_provenance(path) for key, path in paths.items()}
    if args.label:
        res["label"] = args.label
    out_json = args.out
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(res, indent=2) + chr(10), encoding="utf-8")

    keys = (
        "r_A",
        "above_apex",
        "vm_control_MPa",
        "vm_field_MPa",
        "vm_of_difference_MPa",
        "diff_of_vm_MPa",
        "max_RSS_MPa",
        "system",
        "d_sigma_xz_MPa",
        "n_atoms",
        "n_inclusion_al_atoms",
        "d_sigma_xz_axis_MPa",
        "n_axis",
    )
    rows = res["profile"]
    with out_json.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)

    peak = res["peak"]
    print(
        f"{'r':>6} {'apex':>4} {'vM_ctl':>10} {'vM_fld':>10} {'vM[dT]':>10} "
        f"{'d[vM]':>10} {'maxRSS':>9} {'d_sxz':>8} {'N':>6}"
    )
    for r in rows:
        mark = "" if r["above_apex"] else "STR"
        print(
            f"{r['r_A']:6.1f} {mark:>4} {r['vm_control_MPa']:10.2f} "
            f"{r['vm_field_MPa']:10.2f} {r['vm_of_difference_MPa']:10.3f} "
            f"{r['diff_of_vm_MPa']:10.3f} {r['max_RSS_MPa']:9.3f} "
            f"{r['d_sigma_xz_MPa']:8.3f} {r['n_atoms']:6d}"
        )
    print()
    print(
        f"Peak max-RSS = {peak['max_RSS_MPa']:.2f} MPa at r = {peak['r_A']:.0f} A "
        f"on {peak['system']} (d_sigma_xz = {peak['d_sigma_xz_MPa']:.2f} MPa)"
    )
    print("Spatial summary beyond 60 A:", res["noise_floor_beyond_60A"])
    print("rescaled:", res["peak_rescaled_to_real_magnetostriction_MPa"])
    print("sigma_char = 2 mu lambda:", res["sigma_char_2_mu_lambda_MPa"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
