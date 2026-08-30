#!/usr/bin/env python3
"""Stage G4: resolved shear stress (RSS) of the FIELD-INDUCED stress difference.

Methodological correction. Comparing a von Mises invariant against dislocation
thresholds that are quoted in applied shear is not admissible, and
sigma_vM(A) - sigma_vM(B) is not the invariant of the tensor difference. The
physically meaningful driving force on a dislocation is the resolved shear
stress of the DIFFERENCE tensor,

    Delta sigma_ij = sigma_ij(field) - sigma_ij(control),
    RSS_alpha = n_alpha . Delta sigma . b_alpha  (unit vectors),

maximized over the twelve fcc {111}<110> systems. This script computes both
that maximum RSS and, for reference, the von Mises invariant OF the difference
tensor, per 4 A bin of distance from the interface.

Lab frame: x = [1-10], y = [11-2], z = [111].
"""
from __future__ import annotations

import io
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
V_AT = 16.6072
Z_INTERFACE = 20.0
RIDGE_APEX = 40.0
BIN = 4.0
R_MAX = 120.0
EPS_INFLATED = 1.94e-3
LAMBDA_REAL = {"20 ppm": 2e-5, "40 ppm": 4e-5, "100 ppm": 1e-4}


def slip_systems_lab() -> list[tuple[np.ndarray, np.ndarray, str]]:
    """The twelve fcc {111}<110> systems expressed in the lab frame."""
    ex = np.array([1.0, -1.0, 0.0]) / math.sqrt(2.0)
    ey = np.array([1.0, 1.0, -2.0]) / math.sqrt(6.0)
    ez = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    R = np.vstack([ex, ey, ez])          # rows: lab axes in crystal coords
    planes = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    dirs = [(1, -1, 0), (1, 0, -1), (0, 1, -1), (1, 1, 0), (1, 0, 1), (0, 1, 1)]
    out = []
    for p in planes:
        n_c = np.array(p, float) / np.linalg.norm(p)
        for d in dirs:
            b_c = np.array(d, float) / np.linalg.norm(d)
            if abs(float(n_c @ b_c)) > 1e-9:
                continue                  # b must lie in the plane
            out.append((R @ n_c, R @ b_c, f"({p[0]}{p[1]}{p[2]})[{d[0]}{d[1]}{d[2]}]"))
    return out


def load(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = []
    started = False
    for ln in path:
        if ln.startswith("ITEM: ATOMS"):
            started = True
            continue
        if started:
            p = ln.split()
            if len(p) >= 11:
                rows.append([float(v) for v in p])
    a = np.array(rows)
    return a[:, 1].astype(int), a[:, 2:5], a[:, 5:11]


def voigt_to_tensor(v: np.ndarray) -> np.ndarray:
    """[xx, yy, zz, xy, xz, yz] -> 3x3."""
    return np.array([[v[0], v[3], v[4]],
                     [v[3], v[1], v[5]],
                     [v[4], v[5], v[2]]])


def von_mises(t: np.ndarray) -> float:
    d = t - np.trace(t) / 3.0 * np.eye(3)
    return float(math.sqrt(1.5 * np.sum(d * d)))


def main() -> int:
    from _g4clean import source_dir, open_dump, CONTROL, FIELD
    base = source_dir()
    with open_dump(base, CONTROL) as fh:
        t_ctl, p_ctl, s_ctl = load(fh)
    with open_dump(base, FIELD) as fh:
        t_phy, p_phy, s_phy = load(fh)
    assert len(t_ctl) == len(t_phy), "atom counts differ"

    systems = slip_systems_lab()
    edges = np.arange(0.0, R_MAX + BIN, BIN)
    rows = []
    for i in range(len(edges) - 1):
        lo, hi = Z_INTERFACE + edges[i], Z_INTERFACE + edges[i + 1]
        if lo < RIDGE_APEX + 2.0:
            continue
        m = (p_ctl[:, 2] >= lo) & (p_ctl[:, 2] < hi) & (t_ctl != 2)
        n = int(m.sum())
        if n < 50:
            continue
        # tensor-average FIRST, then form invariants (per-atom invariants
        # measure the ~GPa thermal virial amplitude, not the field)
        sc = -s_ctl[m].mean(axis=0) / V_AT / 10.0
        sp = -s_phy[m].mean(axis=0) / V_AT / 10.0
        dt = voigt_to_tensor(sp - sc)
        rss = [(abs(float(nn @ dt @ bb)), lbl) for nn, bb, lbl in systems]
        rss.sort(reverse=True)
        rows.append({
            "r_A": round((edges[i] + edges[i + 1]) / 2, 1),
            "max_RSS_MPa": round(rss[0][0], 3),
            "system": rss[0][1],
            "vM_of_difference_MPa": round(von_mises(dt), 3),
            "d_sigma_xz_MPa": round(float(dt[0, 2]), 3),
            "n_atoms": n,
        })

    peak = max(rows, key=lambda r: r["max_RSS_MPa"])
    far = [r["max_RSS_MPa"] for r in rows if r["r_A"] > 60]
    res = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "method": "Delta sigma_ij = sigma(field) - sigma(control), tensor-averaged per 4 A bin; "
                  "RSS maximized over the 12 fcc {111}<110> systems in the lab frame "
                  "x=[1-10] y=[11-2] z=[111]",
        "note": "vM_of_difference is the invariant OF the difference tensor, which is NOT "
                "the difference of the two von Mises values reported earlier",
        "eigenstrain_used": EPS_INFLATED,
        "peak": peak,
        "far_field_beyond_60A": {"mean_max_RSS_MPa": round(float(np.mean(far)), 3),
                                 "std_MPa": round(float(np.std(far)), 3)},
        "peak_rescaled_to_real_magnetostriction_MPa": {
            k: round(peak["max_RSS_MPa"] * lam / EPS_INFLATED, 4)
            for k, lam in LAMBDA_REAL.items()
        },
        "profile": rows,
    }
    out = REPO_ROOT / "docs" / "reports" / "stageG4_rss_profile.json"
    out.write_text(json.dumps(res, indent=2) + chr(10), encoding="utf-8")

    print("r,A   maxRSS  system              vM(diff)  d_sxz   N")
    for r in rows[:14]:
        print("%5.1f %8.2f  %-18s %8.2f %7.2f %5d" % (
            r["r_A"], r["max_RSS_MPa"], r["system"], r["vM_of_difference_MPa"],
            r["d_sigma_xz_MPa"], r["n_atoms"]))
    print()
    print("PEAK max-RSS = %.2f MPa at r = %.1f A on %s" % (
        peak["max_RSS_MPa"], peak["r_A"], peak["system"]))
    print("beyond 60 A: %.2f +- %.2f MPa" % (
        res["far_field_beyond_60A"]["mean_max_RSS_MPa"], res["far_field_beyond_60A"]["std_MPa"]))
    print("rescaled to real lambda_s:", res["peak_rescaled_to_real_magnetostriction_MPa"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
