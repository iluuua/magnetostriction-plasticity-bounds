#!/usr/bin/env python3
"""Stage G9: the figures the external review asked for.

Fig. 2  dislocation trajectories under the constant-stress staircase, with the
        rung boundaries marked, so the pinning event is visible rather than
        asserted;
Fig. 3  the field-induced resolved shear stress profile RSS(r) together with the
        3D Eshelby exterior field, on one axis, against the thresholds at which
        dislocations actually respond.
"""
from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "docs" / "reports"
PAPER = REPO / "docs" / "paper"
PRE, HOLD = 10000, 30000
RUNGS = [45, 55, 65, 75]


def load_frames(tag: str):
    p = REPORTS / f"stageG6_vstar_{tag}_frames.csv"
    if not p.exists():
        return None
    rows = list(csv.DictReader(io.open(p, encoding="utf-8")))
    t, lo, up = [], [], []
    for r in rows:
        if not r.get("ux_lo") or not r.get("ux_up"):
            continue
        t.append(float(r["step"]) * 1e-3)
        lo.append(float(r["ux_lo"]))
        up.append(float(r["ux_up"]))
    return np.array(t), np.array(lo), np.array(up)


def fig_trajectories() -> None:
    d = load_frames("relA")
    if d is None:
        print("no relA frames")
        return
    t, lo, up = d
    lo = lo - lo[0]
    up = up - up[0]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.plot(t, lo, "o-", ms=3, lw=1.4, color="#b23b3b", label="probe line (lower plane)")
    ax.plot(t, up, "s-", ms=3, lw=1.4, color="#3b6db3", label="reaction partner (upper plane)")
    for k, tau in enumerate(RUNGS):
        x0 = (PRE + k * HOLD) * 1e-3
        ax.axvline(x0, color="gray", ls=":", lw=0.9)
        ax.text(x0 + 1.5, ax.get_ylim()[1] * 0.92 if k == 0 else 0,
                "", fontsize=8)
    ymin, ymax = ax.get_ylim()
    for k, tau in enumerate(RUNGS):
        x0 = (PRE + k * HOLD) * 1e-3
        ax.text(x0 + 13, ymax * 0.90, f"{tau} MPa", ha="center", fontsize=9, color="gray")
    ax.axvline(PRE * 1e-3, color="k", lw=0.9)
    ax.text(PRE * 1e-3 / 2, ymax * 0.90, "no load", ha="center", fontsize=9, color="gray")
    ax.set_xlabel("time (ps)")
    ax.set_ylabel("displacement along glide direction (Å)")
    ax.set_title("Dislocation trajectories in Al–Mg–Si under a constant-stress staircase")
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PAPER / "fig_trajectories.png", dpi=150)
    print("fig_trajectories.png written")


def fig_rss() -> None:
    prof = json.loads(io.open(REPORTS / "stageG4_rss_profile.json", encoding="utf-8").read())
    r = np.array([p["r_A"] for p in prof["profile"]])
    rss = np.array([p["max_RSS_MPa"] for p in prof["profile"]])
    esh = json.loads(io.open(REPORTS / "stageG8_eshelby3d.json", encoding="utf-8").read())
    a_ridge = 35.0
    er = np.array([d["r_over_a"] * a_ridge for d in esh["exterior_decay_sphere"]])
    ev = np.array([d["max_RSS_MPa"] for d in esh["exterior_decay_sphere"]])

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.semilogy(r, np.maximum(rss, 1e-3), "o-", ms=4, color="#3b8b52",
                label="MD, ridge cell (ε* = 1.94·10⁻³)")
    ax.semilogy(er, ev, "s--", ms=5, color="#8b3b8b",
                label="3D Eshelby sphere, same ε*")
    scale = 4e-5 / 1.94e-3
    ax.semilogy(r, np.maximum(rss * scale, 1e-4), "o:", ms=3, color="#3b8b52", alpha=0.55,
                label="MD, rescaled to λ$_s$ = 40 ppm")
    for y, lbl, col in ((65, "solute pinning 65 MPa", "#444444"),
                        (86, "dipole motion 77–86 MPa", "#777777"),
                        (195, "interface nucleation 195 MPa", "#aa2222")):
        ax.axhline(y, ls="--", lw=1.1, color=col)
        ax.text(21, y * 1.16, lbl, fontsize=8, color=col, ha="left")
    ax.set_xlabel("distance from the interface r (Å)")
    ax.set_ylabel("field-induced max RSS (MPa)")
    ax.set_ylim(1e-3, 400)
    ax.set_xlim(20, 92)
    ax.set_title("Field-induced driving stress against the thresholds it must overcome")
    ax.legend(fontsize=8.5, loc="lower left")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(PAPER / "fig_rss_vs_thresholds.png", dpi=150)
    print("fig_rss_vs_thresholds.png written")


if __name__ == "__main__":
    fig_trajectories()
    fig_rss()
