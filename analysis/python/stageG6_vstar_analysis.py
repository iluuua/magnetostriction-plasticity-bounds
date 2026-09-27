#!/usr/bin/env python3
"""Measure dislocation-family drift during the alloy staircase loading test.

Inputs are LAMMPS trajectories with id/type/x/y/z and c_st[1:6], plain or
gzip-sharded. DXA candidates are grouped by height; positions are unwrapped
across the periodic x boundary. Each rung excludes its first 6 ps before
fitting velocity [A/ps] and averaging virial shear [MPa] in a specified box.
CSV contains frames; JSON contains rung fits and a diagnostic V*/b^3 fit.
The historical stress mask excludes type 2. In the Al/Mg/Si alloy map this
excludes Mg, not Fe; it is retained to reproduce the published rung values.
The virial conversion uses compression-positive normal stress, opposite to
the tensile-positive Cauchy convention; it also reverses a signed fitted slope.
Positive fitted drift alone does not establish depinning or an activation
volume. Short DXA segments remain candidates, not confirmed dislocations.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
from _g4clean import file_provenance, trajectory_paths

REPO_ROOT = Path(__file__).resolve().parents[2]
LX = 114.5513  # 40 aluminium periods along x
KT = 1.380649e-23 * 300.0
B_M = 4.05e-10 / math.sqrt(2.0)
V_AT = 16.6072
PRE, HOLD = 10000, 30000
RUNGS = [(PRE + k * HOLD, PRE + (k + 1) * HOLD, 45 + 10 * k) for k in range(4)]
Z_SPLIT = 130.0
QUIET = dict(x0=5.0, x1=45.0, z0=60.0, z1=115.0)  # sampling box in A, full y extent
STRESS_SELECTIONS = {
    "legacy": "type != 2: historical Al/Si selection, excluding Mg",
    "aluminium": "type == 1: aluminium atoms only",
    "alloy": "types 1, 2, 3: all Al, Mg and Si atoms",
}


def cmean(xs, ws):
    """Length-weighted circular x position [A] in a box of length LX."""
    ang = np.asarray(xs) / LX * 2 * math.pi
    ws = np.asarray(ws)
    return (
        (math.atan2((np.sin(ang) * ws).sum(), (np.cos(ang) * ws).sum()) % (2 * math.pi))
        / (2 * math.pi)
        * LX
    )


def sample_shear(pos, types, stress, selection="legacy") -> tuple[float, int]:
    """Mean sigma_xz [MPa] in QUIET using a documented atom-type selection.

    All selections retain the published fixed atomic volume 16.6072 A^3.
    The all-species value therefore uses the same volume approximation.
    """
    if selection == "legacy":
        species = types != 2
    elif selection == "aluminium":
        species = types == 1
    elif selection == "alloy":
        species = np.isin(types, (1, 2, 3))
    else:
        raise ValueError(f"Unknown stress selection: {selection}")
    mask = (
        (pos[:, 0] >= QUIET["x0"])
        & (pos[:, 0] < QUIET["x1"])
        & (pos[:, 2] >= QUIET["z0"])
        & (pos[:, 2] < QUIET["z1"])
        & species
    )
    count = int(mask.sum())
    if count == 0:
        raise ValueError(f"No atoms in the {selection} stress sampling box")
    return float(-stress[mask, 4].sum() / (count * V_AT) / 10.0), count


def loading_motion(frames: list[dict]) -> dict:
    """Endpoint displacement and population spread during loading, after preload."""
    selected = [row for row in frames if row["step"] >= PRE and row["ux_lo"] is not None]
    if not selected:
        return {"n_frames": 0}
    positions = np.array([row["ux_lo"] for row in selected])
    return {
        "start_step": selected[0]["step"],
        "end_step": selected[-1]["step"],
        "n_frames": len(selected),
        "net_displacement_A": float(positions[-1] - positions[0]),
        "position_std_A": float(positions.std()),
        "interpretation": "Loading interval only; initial zero-load motion is excluded",
    }


def diagnostic_activation_fit(rungs: list[dict]) -> dict:
    """Weighted ln(v)-versus-shear fit; no independent validation of glide."""
    good = [row for row in rungs if row["v_A_per_ps"] > 0]
    if len(good) < 3:
        return {"fit_status": "fewer than three positive drift estimates"}
    taus = np.array([row["tau_actual_MPa"] for row in good]) * 1e6
    lnv = np.log([row["v_A_per_ps"] for row in good])
    weights = (
        1.0 / np.array([max(1e-3, row["v_sem_A_per_ps"] / row["v_A_per_ps"]) for row in good]) ** 2
    )
    design = np.vstack([taus, np.ones_like(taus)]).T
    weighted = np.diag(weights)
    try:
        covariance = np.linalg.inv(design.T @ weighted @ design)
    except np.linalg.LinAlgError:
        return {"fit_status": "stress axis does not determine a slope"}
    beta = covariance @ design.T @ weighted @ lnv
    slope = float(beta[0])
    slope_error = float(math.sqrt(covariance[0, 0]))
    return {
        "V_star_b3": slope * KT / B_M**3,
        "V_star_err_b3": slope_error * KT / B_M**3,
        "kT_over_Vstar_MPa": 1.0 / slope / 1e6 if slope > 0 else None,
        "fit_status": "diagnostic only; sustained glide not established",
    }


def main() -> int:
    global LX
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dump", required=True, help="trajectory or quoted gzip shard glob, including virials"
    )
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "docs" / "reports")
    ap.add_argument("--lx", type=float, help="optional cell-length check in A")
    ap.add_argument("--max-frames", type=int, help="labelled prefix-only smoke check")
    ap.add_argument("--stress-selection", choices=STRESS_SELECTIONS, default="legacy")
    ap.add_argument(
        "--compare-stress-selections",
        action="store_true",
        help="write a separate three-selection comparison from the same DXA frames",
    )
    args = ap.parse_args()
    if args.max_frames is not None and args.max_frames <= 0:
        ap.error("--max-frames must be positive")

    from ovito.io import import_file
    from ovito.modifiers import DislocationAnalysisModifier

    paths = trajectory_paths(args.dump)
    pipe = import_file([str(path) for path in paths])
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)
    n = min(pipe.source.num_frames, args.max_frames) if args.max_frames else pipe.source.num_frames
    selections = (
        list(STRESS_SELECTIONS) if args.compare_stress_selections else [args.stress_selection]
    )

    frames = []
    for fi in range(n):
        d = pipe.compute(fi)
        if "Timestep" not in d.attributes:
            raise ValueError("Trajectory must retain original LAMMPS timesteps")
        step = int(d.attributes["Timestep"])
        if frames and step <= frames[-1]["step"]:
            raise ValueError("Shard timesteps must be strictly increasing without overlap")
        box_lx = float(np.linalg.norm(np.asarray(d.cell)[:, 0]))
        if fi == 0:
            LX = box_lx if args.lx is None else args.lx
        if not np.isclose(LX, box_lx, atol=1e-3, rtol=0):
            raise ValueError("Cell length changed or --lx disagrees with the trajectory")
        lo_x, lo_w, up_x, up_w = [], [], [], []
        n_small = 0
        for s in d.dislocations.segments:
            if s.length < 10.0:
                n_small += 1
                continue
            pts = np.asarray(s.points)
            (lo_x if pts[:, 2].mean() < Z_SPLIT else up_x).append(cmean(pts[:, 0], np.ones(1)))
            (lo_w if pts[:, 2].mean() < Z_SPLIT else up_w).append(s.length)
        pos = d.particles.positions[...]
        types = d.particles["Particle Type"][...]
        columns = [f"c_st[{i}]" for i in range(1, 7)]
        if not all(name in d.particles for name in columns):
            raise ValueError("The alloy trajectory must retain all six c_st virial columns")
        st = np.column_stack([d.particles[name][...] for name in columns])
        stresses = {name: sample_shear(pos, types, st, name) for name in selections}
        sxz_quiet = stresses[args.stress_selection][0]
        frames.append(
            {
                "frame": fi,
                "step": step,
                "x_lo": cmean(lo_x, lo_w) if lo_x else None,
                "x_up": cmean(up_x, up_w) if up_x else None,
                "len_lo": float(sum(lo_w)),
                "len_up": float(sum(up_w)),
                "n_small_segments": n_small,
                "sxz_quiet_MPa": sxz_quiet,
            }
        )
        if args.compare_stress_selections:
            for name, (shear, count) in stresses.items():
                frames[-1][f"sxz_{name}_MPa"] = shear
                frames[-1][f"n_{name}_stress_atoms"] = count
        if fi % 20 == 0 or fi == n - 1:
            print(f"Analyzed {fi + 1}/{n} saved frames (step {step})", flush=True)

    for fam in ("x_lo", "x_up"):
        prev, acc = None, 0.0
        for r in frames:
            x = r[fam]
            if x is None:
                r["u" + fam] = None
                continue
            if prev is None:
                acc = x
            else:
                dd = x - prev
                dd -= round(dd / LX) * LX
                acc += dd
            prev = x
            r["u" + fam] = acc

    rungs = []
    comparison_rungs = {name: [] for name in selections}
    for lo, hi, nominal in RUNGS:
        sel = [r for r in frames if lo + 6000 <= r["step"] <= hi and r["ux_lo"] is not None]
        if len(sel) < 8:
            continue
        t = np.array([r["step"] for r in sel]) * 1e-3
        x = np.array([r["ux_lo"] for r in sel])
        A = np.vstack([t, np.ones_like(t)]).T
        coef, res_, *_ = np.linalg.lstsq(A, x, rcond=None)
        v = float(coef[0])
        resid = x - A @ coef
        nn = len(t)
        se = math.sqrt(
            float((resid**2).sum()) / max(1, nn - 2) / float(((t - t.mean()) ** 2).sum())
        )
        rho = float(np.corrcoef(resid[:-1], resid[1:])[0, 1]) if nn > 3 else 0.0
        if not math.isfinite(rho):
            rho = 0.0
        infl = math.sqrt(max(1.0, (1 + rho) / max(1e-6, 1 - rho)))
        tau_act = float(np.mean([r["sxz_quiet_MPa"] for r in sel]))
        tau_sd = float(np.std([r["sxz_quiet_MPa"] for r in sel]) / math.sqrt(len(sel)))
        rungs.append(
            {
                "nominal_MPa": nominal,
                "tau_actual_MPa": tau_act,
                "tau_actual_sem_MPa": tau_sd,
                "v_A_per_ps": v,
                "v_sem_A_per_ps": se * infl,
                "v_m_per_s": v * 100,
                "autocorr_rho": rho,
                "n_frames": nn,
                "displacement_A": float(x[-1] - x[0]),
                "position_residual_std_A": float(np.std(resid)),
                "displacement_over_b": float(abs(x[-1] - x[0]) / (B_M * 1e10)),
            }
        )
        if args.compare_stress_selections:
            for name in selections:
                values = np.array([row[f"sxz_{name}_MPa"] for row in sel])
                comparison_rungs[name].append(
                    {
                        **rungs[-1],
                        "tau_actual_MPa": float(values.mean()),
                        "tau_actual_sem_MPa": float(values.std() / math.sqrt(len(values))),
                        "mean_sampled_atoms": float(
                            np.mean([row[f"n_{name}_stress_atoms"] for row in sel])
                        ),
                    }
                )

    result = {
        "tag": args.tag,
        "dump": str(args.dump),
        "n_frames": n,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "quiet_box": QUIET,
        "rungs": rungs,
        "loading_motion": loading_motion(frames),
        "inputs": [file_provenance(path, checksum=False) for path in paths],
        "cell_length_x_A": LX,
        "coverage": {
            "available_frames": pipe.source.num_frames,
            "analyzed_frames": n,
            "subset_only": n < pipe.source.num_frames,
        },
        "sampling": {
            "timestep_ps": 0.001,
            "pre_steps": PRE,
            "hold_steps": HOLD,
            "settling_steps_per_rung": 6000,
            "segment_cutoff_A": 10.0,
        },
        "stress_selection": args.stress_selection,
        "stress_atom_filter": STRESS_SELECTIONS[args.stress_selection],
        "stress_convention": "Compression-positive; opposite to tensile-positive Cauchy stress",
        "fit_interpretation": (
            "Diagnostic drift fit; independent sustained-glide evidence "
            "is required for an activation volume"
        ),
        "stress_sem_definition": "std/sqrt(N), without a temporal-correlation correction",
        "V_star_validated": False,
    }

    result.update(diagnostic_activation_fit(rungs))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.compare_stress_selections:
        comparison = {
            "inputs": result["inputs"],
            "stress_convention": result["stress_convention"],
            "coverage": result["coverage"],
            "method": "Same DXA positions and rung fits; only the stress atom mask changes",
            "atomic_volume_A3": V_AT,
            "selections": {
                name: {
                    "atom_filter": STRESS_SELECTIONS[name],
                    "rungs": rows,
                    "diagnostic_fit": diagnostic_activation_fit(rows),
                }
                for name, rows in comparison_rungs.items()
            },
            "interpretation": (
                "The selection affects stress and the diagnostic activation-volume fit. "
                "It does not change the tracked displacement or establish sustained glide."
            ),
        }
        comparison_path = args.out_dir / f"stageG6_stress_selection_{args.tag}.json"
        comparison_path.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
        result["stress_selection_comparison"] = str(comparison_path)
    csvp = args.out_dir / f"stageG6_vstar_{args.tag}_frames.csv"
    keys = list(frames[0].keys())
    with csvp.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(frames)
    out = args.out_dir / f"stageG6_vstar_{args.tag}_summary.json"
    out.write_text(json.dumps(result, indent=2) + chr(10), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "dump"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
