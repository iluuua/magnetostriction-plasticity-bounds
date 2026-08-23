#!/usr/bin/env python3
"""Stage G4: sigma(r) decay from the Fe4Al13/Al interface - the figure the
supervisor asked for at the meeting.

For each case, average the per-atom virial stress of Al-matrix atoms in bins of
distance r above the interface plane (z = 20 A) and, separately, of distance
from the ridge surface. Reports von Mises and sigma_xz, the control/physical
difference, and the thickness of the layer where the stress exceeds the matrix
yield stress sigma_T = 120 MPa.

Frames are averaged over the last N dumps of the tau = 0 hold (no external
load) so the curve is the INCLUSION field alone, and separately over the last
N dumps of the run (with the 60 MPa rung applied).

Convention: sigma_ij = -sum(virial_ij)/(N*V_at)/10 -> MPa, V_at = 16.6072 A^3.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = ["G4_tilted_eps0000", "G4_tilted_eps00194"]
V_AT = 16.6072
Z_INTERFACE = 20.0
RIDGE_APEX = 40.0
SIGMA_YIELD = 120.0
BIN = 5.0
R_MAX = 200.0


def frame_stress(data) -> tuple[np.ndarray, np.ndarray]:
    pos = data.particles.positions[...]
    types = data.particles["Particle Type"][...]
    st = np.column_stack([data.particles[f"c_st[{i}]"][...] for i in range(1, 7)])
    return pos, np.column_stack([types, st])


def von_mises(s: np.ndarray) -> np.ndarray:
    xx, yy, zz, xy, xz, yz = (s[:, i] for i in range(6))
    return np.sqrt(0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2)
                   + 3.0 * (xy ** 2 + xz ** 2 + yz ** 2))


def profile(run_dir: Path, case: str, frames: list[int]) -> dict:
    from ovito.io import import_file
    pipe = import_file(str(run_dir / case / f"{case}.mobility.lammpstrj"))
    acc_vm, acc_n = None, None
    edges = np.arange(0.0, R_MAX + BIN, BIN)
    for fi in frames:
        d = pipe.compute(fi)
        pos = d.particles.positions[...]
        types = d.particles["Particle Type"][...]
        st = np.column_stack([d.particles[f"c_st[{i}]"][...] for i in range(1, 7)])
        matrix = (types != 2) & (pos[:, 2] > RIDGE_APEX + 2.0)
        r = pos[matrix, 2] - Z_INTERFACE
        # per-atom stress in MPa (each atom occupies V_AT)
        s = -st[matrix] / V_AT / 10.0
        idx = np.digitize(r, edges) - 1
        ok = (idx >= 0) & (idx < len(edges) - 1)
        n = np.bincount(idx[ok], minlength=len(edges) - 1)
        # Accumulate the six stress COMPONENTS, not the invariant: von Mises is
        # positive-definite, so averaging it per atom just measures the thermal
        # fluctuation amplitude (~6 GPa) instead of the mean field. The invariant
        # must be formed AFTER averaging the tensor.
        comp = np.zeros((len(edges) - 1, 6))
        for j in range(6):
            comp[:, j] = np.bincount(idx[ok], weights=s[ok, j], minlength=len(edges) - 1)
        acc_vm = comp if acc_vm is None else acc_vm + comp
        acc_n = n if acc_n is None else acc_n + n
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_tensor = acc_vm / np.maximum(acc_n, 1)[:, None]
        mean_tensor[acc_n == 0] = np.nan
        vm_mean = von_mises(mean_tensor)
        xz_mean = mean_tensor[:, 4]
    return {"r_lo": edges[:-1].tolist(), "r_hi": edges[1:].tolist(),
            "vm_MPa": vm_mean.tolist(), "sxz_MPa": xz_mean.tolist(),
            "n_atoms_per_bin": (acc_n / len(frames)).tolist()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "docs" / "reports")
    args = ap.parse_args()

    # frames 5-9 = last 5 ps of the tau=0 hold; frames 86-90 = last 5 ps at 60 MPa
    windows = {"no_load": list(range(5, 10)), "loaded_60MPa": list(range(86, 91))}
    res = {"run_dir": str(args.run_dir),
           "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "convention": "sigma = -virial/(V_at)/10 MPa, V_at = 16.6072 A^3; "
                         "r measured from the interface plane z = 20 A; Al matrix atoms only, "
                         "z > ridge apex + 2 A",
           "sigma_yield_MPa": SIGMA_YIELD, "windows": {}}

    for wname, frames in windows.items():
        prof = {c: profile(args.run_dir, c, frames) for c in CASES}
        r_lo = prof[CASES[0]]["r_lo"]
        vm_c = np.array(prof[CASES[0]]["vm_MPa"])
        vm_p = np.array(prof[CASES[1]]["vm_MPa"])
        xz_c = np.array(prof[CASES[0]]["sxz_MPa"])
        xz_p = np.array(prof[CASES[1]]["sxz_MPa"])
        d_vm, d_xz = vm_p - vm_c, xz_p - xz_c
        above = [r for r, v in zip(r_lo, vm_p) if np.isfinite(v) and v > SIGMA_YIELD]
        res["windows"][wname] = {
            "frames": frames,
            "r_lo_A": r_lo,
            "vm_control_MPa": vm_c.tolist(), "vm_physical_MPa": vm_p.tolist(),
            "delta_vm_MPa": d_vm.tolist(),
            "sxz_control_MPa": xz_c.tolist(), "sxz_physical_MPa": xz_p.tolist(),
            "delta_sxz_MPa": d_xz.tolist(),
            "layer_above_yield_physical_A": (max(above) + BIN) if above else 0.0,
            "max_abs_delta_vm_MPa": float(np.nanmax(np.abs(d_vm))),
            "delta_vm_first_bin_MPa": float(d_vm[0]),
            "delta_vm_beyond_50A_mean_MPa": float(np.nanmean(d_vm[10:])),
        }
        csv = args.out_dir / f"stageG4_sigma_profile_{wname}.csv"
        lines = ["r_lo_A,vm_control,vm_physical,delta_vm,sxz_control,sxz_physical,delta_sxz,n_atoms"]
        for i, r in enumerate(r_lo):
            lines.append("%.1f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.0f" % (
                r, vm_c[i], vm_p[i], d_vm[i], xz_c[i], xz_p[i], d_xz[i],
                prof[CASES[0]]["n_atoms_per_bin"][i]))
        csv.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        res["windows"][wname]["csv"] = str(csv)

    out = args.out_dir / "stageG4_sigma_profile_summary.json"
    out.write_text(json.dumps(res, indent=2) + chr(10), encoding="utf-8")
    for w, v in res["windows"].items():
        print(f"--- {w} ---")
        print("  layer above 120 MPa (physical): %.0f A" % v["layer_above_yield_physical_A"])
        print("  delta_vm first bin: %+.1f MPa | max |delta_vm|: %.1f MPa | beyond 50 A: %+.1f MPa"
              % (v["delta_vm_first_bin_MPa"], v["max_abs_delta_vm_MPa"],
                 v["delta_vm_beyond_50A_mean_MPa"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
