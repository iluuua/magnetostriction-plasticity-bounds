#!/usr/bin/env python3
"""Prepare Stage G1 ridge + edge-dislocation-dipole geometry (control/physical pair).

Physics rationale (docs/run_plans/stageG_extended_plasticity_evidence_ideas_ru.md, G1):
- A uniform planar eigenstrain layer under p p f transfers almost no stress into the
  matrix (Stage F CPU result: Delta-sigma localized to the first ~4 A). A FINITE
  eigenstrained patch has edges, and the edges radiate a decaying shear field
  sigma_xz into Al. The ridge (half-elliptic cylinder along y) is the minimal
  edge-bearing geometry that matches the physicist's "cut ellipse top" sketch and
  keeps translational invariance along the dislocation line.
- Homogeneous dislocation nucleation in perfect Al needs ~GPa; 147 MPa cannot do it.
  But the Peierls stress of Al is ~1-10 MPa, so a PRE-EXISTING dislocation is a
  sensitive probe: the eigenstrain edge field visibly displaces it within ps-ns.
- Al slab is oriented x=[1-10], y=[11-2], z=[111] so a straight 1/2<110>{111} edge
  dislocation with line along y is periodic in y and glides in +-x on planes
  parallel to the interface. |b| = a/sqrt(2) equals the x lattice period, so the
  periodic-dipole construction is exact.
- The dipole (+b, -b) partners sit near the right ridge edge in the stable
  45-degree configuration; the control/physical difference in their x(t) is the
  headline observable.
- eps_z is applied by scaling Fe-block z about z=0 AFTER all cuts, so control and
  physical have IDENTICAL atom sets (clean Delta-Q subtraction).
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from prepare_stageF_boundary_patch_geometry import (  # noqa: E402
    CLEARANCE_A,
    MIN_HARD_A,
    MIN_WARN_A,
    dedup_pbc_boundary,
    pbc_seam_check,
    replicate_fe4al13_box,
    write_json,
)

AL_A = 4.05
PX = AL_A / math.sqrt(2.0)          # 2.863782  x period along [1-10] = |b|
PY = AL_A * math.sqrt(6.0) / 2.0    # 4.960075  y period along [11-2]
D111 = AL_A / math.sqrt(3.0)        # 2.338269  (111) interlayer spacing
NU = 0.347                          # Poisson ratio of Al (isotropic Volterra field)

# --- Geometry parameters (Stage G1 design) ---
# NX/NY chosen so the box is near-commensurate with BOTH lattices:
#   Lx = 65*2.863782 = 186.146 = 12*15.498*(1+0.09%)  (Fe a_x misfit +0.09%)
#   Ly = 18*4.960075 =  89.281 = 11*8.0814*(1+0.43%)  (Fe b_y misfit +0.43%)
NX = 65                             # Lx = 186.146 A
NY = 18                             # Ly =  89.281 A
N_AL_LAYERS = 120                   # Al depth = 280.59 A above the interface plane
Z_SUP = 20.0                        # Fe4Al13 support slab thickness; interface plane r=0
RIDGE_RX = 45.0                     # ridge half-width (x semi-axis)
RIDGE_H = 25.0                      # ridge protrusion height (z semi-axis)
VACUUM_TOP = 15.0
Z_BOT = -10.0                       # margin below the Fe support so minimize cannot lose atoms through zlo

# --- Dipole parameters ---
# Partners in the stable 45-degree configuration near the right ridge edge
# (edge at cx + RIDGE_RX). z values sit midway between (111) layers.
# Both glide planes MUST clear the ridge apex (Z_SUP + RIDGE_H = 45 A): the Volterra
# cut of each partner spans all x < x_partner on its plane, and slipping through
# Fe4Al13 (x-period 15.5 A, not b-invariant) would shred the intermetallic.
DIPOLE = {
    "burgers_A": PX,                # full 1/2<110> along +x
    "line_axis": "y",
    "glide_plane": "(111) parallel to interface",
    "partner_plus": {"x": 165.0, "z": Z_SUP + 12.5 * D111},   # z = 49.23, 4.2 A above ridge apex
    "partner_minus": {"x": 141.6, "z": Z_SUP + 22.5 * D111},  # z = 72.61, 45-degree stable offset
    "n_x_images": 3,
}

EPS_CASES = {"eps0000": 0.0, "eps00194": 0.00194}
OUT_ROOT = REPO_ROOT / "structures" / "stageG1_ridge_dipole"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def fcc111_al_block(lx: float, ly: float, z0: float, n_layers: int) -> np.ndarray:
    """Al fcc slab with x=[1-10], y=[11-2], z=[111]; ABC stacking via y-offset PY/3."""
    sites = []
    for k in range(n_layers):
        z = z0 + k * D111
        off_y = (k % 3) * PY / 3.0
        for i in range(NX):
            for j in range(NY):
                for sx, sy in ((0.0, 0.0), (PX / 2.0, PY / 2.0)):
                    sites.append((i * PX + sx, (j * PY + off_y + sy) % ly, z))
    pos = np.array(sites, dtype=float)
    pos[:, 0] %= lx
    return pos


def ridge_mask(pos: np.ndarray, cx: float, rx: float, h: float, dilate: float = 0.0) -> np.ndarray:
    """Half-elliptic cylinder along y protruding above Z_SUP."""
    val = ((pos[:, 0] - cx) / (rx + dilate)) ** 2 + ((pos[:, 2] - Z_SUP) / (h + dilate)) ** 2
    return (val <= 1.0) & (pos[:, 2] >= Z_SUP - 1.0e-9 - dilate)


def remove_close_matrix_atoms_pbc(
    al_pos: np.ndarray, fe_pos: np.ndarray, lx: float, ly: float
) -> tuple[np.ndarray, int, float, int, int]:
    """PBC-aware clearance filter: drop Al atoms within CLEARANCE_A of any Fe atom
    including its x/y periodic images (the Stage F helper is non-periodic and
    misses cross-species pairs straddling the seam)."""
    from scipy.spatial import cKDTree

    shifts = [(0.0, 0.0), (-lx, 0.0), (lx, 0.0), (0.0, -ly), (0.0, ly),
              (-lx, -ly), (-lx, ly), (lx, -ly), (lx, ly)]
    images = []
    for dx, dy in shifts:
        p = fe_pos.copy()
        p[:, 0] += dx
        p[:, 1] += dy
        images.append(p)
    tree = cKDTree(np.vstack(images))
    distances, _ = tree.query(al_pos, k=1)
    keep = distances >= CLEARANCE_A
    hard = int(np.count_nonzero(distances < MIN_HARD_A))
    warn = int(np.count_nonzero(distances < MIN_WARN_A))
    return al_pos[keep], int(np.count_nonzero(~keep)), float(distances.min()), hard, warn


def edge_dislocation_disp(dx: np.ndarray, dz: np.ndarray, b: float) -> tuple[np.ndarray, np.ndarray]:
    """Isotropic Volterra edge dislocation, b along +x, line along y (Hirth-Lothe)."""
    r2 = np.maximum(dx * dx + dz * dz, 1.0e-4)
    pre = b / (2.0 * math.pi)
    ux = pre * (np.arctan2(dz, dx) + dx * dz / (2.0 * (1.0 - NU) * r2))
    uz = -pre * ((1.0 - 2.0 * NU) / (4.0 * (1.0 - NU)) * np.log(r2)
                 + (dx * dx - dz * dz) / (4.0 * (1.0 - NU) * r2))
    return ux, uz


def dipole_displacement(pos: np.ndarray, lx: float) -> np.ndarray:
    b = DIPOLE["burgers_A"]
    disp = np.zeros((len(pos), 2))
    for sign, p in ((+1.0, DIPOLE["partner_plus"]), (-1.0, DIPOLE["partner_minus"])):
        for ix in range(-DIPOLE["n_x_images"], DIPOLE["n_x_images"] + 1):
            ux, uz = edge_dislocation_disp(pos[:, 0] - (p["x"] + ix * lx), pos[:, 2] - p["z"], sign * b)
            disp[:, 0] += ux
            disp[:, 1] += uz
    disp -= disp.mean(axis=0)
    return disp


def write_lammps_data(path: Path, pos: np.ndarray, types: np.ndarray, lx: float, ly: float, z_hi: float) -> None:
    lines = [
        f"# Stage G1 ridge+dipole {path.name} generated {now()}",
        "",
        f"{len(pos)} atoms",
        "2 atom types",
        "",
        f"0.0 {lx:.10f} xlo xhi",
        f"0.0 {ly:.10f} ylo yhi",
        f"{Z_BOT:.10f} {z_hi:.10f} zlo zhi",
        "",
        "Masses",
        "",
        "1 26.981539",
        "2 55.845",
        "",
        "Atoms # atomic",
        "",
    ]
    body = [f"{i + 1} {int(t)} {p[0]:.8f} {p[1]:.8f} {p[2]:.8f}" for i, (t, p) in enumerate(zip(types, pos))]
    path.write_text("\n".join(lines + body) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    args = parser.parse_args()

    lx, ly = NX * PX, NY * PY
    cx = lx / 2.0
    z_al_top = Z_SUP + N_AL_LAYERS * D111
    z_hi = z_al_top + VACUUM_TOP

    fe_symbols, fe_pos, misfit = replicate_fe4al13_box(
        lx, ly, 0.0, Z_SUP + RIDGE_H + 1.0, 0.0, commensurate=True
    )
    keep_fe = (fe_pos[:, 2] < Z_SUP) | ridge_mask(fe_pos, cx, RIDGE_RX, RIDGE_H)
    fe_symbols, fe_pos = fe_symbols[keep_fe], fe_pos[keep_fe]
    # The commensurate scaling leaves float-coincident duplicates on the x/y
    # periodic seam; fold and drop them exactly as the Stage F generator does.
    fe_types_tmp = np.where(fe_symbols == "Fe", 2, 1)
    fe_pos, fe_types_tmp, fe_symbols, fe_seam_dedup = dedup_pbc_boundary(
        fe_pos, fe_types_tmp, fe_symbols, lx, ly
    )

    al_pos = fcc111_al_block(lx, ly, Z_SUP, N_AL_LAYERS)
    al_pos = al_pos[~ridge_mask(al_pos, cx, RIDGE_RX, RIDGE_H, dilate=CLEARANCE_A)]
    al_pos, removed_al, min_cross, hard_cross, warn_cross = remove_close_matrix_atoms_pbc(
        al_pos, fe_pos, lx, ly
    )

    n_al, n_fe_block = len(al_pos), len(fe_pos)
    base = np.vstack([al_pos, fe_pos])
    types = np.concatenate([
        np.ones(n_al, dtype=int),
        np.where(fe_symbols == "Fe", 2, 1),
    ])
    fe_block = np.zeros(len(base), dtype=bool)
    fe_block[n_al:] = True

    disp = dipole_displacement(base, lx)

    results: dict[str, Any] = {}
    for label, eps in EPS_CASES.items():
        pos = base.copy()
        pos[fe_block, 2] *= 1.0 + eps
        pos[:, 0] += disp[:, 0]
        pos[:, 2] += disp[:, 1]
        pos[:, 0] %= lx
        pos[:, 1] %= ly

        case_id = f"G1_ridge_dipole_{label}"
        out_dir = args.out_root / case_id
        out_dir.mkdir(parents=True, exist_ok=True)
        data_file = out_dir / f"data.{case_id}"
        write_lammps_data(data_file, pos, types, lx, ly, z_hi)
        seam = pbc_seam_check(pos, lx, ly)
        overall_min = seam.get("overall_min_nn_A")
        if overall_min is not None and overall_min < MIN_HARD_A:
            raise RuntimeError(
                f"{case_id}: overall min nn {overall_min:.3f} A < hard limit {MIN_HARD_A} A - geometry rejected"
            )

        meta = {
            "case_id": case_id,
            "geometry_id": "G1_ridge_dipole",
            "geometry_type": "ridge_cylinder_plus_edge_dipole",
            "created_at": now(),
            "git_head_at_generation": git_head(),
            "al_orientation": {"x": "[1-10]", "y": "[11-2]", "z": "[111]"},
            "box_A": {"lx": lx, "ly": ly, "z_lo": Z_BOT, "z_hi": z_hi},
            "al_lattice_A": AL_A,
            "interface_plane_z_A": Z_SUP,
            "al_depth_A": N_AL_LAYERS * D111,
            "fe_support_A": Z_SUP,
            "ridge": {"center_x_A": cx, "rx_A": RIDGE_RX, "h_A": RIDGE_H,
                      "right_edge_x_A": cx + RIDGE_RX, "axis": "y"},
            "dipole": {**DIPOLE, "poisson_nu": NU,
                       "note": "isotropic Volterra field, x-periodic images summed"},
            "eigenstrain_axis": "Z",
            "eps_z": eps,
            "eps_application": "Fe-block z scaled about z=0 AFTER cuts; atom sets identical across cases",
            "counts": {"total": int(len(pos)), "al_matrix": int(n_al),
                       "fe_block_total": int(n_fe_block),
                       "fe_block_species_fe": int(np.count_nonzero(types[fe_block] == 2)),
                       "fe_block_species_al": int(np.count_nonzero((types == 1) & fe_block))},
            "cleanup": {"removed_al_near_fe": int(removed_al), "min_cross_A": min_cross,
                        "hard_cross_lt_1p8": int(hard_cross), "warn_cross_lt_2p1": int(warn_cross),
                        "fe_seam_dedup_removed": int(fe_seam_dedup)},
            "seam_check": seam,
            "commensurate_misfit": misfit,
            "boundary_conditions": "p p f",
            "data_file": str(data_file),
        }
        write_json(out_dir / f"{case_id}_metadata.json", meta)
        results[case_id] = {
            "atoms": int(len(pos)),
            "seam_min_nn_A": seam.get("overall_min_nn_A"),
            "data_file": str(data_file),
        }

    print(json.dumps({"status": "prepared", "cases": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
