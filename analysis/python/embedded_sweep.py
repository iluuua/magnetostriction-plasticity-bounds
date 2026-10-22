#!/usr/bin/env python3
"""Resistance curve of the edge dislocation from a quasi-static sweep.

Reads the STEP lines of lammps/embedded_inclusion/in.disl_sweep (step, reaction
of the top block, the same from the bottom block, force norm, elastic shear of
the lower half). The printed reactions are minus the applied shear stress, so
tau below is the applied sigma_xz, -(tau_top + tau_bottom)/2. In a cell periodic along x a single dislocation that
moves by dx slips the top relative to the bottom by b dx / Lx, so the line
position follows from the top-block displacement D = n DELTA minus its elastic
part tau H / G:

    x_line = x_0 + (D - tau H / G) Lx / b

Optional DXA check: with --full, the line positions found by OVITO's dislocation
analysis in the full dumps are reported next to the inferred ones.

With two sweeps (--control, --strained) the change of the resistance,
dtau(x) = tau_strained(x) - tau_control(x) at the same line position, is formed
on a common grid; this is what the static field predicts as -<sigma_xz>_y(x).

    python analysis/python/embedded_sweep.py --control ctl/log.sweep --strained fld/log.sweep \
        --lx 126.006 --h 110.3 --x0 31.5 --out sweep.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np

B = 2.863782
G_MPA = 26000.0


def read_steps(log: Path) -> np.ndarray:
    rows = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"STEP (\d+) tau (\S+) taub (\S+) fnorm (\S+)", line)
        if m:
            rows.append([float(v) for v in m.groups()])
    return np.array(rows)


def tau_mean(steps: np.ndarray) -> np.ndarray:
    """Applied shear stress, minus the mean of the top and bottom block
    reactions; their difference measures the residual force left by CG."""
    return -0.5 * (steps[:, 1] + steps[:, 2])


def line_positions(steps: np.ndarray, delta: float, lx: float, h: float, x0: float) -> np.ndarray:
    D = steps[:, 0] * delta
    return x0 + (D - tau_mean(steps) / G_MPA * h) * lx / B


def first_depinning(tau: np.ndarray, drop: float = 2.0) -> tuple[int | None, float | None]:
    """Step and applied stress just before the first drop of more than `drop` MPa:
    the stress at which the line leaves its starting position."""
    for i in range(2, len(tau)):
        if tau[i] < tau[i - 1] - drop:
            return i - 1, float(tau[i - 1])
    return None, None


def dxa_positions(pattern: str) -> dict:
    from ovito.io import import_file
    from ovito.modifiers import DislocationAnalysisModifier
    out = {}
    for path in sorted(Path().glob(pattern)):
        pipe = import_file(str(path))
        pipe.source.data.cell_.pbc = (True, True, False)
        pipe.modifiers.append(DislocationAnalysisModifier(
            input_crystal_structure=DislocationAnalysisModifier.Lattice.FCC))
        d = pipe.compute()
        xs = [float(np.mean(np.asarray(s.points)[:, 0])) for s in d.dislocations.segments
              if s.length > 0.5 * d.cell[1][1]]
        out[int(re.findall(r"(\d+)\.lammpstrj$", path.name)[0])] = xs
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--control", type=Path, required=True)
    ap.add_argument("--strained", type=Path, default=None)
    ap.add_argument("--delta", type=float, default=0.057)
    ap.add_argument("--lx", type=float, required=True)
    ap.add_argument("--h", type=float, required=True, help="height between the rigid blocks, A")
    ap.add_argument("--x0", type=float, required=True, help="initial line position, A")
    ap.add_argument("--full", default=None, help="glob of full dumps for a DXA check")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    res = {"delta_A": a.delta, "lx_A": a.lx, "h_A": a.h, "G_MPa": G_MPA, "burgers_A": B}
    sweeps = {"control": a.control, "strained": a.strained}
    curves = {}
    for name, log in sweeps.items():
        if log is None:
            continue
        s = read_steps(log)
        x = line_positions(s, a.delta, a.lx, a.h, a.x0)
        tm = tau_mean(s)
        curves[name] = (x, tm)
        res[name] = {"step": s[:, 0].astype(int).tolist(), "tau_MPa": tm.round(4).tolist(),
                     "tau_top_MPa": s[:, 1].round(4).tolist(), "tau_bottom_MPa": s[:, 2].round(4).tolist(),
                     "top_bottom_difference_max_MPa": float(np.abs(s[:, 1] - s[:, 2]).max()),
                     "fnorm": s[:, 3].tolist(), "x_line_A": x.round(3).tolist(),
                     "tau_peak_to_peak_MPa": float(tm[1:].max() - tm[1:].min()) if len(s) > 2 else None}
        res[name]["depin_step"], res[name]["tau_depin_MPa"] = first_depinning(tm)
    if "strained" in res and res["control"]["tau_depin_MPa"] is not None             and res["strained"]["tau_depin_MPa"] is not None:
        res["dtau_depin_MPa"] = res["strained"]["tau_depin_MPa"] - res["control"]["tau_depin_MPa"]
    if "strained" in curves:
        xc, tc = curves["control"]
        xs, ts = curves["strained"]
        lo, hi = max(xc.min(), xs.min()), min(xc.max(), xs.max())
        grid = np.linspace(lo, hi, 200)
        oc, os_ = np.argsort(xc), np.argsort(xs)
        dt = np.interp(grid, xs[os_], ts[os_]) - np.interp(grid, xc[oc], tc[oc])
        res["dtau"] = {"x_line_A": grid.round(3).tolist(), "dtau_MPa": dt.round(4).tolist(),
                       "max_abs_MPa": float(np.abs(dt).max())}
    if a.full:
        res["dxa_line_x_A"] = dxa_positions(a.full)
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for name in curves:
        print("%-8s steps %d, tau %.2f..%.2f MPa, line %.1f..%.1f A" % (
            name, len(res[name]["step"]), min(res[name]["tau_MPa"]), max(res[name]["tau_MPa"]),
            min(res[name]["x_line_A"]), max(res[name]["x_line_A"])))
    for name in curves:
        print("%-8s first depinning at step %s, tau %s MPa" % (name, res[name]["depin_step"], res[name]["tau_depin_MPa"]))
    if "dtau_depin_MPa" in res:
        print("depinning stress strained - control = %.2f MPa" % res["dtau_depin_MPa"])
    if "dtau" in res:
        print("max |dtau| = %.2f MPa" % res["dtau"]["max_abs_MPa"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
