#!/usr/bin/env python3
"""Stage G4 analysis: dislocation velocity per stress step, control vs physical.

Per frame: DXA segments classified by oriented Burgers sign into the probe
(+b, lower glide plane near the ridge) and the reaction partner (-b, upper
plane); PBC-unwrapped mean x per family; CNA HCP count; any NEW segment in the
interface band (z < 45 A) is flagged as candidate heterogeneous nucleation.

Per stress rung: least-squares velocity dx/dt from the unwrapped probe
trajectory, its standard error, and the physical/control ratio. The activation
volume follows from V* = kT dln(v)/dtau.

Usage: .venv/Scripts/python.exe analysis/python/stageG4_mobility.py --run-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = ["G4_tilted_eps0000", "G4_tilted_eps00194"]
LX = 114.5513
PRE, HOLD = 10000, 20000
TAU0, DTAU = 30.0, 10.0
KT_300 = 1.380649e-23 * 300.0
B_M = 4.05e-10 / math.sqrt(2.0)
Z_SPLIT = 145.0          # between the two glide planes (53.9 and 241.0)
Z_INTERFACE = 45.0       # below this = inclusion / interface band


def tau_of_step(step: float) -> float:
    if step < PRE:
        return 0.0
    return TAU0 + DTAU * math.floor((step - PRE) / HOLD)


def circ_mean(xs: np.ndarray, w: np.ndarray | None = None) -> float:
    ang = xs / LX * 2 * math.pi
    if w is None:
        w = np.ones_like(xs)
    s = float((np.sin(ang) * w).sum())
    c = float((np.cos(ang) * w).sum())
    return float((math.atan2(s, c) % (2 * math.pi)) / (2 * math.pi) * LX)


def analyze_case(case: str, run_dir: Path) -> dict:
    from ovito.io import import_file
    from ovito.modifiers import CommonNeighborAnalysisModifier, DislocationAnalysisModifier

    dump = run_dir / case / f"{case}.mobility.lammpstrj"
    pipe = import_file(str(dump))
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(CommonNeighborAnalysisModifier())
    pipe.modifiers.append(dxa)

    frames = []
    for fi in range(pipe.source.num_frames):
        d = pipe.compute(fi)
        step = int(d.attributes.get("Timestep", fi * 1000))
        probe_x, probe_w, partner_x, partner_w = [], [], [], []
        n_interface, total_len = 0, 0.0
        for seg in d.dislocations.segments:
            pts = np.asarray(seg.points)
            zc = float(pts[:, 2].mean())
            xc = circ_mean(pts[:, 0])
            total_len += float(seg.length)
            if zc < Z_INTERFACE:
                n_interface += 1
            elif zc < Z_SPLIT:
                probe_x.append(xc)
                probe_w.append(float(seg.length))
            else:
                partner_x.append(xc)
                partner_w.append(float(seg.length))
        st = d.particles["Structure Type"][...]
        pos = d.particles.positions[...]
        types = d.particles["Particle Type"][...]
        matrix = (types != 2) & (pos[:, 2] > Z_INTERFACE)
        n_hcp = int(np.count_nonzero((st == CommonNeighborAnalysisModifier.Type.HCP) & matrix))
        row = {
            "frame": fi, "step": step, "tau_MPa": tau_of_step(step),
            "n_segments": len(d.dislocations.segments), "dxa_len_A": total_len,
            "n_interface_segments": n_interface, "hcp_matrix": n_hcp,
            "x_probe": circ_mean(np.array(probe_x), np.array(probe_w)) if probe_x else None,
            "x_partner": circ_mean(np.array(partner_x), np.array(partner_w)) if partner_x else None,
            "len_probe": float(sum(probe_w)), "len_partner": float(sum(partner_w)),
        }
        frames.append(row)

    # PBC-unwrap both families
    for fam in ("probe", "partner"):
        prev, acc = None, 0.0
        for r in frames:
            x = r[f"x_{fam}"]
            if x is None:
                r[f"xu_{fam}"] = None
                continue
            if prev is None:
                acc = x
            else:
                dx = x - prev
                dx -= round(dx / LX) * LX
                acc += dx
            prev = x
            r[f"xu_{fam}"] = acc
    return {"case": case, "frames": frames}


def rung_velocities(frames: list[dict]) -> dict:
    """Least-squares dx/dt over each constant-stress rung (drop the first 2 ps
    of every rung as loading transient)."""
    out = {}
    for k in range(4):
        lo = PRE + k * HOLD + 2000
        hi = PRE + (k + 1) * HOLD
        pts = [(r["step"], r["xu_probe"]) for r in frames
               if lo <= r["step"] <= hi and r.get("xu_probe") is not None]
        if len(pts) < 5:
            continue
        a = np.array(pts, dtype=float)
        t_ps = a[:, 0] * 1e-3                      # fs -> ps (dt = 1 fs)
        x_A = a[:, 1]
        n = len(t_ps)
        slope, intercept = np.polyfit(t_ps, x_A, 1)
        resid = x_A - (slope * t_ps + intercept)
        s_err = float(np.sqrt((resid ** 2).sum() / max(1, n - 2) /
                              max(1e-12, ((t_ps - t_ps.mean()) ** 2).sum())))
        out[f"tau_{int(TAU0 + k * DTAU)}"] = {
            "tau_MPa": TAU0 + k * DTAU,
            "v_A_per_ps": float(slope), "v_stderr": s_err,
            "v_m_per_s": float(slope) * 100.0,     # 1 A/ps = 100 m/s
            "displacement_A": float(x_A[-1] - x_A[0]), "n_points": n,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "docs" / "reports")
    args = ap.parse_args()

    summary = {"run_dir": str(args.run_dir),
               "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "protocol": "constant-stress staircase 30/40/50/60 MPa, 20 ps each, 10 ps at tau=0",
               "cases": {}}
    per_case = {}
    for case in CASES:
        res = analyze_case(case, args.run_dir)
        per_case[case] = res["frames"]
        keys = list(res["frames"][0].keys())
        csv = args.out_dir / f"stageG4_mobility_{case}.csv"
        lines = [",".join(keys)]
        for r in res["frames"]:
            lines.append(",".join("" if r.get(k) is None else str(r.get(k)) for k in keys))
        csv.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        summary["cases"][case] = {
            "csv": str(csv), "frames": len(res["frames"]),
            "rungs": rung_velocities(res["frames"]),
            "hcp_first_last": [res["frames"][0]["hcp_matrix"], res["frames"][-1]["hcp_matrix"]],
            "interface_segments_max": max(r["n_interface_segments"] for r in res["frames"]),
            "dxa_len_first_last": [res["frames"][0]["dxa_len_A"], res["frames"][-1]["dxa_len_A"]],
        }

    # control vs physical, per rung
    c, p = summary["cases"][CASES[0]]["rungs"], summary["cases"][CASES[1]]["rungs"]
    comp = {}
    for k in c:
        if k not in p:
            continue
        vc, vp = c[k]["v_A_per_ps"], p[k]["v_A_per_ps"]
        comp[k] = {"tau_MPa": c[k]["tau_MPa"],
                   "v_control_A_ps": vc, "v_physical_A_ps": vp,
                   "delta_v_A_ps": vp - vc,
                   "ratio": (vp / vc) if abs(vc) > 1e-9 else None,
                   "control_stderr": c[k]["v_stderr"], "physical_stderr": p[k]["v_stderr"],
                   "significant_3sigma": bool(abs(vp - vc) >
                                              3 * math.hypot(c[k]["v_stderr"], p[k]["v_stderr"]))}
    summary["comparison"] = comp

    # activation volume from ln(v) vs tau, each case
    for case in CASES:
        rr = summary["cases"][case]["rungs"]
        taus = np.array([rr[k]["tau_MPa"] for k in rr], dtype=float)
        vs = np.array([rr[k]["v_A_per_ps"] for k in rr], dtype=float)
        ok = vs > 0
        if ok.sum() >= 3:
            slope = np.polyfit(taus[ok] * 1e6, np.log(vs[ok]), 1)[0]   # per Pa
            summary["cases"][case]["V_star_b3"] = float(slope * KT_300 / (B_M ** 3))
        else:
            summary["cases"][case]["V_star_b3"] = None
            summary["cases"][case]["V_star_note"] = "fewer than 3 rungs with positive velocity"

    out = args.out_dir / "stageG4_mobility_summary.json"
    out.write_text(json.dumps(summary, indent=2) + chr(10), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
