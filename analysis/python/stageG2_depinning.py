#!/usr/bin/env python3
"""Stage G2: extract the dipole-breakup threshold tau_c per case.

Protocol fixed by the adversarial review (g2-shear-protocol-verify):
- classify DXA segments by ORIENTED Burgers sign b_x (+b / -b families),
  z only as a secondary attribute; flag interface-band segments (z<40 A);
- unwrap family mean-x across frames (PBC continuity);
- s(t) = x_plus - x_minus (unwrapped separation);
- baseline = frames with nominal tau < 40 MPa: linear fit of s, residual sigma_s;
- onset = first frame with s - fit > max(6*sigma_s, 8 A), sustained 2 more frames;
- tau_c = nominal ramp tau at onset step, plus the local reduce/region monitor
  (tauLow/tauUpp from log, averaged over +-1000 steps around onset).
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = ["G2_shear_eps0000", "G2_shear_eps00194"]
LX = 186.1458
PRE, TS, NTOT = 5000, 16000, 101000
TAUMAX = 400.0


def tau_nominal_mpa(step: float) -> float:
    n_ramp = NTOT - PRE
    r = TAUMAX / (n_ramp - 0.5 * TS)          # MPa per step
    sp = step - PRE
    if sp <= 0:
        return 0.0
    if sp < TS:
        return r * (0.5 * sp - (TS / (2 * math.pi)) * math.sin(math.pi * sp / TS))
    return r * (sp - 0.5 * TS)


def parse_log(log_path: Path) -> dict[str, np.ndarray]:
    rows = []
    for ln in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = ln.split()
        if len(parts) == 11 and re.fullmatch(r"\d+", parts[0]):
            try:
                rows.append([float(v) for v in parts])
            except ValueError:
                pass
    arr = np.array(rows)
    return {"step": arr[:, 0], "temp": arr[:, 2], "taubar": arr[:, 8],
            "tauLow": arr[:, 9], "tauUpp": arr[:, 10]}


def circ_mean(xs: np.ndarray) -> float:
    ang = xs / LX * 2 * math.pi
    return float((math.atan2(np.sin(ang).mean(), np.cos(ang).mean()) % (2 * math.pi)) / (2 * math.pi) * LX)


def analyze_case(case: str, run_dir: Path) -> dict:
    from ovito.io import import_file
    from ovito.modifiers import DislocationAnalysisModifier

    dump = run_dir / case / "production" / f"{case}.production.lammpstrj"
    pipe = import_file(str(dump))
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)

    frames = []
    for fi in range(pipe.source.num_frames):
        data = pipe.compute(fi)
        step = int(data.attributes.get("Timestep", fi * 2000))
        fam: dict[str, list] = {"plus": [], "minus": [], "other": [], "interface": []}
        total_len = 0.0
        for seg in data.dislocations.segments:
            pts = np.asarray(seg.points)
            bx = float(seg.spatial_burgers_vector[0])
            zc = float(pts[:, 2].mean())
            xc = circ_mean(pts[:, 0])
            total_len += float(seg.length)
            entry = (xc, zc, float(seg.length), bx)
            if zc < 40.0:
                fam["interface"].append(entry)
            elif bx > 0.5:
                fam["plus"].append(entry)
            elif bx < -0.5:
                fam["minus"].append(entry)
            else:
                fam["other"].append(entry)
        row = {"frame": fi, "step": step, "tau_nominal_MPa": tau_nominal_mpa(step),
               "n_segments": len(data.dislocations.segments), "dxa_total_len_A": total_len,
               "n_interface_segments": len(fam["interface"]),
               "n_other_segments": len(fam["other"])}
        for name in ("plus", "minus"):
            entries = fam[name]
            if entries:
                xs = np.array([e[0] for e in entries])
                w = np.array([e[2] for e in entries])
                row[f"x_{name}"] = circ_mean(np.repeat(xs, np.maximum(1, (w / 10).astype(int))))
                row[f"z_{name}"] = float(np.mean([e[1] for e in entries]))
                row[f"len_{name}"] = float(w.sum())
                row[f"xmin_{name}"] = float(xs.min())
                row[f"xmax_{name}"] = float(xs.max())
            else:
                row[f"x_{name}"] = None
        frames.append(row)

    # unwrap family means across frames
    for name in ("plus", "minus"):
        prev = None
        acc = 0.0
        for row in frames:
            x = row.get(f"x_{name}")
            if x is None:
                row[f"xu_{name}"] = None
                continue
            if prev is not None:
                d = x - prev
                d -= round(d / LX) * LX
                acc += d
            else:
                acc = x
            prev = x
            row[f"xu_{name}"] = acc

    for row in frames:
        xp, xm = row.get("xu_plus"), row.get("xu_minus")
        row["s_A"] = (xp - xm) if (xp is not None and xm is not None) else None

    # depinning detection
    base = [(r["step"], r["s_A"]) for r in frames if r["tau_nominal_MPa"] < 40.0 and r["s_A"] is not None]
    bs = np.array(base)
    coef = np.polyfit(bs[:, 0], bs[:, 1], 1)
    sigma_s = float(np.std(bs[:, 1] - np.polyval(coef, bs[:, 0])))
    thresh = max(6 * sigma_s, 8.0)
    onset = None
    for i, r in enumerate(frames):
        if r["s_A"] is None:
            continue
        dev = r["s_A"] - float(np.polyval(coef, r["step"]))
        r["s_dev_A"] = dev
        if onset is None and dev > thresh:
            later = [f for f in frames[i + 1:i + 3] if f["s_A"] is not None]
            if len(later) >= 2 and all(
                    (f["s_A"] - np.polyval(coef, f["step"])) > dev - 2.0 for f in later):
                onset = r
    result = {"case": case, "frames": frames, "sigma_s_A": sigma_s, "threshold_A": thresh,
              "baseline_fit": {"slope_A_per_step": float(coef[0]), "intercept_A": float(coef[1])}}
    if onset is not None:
        log = parse_log(run_dir / case / "production" / "log.lammps")
        m = (log["step"] > onset["step"] - 1000) & (log["step"] < onset["step"] + 1000)
        result["onset"] = {
            "step": onset["step"], "frame": onset["frame"],
            "tau_c_nominal_MPa": onset["tau_nominal_MPa"],
            "tau_local_low_MPa": float(log["tauLow"][m].mean()),
            "tau_local_upp_MPa": float(log["tauUpp"][m].mean()),
            "s_at_onset_A": onset["s_A"], "s_dev_at_onset_A": onset["s_dev_A"],
        }
    else:
        result["onset"] = None
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "docs" / "reports")
    args = parser.parse_args()

    summary = {"run_dir": str(args.run_dir),
               "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "protocol": "adversarial-review v2: oriented-Burgers families, unwrapped s(t), "
                           "baseline tau<40 MPa, onset 6*sigma_s (min 8 A) sustained 3 frames",
               "cases": {}}
    for case in CASES:
        res = analyze_case(case, args.run_dir)
        keys = [k for k in res["frames"][0].keys()]
        csv_path = args.out_dir / f"stageG2_depinning_{case}.csv"
        lines = [",".join(keys)]
        for r in res["frames"]:
            lines.append(",".join("" if r.get(k) is None else str(r.get(k)) for k in keys))
        csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        summary["cases"][case] = {k: v for k, v in res.items() if k != "frames"}
        summary["cases"][case]["csv"] = str(csv_path)

    o0 = summary["cases"][CASES[0]]["onset"]
    o1 = summary["cases"][CASES[1]]["onset"]
    if o0 and o1:
        summary["delta_tau_c_nominal_MPa"] = o1["tau_c_nominal_MPa"] - o0["tau_c_nominal_MPa"]
    out = args.out_dir / "stageG2_depinning_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}, indent=2))
    for c, v in summary["cases"].items():
        print(c, "onset:", json.dumps(v["onset"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
