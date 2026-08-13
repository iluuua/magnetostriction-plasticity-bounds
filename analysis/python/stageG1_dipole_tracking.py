#!/usr/bin/env python3
"""Stage G1: track the edge-dislocation dipole through production dumps.

For each frame of each case (control eps0000 / physical eps00194):
- OVITO DXA (FCC): all segments with spatial Burgers vectors;
- classify segments into the two design dislocations by z band
  (lower ~49 A = +b pair, upper ~73 A = -b pair; each may be split into
  two Shockley partials bounding a stacking-fault ribbon);
- per band: circular-mean x position (PBC in x), mean z, partial split
  width, total segment length;
- CNA HCP count (stacking-fault atoms) in the Al matrix;
- thermo-free sanity: atom count per frame.

Outputs per-case CSV, a combined Delta JSON, and PNG plots.
Usage: .venv python. Works on partial dumps mid-production.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = ["G1_ridge_dipole_eps0000", "G1_ridge_dipole_eps00194"]
Z_BANDS = {"lower": (40.0, 62.0), "upper": (62.0, 85.0)}  # design: 49.23 / 72.61 A
LX_DEFAULT = 186.1458


def circular_mean_x(xs: np.ndarray, lx: float) -> float:
    ang = xs / lx * 2.0 * math.pi
    return float((math.atan2(np.sin(ang).mean(), np.cos(ang).mean()) % (2.0 * math.pi)) / (2.0 * math.pi) * lx)


def analyze_case(dump_path: Path, lx: float) -> list[dict]:
    from ovito.io import import_file
    from ovito.modifiers import (
        CommonNeighborAnalysisModifier,
        DislocationAnalysisModifier,
    )

    pipe = import_file(str(dump_path))
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(CommonNeighborAnalysisModifier())
    pipe.modifiers.append(dxa)

    rows: list[dict] = []
    for fi in range(pipe.source.num_frames):
        data = pipe.compute(fi)
        step = int(data.attributes.get("Timestep", fi))
        structure = data.particles["Structure Type"][...]
        types = data.particles["Particle Type"][...]
        pos = data.particles.positions[...]
        # HCP in the Al matrix only, above the interface plane, excluding Fe block species mix:
        al_matrix = (types == 1) & (pos[:, 2] > 21.0)
        n_hcp = int(np.count_nonzero((structure == CommonNeighborAnalysisModifier.Type.HCP) & al_matrix))
        row: dict = {
            "frame": fi,
            "step": step,
            "n_atoms": int(len(pos)),
            "hcp_matrix_atoms": n_hcp,
            "dxa_total_length_A": 0.0,
            "n_segments": 0,
        }
        for band in Z_BANDS:
            row[f"{band}_n_segments"] = 0
            row[f"{band}_length_A"] = 0.0
            row[f"{band}_mean_x_A"] = None
            row[f"{band}_mean_z_A"] = None
            row[f"{band}_split_width_A"] = None
            row[f"{band}_bx_sum"] = 0.0
        band_xs: dict[str, list[float]] = {b: [] for b in Z_BANDS}
        for seg in data.dislocations.segments:
            pts = np.asarray(seg.points)
            zc = float(pts[:, 2].mean())
            xc = circular_mean_x(pts[:, 0], lx)
            bvec = np.asarray(seg.spatial_burgers_vector)
            row["dxa_total_length_A"] += float(seg.length)
            row["n_segments"] += 1
            for band, (zlo, zhi) in Z_BANDS.items():
                if zlo <= zc < zhi:
                    row[f"{band}_n_segments"] += 1
                    row[f"{band}_length_A"] += float(seg.length)
                    row[f"{band}_bx_sum"] += float(bvec[0])
                    band_xs[band].append(xc)
        for band, xs in band_xs.items():
            if xs:
                xs_arr = np.array(xs)
                row[f"{band}_mean_x_A"] = circular_mean_x(xs_arr, lx)
                zs = [float(np.asarray(s.points)[:, 2].mean()) for s in data.dislocations.segments
                      if Z_BANDS[band][0] <= float(np.asarray(s.points)[:, 2].mean()) < Z_BANDS[band][1]]
                row[f"{band}_mean_z_A"] = float(np.mean(zs))
                if len(xs) >= 2:
                    d = np.abs(xs_arr[:, None] - xs_arr[None, :])
                    d = np.minimum(d, lx - d)
                    row[f"{band}_split_width_A"] = float(d.max())
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    keys = list(rows[0].keys())
    lines = [",".join(keys)]
    for r in rows:
        lines.append(",".join("" if r.get(k) is None else str(r.get(k)) for k in keys))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True,
                        help="runs/stageG1_ridge_dipole/<stamp>")
    parser.add_argument("--stage", default="production", choices=["production", "smoke"])
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "docs" / "reports")
    parser.add_argument("--lx", type=float, default=LX_DEFAULT)
    args = parser.parse_args()

    summary: dict = {"run_dir": str(args.run_dir), "stage": args.stage,
                     "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                     "cases": {}}
    per_case_rows: dict[str, list[dict]] = {}
    for case in CASES:
        stage_dir = args.run_dir / case / args.stage
        if args.stage == "production":
            dump = stage_dir / f"{case}.production.lammpstrj"
        else:
            dump = stage_dir / f"{case}.smoke.final.lammpstrj"
        if not dump.exists():
            summary["cases"][case] = {"status": "dump_missing", "dump": str(dump)}
            continue
        rows = analyze_case(dump, args.lx)
        per_case_rows[case] = rows
        csv_path = args.out_dir / f"stageG1_dipole_tracking_{case}_{args.stage}.csv"
        write_csv(csv_path, rows)
        summary["cases"][case] = {
            "status": "ok", "frames": len(rows), "csv": str(csv_path),
            "last": rows[-1] if rows else None,
        }

    if all(c in per_case_rows for c in CASES):
        rows0, rows1 = per_case_rows[CASES[0]], per_case_rows[CASES[1]]
        n = min(len(rows0), len(rows1))
        deltas = []
        for i in range(n):
            d = {"step": rows0[i]["step"]}
            for band in Z_BANDS:
                x0, x1 = rows0[i].get(f"{band}_mean_x_A"), rows1[i].get(f"{band}_mean_x_A")
                if x0 is not None and x1 is not None:
                    dx = x1 - x0
                    dx -= round(dx / args.lx) * args.lx
                    d[f"delta_x_{band}_A"] = dx
                d[f"delta_hcp"] = rows1[i]["hcp_matrix_atoms"] - rows0[i]["hcp_matrix_atoms"]
                d[f"delta_dxa_length_A"] = rows1[i]["dxa_total_length_A"] - rows0[i]["dxa_total_length_A"]
            deltas.append(d)
        summary["delta_physical_minus_control"] = deltas
        write_csv(args.out_dir / f"stageG1_dipole_tracking_delta_{args.stage}.csv", deltas)

    out_json = args.out_dir / f"stageG1_dipole_tracking_{args.stage}_summary.json"
    out_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: (v if k != "delta_physical_minus_control" else f"{len(v)} rows")
                      for k, v in summary.items()}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
