#!/usr/bin/env python3
"""Stage G1: stress-field analysis of the ridge+dipole production runs.

Reads the LAST_N frames of both production dumps (time-average) plus frame 0 and
produces, for Al MATRIX atoms only (id <= n_matrix, i.e. the (111) slab written
first by the generator; the ridge interior and Fe-block Al are excluded by id):

  (a) z-profile in the FLAT interface region (|x - cx| > flat_min): sigma_zz,
      sigma_vm, sigma_xz vs distance from the interface plane (z - 20), per case
      and Delta = physical - control  -> the physicist's sigma(r) deliverable;
  (b) y-averaged xz map of sigma_xz (the glide-driving component for b || x on
      (111) planes parallel to the interface), per case and Delta;
  (c) JSON summary: Delta sigma_xz at the dipole partner design positions, the
      max |Delta sigma_xz| near the ridge edge, and a far-field noise floor.

Stress convention (documented, same style as Stage F): per-atom virial
c_st[1..6] from `compute stress/atom NULL virial` is stress*volume in bar*A^3;
bin stress sigma_ij = -sum(st_ij)/(N_bin * V_at) * 0.1 MPa with V_at = a^3/4 =
16.6072 A^3 (ideal fcc Al). Absolute MPa are a proxy; Delta between the
control/physical pair is the trustworthy quantity.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = ["G1_ridge_dipole_eps0000", "G1_ridge_dipole_eps00194"]
N_MATRIX = 268488          # Al (111) slab atoms, ids 1..N_MATRIX (generator order)
CX = 186.1458 / 2.0
Z_IF = 20.0
V_AT = 4.05 ** 3 / 4.0     # 16.6072 A^3
BAR_A3_TO_MPA = 0.1        # 1 bar = 0.1 MPa after dividing by volume in A^3
DIPOLE_POINTS = {"partner_plus": (165.0, 49.23), "partner_minus": (141.6, 72.61)}


def read_frames(dump: Path, want_steps: set[int] | None, last_n: int) -> dict[int, np.ndarray]:
    """Return {step: array[N,9] (id,type,x,y,z,sxx,syy,szz,sxz)} for selected frames."""
    steps_index: list[tuple[int, int]] = []   # (step, header_offset_line)
    # First pass: index frames.
    with open(dump, "r", encoding="utf-8", errors="replace") as fh:
        lines_pos = 0
        offsets = []
        while True:
            line = fh.readline()
            if not line:
                break
            if line.startswith("ITEM: TIMESTEP"):
                step = int(fh.readline())
                offsets.append(step)
        all_steps = offsets
    selected = set(all_steps[-last_n:]) | {all_steps[0]}
    if want_steps:
        selected |= (want_steps & set(all_steps))
    out: dict[int, np.ndarray] = {}
    with open(dump, "r", encoding="utf-8", errors="replace") as fh:
        while True:
            line = fh.readline()
            if not line:
                break
            if not line.startswith("ITEM: TIMESTEP"):
                continue
            step = int(fh.readline())
            fh.readline()                       # ITEM: NUMBER OF ATOMS
            natoms = int(fh.readline())
            for _ in range(4):                  # BOX BOUNDS + 3 lines
                fh.readline()
            header = fh.readline()              # ITEM: ATOMS id type x y z c_pe ...
            cols = header.split()[2:]
            idx = {name: i for i, name in enumerate(cols)}
            take = step in selected
            if not take:
                for _ in range(natoms):
                    fh.readline()
                continue
            rows = np.empty((natoms, 9), dtype=float)
            want_cols = [idx["id"], idx["type"], idx["x"], idx["y"], idx["z"],
                         idx["c_st[1]"], idx["c_st[2]"], idx["c_st[3]"], idx["c_st[5]"]]
            for i in range(natoms):
                parts = fh.readline().split()
                for j, c in enumerate(want_cols):
                    rows[i, j] = float(parts[c])
            out[step] = rows
    return out


def matrix_mask(fr: np.ndarray) -> np.ndarray:
    return fr[:, 0] <= N_MATRIX


def bin_stats(fr_list: list[np.ndarray], sel_fn, coord_fn, edges: np.ndarray) -> dict[str, np.ndarray]:
    """Time-averaged per-bin mean stress components (MPa) and counts."""
    sums = np.zeros((len(edges) - 1, 4))
    counts = np.zeros(len(edges) - 1)
    for fr in fr_list:
        m = sel_fn(fr)
        c = coord_fn(fr[m])
        st = fr[m][:, 5:9]                     # sxx syy szz sxz (bar*A^3)
        which = np.digitize(c, edges) - 1
        ok = (which >= 0) & (which < len(edges) - 1)
        for comp in range(4):
            sums[:, comp] += np.bincount(which[ok], weights=st[ok, comp], minlength=len(edges) - 1)
        counts += np.bincount(which[ok], minlength=len(edges) - 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = -(sums / counts[:, None]) / V_AT * BAR_A3_TO_MPA
    return {"mean_MPa": mean, "counts": counts / max(len(fr_list), 1)}


def vm_from(sxx: np.ndarray, syy: np.ndarray, szz: np.ndarray, sxz: np.ndarray) -> np.ndarray:
    return np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3.0 * sxz ** 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--last-n", type=int, default=5)
    parser.add_argument("--flat-min", type=float, default=65.0,
                        help="|x-cx| beyond which the interface is flat (edge at 45)")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "docs" / "reports")
    args = parser.parse_args()

    z_edges = np.arange(0.0, 285.0, 5.0)
    x_edges = np.arange(0.0, 186.5, 4.0)
    zmap_edges = np.arange(20.0, 122.0, 4.0)

    profiles: dict[str, dict] = {}
    maps: dict[str, np.ndarray] = {}
    for case in CASES:
        dump = args.run_dir / case / "production" / f"{case}.production.lammpstrj"
        frames = read_frames(dump, None, args.last_n)
        steps = sorted(frames)
        last_frames = [frames[s] for s in steps[-args.last_n:]]

        def sel_flat(fr):
            return matrix_mask(fr) & (np.abs(fr[:, 2] - CX) > args.flat_min)

        prof = bin_stats(last_frames, sel_flat, lambda a: a[:, 4] - Z_IF, z_edges)
        profiles[case] = {"z_edges": z_edges, **prof}

        # y-averaged xz map of sigma_xz
        hist_s = np.zeros((len(x_edges) - 1, len(zmap_edges) - 1))
        hist_n = np.zeros_like(hist_s)
        for fr in last_frames:
            m = matrix_mask(fr)
            x, z, sxz = fr[m][:, 2], fr[m][:, 4], fr[m][:, 8]
            hs, _, _ = np.histogram2d(x, z, bins=[x_edges, zmap_edges], weights=sxz)
            hn, _, _ = np.histogram2d(x, z, bins=[x_edges, zmap_edges])
            hist_s += hs
            hist_n += hn
        with np.errstate(invalid="ignore", divide="ignore"):
            maps[case] = -(hist_s / hist_n) / V_AT * BAR_A3_TO_MPA

    # CSV: z profile per case + delta
    rows = ["r_lo_A,r_hi_A," + ",".join(
        f"{c}_{q}" for c in ["eps0000", "eps00194", "delta"]
        for q in ["sxx", "syy", "szz", "sxz", "vm", "natoms"])]
    p0, p1 = profiles[CASES[0]], profiles[CASES[1]]
    for i in range(len(z_edges) - 1):
        vals = []
        for prof in (p0, p1):
            sxx, syy, szz, sxz = prof["mean_MPa"][i]
            vals += [sxx, syy, szz, sxz, float(vm_from(*[np.array([v]) for v in (sxx, syy, szz, sxz)])[0]),
                     prof["counts"][i]]
        d = [vals[6 + j] - vals[j] for j in range(5)] + [vals[11]]
        allv = vals[:6] + vals[6:12] + d
        rows.append(f"{z_edges[i]},{z_edges[i+1]}," + ",".join(
            "" if (isinstance(v, float) and np.isnan(v)) else f"{v:.3f}" for v in allv))
    (args.out_dir / "stageG1_sigma_profile_flat.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    # Delta sigma_xz map CSV (x rows, z cols)
    dmap = maps[CASES[1]] - maps[CASES[0]]
    hdr = "x_center_A," + ",".join(f"z{(zmap_edges[j]+zmap_edges[j+1])/2:.0f}" for j in range(len(zmap_edges) - 1))
    lines = [hdr]
    for i in range(len(x_edges) - 1):
        xc = (x_edges[i] + x_edges[i + 1]) / 2
        lines.append(f"{xc:.1f}," + ",".join(
            "" if np.isnan(v) else f"{v:.2f}" for v in dmap[i]))
    (args.out_dir / "stageG1_delta_sigma_xz_map.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Summary
    def map_value_at(x: float, z: float) -> float | None:
        i = int(np.digitize(x, x_edges)) - 1
        j = int(np.digitize(z, zmap_edges)) - 1
        if 0 <= i < dmap.shape[0] and 0 <= j < dmap.shape[1] and not np.isnan(dmap[i, j]):
            return float(dmap[i, j])
        return None

    edge_zone = dmap[(x_edges[:-1] >= 110) & (x_edges[:-1] <= 180)][:, (zmap_edges[:-1] >= 20) & (zmap_edges[:-1] <= 90)]
    far_zone = dmap[(x_edges[:-1] <= 40)]
    summary = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_dir": str(args.run_dir),
        "convention": "sigma_ij = -sum(c_st)/(N*V_at)*0.1 MPa, V_at=16.6072 A^3; last %d frames averaged" % args.last_n,
        "delta_sigma_xz_at_dipole_MPa": {k: map_value_at(*v) for k, v in DIPOLE_POINTS.items()},
        "max_abs_delta_sigma_xz_edge_zone_MPa": float(np.nanmax(np.abs(edge_zone))) if edge_zone.size else None,
        "far_field_noise_MPa": {
            "median_abs": float(np.nanmedian(np.abs(far_zone))),
            "p95_abs": float(np.nanpercentile(np.abs(far_zone), 95)),
        },
        "outputs": ["stageG1_sigma_profile_flat.csv", "stageG1_delta_sigma_xz_map.csv"],
    }
    (args.out_dir / "stageG1_stress_field_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
