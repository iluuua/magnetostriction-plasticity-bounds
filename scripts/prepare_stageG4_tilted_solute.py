#!/usr/bin/env python3
"""Stage G4: the Pshonkin system, with every diagnosed defect fixed.

This IS the target model: Al matrix + Fe4Al13 inclusion + magnetostrictive
eigenstrain. It differs from G1/G2 by the three fixes the Stage G diagnosis
demanded (docs/reports/stageG_diagnosis_and_pivot_ru.md):

1. TILTED EIGENSTRAIN. G1/G2 applied eps* along z, whose resolved shear stress
   on the dipole glide plane is IDENTICALLY ZERO (Schmid factor 0.00000). Here
   eps* is applied along an axis tilted 45 deg from z toward x, giving
   RSS = 0.5*sigma - the maximum possible. Physically this is the favourably
   oriented inclusion: in a polycrystal inclusions are randomly oriented with
   respect to the matrix slip systems, and the ones that carry the effect are
   exactly those whose magnetostriction axis is inclined to a slip plane. The
   tilt is IDENTICAL in control and physical, so it cancels in Delta-Q.

2. SOLUTE AMPLIFIER. Mg/Si substitutional solutes (6xxx-like) give thermally
   activated depinning, whose response to a small stress change is exponential,
   exp(V* dtau/kT), instead of the linear athermal response of pure Al.

3. CONSTANT-STRESS STAIRCASE instead of a ramp: five velocity measurements per
   run rather than one threshold.

Cell is sized for time-to-result: ~70k atoms, ~10 h per 130 ps run.
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

import prepare_stageG1_ridge_dipole as g1  # noqa: E402
from prepare_stageG1_ridge_dipole import (  # noqa: E402
    CLEARANCE_A, D111, MIN_HARD_A, NU, PX, PY, dedup_pbc_boundary,
    dipole_displacement, fcc111_al_block, pbc_seam_check,
    remove_close_matrix_atoms_pbc, replicate_fe4al13_box, write_json,
)

# COMMENSURATE cell: Fe4Al13 in-plane periods are a_x = 15.498, b_y = 8.0814 A.
# NX = 38 -> Lx = 108.82 A = 7 Fe cells (+0.31% misfit); NY = 13 -> Ly = 64.48 A
# = 8 Fe cells (-0.26%). The previous 40x8 cell carried +5.59%/-1.79% misfit,
# i.e. a lattice-mismatch stress 29x LARGER than the magnetostrictive signal -
# it buried the effect under a ~600 MPa background.
NX, NY = 38, 13                  # Lx = 108.82 A, Ly = 64.48 A
Z_SUP = 20.0                     # Fe4Al13 support slab; interface plane
RIDGE_RX, RIDGE_H = 35.0, 20.0   # ridge apex at z = 40 A
AL_LAYERS = 60                   # Al up to z = 160.3 A
VACUUM_TOP, Z_BOT = 15.0, -10.0
# The dipole is only a reaction partner; its passing stress must be SMALL compared
# with the solute strength (~38 MPa for 1.1 at% Mg + 0.7 at% Si) so that what the
# probe dislocation fights is the solutes, not its own partner.
# h = 80 layers = 187.1 A -> tau_pass = 25 MPa, still far below the ~38 MPa
# solute strength. (100 layers put the upper partner at z = 287.7 A, i.e. 0.3 A
# under the driven slab at z > 288 - it would have been dragged by the loading
# fix instead of gliding freely.)
DIPOLE_DZ_LAYERS = 30
TILT_DEG = 45.0                  # eigenstrain axis tilt from z toward x
MG_AT_PCT, SI_AT_PCT = 1.0, 0.6
SOLUTE_SEED = 12345
MASSES = {1: 26.981539, 2: 55.845, 3: 24.305, 4: 28.0855}   # Al, Fe, Mg, Si
EPS_CASES = {"eps0000": 0.0, "eps00194": 0.00194}
OUT_ROOT = REPO_ROOT / "structures" / "stageG4_tilted_solute"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def tau_pass_mpa(h_A: float) -> float:
    return 26.5e9 * PX * 1e-10 / (8 * math.pi * (1 - NU) * h_A * 1e-10) / 1e6


def write_data(path: Path, pos, types, lx, ly, z_lo, z_hi) -> None:
    lines = [f"# Stage G4 tilted-eigenstrain + solutes {path.name} {now()}", "",
             f"{len(pos)} atoms", "4 atom types", "",
             f"0.0 {lx:.10f} xlo xhi", f"0.0 {ly:.10f} ylo yhi",
             f"{z_lo:.10f} {z_hi:.10f} zlo zhi", "", "Masses", ""]
    for t, m in MASSES.items():
        lines.append(f"{t} {m}")
    lines += ["", "Atoms # atomic", ""]
    body = [f"{i+1} {int(t)} {p[0]:.8f} {p[1]:.8f} {p[2]:.8f}"
            for i, (t, p) in enumerate(zip(types, pos))]
    path.write_text(chr(10).join(lines + body) + chr(10), encoding="utf-8")


def main() -> int:
    global AL_LAYERS
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=Path, default=OUT_ROOT)
    ap.add_argument("--no-dipole", action="store_true",
                    help="omit the dislocation dipole (clean sigma(r) measurement)")
    ap.add_argument("--no-solutes", action="store_true",
                    help="omit Mg/Si solutes (they add their own misfit stress)")
    ap.add_argument("--tag", default="", help="suffix for case names")
    ap.add_argument("--al-layers", type=int, default=60,
                    help="Al (111) layers above the interface; 60 -> 66.7k atoms, "
                         "94 -> ~100k atoms with the same commensurate footprint")
    args = ap.parse_args()
    AL_LAYERS = args.al_layers

    g1.NX, g1.NY = NX, NY
    lx, ly = NX * PX, NY * PY
    cx = lx / 2.0
    z_al_top = Z_SUP + AL_LAYERS * D111
    z_hi = z_al_top + VACUUM_TOP

    # --- Fe4Al13 support + ridge -------------------------------------------
    # fold_pbc: the monoclinic tilt of Al13Fe4 otherwise leaves the support slab
    # missing for x < 15 A - see replicate_fe4al13_box for the mechanism
    fe_symbols, fe_pos, misfit = replicate_fe4al13_box(
        lx, ly, 0.0, Z_SUP + RIDGE_H + 1.0, 0.0, commensurate=True, fold_pbc=True)
    keep = (fe_pos[:, 2] < Z_SUP) | g1.ridge_mask(fe_pos, cx, RIDGE_RX, RIDGE_H)
    fe_symbols, fe_pos = fe_symbols[keep], fe_pos[keep]
    fe_types_tmp = np.where(fe_symbols == "Fe", 2, 1)
    fe_pos, fe_types_tmp, fe_symbols, fe_dedup = dedup_pbc_boundary(
        fe_pos, fe_types_tmp, fe_symbols, lx, ly)

    # --- Al matrix ----------------------------------------------------------
    al_pos = fcc111_al_block(lx, ly, Z_SUP, AL_LAYERS)
    al_pos = al_pos[~g1.ridge_mask(al_pos, cx, RIDGE_RX, RIDGE_H, dilate=CLEARANCE_A)]
    al_pos, removed_al, min_cross, hard_cross, warn_cross = remove_close_matrix_atoms_pbc(
        al_pos, fe_pos, lx, ly)

    n_al = len(al_pos)
    base = np.vstack([al_pos, fe_pos])
    types0 = np.concatenate([np.ones(n_al, dtype=int), fe_types_tmp])
    fe_block = np.zeros(len(base), dtype=bool)
    fe_block[n_al:] = True

    # --- dipole, glide planes above the ridge apex --------------------------
    h = DIPOLE_DZ_LAYERS * D111
    # Al layers are at z = Z_SUP + k*D111, so a glide plane must sit at HALF-integer
    # k to pass between layers; k = 14.5 also clears the ridge apex (z = 40 A).
    z_lo_plane = Z_SUP + 14.5 * D111                 # z = 53.9 A
    g1.DIPOLE = {
        "burgers_A": PX, "line_axis": "y", "glide_plane": "(111) parallel to interface",
        # Dipole interaction stress vs horizontal offset d:
        #   tau_int(d) = mu*b/(2 pi (1-nu)) * d(d^2-h^2)/(d^2+h^2)^2
        # -> d = 0 is the STABLE equilibrium (the classic dipole wall), the barrier
        # peaks at d = h/sqrt(3) with tau_pass = mu*b/(8 pi (1-nu) h), and d = h is
        # an UNSTABLE equilibrium where the force is exactly zero. Probe run
        # 2026-08-22 started at d = h and the lower line ran away at 66 MPa; both
        # partners now start stacked (d = 0) so that sub-tau_pass loading holds them
        # in the well and escape is a thermally activated event.
        # The lower (+b) line sits 12 A right of the ridge shoulder - in the
        # inclusion field, which is the probe; both stay >24 A from the x seam.
        "partner_plus":  {"x": cx + RIDGE_RX + 12.0, "z": z_lo_plane},
        "partner_minus": {"x": cx + RIDGE_RX + 12.0, "z": z_lo_plane + h},
        "n_x_images": 3,
    }
    disp = (np.zeros((len(base), 2)) if args.no_dipole
            else dipole_displacement(base, lx))

    # --- solutes: same sites in BOTH cases (identical atom sets) ------------
    rng = np.random.default_rng(SOLUTE_SEED)
    matrix_idx = np.where((~fe_block) & (base[:, 2] > Z_SUP + 6.0) & (base[:, 2] < z_al_top - 8.0))[0]
    n_mg = int(round(n_al * MG_AT_PCT / 100.0))
    n_si = int(round(n_al * SI_AT_PCT / 100.0))
    types = types0.copy()
    if not args.no_solutes:
        pick = rng.choice(matrix_idx, size=n_mg + n_si, replace=False)
        types[pick[:n_mg]] = 3
        types[pick[n_mg:]] = 4

    # --- tilted, VOLUME-CONSERVING magnetostrictive eigenstrain ------------
    # Magnetostriction strains the crystal along the magnetization without
    # changing its volume: eps* = lambda*(3/2 u(x)u - 1/2 I), trace = 0.
    # The old form eps*u(x)u had trace = lambda (a spurious 0.194% dilatation)
    # and a deviator 1.5x too small - and only the deviator drives glide.
    t = math.radians(TILT_DEG)
    u = np.array([math.sin(t), 0.0, math.cos(t)])
    E_TENSOR = 1.5 * np.outer(u, u) - 0.5 * np.eye(3)

    results = {}
    for label, eps in EPS_CASES.items():
        pos = base.copy()
        if eps != 0.0:
            # applied about the Fe-block centroid, not the box origin
            centroid = pos[fe_block].mean(axis=0)
            r = pos[fe_block] - centroid
            pos[fe_block] += eps * (r @ E_TENSOR)
        pos[:, 0] += disp[:, 0]
        pos[:, 2] += disp[:, 1]
        pos[:, 0] %= lx
        pos[:, 1] %= ly

        case = f"G4_tilted_{label}{args.tag}"
        out_dir = args.out_root / case
        out_dir.mkdir(parents=True, exist_ok=True)
        data_file = out_dir / f"{case}.start.data"
        write_data(data_file, pos, types, lx, ly, Z_BOT, z_hi)
        seam = pbc_seam_check(pos, lx, ly)
        if seam.get("overall_min_nn_A", 9) < MIN_HARD_A:
            from scipy.spatial import cKDTree
            dd, ii = cKDTree(pos).query(pos, k=2)
            w = int(np.argmin(dd[:, 1]))
            raise RuntimeError(
                f"{case}: min nn {seam['overall_min_nn_A']:.2f} A too small; worst pair at "
                f"{np.round(pos[w], 1)} (type {types[w]}) and {np.round(pos[ii[w, 1]], 1)} "
                f"(type {types[ii[w, 1]]})")
        meta = {
            "case_id": case, "created_at": now(), "git_head_at_generation": git_head(),
            "model": "Al matrix + Fe4Al13 ridge inclusion + Mg/Si solutes",
            "orientation": {"x": "[1-10]", "y": "[11-2]", "z": "[111]"},
            "box_A": {"lx": lx, "ly": ly, "z_lo": Z_BOT, "z_hi": z_hi},
            "interface_plane_z_A": Z_SUP, "al_depth_A": AL_LAYERS * D111,
            "ridge": {"rx_A": RIDGE_RX, "h_A": RIDGE_H, "center_x_A": cx,
                      "apex_z_A": Z_SUP + RIDGE_H, "right_edge_x_A": cx + RIDGE_RX},
            "eigenstrain": {"eps": eps, "tilt_deg_from_z_toward_x": TILT_DEG,
                            "axis_unit_vector": list(u),
                            "tensor": "lambda*(1.5 u(x)u - 0.5 I), trace = 0 (volume conserving)",
                            "tensor_matrix": [list(row) for row in (eps * E_TENSOR)],
                            "schmid_on_dipole_plane": 0.5,
                            "note": "a z-axis eigenstrain would give Schmid 0.00000"},
            "solutes": {"Mg_at_pct": MG_AT_PCT, "Si_at_pct": SI_AT_PCT, "seed": SOLUTE_SEED,
                        "n_Mg": int((types == 3).sum()), "n_Si": int((types == 4).sum())},
            "dipole": {**g1.DIPOLE, "separation_z_A": h, "tau_pass_MPa": tau_pass_mpa(h)},
            "counts": {"total": int(len(pos)), "al_matrix": int(n_al),
                       "fe_block": int(fe_block.sum()),
                       "type_Al": int((types == 1).sum()), "type_Fe": int((types == 2).sum()),
                       "type_Mg": int((types == 3).sum()), "type_Si": int((types == 4).sum())},
            "cleanup": {"removed_al_near_fe": int(removed_al), "min_cross_A": min_cross,
                        "fe_seam_dedup": int(fe_dedup)},
            "seam_check": seam, "commensurate_misfit": misfit,
            "boundary_conditions": "p p f", "data_file": str(data_file),
        }
        write_json(out_dir / f"{case}_metadata.json", meta)
        results[case] = {"atoms": int(len(pos)), "min_nn_A": round(seam["overall_min_nn_A"], 2),
                         "tau_pass_MPa": round(tau_pass_mpa(h), 1),
                         "Fe_atoms": int((types == 2).sum()),
                         "Mg_Si": [int((types == 3).sum()), int((types == 4).sum())]}
    print(json.dumps({"status": "prepared", "lx": round(lx, 2), "ly": round(ly, 2),
                      "lz": round(z_hi - Z_BOT, 2), "tilt_deg": TILT_DEG,
                      "cases": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
