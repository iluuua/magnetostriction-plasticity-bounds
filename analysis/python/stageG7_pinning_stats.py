#!/usr/bin/env python3
"""Stage G7 analysis: pinning statistics across independent solute realizations.

For each realization the probe trajectory is extracted by DXA and reduced to
the quantities that matter now that we know the line does not glide:

  - net displacement over the whole loading history, in units of b;
  - per-rung net displacement and the thermal oscillation amplitude;
  - whether any rung shows a displacement exceeding 3x the oscillation, which
    is what a genuine depinning event would look like;
  - the highest applied stress the configuration withstands.

Usage: .venv/Scripts/python.exe analysis/python/stageG7_pinning_stats.py \
           --run-dir runs/stageG7_replicas/<stamp> [--include-relA]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "docs" / "reports"
LX = 114.5513
B_A = 4.05 / math.sqrt(2.0)
PRE, HOLD = 10000, 30000
RUNGS = [45, 55, 65, 75]
Z_SPLIT = 130.0


def circ_mean(xs, ws) -> float:
    ang = np.asarray(xs) / LX * 2 * math.pi
    ws = np.asarray(ws)
    return (math.atan2(float((np.sin(ang) * ws).sum()), float((np.cos(ang) * ws).sum()))
            % (2 * math.pi)) / (2 * math.pi) * LX


def trajectory_from_dump(dump: Path):
    from ovito.io import import_file
    from ovito.modifiers import DislocationAnalysisModifier
    pipe = import_file(str(dump))
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)
    steps, xs = [], []
    for fi in range(pipe.source.num_frames):
        d = pipe.compute(fi)
        lo_x, lo_w = [], []
        for s in d.dislocations.segments:
            if s.length < 10.0:
                continue
            pts = np.asarray(s.points)
            if pts[:, 2].mean() < Z_SPLIT:
                lo_x.append(circ_mean(pts[:, 0], np.ones(1)))
                lo_w.append(float(s.length))
        if not lo_x:
            continue
        steps.append(int(d.attributes.get("Timestep", fi * 1000)))
        xs.append(circ_mean(lo_x, lo_w))
    # PBC unwrap
    out, acc, prev = [], 0.0, None
    for x in xs:
        if prev is None:
            acc = x
        else:
            dx = x - prev
            dx -= round(dx / LX) * LX
            acc += dx
        prev = x
        out.append(acc)
    return np.array(steps, dtype=float), np.array(out)


def trajectory_from_csv(path: Path):
    rows = list(csv.DictReader(io.open(path, encoding="utf-8")))
    s, x = [], []
    for r in rows:
        if r.get("ux_lo"):
            s.append(float(r["step"]))
            x.append(float(r["ux_lo"]))
    return np.array(s), np.array(x)


def analyse(name: str, steps: np.ndarray, x: np.ndarray) -> dict:
    t = steps * 1e-3
    load = t >= PRE * 1e-3
    net_total = float(x[-1] - x[load][0])
    rungs = []
    for k, tau in enumerate(RUNGS):
        a = (PRE + k * HOLD) * 1e-3 + 6.0
        b = (PRE + (k + 1) * HOLD) * 1e-3
        m = (t >= a) & (t <= b)
        if m.sum() < 5:
            continue
        seg = x[m]
        net = float(seg[-1] - seg[0])
        osc = float(np.std(seg))
        rungs.append({"tau_MPa": tau, "net_displacement_A": round(net, 2),
                      "oscillation_A": round(osc, 2),
                      "ratio": round(abs(net) / max(osc, 1e-9), 2),
                      "depinned": bool(abs(net) > 3 * osc and abs(net) > B_A)})
    # A replica that was stopped early cannot be said to have withstood a rung it
    # never reached: bound the claim by the highest rung the trajectory covers.
    covered = [r["tau_MPa"] for r in rungs]
    highest = max(covered) if covered else 0
    return {"case": name,
            "net_displacement_A": round(net_total, 2),
            "net_displacement_b": round(net_total / B_A, 2),
            "oscillation_A": round(float(np.std(x[load])), 2),
            "rungs": rungs,
            "rungs_covered_MPa": covered,
            "complete": highest == max(RUNGS),
            "any_depinning": any(r["depinned"] for r in rungs),
            "max_stress_withstood_MPa": highest if not any(r["depinned"] for r in rungs)
            else min(r["tau_MPa"] for r in rungs if r["depinned"])}


def _verdict(results, nets) -> str:
    """State only what the trajectories that exist actually support."""
    if any(r["any_depinning"] for r in results):
        return ("%d of %d realizations show a depinning event; the pinning stress is "
                "not uniform across solute configurations."
                % (sum(1 for r in results if r["any_depinning"]), len(results)))
    full = [r for r in results if r["complete"]]
    part = [r for r in results if not r["complete"]]
    s = ("In %d realization%s the probe stays pinned through every rung it was taken "
         "to: net displacement %.1f-%.1f b, with no rung showing a displacement above "
         "three times the thermal oscillation."
         % (len(results), "" if len(results) == 1 else "s", min(nets), max(nets)))
    if full:
        s += (" %s ran the complete staircase and therefore withstands at least "
              "%d MPa." % (", ".join(r["case"] for r in full), max(RUNGS)))
    for r in part:
        s += (" %s was stopped early at %d MPa and bounds nothing above that."
              % (r["case"], r["max_stress_withstood_MPa"]))
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--include-relA", action="store_true")
    args = ap.parse_args()

    results = []
    if args.include_relA:
        p = REPORTS / "stageG6_vstar_relA_frames.csv"
        if p.exists():
            s, x = trajectory_from_csv(p)
            results.append(analyse("G3_solute_relA", s, x))

    for d in sorted(args.run_dir.glob("G3_solute_rel*")):
        dump = d / f"{d.name}.vstar.lammpstrj"
        if not dump.exists():
            continue
        s, x = trajectory_from_dump(dump)
        if len(s) < 10:
            continue
        results.append(analyse(d.name, s, x))

    if not results:
        print("no finished replicas yet")
        return 1

    nets = [r["net_displacement_b"] for r in results]
    summary = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "n_realizations": len(results),
        "realizations": results,
        "net_displacement_b": {"mean": round(float(np.mean(nets)), 2),
                               "min": round(float(np.min(nets)), 2),
                               "max": round(float(np.max(nets)), 2)},
        "depinning_events": sum(1 for r in results if r["any_depinning"]),
        "verdict": _verdict(results, nets)}

    out = REPORTS / "stageG7_pinning_statistics.json"
    out.write_text(json.dumps(summary, indent=2) + chr(10), encoding="utf-8")
    for r in results:
        print("%-18s net = %+5.2f A (%+.2f b), osc %.2f A, depinning: %s"
              % (r["case"], r["net_displacement_A"], r["net_displacement_b"],
                 r["oscillation_A"], r["any_depinning"]))
    print()
    print(summary["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
