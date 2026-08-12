#!/usr/bin/env python3
"""Prepare Stage F boundary-patch geometry metadata and optional data files.

This helper does not launch LAMMPS. It creates local Fe4Al13/Al patch geometry
for smoke-first Stage F runs and writes metadata compatible with
analysis/python/stageF_boundary_stress_decay.py.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = REPO_ROOT / "analysis" / "python"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from stage_runner import builder, paths  # noqa: E402


AL_A = builder.AL_A
CLEARANCE_A = 2.2
MIN_HARD_A = 1.8
MIN_WARN_A = 2.1
OUT_ROOT = REPO_ROOT / "structures" / "stageF_boundary_patch"


@dataclass(frozen=True)
class GeometrySpec:
    geometry_id: str
    geometry_type: str
    box_x_A: float
    box_y_A: float
    al_depth_A: float
    fe_depth_A: float
    total_z_A: float
    cap_radius_x_A: float | None = None
    cap_radius_y_A: float | None = None
    cap_height_A: float | None = None
    # When True the box is a lateral-commensurate periodic supercell (p p f): box_x/box_y are
    # exact multiples of the Al fcc constant, and the Fe4Al13 inclusion is given a small in-plane
    # misfit strain so an integer number of its cells tiles the same box -> clean periodic seam.
    commensurate_ppf: bool = False


# Lateral-commensurate F0 supercell (path A, see forensic_decision_report):
#   Al fcc a = 4.05; Fe4Al13 in-plane periods a_x = 15.498, b_y = 8.0814 (orthogonal in xy).
#   Lx = 93.15 = 23*4.05 (Al exact) = 6*15.498 strained (+0.17% Fe-a misfit)
#   Ly = 121.5 = 30*4.05 (Al exact) = 15*8.0814 strained (+0.23% Fe-b misfit)
# Al stays unstrained (pristine matrix reference); the small misfit sits on the inclusion and is
# identical for eps0000/eps00194 -> cancels in the Delta-sigma deliverable.
GEOMETRIES = {
    "F0_planar_100A": GeometrySpec("F0_planar_100A", "planar", 120.0, 120.0, 100.0, 50.0, 170.0),
    "F0_planar_100A_comm": GeometrySpec(
        "F0_planar_100A_comm", "planar", 93.15, 121.5, 100.0, 50.0, 170.0, commensurate_ppf=True
    ),
    "F0_planar_300A": GeometrySpec("F0_planar_300A", "planar", 120.0, 120.0, 300.0, 50.0, 370.0),
    "F1_curved_cap_100A": GeometrySpec(
        "F1_curved_cap_100A",
        "curved_cap",
        200.0,
        200.0,
        120.0,
        50.0,
        220.0,
        cap_radius_x_A=80.0,
        cap_radius_y_A=80.0,
        cap_height_A=40.0,
    ),
}

EPS_SCENARIOS = {
    "eps0000": 0.0,
    "eps00194": 0.00194,
    "eps005": 0.005,
    "eps010": 0.010,
}


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def eps_label(eps_z: float) -> str:
    for label, value in EPS_SCENARIOS.items():
        if abs(float(eps_z) - value) < 5e-7:
            return label
    return "eps" + str(float(eps_z)).replace("-", "m").replace(".", "p")


def fcc_al_block(box_x: float, box_y: float, z_lo: float, z_hi: float) -> np.ndarray:
    nx = int(math.ceil(box_x / AL_A)) + 1
    ny = int(math.ceil(box_y / AL_A)) + 1
    nz = int(math.ceil((z_hi - z_lo) / AL_A)) + 1
    basis = np.array(
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0], [0.5, 0.0, 0.5], [0.0, 0.5, 0.5]],
        dtype=float,
    ) * AL_A
    cells = (
        np.stack(np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing="ij"), axis=-1).reshape(-1, 3)
        * AL_A
    )
    pos = (cells[:, None, :] + basis[None, :, :]).reshape(-1, 3)
    pos[:, 2] += z_lo
    keep = (pos[:, 0] < box_x) & (pos[:, 1] < box_y) & (pos[:, 2] >= z_lo) & (pos[:, 2] < z_hi)
    return pos[keep]


def parse_fe4al13_source() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    symbols, positions, cell = builder._parse_lammps_atomic_data(paths.AL13FE4_DATA)
    return symbols.astype(object), positions.astype(float), np.asarray(cell, dtype=float)


def replicate_fe4al13_box(
    box_x: float, box_y: float, z_lo: float, z_hi: float, eps_z: float, commensurate: bool = False
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    symbols0, pos0, cell = parse_fe4al13_source()
    lengths = np.linalg.norm(cell, axis=1)
    reps = np.ceil(np.array([box_x, box_y, z_hi - z_lo]) / lengths).astype(int) + 2
    all_symbols: list[np.ndarray] = []
    all_pos: list[np.ndarray] = []
    for i in range(int(reps[0])):
        for j in range(int(reps[1])):
            for k in range(int(reps[2])):
                shift = i * cell[0] + j * cell[1] + k * cell[2]
                all_symbols.append(symbols0)
                all_pos.append(pos0 + shift)
    symbols = np.concatenate(all_symbols).astype(object)
    pos = np.vstack(all_pos)
    pos -= pos.min(axis=0)

    misfit: dict[str, Any] = {"commensurate": bool(commensurate)}
    if commensurate:
        # In-plane periods of Fe4Al13 (a along x, b along y; orthogonal in xy for this cell).
        a_x = abs(float(cell[0, 0]))
        b_y = abs(float(cell[1, 1]))
        n_fe_x = max(1, int(round(box_x / a_x)))
        n_fe_y = max(1, int(round(box_y / b_y)))
        # Uniformly scale the whole inclusion block in x,y so an integer number of cells tiles the
        # box exactly -> after cutting [0,box) the periodic seam is clean. (z handled below.)
        scale_x = box_x / (n_fe_x * a_x)
        scale_y = box_y / (n_fe_y * b_y)
        pos[:, 0] *= scale_x
        pos[:, 1] *= scale_y
        misfit.update(
            {
                "fe_cell_a_x_A": a_x,
                "fe_cell_b_y_A": b_y,
                "n_fe_cells_x": n_fe_x,
                "n_fe_cells_y": n_fe_y,
                "inplane_scale_x": scale_x,
                "inplane_scale_y": scale_y,
                "inplane_misfit_x_pct": (scale_x - 1.0) * 100.0,
                "inplane_misfit_y_pct": (scale_y - 1.0) * 100.0,
            }
        )

    pos[:, 2] *= 1.0 + float(eps_z)
    pos[:, 2] += z_lo
    keep = (pos[:, 0] < box_x) & (pos[:, 1] < box_y) & (pos[:, 2] >= z_lo) & (pos[:, 2] < z_hi)
    return symbols[keep], pos[keep], misfit


def curved_cap_mask(pos: np.ndarray, spec: GeometrySpec, interface_z: float) -> np.ndarray:
    assert spec.cap_radius_x_A and spec.cap_radius_y_A and spec.cap_height_A
    cx = spec.box_x_A * 0.5
    cy = spec.box_y_A * 0.5
    cap_center_z = interface_z - spec.cap_height_A
    value = (
        ((pos[:, 0] - cx) / spec.cap_radius_x_A) ** 2
        + ((pos[:, 1] - cy) / spec.cap_radius_y_A) ** 2
        + ((pos[:, 2] - cap_center_z) / spec.cap_height_A) ** 2
    )
    cap = (value <= 1.0) & (pos[:, 2] <= interface_z)
    support = pos[:, 2] < interface_z - spec.cap_height_A
    return cap | support


def remove_close_matrix_atoms(al_pos: np.ndarray, fe_pos: np.ndarray) -> tuple[np.ndarray, int, float | None, int, int]:
    try:
        from scipy.spatial import cKDTree
    except Exception:
        return al_pos, 0, None, 0, 0
    if len(al_pos) == 0 or len(fe_pos) == 0:
        return al_pos, 0, None, 0, 0
    tree = cKDTree(fe_pos)
    distances, _ = tree.query(al_pos, k=1)
    keep = distances >= CLEARANCE_A
    hard = int(np.count_nonzero(distances < MIN_HARD_A))
    warn = int(np.count_nonzero(distances < MIN_WARN_A))
    min_dist = float(distances.min()) if distances.size else None
    return al_pos[keep], int(np.count_nonzero(~keep)), min_dist, hard, warn


def dedup_pbc_boundary(
    pos: np.ndarray, atom_types: np.ndarray, symbols: np.ndarray, box_x: float, box_y: float, grid: float = 1.0e-3
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Remove periodic-image boundary duplicates introduced by the commensurate cut.

    A commensurate supercell tiles an integer number of periods, so the over-replicated block
    leaves a thin face at x~box (or y~box) that, due to floating-point scaling, survives the
    ``< box`` cut and exactly coincides (under PBC) with the x~0 (y~0) face. Fold those onto 0
    and drop the duplicate so the periodic seam is clean. Genuine atoms (>= grid from the edge)
    are untouched; the in-cell minimum nn (~2.2 A) guarantees no real atoms are merged.
    """
    fx = np.mod(pos[:, 0], box_x)
    fy = np.mod(pos[:, 1], box_y)
    fx = np.where(box_x - fx < grid, 0.0, fx)
    fy = np.where(box_y - fy < grid, 0.0, fy)
    keys = np.round(np.stack([fx, fy, pos[:, 2]], axis=1) / grid).astype(np.int64)
    _, idx = np.unique(keys, axis=0, return_index=True)
    idx = np.sort(idx)
    removed = int(len(pos) - len(idx))
    return pos[idx], atom_types[idx], symbols[idx], removed


def pbc_seam_check(pos: np.ndarray, box_x: float, box_y: float) -> dict[str, Any]:
    """PBC-aware nearest-neighbour check across the x,y periodic seam (z is non-periodic).

    The old cross-only, non-periodic check could not see periodic-image collisions; this tiles the
    cell by +/-1 image in x and y and measures the minimum atom-atom distance to a periodic image,
    plus the in-cell minimum, over ALL atoms (both species).
    """
    result: dict[str, Any] = {"n_atoms": int(len(pos))}
    try:
        from scipy.spatial import cKDTree
    except Exception:
        result["scipy_available"] = False
        return result
    result["scipy_available"] = True
    if len(pos) < 2:
        return result

    # In-cell (non-periodic) nearest neighbour.
    intra = cKDTree(pos).query(pos, k=2)[0][:, 1]
    intra_min = float(intra.min())

    # Minimum distance to a periodic image across the x,y seam (the previously-missed case).
    shifts = [
        (-box_x, 0.0), (box_x, 0.0), (0.0, -box_y), (0.0, box_y),
        (-box_x, -box_y), (-box_x, box_y), (box_x, -box_y), (box_x, box_y),
    ]
    images = []
    for dx, dy in shifts:
        p = pos.copy()
        p[:, 0] += dx
        p[:, 1] += dy
        images.append(p)
    image_pts = np.vstack(images)
    seam = cKDTree(image_pts).query(pos, k=1)[0]
    seam_min = float(seam.min())

    result.update(
        {
            "intra_cell_min_nn_A": intra_min,
            "seam_min_nn_A": seam_min,
            "overall_min_nn_A": min(intra_min, seam_min),
            "seam_pairs_lt_1p8_A": int(np.count_nonzero(seam < MIN_HARD_A)),
            "seam_pairs_lt_2p1_A": int(np.count_nonzero(seam < MIN_WARN_A)),
            "intra_pairs_lt_1p8_A": int(np.count_nonzero(intra < MIN_HARD_A)),
            "seam_clean": bool(seam_min >= MIN_HARD_A and intra_min >= MIN_HARD_A),
        }
    )
    return result


def build_geometry(spec: GeometrySpec, eps_z: float, out_dir: Path, write_data: bool) -> dict[str, Any]:
    interface_z = spec.fe_depth_A
    fe_symbols, fe_pos, misfit = replicate_fe4al13_box(
        spec.box_x_A, spec.box_y_A, 0.0, interface_z, eps_z, commensurate=spec.commensurate_ppf
    )
    if spec.geometry_type == "curved_cap":
        keep = curved_cap_mask(fe_pos, spec, interface_z)
        fe_symbols = fe_symbols[keep]
        fe_pos = fe_pos[keep]
    al_pos = fcc_al_block(spec.box_x_A, spec.box_y_A, interface_z, spec.total_z_A)
    al_pos, removed_al, min_cross, hard_cross, warn_cross = remove_close_matrix_atoms(al_pos, fe_pos)

    symbols = np.concatenate([np.array(["Al"] * len(al_pos), dtype=object), fe_symbols])
    pos = np.vstack([al_pos, fe_pos])
    atom_types = np.where(symbols == "Fe", 2, 1)
    order = np.lexsort((pos[:, 2], pos[:, 1], pos[:, 0], atom_types))
    symbols = symbols[order]
    pos = pos[order]
    atom_types = atom_types[order]
    seam_dedup_removed = 0
    if spec.commensurate_ppf:
        pos, atom_types, symbols, seam_dedup_removed = dedup_pbc_boundary(
            pos, atom_types, symbols, spec.box_x_A, spec.box_y_A
        )
    matrix_atoms = int(np.count_nonzero(atom_types == 1))
    total_atoms = int(len(pos))
    seam = pbc_seam_check(pos, spec.box_x_A, spec.box_y_A)
    data_file = out_dir / f"data.{spec.geometry_id}_{eps_label(eps_z)}"
    if write_data:
        write_lammps_data(data_file, spec, pos, atom_types)

    meta = {
        "case_id": f"{spec.geometry_id}_{eps_label(eps_z)}",
        "geometry_id": spec.geometry_id,
        "geometry_type": spec.geometry_type,
        "box_x_A": spec.box_x_A,
        "box_y_A": spec.box_y_A,
        "box_z_A": spec.total_z_A,
        "al_depth_A": spec.al_depth_A,
        "fe_depth_A": spec.fe_depth_A,
        "cap_radius_x_A": spec.cap_radius_x_A,
        "cap_radius_y_A": spec.cap_radius_y_A,
        "cap_height_A": spec.cap_height_A,
        "interface_definition": "Fe4Al13/Al boundary patch; r=0 at nominal interface surface",
        "r_zero_definition": "F0: z=fe_depth_A plane; F1: curved cap surface plus support transition",
        "r_direction": "+Z into Al for F0; local outward normal into Al for F1",
        "eigenstrain_axis": "Z",
        "eps_z": float(eps_z),
        "temperature_K": 300.0,
        "yield_threshold_mpa": 120.0,
        "data_file": str(data_file) if write_data else None,
        "dump_files": [],
        "restart_files": [],
        "lammps_input": None,
        "log_file": None,
        "total_atoms_estimated_or_written": total_atoms,
        "matrix_atoms": matrix_atoms,
        "inclusion_atoms": int(total_atoms - matrix_atoms),
        "matrix_max_id": matrix_atoms,
        "source_fe4al13": str(paths.AL13FE4_DATA),
        "removed_matrix_atoms_near_inclusion": removed_al,
        "min_cross_distance_before_cleanup_A": min_cross,
        "hard_cross_pairs_before_cleanup_lt_1p8_A": hard_cross,
        "warn_cross_pairs_before_cleanup_lt_2p1_A": warn_cross,
        "boundary_conditions_preferred": "p p f",
        "commensurate_ppf": bool(spec.commensurate_ppf),
        "inplane_commensurate_misfit": misfit,
        "seam_boundary_duplicates_removed": seam_dedup_removed,
        "pbc_seam_check": seam,
        "created_at": now(),
        "write_data": bool(write_data),
    }
    write_json(out_dir / f"{spec.geometry_id}_{eps_label(eps_z)}_metadata.json", meta)
    return meta


def write_lammps_data(path: Path, spec: GeometrySpec, pos: np.ndarray, atom_types: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(f"LAMMPS data file for Stage F {spec.geometry_id}; written by prepare_stageF_boundary_patch_geometry.py\n\n")
        handle.write(f"{len(pos)} atoms\n")
        handle.write("2 atom types\n\n")
        handle.write(f"0.0 {spec.box_x_A:.8f} xlo xhi\n")
        handle.write(f"0.0 {spec.box_y_A:.8f} ylo yhi\n")
        handle.write(f"0.0 {spec.total_z_A:.8f} zlo zhi\n\n")
        handle.write("Masses\n\n")
        handle.write("1 26.9815385 # Al\n")
        handle.write("2 55.845 # Fe\n\n")
        handle.write("Atoms # atomic\n\n")
        for atom_id, (atype, xyz) in enumerate(zip(atom_types, pos), start=1):
            handle.write(f"{atom_id} {int(atype)} {xyz[0]:.8f} {xyz[1]:.8f} {xyz[2]:.8f}\n")


def write_catalog(out_root: Path) -> None:
    catalog = {
        "status": "prepared",
        "created_at": now(),
        "geometries": {key: spec.__dict__ for key, spec in GEOMETRIES.items()},
        "eps_scenarios": EPS_SCENARIOS,
        "first_safe_smoke_cases": [
            "F0_planar_100A_eps0000",
            "F0_planar_100A_eps00194",
            "F0_planar_100A_eps005",
            "F0_planar_300A_eps00194",
            "F1_curved_cap_100A_eps00194",
            "F1_curved_cap_100A_eps005",
        ],
        "no_production_without_smoke": True,
    }
    write_json(out_root / "stageF_boundary_patch_geometry_catalog.json", catalog)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry", choices=sorted(GEOMETRIES), default="F0_planar_100A")
    parser.add_argument("--eps-z", type=float, default=0.00194)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    parser.add_argument("--write-data", action="store_true", help="Write a LAMMPS data file. Default writes metadata/estimate only.")
    parser.add_argument("--all-metadata", action="store_true", help="Write metadata estimates for all Stage F initial cases.")
    args = parser.parse_args(argv)

    args.out_root.mkdir(parents=True, exist_ok=True)
    write_catalog(args.out_root)
    if args.all_metadata:
        outputs = []
        for geom in ["F0_planar_100A", "F0_planar_300A", "F1_curved_cap_100A"]:
            eps_values = [0.0, 0.00194, 0.005] if geom == "F0_planar_100A" else [0.00194, 0.005]
            for eps in eps_values:
                out_dir = args.out_root / f"{geom}_{eps_label(eps)}"
                outputs.append(build_geometry(GEOMETRIES[geom], eps, out_dir, write_data=False))
        print(json.dumps({"status": "metadata_prepared", "count": len(outputs), "out_root": str(args.out_root)}, ensure_ascii=False, indent=2))
        return 0

    out_dir = args.out_root / f"{args.geometry}_{eps_label(args.eps_z)}"
    meta = build_geometry(GEOMETRIES[args.geometry], args.eps_z, out_dir, write_data=args.write_data)
    print(json.dumps({"status": "prepared", "metadata": str(out_dir / f'{args.geometry}_{eps_label(args.eps_z)}_metadata.json'), "atoms": meta["total_atoms_estimated_or_written"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
