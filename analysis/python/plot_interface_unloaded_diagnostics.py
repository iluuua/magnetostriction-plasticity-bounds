#!/usr/bin/env python3
"""Plot unloaded interface stress and strain profiles."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_rows(path: Path) -> list[dict[str, float]]:
    with path.open() as handle:
        rows = []
        for row in csv.DictReader(handle):
            rows.append({key: float(value) for key, value in row.items() if value != ""})
        return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stress-csv",
        type=Path,
        default=ROOT / "results/tables/interface_trial_001_unloaded_stress_profile.csv",
    )
    parser.add_argument(
        "--strain-csv",
        type=Path,
        default=ROOT / "results/tables/interface_trial_001_unloaded_strain_profile.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "lammps/02_interface_relax/trial_001/interface_unloaded_diagnostics_summary.json",
    )
    parser.add_argument(
        "--stress-png",
        type=Path,
        default=ROOT / "results/figures/interface_trial_001_unloaded_stress_profile.png",
    )
    parser.add_argument(
        "--strain-png",
        type=Path,
        default=ROOT / "results/figures/interface_trial_001_unloaded_strain_profile.png",
    )
    args = parser.parse_args()

    import matplotlib.pyplot as plt

    stress_rows = read_rows(args.stress_csv)
    strain_rows = read_rows(args.strain_csv)
    summary = json.loads(args.summary.read_text())
    interface_z = float(summary["interface_z_A"])

    args.stress_png.parent.mkdir(parents=True, exist_ok=True)
    z = [row["z_center_A"] for row in stress_rows]
    fig, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(z, [row["hydrostatic_GPa"] for row in stress_rows], marker="o", label="hydrostatic")
    axis.plot(z, [row["sigma_zz_GPa"] for row in stress_rows], marker="s", label="sigma_zz")
    axis.axvline(interface_z, color="black", linestyle="--", linewidth=1, label="interface")
    axis.set_xlabel("z, A")
    axis.set_ylabel("Stress proxy, GPa")
    axis.set_title("Unloaded trial_001 local virial stress profile")
    axis.grid(True, alpha=0.3)
    axis.legend()
    fig.tight_layout()
    fig.savefig(args.stress_png, dpi=180)
    plt.close(fig)

    z = [row["z_center_A"] for row in strain_rows]
    fig, axis1 = plt.subplots(figsize=(8, 4.5))
    axis1.plot(z, [row["mean_von_mises_strain_proxy"] for row in strain_rows], marker="o", color="tab:blue", label="VM strain proxy")
    axis1.set_xlabel("z, A")
    axis1.set_ylabel("VM strain proxy", color="tab:blue")
    axis1.tick_params(axis="y", labelcolor="tab:blue")
    axis1.grid(True, alpha=0.3)
    axis2 = axis1.twinx()
    axis2.plot(z, [row["mean_displacement_A"] for row in strain_rows], marker="s", color="tab:red", label="mean displacement")
    axis2.set_ylabel("Mean displacement, A", color="tab:red")
    axis2.tick_params(axis="y", labelcolor="tab:red")
    axis1.axvline(interface_z, color="black", linestyle="--", linewidth=1)
    axis1.set_title("Unloaded trial_001 local strain/displacement proxies")
    fig.tight_layout()
    fig.savefig(args.strain_png, dpi=180)
    plt.close(fig)

    print(f"stress plot: {args.stress_png}")
    print(f"strain plot: {args.strain_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
