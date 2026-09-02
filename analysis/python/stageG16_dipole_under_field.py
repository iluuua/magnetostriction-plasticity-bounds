#!/usr/bin/env python3
"""Stage G16: does the field of a maintained eigenstrain move a dislocation
pair that is already next to the inclusion, with no applied load?

Reads the dynamic dumps of the control and strained cells, extracts both
partners' positions frame by frame with DXA, unwraps the periodic x, and
reports the net displacement of each line relative to the control - the
control removes whatever drift the pair has on its own from the thermal
start and the image forces of the finite cell.

The decision criterion is the one stageG7 used: a line has moved if its net
displacement exceeds one Burgers vector AND three times its own thermal
oscillation, and the field has moved it if the strained-minus-control
difference does. Everything else is reported as observed.

Usage: stageG16_dipole_under_field.py --run-dir runs/stageG15_unified/<stamp>
"""
from __future__ import annotations

import argparse
import io
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "docs" / "reports"
B_A = 4.05 / math.sqrt(2.0)


def cell_lx(dump: Path) -> float:
    with io.open(dump, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if ln.startswith("ITEM: BOX BOUNDS"):
                lo, hi = map(float, next(fh).split()[:2])
                return hi - lo
    raise ValueError("no box in " + str(dump))


def circ_mean(xs, ws, lx) -> float:
    ang = np.asarray(xs) / lx * 2 * math.pi
    ws = np.asarray(ws)
    return (math.atan2(float((np.sin(ang) * ws).sum()), float((np.cos(ang) * ws).sum()))
            % (2 * math.pi)) / (2 * math.pi) * lx


def trajectories(dump: Path, z_split: float):
    """Per frame: (timestep, x of the lower line, x of the upper line)."""
    from ovito.io import import_file
    from ovito.modifiers import DislocationAnalysisModifier
    lx = cell_lx(dump)
    pipe = import_file(str(dump))
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)
    steps, lo, up = [], [], []
    for fi in range(pipe.source.num_frames):
        d = pipe.compute(fi)
        lo_x, lo_w, up_x, up_w = [], [], [], []
        for s in d.dislocations.segments:
            if s.length < 10.0:
                continue
            pts = np.asarray(s.points)
            (lo_x if pts[:, 2].mean() < z_split else up_x).append(circ_mean(pts[:, 0], np.ones(len(pts)), lx))
            (lo_w if pts[:, 2].mean() < z_split else up_w).append(float(s.length))
        if not lo_x or not up_x:
            continue
        steps.append(int(d.attributes.get("Timestep", fi)))
        lo.append(circ_mean(lo_x, lo_w, lx))
        up.append(circ_mean(up_x, up_w, lx))
    steps, lo, up = map(np.array, (steps, lo, up))
    for arr in (lo, up):                       # unwrap the periodic x
        for i in range(1, len(arr)):
            dx = arr[i] - arr[i - 1]
            arr[i] = arr[i - 1] + dx - round(dx / lx) * lx
    return steps, lo, up


def summarise(name, steps, lo, up) -> dict:
    t = steps * 1e-3
    out = {"case": name, "n_frames": int(len(steps)), "t_ps": [float(t[0]), float(t[-1])]}
    for lab, x in (("lower_plus_b", lo), ("upper_minus_b", up)):
        skip = t >= 5.0                      # first 5 ps: thermal settling
        seg = x[skip] if skip.sum() > 5 else x
        net = float(seg[-1] - seg[0])
        osc = float(np.std(seg))
        out[lab] = {"net_A": round(net, 2), "net_b": round(net / B_A, 2),
                    "oscillation_A": round(osc, 2),
                    "moved": bool(abs(net) > B_A and abs(net) > 3 * osc)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--z-split", type=float, default=61.0,
                    help="z separating the two glide planes (49.2 and 72.6 in the unified cell)")
    args = ap.parse_args()
    res = {"created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "run_dir": str(args.run_dir), "cases": {}, "traces": {}}
    for case in ("ctl", "fld"):
        dump = args.run_dir / f"G16_{case}" / f"G16_{case}.dyn.lammpstrj"
        if not dump.exists():
            print("missing", dump)
            continue
        s, lo, up = trajectories(dump, args.z_split)
        res["cases"][case] = summarise(case, s, lo, up)
        res["traces"][case] = {"t_ps": (s * 1e-3).round(3).tolist(),
                               "lower_x_A": lo.round(3).tolist(), "upper_x_A": up.round(3).tolist()}
        print("%s: %d frames, lower net %+.2f A (%+.2f b), upper net %+.2f A" % (
            case, len(s), res["cases"][case]["lower_plus_b"]["net_A"],
            res["cases"][case]["lower_plus_b"]["net_b"], res["cases"][case]["upper_minus_b"]["net_A"]))
    if "ctl" in res["cases"] and "fld" in res["cases"]:
        c, f = res["cases"]["ctl"], res["cases"]["fld"]
        diff = {}
        for lab in ("lower_plus_b", "upper_minus_b"):
            d = f[lab]["net_A"] - c[lab]["net_A"]
            osc = max(f[lab]["oscillation_A"], c[lab]["oscillation_A"])
            diff[lab] = {"field_minus_control_A": round(d, 2), "in_b": round(d / B_A, 2),
                         "field_moved_it": bool(abs(d) > B_A and abs(d) > 3 * osc)}
        res["field_effect"] = diff
        res["verdict"] = ("The maintained field displaced the %s by %.1f A relative to the control."
                          % (", ".join(k for k, v in diff.items() if v["field_moved_it"]),
                             max(abs(v["field_minus_control_A"]) for v in diff.values()))
                          if any(v["field_moved_it"] for v in diff.values()) else
                          "Neither line moved under the maintained field beyond its own thermal "
                          "oscillation: field-minus-control displacement %s A for the lower and %s A "
                          "for the upper partner, against oscillations of %s and %s A."
                          % (diff["lower_plus_b"]["field_minus_control_A"],
                             diff["upper_minus_b"]["field_minus_control_A"],
                             max(c["lower_plus_b"]["oscillation_A"], f["lower_plus_b"]["oscillation_A"]),
                             max(c["upper_minus_b"]["oscillation_A"], f["upper_minus_b"]["oscillation_A"])))
        print(res["verdict"])
    out = REPORTS / "stageG16_dipole_under_field.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
