#!/usr/bin/env python3
"""Stage G10: ONE authoritative field profile, replacing two inconsistent ones.

The manuscript figure (fig_sigma_profile) and the RSS table
(stageG4_rss_profile.json) were produced by different scripts with different
atom filters and a different treatment of the bin that straddles the ridge
apex. They disagreed: the figure showed a peak shear increment of 6.61 MPa at
r = 22 A, the table 6.26 MPa at r = 30 A. This script recomputes every
quantity that enters the paper from the same two dumps, the same bins and the
same atom set, and emits both the numbers and the figures.

Definitions (all evaluated AFTER averaging the six virial components per bin,
never per atom, since a per-atom invariant measures the ~GPa thermal virial):

    Delta sigma_ij(r) = sigma_ij(r; eps*) - sigma_ij(r; 0)
    RSS_max(r)        = max over the 12 fcc {111}<110> systems of
                        |n_a . Delta sigma(r) . s_a|              >= 0
    sigma_vM[Delta]   = sqrt(3/2 dev(Delta):dev(Delta))           >= 0
    Delta[sigma_vM]   = vM(field) - vM(control)                   any sign

The last one is a diagnostic only: it is a difference of invariants, not the
invariant of the difference, and it is what the earlier figure plotted.

Bins are 4 A wide in r = z - z_interface. Only Al atoms are used, and only
bins lying entirely above the ridge apex, where distance from the interface is
unambiguous; the apex-straddling bin is reported separately.
"""
from __future__ import annotations

import io
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "docs" / "reports"
from _g4clean import source_dir, open_dump, CONTROL, FIELD

V_AT = 16.6072          # A^3 per Al atom
Z_INTERFACE = 20.0      # flat Fe4Al13/Al boundary
RIDGE_APEX = 40.24      # highest Fe atom
BIN = 4.0
R_MAX = 120.0
EPS_INFLATED = 1.94e-3
LAMBDA_REAL = {"20 ppm": 2e-5, "40 ppm": 4e-5, "100 ppm": 1e-4}
MU_AL = 26.5e9


def slip_systems_lab():
    ex = np.array([1.0, -1.0, 0.0]) / math.sqrt(2.0)
    ey = np.array([1.0, 1.0, -2.0]) / math.sqrt(6.0)
    ez = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    R = np.vstack([ex, ey, ez])
    planes = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    dirs = [(1, -1, 0), (1, 0, -1), (0, 1, -1), (1, 1, 0), (1, 0, 1), (0, 1, 1)]
    out = []
    for p in planes:
        n_c = np.array(p, float) / np.linalg.norm(p)
        for d in dirs:
            b_c = np.array(d, float) / np.linalg.norm(d)
            if abs(float(n_c @ b_c)) > 1e-9:
                continue
            out.append((R @ n_c, R @ b_c, "(%d%d%d)[%d%d%d]" % (p + d)))
    return out


def load(path: Path):
    rows, started = [], False
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


def tensor(v):
    return np.array([[v[0], v[3], v[4]], [v[3], v[1], v[5]], [v[4], v[5], v[2]]])


def vm(t):
    d = t - np.trace(t) / 3.0 * np.eye(3)
    return float(math.sqrt(1.5 * np.sum(d * d)))


def main() -> int:
    global R_MAX
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", help="control dump (default: data/stageG4_clean)")
    ap.add_argument("--field", help="strained dump (default: data/stageG4_clean)")
    ap.add_argument("--out", help="output JSON (default: docs/reports/stageG10_field_profile.json)")
    ap.add_argument("--r-max", type=float, default=R_MAX)
    ap.add_argument("--label", default="", help="free-text label stored in the record")
    args = ap.parse_args()
    R_MAX = args.r_max
    src = source_dir()
    if args.control and args.field:
        import gzip
        def _open(pth):
            pth = Path(pth)
            return (io.TextIOWrapper(gzip.open(pth, "rb"), encoding="utf-8", errors="replace")
                    if pth.suffix == ".gz" else io.open(pth, encoding="utf-8", errors="replace"))
        ctl_fh, fld_fh = _open(args.control), _open(args.field)
    else:
        ctl_fh, fld_fh = open_dump(src, CONTROL), open_dump(src, FIELD)
    with ctl_fh as fh:
        t_c, p_c, s_c = load(fh)
    with fld_fh as fh:
        t_f, p_f, s_f = load(fh)
    assert len(t_c) == len(t_f)
    systems = slip_systems_lab()

    rows = []
    edges = np.arange(0.0, R_MAX + BIN, BIN)
    for i in range(len(edges) - 1):
        lo, hi = Z_INTERFACE + edges[i], Z_INTERFACE + edges[i + 1]
        m = (p_c[:, 2] >= lo) & (p_c[:, 2] < hi) & (t_c == 1)
        # the same bin restricted to a 20 A window over the ridge crest: what a
        # continuum solution predicts on the vertical through the apex (stageG17)
        cx_ = 0.5 * float(np.max(p_c[:, 0]) + np.min(p_c[:, 0]))
        m_axis = m & (np.abs(p_c[:, 0] - cx_) < 10.0)
        n = int(m.sum())
        if n < 50:
            continue
        sc = -s_c[m].mean(axis=0) / V_AT / 10.0
        sf = -s_f[m].mean(axis=0) / V_AT / 10.0
        Tc, Tf = tensor(sc), tensor(sf)
        dT = Tf - Tc
        rss = sorted(((abs(float(nn @ dT @ bb)), lbl) for nn, bb, lbl in systems), reverse=True)
        rows.append({
            "r_A": round((edges[i] + edges[i + 1]) / 2, 1),
            "above_apex": bool(lo >= RIDGE_APEX),
            "vm_control_MPa": round(vm(Tc), 3),
            "vm_field_MPa": round(vm(Tf), 3),
            "vm_of_difference_MPa": round(vm(dT), 3),
            "diff_of_vm_MPa": round(vm(Tf) - vm(Tc), 3),
            "max_RSS_MPa": round(rss[0][0], 3),
            "system": rss[0][1],
            "d_sigma_xz_MPa": round(float(dT[0, 2]), 3),
            "d_sigma_xz_axis_MPa": (round(float(((-s_f[m_axis].mean(axis=0) + s_c[m_axis].mean(axis=0)) / V_AT / 10.0)[4]), 3)
                                    if m_axis.sum() >= 20 else None),
            "n_axis": int(m_axis.sum()),
            "n_atoms": n,
        })

    clean = [r for r in rows if r["above_apex"]]
    peak = max(clean, key=lambda r: r["max_RSS_MPa"])
    far = [r for r in clean if r["r_A"] > 60]
    noise_rss = float(np.mean([r["max_RSS_MPa"] for r in far]))
    noise_sd = float(np.std([r["max_RSS_MPa"] for r in far]))
    straddle = [r for r in rows if not r["above_apex"]]

    # the two consistency properties the manuscript now asserts
    assert all(r["vm_of_difference_MPa"] >= 0 and r["max_RSS_MPa"] >= 0 for r in rows)
    viol = [r["r_A"] for r in rows if r["max_RSS_MPa"] < abs(r["d_sigma_xz_MPa"]) - 1e-6]
    assert not viol, "max RSS below |d_sigma_xz| at r = %s" % viol

    res = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "supersedes": ["stageG4_rss_profile.json", "stageG4_clean_sigma_profile.csv"],
        "cell": "Al matrix + Al13Fe4 ridge, unified cell of 91428 atoms (perturbation pair), CG minimisation only, "
                "no dislocations, no solutes",
        "atom_filter": "Al only (type 1); Fe excluded",
        "bin_A": BIN,
        "z_interface_A": Z_INTERFACE,
        "ridge_apex_A": RIDGE_APEX,
        "eigenstrain_used": EPS_INFLATED,
        "peak": peak,
        "apex_straddling_bins_excluded": straddle,
        "noise_floor_beyond_60A": {"mean_max_RSS_MPa": round(noise_rss, 3),
                                   "std_MPa": round(noise_sd, 3),
                                   "n_bins": len(far)},
        "peak_rescaled_to_real_magnetostriction_MPa": {
            k: round(peak["max_RSS_MPa"] * lam / EPS_INFLATED, 4)
            for k, lam in LAMBDA_REAL.items()},
        "sigma_char_2_mu_lambda_MPa": {
            k: round(2 * MU_AL * lam / 1e6, 3) for k, lam in LAMBDA_REAL.items()},
        "profile": rows,
    }
    if args.label:
        res["label"] = args.label
        res["inputs"] = {"control": args.control, "field": args.field}
    (Path(args.out) if args.out else REPORTS / "stageG10_field_profile.json").write_text(
        json.dumps(res, indent=2) + chr(10), encoding="utf-8")

    keys = ("r_A", "above_apex", "vm_control_MPa", "vm_field_MPa", "vm_of_difference_MPa",
            "diff_of_vm_MPa", "max_RSS_MPa", "system", "d_sigma_xz_MPa", "n_atoms")
    lines = [",".join(keys)] + [",".join(str(r[k]) for k in keys) for r in rows]
    (REPORTS / "stageG10_field_profile.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("%6s %4s %10s %10s %10s %10s %9s %8s %6s" %
          ("r", "apex", "vM_ctl", "vM_fld", "vM[dT]", "d[vM]", "maxRSS", "d_sxz", "N"))
    for r in rows:
        print("%6.1f %4s %10.2f %10.2f %10.3f %10.3f %9.3f %8.3f %6d" %
              (r["r_A"], "" if r["above_apex"] else "STR", r["vm_control_MPa"],
               r["vm_field_MPa"], r["vm_of_difference_MPa"], r["diff_of_vm_MPa"],
               r["max_RSS_MPa"], r["d_sigma_xz_MPa"], r["n_atoms"]))
    print()
    print("PEAK max-RSS = %.2f MPa at r = %.0f A on %s (d_sigma_xz there = %.2f)" %
          (peak["max_RSS_MPa"], peak["r_A"], peak["system"], peak["d_sigma_xz_MPa"]))
    print("noise floor beyond 60 A: %.2f +- %.2f MPa over %d bins" %
          (noise_rss, noise_sd, len(far)))
    print("rescaled:", res["peak_rescaled_to_real_magnetostriction_MPa"])
    print("sigma_char = 2 mu lambda:", res["sigma_char_2_mu_lambda_MPa"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
