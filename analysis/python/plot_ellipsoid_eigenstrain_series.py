#!/usr/bin/env python3

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]

CSV = ROOT / "results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_summary.csv"
OUT_DIR = ROOT / "results/figures/ellipsoid_inclusion"
OUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(CSV)

def save_plot(y, ylabel, title, filename):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(df["eps_z"], df[y], marker="o")
    ax.set_xlabel("eps_z")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out = OUT_DIR / filename
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"Saved: {out}")

save_plot(
    "energy_final_eV",
    "Final potential energy, eV",
    "Ellipsoid inclusion eigenstrain: final energy",
    "ellipsoid_trial_001_eigenstrain_energy_final.png",
)

save_plot(
    "minimized_min_pair_A",
    "Minimum pair distance after minimization, Å",
    "Ellipsoid inclusion eigenstrain: minimum pair distance",
    "ellipsoid_trial_001_eigenstrain_min_pair_distance.png",
)

save_plot(
    "minimized_Al_Fe_below_2p1",
    "Al-Fe warning pairs below 2.1 Å",
    "Ellipsoid inclusion eigenstrain: Al-Fe warning contacts",
    "ellipsoid_trial_001_eigenstrain_alfe_warning_pairs.png",
)

save_plot(
    "force_two_norm_final",
    "Final force two-norm",
    "Ellipsoid inclusion eigenstrain: final force norm",
    "ellipsoid_trial_001_eigenstrain_force_two_norm_final.png",
)
