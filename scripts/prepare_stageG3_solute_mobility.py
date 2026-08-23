#!/usr/bin/env python3
"""Stage G3: solute-pinned dislocation mobility cell (no inclusion).

Why this cell exists (docs/reports/stageG_diagnosis_and_pivot_ru.md):
the Stage G lineage failed not for lack of stress but for lack of an AMPLIFIER.
In pure Al the Peierls stress is 1-10 MPa, glide is athermal, and a small stress
perturbation shifts a threshold LINEARLY (~10%, at the noise floor). In the real
Al-Mg-Si alloy the rate-limiting step is thermally activated escape from solute
pinning, where the response is EXPONENTIAL, exp(V* dtau / kT). This cell measures
the activation volume V* that sets that exponent.

Design:
- pure fcc Al slab, x=[1-10] (b and glide direction), y=[11-2] (line), z=[111];
- ONE edge-dislocation dipole, partners 24 (111) layers apart (h = 56.1 A) so the
  dipole passing stress mu*b/(8*pi*(1-nu)*h) = 82 MPa sits below the applied
  steps: above it the partners separate and their relative velocity is the
  observable, and tau_eff = tau_app - tau_int(s) sweeps a RANGE of effective
  stresses within a single run;
- substitutional Mg/Si solutes at 6xxx-like concentrations, a different random
  realization per replica (independent solute fields, not velocity seeds);
- ~45k atoms => ~6 h per 130 ps run on the RTX 3060 (vs 31 h for Stage G2).

Cases: pure Al (control: shows the athermal, un-amplified response) and two
independent Al-Mg-Si realizations.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from prepare_stageG1_ridge_dipole import (  # noqa: E402
    D111, NU, PX, PY, dipole_displacement, fcc111_al_block, write_json,
)

AL_A = 4.05
NX, NY = 40, 10                 # Lx = 114.55 A, Ly = 49.60 A
N_LAYERS = 116                  # Lz = 271.2 A (tall: room for h = 88 layers)
Z_BOT_FIXED = 8.0               # bottom rigid slab (frozen)
Z_TOP_GRAB = 12.0               # top slab thickness used to apply the shear
# h = 88 layers = 205.8 A -> tau_pass = 22 MPa, well below the ~38 MPa solute
# strength: above ~40 MPa applied the partners separate and each glides
# steadily against solute friction - the v(tau) regime that yields V*.
DIPOLE_DZ_LAYERS = 88
MASSES = {1: 26.981539, 2: 24.305, 3: 28.0855}   # Al, Mg, Si
CASES = {
    "G3_pureAl":      {"mg_at_pct": 0.0, "si_at_pct": 0.0, "solute_seed": None},
    "G3_solute_relA": {"mg_at_pct": 1.0, "si_at_pct": 0.6, "solute_seed": 12345},
    "G3_solute_relB": {"mg_at_pct": 1.0, "si_at_pct": 0.6, "solute_seed": 67890},
}
OUT_ROOT = REPO_ROOT / "structures" / "stageG3_solute_mobility"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def tau_pass_mpa(h_A: float) -> float:
    mu, b, = 26.5e9, PX * 1e-10
    return mu * b / (8 * math.pi * (1 - NU) * h_A * 1e-10) / 1e6


def write_data(path: Path, pos, types, lx, ly, z_lo, z_hi) -> None:
    lines = [f"# Stage G3 solute mobility cell {path.name} generated {now()}", "",
             f"{len(pos)} atoms", "3 atom types", "",
             f"0.0 {lx:.10f} xlo xhi", f"0.0 {ly:.10f} ylo yhi",
             f"{z_lo:.10f} {z_hi:.10f} zlo zhi", "", "Masses", ""]
    for t, m in MASSES.items():
        lines.append(f"{t} {m}")
    lines += ["", "Atoms # atomic", ""]
    body = [f"{i+1} {int(t)} {p[0]:.8f} {p[1]:.8f} {p[2]:.8f}"
            for i, (t, p) in enumerate(zip(types, pos))]
    path.write_text(chr(10).join(lines + body) + chr(10), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=Path, default=OUT_ROOT)
    args = ap.parse_args()

    lx, ly = NX * PX, NY * PY
    z0 = 0.0
    z_top = z0 + N_LAYERS * D111
    z_lo, z_hi = -8.0, z_top + 12.0

    # fcc111_al_block reads NX/NY from its defining module's globals, so set them
    # to this cell's dimensions before calling it (otherwise atoms fold onto each
    # other when wrapped into the smaller box).
    import prepare_stageG1_ridge_dipole as g1
    g1.NX, g1.NY = NX, NY
    base = fcc111_al_block(lx, ly, z0, N_LAYERS)

    # dipole: partners centred in z, DIPOLE_DZ_LAYERS apart, offset in x by ~h
    h = DIPOLE_DZ_LAYERS * D111
    z_mid = z0 + (N_LAYERS / 2) * D111
    g1.DIPOLE = {
        "burgers_A": PX, "line_axis": "y", "glide_plane": "(111)",
        # STACKED partners (same x) = the stable dipole-wall equilibrium; glide
        # planes at half-integer layer indices (between atomic layers). Probe
        # plane z = 29.2 A clears the frozen bottom (8 A); partner plane
        # z = 235.0 A clears the driven slab (z > 259 A) by 24 A.
        "partner_plus":  {"x": lx * 0.5, "z": 12.5 * D111},
        "partner_minus": {"x": lx * 0.5, "z": 100.5 * D111},
        "n_x_images": 3,
    }
    disp = dipole_displacement(base, lx)
    pos = base.copy()
    pos[:, 0] += disp[:, 0]
    pos[:, 2] += disp[:, 1]
    pos[:, 0] %= lx
    pos[:, 1] %= ly

    results = {}
    for case, cfg in CASES.items():
        types = np.ones(len(pos), dtype=int)
        counts = {"Al": len(pos), "Mg": 0, "Si": 0}
        if cfg["solute_seed"] is not None:
            rng = np.random.default_rng(cfg["solute_seed"])
            # solutes only in the mobile interior: keep rigid slabs pure so the
            # boundary conditions are identical across cases
            interior = np.where((pos[:, 2] > Z_BOT_FIXED + 4.0) & (pos[:, 2] < z_top - Z_TOP_GRAB - 4.0))[0]
            n_mg = int(round(len(pos) * cfg["mg_at_pct"] / 100.0))
            n_si = int(round(len(pos) * cfg["si_at_pct"] / 100.0))
            pick = rng.choice(interior, size=n_mg + n_si, replace=False)
            types[pick[:n_mg]] = 2
            types[pick[n_mg:]] = 3
            counts = {"Al": int((types == 1).sum()), "Mg": int((types == 2).sum()),
                      "Si": int((types == 3).sum())}
        out_dir = args.out_root / case
        out_dir.mkdir(parents=True, exist_ok=True)
        data_file = out_dir / f"{case}.start.data"
        write_data(data_file, pos, types, lx, ly, z_lo, z_hi)
        meta = {
            "case_id": case, "created_at": now(), "git_head_at_generation": git_head(),
            "orientation": {"x": "[1-10]", "y": "[11-2]", "z": "[111]"},
            "box_A": {"lx": lx, "ly": ly, "z_lo": z_lo, "z_hi": z_hi},
            "n_layers": N_LAYERS, "atoms": int(len(pos)), "counts": counts,
            "solute_at_pct": {"Mg": cfg["mg_at_pct"], "Si": cfg["si_at_pct"]},
            "solute_seed": cfg["solute_seed"],
            "dipole": {**g1.DIPOLE, "separation_z_A": h,
                       "tau_pass_MPa": tau_pass_mpa(h), "poisson_nu": NU},
            "rigid_slabs_A": {"bottom_fixed": Z_BOT_FIXED, "top_grab": Z_TOP_GRAB},
            "boundary_conditions": "p p f",
            "data_file": str(data_file),
        }
        write_json(out_dir / f"{case}_metadata.json", meta)
        results[case] = {"atoms": int(len(pos)), "counts": counts,
                         "tau_pass_MPa": round(tau_pass_mpa(h), 1)}
    print(json.dumps({"status": "prepared", "lx": round(lx, 2), "ly": round(ly, 2),
                      "lz": round(z_hi - z_lo, 2), "cases": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
