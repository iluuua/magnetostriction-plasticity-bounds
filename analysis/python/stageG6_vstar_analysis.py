#!/usr/bin/env python3
"""Stage G6: extract V* from the staircase run - careful version.

Per frame: DXA (FCC), segments >= 10 A, lower family (probe, z < 130) and upper
family; length-weighted circular-mean x, PBC-unwrapped across frames.
Per rung (drop the first 6 ps: 4 ps smoothstep + 2 ps settling):
  - probe velocity dx/dt by least squares, stderr inflated by lag-1
    autocorrelation of residuals (Bartlett);
  - the ACTUAL stress axis: tensor-averaged sigma_xz over a quiet matrix box
    (away from both glide planes, the ridge, the driven slab and the seam),
    because the G4 post-mortem showed nominal and global-pxz axes are unreliable.
V*: weighted fit of ln(v) vs actual tau; error from the fit covariance.
"""
from __future__ import annotations

import argparse, json, math
from datetime import datetime
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
LX = 114.5513   # G6 cell Lx (40*PX); the G4 cell is 108.8237 - do not mix
KT = 1.380649e-23 * 300.0
B_M = 4.05e-10 / math.sqrt(2.0)
V_AT = 16.6072
PRE, HOLD = 10000, 30000
RUNGS = [(PRE + k * HOLD, PRE + (k + 1) * HOLD, 45 + 10 * k) for k in range(4)]
Z_SPLIT = 130.0
QUIET = dict(x0=5.0, x1=45.0, z0=60.0, z1=115.0)   # away from ridge edge (~89), dipole x (~101), slabs


def cmean(xs, ws):
    ang = np.asarray(xs) / LX * 2 * math.pi
    ws = np.asarray(ws)
    return (math.atan2((np.sin(ang) * ws).sum(), (np.cos(ang) * ws).sum())
            % (2 * math.pi)) / (2 * math.pi) * LX


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=Path, required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "docs" / "reports")
    args = ap.parse_args()

    from ovito.io import import_file
    from ovito.modifiers import DislocationAnalysisModifier
    pipe = import_file(str(args.dump))
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)
    n = pipe.source.num_frames

    frames = []
    for fi in range(n):
        d = pipe.compute(fi)
        step = int(d.attributes.get("Timestep", fi * 1000))
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
        st = np.column_stack([d.particles[f"c_st[{i}]"][...] for i in range(1, 7)])
        q = ((pos[:, 0] >= QUIET["x0"]) & (pos[:, 0] < QUIET["x1"])
             & (pos[:, 2] >= QUIET["z0"]) & (pos[:, 2] < QUIET["z1"]) & (types != 2))
        sxz_quiet = float(-st[q, 4].sum() / (q.sum() * V_AT) / 10.0)
        frames.append({
            "frame": fi, "step": step,
            "x_lo": cmean(lo_x, lo_w) if lo_x else None,
            "x_up": cmean(up_x, up_w) if up_x else None,
            "len_lo": float(sum(lo_w)), "len_up": float(sum(up_w)),
            "n_small_segments": n_small, "sxz_quiet_MPa": sxz_quiet,
        })

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
        se = math.sqrt(float((resid ** 2).sum()) / max(1, nn - 2)
                       / float(((t - t.mean()) ** 2).sum()))
        rho = float(np.corrcoef(resid[:-1], resid[1:])[0, 1]) if nn > 3 else 0.0
        infl = math.sqrt(max(1.0, (1 + rho) / max(1e-6, 1 - rho)))
        tau_act = float(np.mean([r["sxz_quiet_MPa"] for r in sel]))
        tau_sd = float(np.std([r["sxz_quiet_MPa"] for r in sel]) / math.sqrt(len(sel)))
        rungs.append({"nominal_MPa": nominal, "tau_actual_MPa": tau_act,
                      "tau_actual_sem_MPa": tau_sd,
                      "v_A_per_ps": v, "v_sem_A_per_ps": se * infl,
                      "v_m_per_s": v * 100, "autocorr_rho": rho, "n_frames": nn,
                      "displacement_A": float(x[-1] - x[0])})

    result = {"tag": args.tag, "dump": str(args.dump), "n_frames": n,
              "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
              "quiet_box": QUIET, "rungs": rungs}

    good = [r for r in rungs if r["v_A_per_ps"] > 0]
    if len(good) >= 3:
        taus = np.array([r["tau_actual_MPa"] for r in good]) * 1e6
        lnv = np.log([r["v_A_per_ps"] for r in good])
        w = 1.0 / np.array([max(1e-3, r["v_sem_A_per_ps"] / r["v_A_per_ps"]) for r in good]) ** 2
        W = np.diag(w)
        A = np.vstack([taus, np.ones_like(taus)]).T
        cov = np.linalg.inv(A.T @ W @ A)
        beta = cov @ A.T @ W @ lnv
        slope, slope_err = float(beta[0]), float(math.sqrt(cov[0, 0]))
        result["V_star_b3"] = slope * KT / B_M ** 3
        result["V_star_err_b3"] = slope_err * KT / B_M ** 3
        result["kT_over_Vstar_MPa"] = KT / (slope * KT) / 1e6 if slope > 0 else None
    csvp = args.out_dir / f"stageG6_vstar_{args.tag}_frames.csv"
    keys = list(frames[0].keys())
    lines = [",".join(keys)]
    for r in frames:
        lines.append(",".join("" if r.get(k) is None else str(r.get(k)) for k in keys))
    csvp.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    out = args.out_dir / f"stageG6_vstar_{args.tag}_summary.json"
    out.write_text(json.dumps(result, indent=2) + chr(10), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "dump"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
