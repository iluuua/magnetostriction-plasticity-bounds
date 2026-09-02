#!/usr/bin/env python3
"""The two stress-versus-time programmes of the loaded cells, for the
loading-scheme figure of the paper: the smooth ramp 0-400 MPa over 96 ps of
the interface cell with the dislocation pair (lammps/stageG4_tilted_solute/
in.ramp, identical to stageG1) and the 45/55/65/75 MPa staircase of the alloy
cell (stageG3, 30 ps per step after 10 ps at zero stress)."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42
import matplotlib.pyplot as plt
import numpy as np

PAPER = Path(__file__).resolve().parents[2] / "docs" / "paper"
L = {"en": dict(x="time (ps)", y="applied shear stress (MPa)",
                a="(a) interface cell with the dislocation pair: ramp to 400 MPa",
                b="(b) alloy cell: constant-stress steps"),
     "ru": dict(x="время, пс", y="приложенное касательное напряжение, МПа",
                a="(а) ячейка границы с парой дислокаций: рост до 400 МПа",
                b="(б) ячейка сплава: ступени постоянного напряжения")}


def ramp(t_ps, taumax=400.0, pre=5.0, nramp=96.0, ts=16.0):
    sp = t_ps - pre
    rbar = taumax / (nramp - 0.5 * ts)
    out = np.where(sp < ts, rbar * (0.5 * sp - (ts / (2 * np.pi)) * np.sin(np.pi * sp / ts)),
                   rbar * (sp - 0.5 * ts))
    return np.where(sp < 0, 0.0, out)


def main():
    plt.rcParams["font.family"] = ["DejaVu Sans"]
    for lg, t in L.items():
        fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 2.6))
        tt = np.linspace(0, 101, 600)
        a.plot(tt, ramp(tt), color="#1f4e9c", lw=1.8)
        a.set_xlim(0, 101); a.set_ylim(0, 420)
        a.set_title(t["a"], fontsize=8.5)
        steps = [(0, 10, 0), (10, 40, 45), (40, 70, 55), (70, 100, 65), (100, 130, 75)]
        for t0, t1, tau in steps:
            b.plot([t0, t1], [tau, tau], color="#1f4e9c", lw=1.8)
        for (t0, t1, tau), (u0, u1, tau2) in zip(steps[:-1], steps[1:]):
            b.plot([t1, t1], [tau, tau2], color="#1f4e9c", lw=1.0, ls=":")
        b.set_xlim(0, 130); b.set_ylim(0, 90)
        b.set_title(t["b"], fontsize=8.5)
        for ax in (a, b):
            ax.set_xlabel(t["x"], fontsize=8.5); ax.set_ylabel(t["y"], fontsize=8.5)
            ax.tick_params(labelsize=8); ax.grid(alpha=0.3)
        fig.tight_layout()
        for ext in ("png", "pdf"):
            fig.savefig(PAPER / f"fig_loading_programme_{lg}.{ext}", dpi=150)
        plt.close(fig)
        print("fig_loading_programme_%s written" % lg)


if __name__ == "__main__":
    main()
