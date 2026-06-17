"""A1-small structure builder: scaled-up Al matrix + Fe4Al13 ellipsoid inclusion.

Same construction as analysis/python/build_ellipsoid_inclusion_trial.py (A0 was
NX=NY=16, NZ=24, axes 12x12x24 A), parametrized by atom-count target and writing
only into a run-local directory. The inclusion axis ratio 1:1:2 and the
box-to-inclusion proportions of A0 are preserved; box dimensions stay exact
multiples of the Al lattice constant (avoids periodic hard overlaps).

Also generates the A1 prep LAMMPS input. The GPU-safe production path uses a
thermal settle + NVT equilibration at 300 K, mirroring the committed trial_001
baseline intent without invoking the GPU-unsafe relaxation command.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

from . import paths
from .resources import estimate_lammps_memory_gb

AL_A = 4.05
AL_DENSITY = 4.0 / AL_A**3  # atoms / A^3 (fcc)
# Measured from the A0 build: 996 inclusion atoms in a 12x12x24 A ellipsoid.
INCLUSION_DENSITY = 996.0 / ((4.0 / 3.0) * math.pi * 12.0 * 12.0 * 24.0)
CLEARANCE = 2.20
MIN_DISTANCE_HARD = 1.80
MIN_DISTANCE_WARN = 2.10

# A0 reference proportions: NX=16 -> axes (12, 12, 24), NZ = 1.5 * NX.
A0_NX = 16
A0_AXES = np.array([12.0, 12.0, 24.0])
STAGEB_POSITIONS = ("grain_interior", "near_grain_boundary")
STAGEB_PREDEFECTS = ("perfect", "vacancies_medium", "seed_dislocation_if_available")
STAGEB_GRAIN2_ROTATION_DEG = 36.86989765
STAGEB_VACANCY_PROTECTION_A = 4.0
STAGEB_DEFAULT_BOUNDARY_SURFACE_GAP_A = 5.0


class BuildError(RuntimeError):
    pass


def plan_for_target(target_atoms: int, ranks: int, max_memory_gb: float) -> dict:
    """Geometry plan for one atom-count target (no construction yet)."""
    nx = max(8, round((target_atoms / 6.0) ** (1.0 / 3.0)))
    ny = nx
    nz = round(1.5 * nx)
    scale = nx / A0_NX
    axes = A0_AXES * scale
    box = np.array([nx * AL_A, ny * AL_A, nz * AL_A])
    v_cavity = (4.0 / 3.0) * math.pi * np.prod(axes + CLEARANCE)
    v_inclusion = (4.0 / 3.0) * math.pi * np.prod(axes)
    est_atoms = int(
        round(4 * nx * ny * nz - v_cavity * AL_DENSITY + v_inclusion * INCLUSION_DENSITY)
    )
    est_mem = estimate_lammps_memory_gb(est_atoms, ranks)
    return {
        "target_atoms": int(target_atoms),
        "nx": int(nx),
        "ny": int(ny),
        "nz": int(nz),
        "box_A": [float(b) for b in box],
        "inclusion_axes_A": [float(a) for a in axes],
        "axis_ratio": [1.0, 1.0, 2.0],
        "estimated_atoms": est_atoms,
        "estimated_memory_gb": round(est_mem, 2),
        "feasible_under_memory_limit": bool(est_mem <= float(max_memory_gb)),
    }


def select_plan(candidates: list[int], ranks: int, max_memory_gb: float) -> tuple[dict, list[dict]]:
    plans = [plan_for_target(t, ranks, max_memory_gb) for t in candidates]
    for plan in plans:
        if plan["feasible_under_memory_limit"]:
            return plan, plans
    raise BuildError(
        f"no A1-small candidate fits under the {max_memory_gb} GB memory limit: "
        + json.dumps(plans)
    )


def _ellipsoid_value(pos: np.ndarray, center: np.ndarray, axes: np.ndarray) -> np.ndarray:
    d = (pos - center) / axes
    return np.sum(d * d, axis=1)


def _fcc_positions(nx: int, ny: int, nz: int) -> np.ndarray:
    basis = np.array(
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0], [0.5, 0.0, 0.5], [0.0, 0.5, 0.5]]
    ) * AL_A
    cells = (
        np.stack(
            np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing="ij"),
            axis=-1,
        ).reshape(-1, 3)
        * AL_A
    )
    return (cells[:, None, :] + basis[None, :, :]).reshape(-1, 3)


def _rotation_z(degrees: float) -> np.ndarray:
    theta = math.radians(float(degrees))
    c = math.cos(theta)
    s = math.sin(theta)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=float)


def _cleanup_close_pairs(
    pos: np.ndarray,
    labels: np.ndarray,
    box: np.ndarray,
    cutoff: float,
    *,
    prefer_remove_label: str | None = None,
    max_passes: int = 8,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Remove one atom from each severe pair until no pair remains below cutoff."""
    total_removed = 0
    pos = np.asarray(pos, dtype=float) % box
    labels = np.asarray(labels, dtype=object)
    for _ in range(max_passes):
        if len(pos) == 0:
            break
        tree = cKDTree(pos, boxsize=box)
        pairs = sorted(tree.query_pairs(r=float(cutoff)))
        if not pairs:
            break
        remove: set[int] = set()
        for i, j in pairs:
            if i in remove or j in remove:
                continue
            if prefer_remove_label and labels[j] == prefer_remove_label:
                remove.add(j)
            elif prefer_remove_label and labels[i] == prefer_remove_label:
                remove.add(i)
            else:
                remove.add(max(i, j))
        keep = np.array([i not in remove for i in range(len(pos))], dtype=bool)
        total_removed += len(remove)
        pos = pos[keep]
        labels = labels[keep]
    return pos, labels, total_removed


def _bicrystal_matrix(plan: MappingLike) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    nx, ny, nz = int(plan["nx"]), int(plan["ny"]), int(plan["nz"])
    box = np.array(plan["box_A"], dtype=float)
    boundary_x = 0.5 * box[0]

    grain1 = _fcc_positions(nx, ny, nz)
    grain1 = grain1[grain1[:, 0] < boundary_x]
    grain1_labels = np.array(["grain_1"] * len(grain1), dtype=object)

    basis = np.array(
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0], [0.5, 0.0, 0.5], [0.0, 0.5, 0.5]]
    ) * AL_A
    ix = np.arange(-nx, 2 * nx)
    iy = np.arange(-ny, 2 * ny)
    iz = np.arange(0, nz)
    cells = (
        np.stack(np.meshgrid(ix, iy, iz, indexing="ij"), axis=-1).reshape(-1, 3)
        * AL_A
    )
    raw = (cells[:, None, :] + basis[None, :, :]).reshape(-1, 3)
    origin = np.array([boundary_x, 0.5 * box[1], 0.5 * box[2]], dtype=float)
    rot = _rotation_z(STAGEB_GRAIN2_ROTATION_DEG)
    grain2 = (raw - origin) @ rot.T + origin
    keep = (
        (grain2[:, 0] >= boundary_x)
        & (grain2[:, 0] < box[0])
        & (grain2[:, 1] >= 0.0)
        & (grain2[:, 1] < box[1])
        & (grain2[:, 2] >= 0.0)
        & (grain2[:, 2] < box[2])
    )
    grain2 = grain2[keep]
    grain2_labels = np.array(["grain_2"] * len(grain2), dtype=object)

    pos = np.vstack([grain1, grain2]) % box
    labels = np.concatenate([grain1_labels, grain2_labels])
    pos, labels, removed = _cleanup_close_pairs(
        pos, labels, box, MIN_DISTANCE_HARD, prefer_remove_label="grain_2")
    meta = {
        "grain1_orientation": "fcc_identity_[100]x_[010]y_[001]z",
        "grain2_orientation": f"fcc_rotated_z_{STAGEB_GRAIN2_ROTATION_DEG:.6f}_deg",
        "boundary_plane": "x",
        "boundary_location": float(boundary_x),
        "boundary_normal": [1.0, 0.0, 0.0],
        "orientation_discontinuity_degrees": STAGEB_GRAIN2_ROTATION_DEG,
        "overlap_cleanup_count": int(removed),
        "grain1_atoms_before_cavity": int(np.count_nonzero(labels == "grain_1")),
        "grain2_atoms_before_cavity": int(np.count_nonzero(labels == "grain_2")),
    }
    return pos, labels, meta


def _inclusion_atoms(center: np.ndarray, axes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    symbols0, pos0, cell0 = _parse_lammps_atomic_data(paths.AL13FE4_DATA)
    cell_lengths = np.linalg.norm(cell0, axis=1)
    reps = np.ceil((2.0 * axes + 10.0) / cell_lengths).astype(int) + 2
    reps = np.maximum(reps, 3)

    all_symbols, all_pos = [], []
    for i in range(int(reps[0])):
        for j in range(int(reps[1])):
            for k in range(int(reps[2])):
                shift = i * cell0[0] + j * cell0[1] + k * cell0[2]
                all_symbols.append(symbols0)
                all_pos.append(pos0 + shift)
    inc_symbols = np.concatenate(all_symbols).astype(object)
    inc_pos = np.vstack(all_pos)
    current_center = 0.5 * (inc_pos.min(axis=0) + inc_pos.max(axis=0))
    inc_pos = inc_pos + (center - current_center)
    mask = _ellipsoid_value(inc_pos, center, axes) <= 1.0
    return inc_symbols[mask], inc_pos[mask]


def _sort_atoms(
    symbols: np.ndarray,
    pos: np.ndarray,
    source: np.ndarray,
    grain: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rank = np.array(
        [
            0 if (src == "matrix" and sym == "Al")
            else 1 if (src == "inclusion" and sym == "Al")
            else 2
            for sym, src in zip(symbols, source)
        ]
    )
    order = np.lexsort((pos[:, 2], pos[:, 1], pos[:, 0], rank))
    return symbols[order], pos[order], source[order], grain[order]


def _pair_report(
    symbols: np.ndarray,
    pos: np.ndarray,
    source: np.ndarray,
    box: np.ndarray,
) -> dict[str, Any]:
    tree = cKDTree(pos % box, boxsize=box)
    pairs = tree.query_pairs(r=MIN_DISTANCE_WARN)
    warn_pairs, hard_pairs, cross_pairs = [], [], []
    min_d = None
    for i, j in pairs:
        dvec = pos[i] - pos[j]
        dvec -= box * np.round(dvec / box)
        d = float(np.linalg.norm(dvec))
        min_d = d if min_d is None else min(min_d, d)
        item = {
            "i": int(i + 1),
            "j": int(j + 1),
            "si": str(symbols[i]),
            "sj": str(symbols[j]),
            "source_i": str(source[i]),
            "source_j": str(source[j]),
            "distance_A": d,
        }
        if d < MIN_DISTANCE_WARN:
            warn_pairs.append(item)
            if item["source_i"] != item["source_j"]:
                cross_pairs.append(item)
        if d < MIN_DISTANCE_HARD:
            hard_pairs.append(item)
    return {
        "min_pair_distance_A": min_d,
        "pairs_below_2p1_A": len(warn_pairs),
        "pairs_below_1p8_A": len(hard_pairs),
        "cross_source_pairs_below_2p1_A": len(cross_pairs),
        "warning_pairs_preview": warn_pairs[:30],
        "hard_pairs_preview": hard_pairs[:30],
        "cross_source_warning_pairs_preview": cross_pairs[:30],
        "safe_basic": len(hard_pairs) == 0 and len(cross_pairs) == 0,
    }


def _write_atomic_data(
    out_data: Path,
    symbols: np.ndarray,
    pos: np.ndarray,
    box: np.ndarray,
    *,
    title: str,
) -> None:
    type_map = {"Al": 1, "Fe": 2}
    with out_data.open("w", encoding="utf-8", newline="\n") as f:
        f.write(title + "\n\n")
        f.write(f"{len(pos)} atoms\n")
        f.write("2 atom types\n\n")
        f.write(f"0.0 {box[0]:.16f} xlo xhi\n")
        f.write(f"0.0 {box[1]:.16f} ylo yhi\n")
        f.write(f"0.0 {box[2]:.16f} zlo zhi\n\n")
        f.write("Masses\n\n")
        f.write("1 26.9815385 # Al\n")
        f.write("2 55.845 # Fe\n\n")
        f.write("Atoms # atomic\n\n")
        for idx, (sym, xyz) in enumerate(zip(symbols, pos), start=1):
            f.write(
                f"{idx} {type_map[str(sym)]} "
                f"{xyz[0]:.16f} {xyz[1]:.16f} {xyz[2]:.16f}\n"
            )


MappingLike = dict[str, Any]


def _parse_lammps_atomic_data(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    xlo = xhi = ylo = yhi = zlo = zhi = None
    xy = xz = yz = 0.0
    atoms_start = None
    for idx, line in enumerate(text):
        s = line.strip()
        parts = s.split()
        if len(parts) >= 4 and parts[-2:] == ["xlo", "xhi"]:
            xlo, xhi = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[-2:] == ["ylo", "yhi"]:
            ylo, yhi = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[-2:] == ["zlo", "zhi"]:
            zlo, zhi = float(parts[0]), float(parts[1])
        elif len(parts) >= 6 and parts[-3:] == ["xy", "xz", "yz"]:
            xy, xz, yz = float(parts[0]), float(parts[1]), float(parts[2])
        elif s.startswith("Atoms"):
            atoms_start = idx + 2
            break
    if None in [xlo, xhi, ylo, yhi, zlo, zhi]:
        raise BuildError(f"could not parse box bounds from {path}")
    if atoms_start is None:
        raise BuildError(f"could not find Atoms section in {path}")

    a_vec = np.array([xhi - xlo, 0.0, 0.0])
    b_vec = np.array([xy, yhi - ylo, 0.0])
    c_vec = np.array([xz, yz, zhi - zlo])
    cell = np.vstack([a_vec, b_vec, c_vec])

    atom_types, positions = [], []
    for line in text[atoms_start:]:
        s = line.strip()
        if not s:
            continue
        if s[0].isalpha():
            break
        parts = s.split()
        if len(parts) < 5:
            continue
        atom_types.append(int(parts[1]))
        positions.append([float(parts[2]), float(parts[3]), float(parts[4])])

    atom_types = np.array(atom_types, dtype=int)
    positions = np.array(positions, dtype=float)
    symbols = np.where(atom_types == 1, "Al", "Fe")
    return symbols, positions, cell


def build_structure(plan: dict, out_dir: Path) -> dict:
    """Construct the A1-small structure; returns metadata incl. inclusion id range."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    nx, ny, nz = plan["nx"], plan["ny"], plan["nz"]
    box = np.array(plan["box_A"], dtype=float)
    center = box / 2.0
    axes = np.array(plan["inclusion_axes_A"], dtype=float)

    # --- Al fcc matrix ---
    basis = np.array(
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0], [0.5, 0.0, 0.5], [0.0, 0.5, 0.5]]
    ) * AL_A
    cells = (
        np.stack(
            np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing="ij"),
            axis=-1,
        ).reshape(-1, 3)
        * AL_A
    )
    al_pos = (cells[:, None, :] + basis[None, :, :]).reshape(-1, 3)
    al_symbols = np.array(["Al"] * len(al_pos), dtype=object)
    al_source = np.array(["matrix"] * len(al_pos), dtype=object)

    # --- carve cavity ---
    cavity_axes = axes + CLEARANCE
    keep = _ellipsoid_value(al_pos, center, cavity_axes) > 1.0
    al_symbols, al_pos, al_source = al_symbols[keep], al_pos[keep], al_source[keep]

    # --- Fe4Al13 ellipsoid ---
    symbols0, pos0, cell0 = _parse_lammps_atomic_data(paths.AL13FE4_DATA)
    cell_lengths = np.linalg.norm(cell0, axis=1)
    reps = np.ceil((2.0 * axes + 10.0) / cell_lengths).astype(int) + 2
    reps = np.maximum(reps, 3)

    all_symbols, all_pos = [], []
    for i in range(int(reps[0])):
        for j in range(int(reps[1])):
            for k in range(int(reps[2])):
                shift = i * cell0[0] + j * cell0[1] + k * cell0[2]
                all_symbols.append(symbols0)
                all_pos.append(pos0 + shift)
    inc_symbols = np.concatenate(all_symbols)
    inc_pos = np.vstack(all_pos)
    current_center = 0.5 * (inc_pos.min(axis=0) + inc_pos.max(axis=0))
    inc_pos = inc_pos + (center - current_center)
    mask = _ellipsoid_value(inc_pos, center, axes) <= 1.0
    inc_symbols = inc_symbols[mask].astype(object)
    inc_pos = inc_pos[mask]
    inc_source = np.array(["inclusion"] * len(inc_pos), dtype=object)

    symbols = np.concatenate([al_symbols, inc_symbols])
    pos = np.vstack([al_pos, inc_pos])
    source = np.concatenate([al_source, inc_source])

    # --- remove matrix atoms too close to the inclusion ---
    matrix_idx = np.where(source == "matrix")[0]
    inclusion_idx = np.where(source == "inclusion")[0]
    if len(inclusion_idx) == 0:
        raise BuildError("inclusion carved to zero atoms")
    tree_inc = cKDTree(pos[inclusion_idx] % box, boxsize=box)
    near = tree_inc.query_ball_point(pos[matrix_idx] % box, r=MIN_DISTANCE_WARN)
    remove_local = [i for i, hits in enumerate(near) if len(hits) > 0]
    remove_global = set(matrix_idx[remove_local].tolist())
    keep = np.array([i not in remove_global for i in range(len(pos))], dtype=bool)
    symbols, pos, source = symbols[keep], pos[keep], source[keep]
    removed_near = len(remove_global)

    pos = pos % box

    # --- sort: matrix Al first, then inclusion Al, then inclusion Fe ---
    rank = np.array(
        [
            0 if (src == "matrix" and sym == "Al")
            else 1 if (src == "inclusion" and sym == "Al")
            else 2
            for sym, src in zip(symbols, source)
        ]
    )
    order = np.lexsort((pos[:, 2], pos[:, 1], pos[:, 0], rank))
    symbols, pos, source = symbols[order], pos[order], source[order]

    n_total = len(pos)
    n_matrix = int(np.sum(source == "matrix"))
    n_inclusion = int(np.sum(source == "inclusion"))

    # --- distance report ---
    tree = cKDTree(pos, boxsize=box)
    pairs = tree.query_pairs(r=MIN_DISTANCE_WARN)
    warn_pairs, hard_pairs, cross_pairs = [], [], []
    min_d = None
    for i, j in pairs:
        dvec = pos[i] - pos[j]
        dvec -= box * np.round(dvec / box)
        d = float(np.linalg.norm(dvec))
        min_d = d if min_d is None else min(min_d, d)
        item = {
            "i": int(i + 1),
            "j": int(j + 1),
            "si": str(symbols[i]),
            "sj": str(symbols[j]),
            "source_i": str(source[i]),
            "source_j": str(source[j]),
            "distance_A": d,
        }
        if d < MIN_DISTANCE_WARN:
            warn_pairs.append(item)
            if item["source_i"] != item["source_j"]:
                cross_pairs.append(item)
        if d < MIN_DISTANCE_HARD:
            hard_pairs.append(item)

    report = {
        "total_atoms": int(n_total),
        "al_atoms": int(np.sum(symbols == "Al")),
        "fe_atoms": int(np.sum(symbols == "Fe")),
        "matrix_atoms": n_matrix,
        "inclusion_atoms": n_inclusion,
        "box_A": box.tolist(),
        "center_A": center.tolist(),
        "ellipsoid_axes_A": axes.tolist(),
        "clearance_A": CLEARANCE,
        "removed_matrix_atoms_near_inclusion": removed_near,
        "pairs_below_2p1_A": len(warn_pairs),
        "pairs_below_1p8_A": len(hard_pairs),
        "cross_source_pairs_below_2p1_A": len(cross_pairs),
        "min_pair_distance_A": min_d,
        "warning_pairs_preview": warn_pairs[:30],
    }
    report["safe_basic"] = (
        report["pairs_below_1p8_A"] == 0
        and report["cross_source_pairs_below_2p1_A"] == 0
    )

    # --- write data file ---
    out_data = out_dir / "data.a1_small_ellipsoid"
    type_map = {"Al": 1, "Fe": 2}
    with out_data.open("w", encoding="utf-8", newline="\n") as f:
        f.write("LAMMPS data file for A1-small ellipsoid; written by stage_runner.builder\n\n")
        f.write(f"{n_total} atoms\n")
        f.write("2 atom types\n\n")
        f.write(f"0.0 {box[0]:.16f} xlo xhi\n")
        f.write(f"0.0 {box[1]:.16f} ylo yhi\n")
        f.write(f"0.0 {box[2]:.16f} zlo zhi\n\n")
        f.write("Masses\n\n")
        f.write("1 26.9815385 # Al\n")
        f.write("2 55.845 # Fe\n\n")
        f.write("Atoms # atomic\n\n")
        for idx, (sym, xyz) in enumerate(zip(symbols, pos), start=1):
            f.write(f"{idx} {type_map[str(sym)]} {xyz[0]:.16f} {xyz[1]:.16f} {xyz[2]:.16f}\n")

    meta = {
        "model": "Al matrix with Fe4Al13 ellipsoidal inclusion (A1-small)",
        "plan": plan,
        "data_file": str(out_data),
        "total_atoms": n_total,
        "matrix_atoms": n_matrix,
        "inclusion_atoms": n_inclusion,
        "matrix_max_id": n_matrix,
        "inclusion_id_min": n_matrix + 1,
        "inclusion_id_max": n_total,
        "box_A": box.tolist(),
        "center_A": center.tolist(),
        "inclusion_axes_A": axes.tolist(),
        "al_lattice_A": AL_A,
        "type_mapping": {"1": "Al", "2": "Fe"},
        "source_fe4al13": str(paths.AL13FE4_DATA),
        "safe_basic": report["safe_basic"],
    }

    (out_dir / "a1_small_build_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (out_dir / "a1_small_metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    if not report["safe_basic"]:
        raise BuildError(
            "A1-small build failed safety check: "
            f"hard pairs={report['pairs_below_1p8_A']}, "
            f"cross-source warn pairs={report['cross_source_pairs_below_2p1_A']}"
        )
    return meta


def build_stageb_realism_structure(
    plan: dict,
    out_dir: Path,
    *,
    case_id: str,
    position: str,
    predefect: str,
    deterministic_seed: int,
    vacancy_fraction: float | None = None,
    vacancy_count: int | None = None,
    boundary_surface_gap_A: float = STAGEB_DEFAULT_BOUNDARY_SURFACE_GAP_A,
) -> dict[str, Any]:
    """Build one Stage B realism geometry.

    `near_grain_boundary` is a deterministic two-grain Al matrix with a planar
    x-normal boundary and a z-rotated second grain. It is intentionally small
    and conservative, but it is a true orientation discontinuity, not a shifted
    inclusion in a perfect monocrystal.
    """
    if position not in STAGEB_POSITIONS:
        raise BuildError(f"unsupported Stage B position: {position}")
    if predefect not in STAGEB_PREDEFECTS:
        raise BuildError(f"unsupported Stage B predefect: {predefect}")
    if predefect == "seed_dislocation_if_available":
        raise BuildError("seed_dislocation_if_available is not implemented")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    box = np.array(plan["box_A"], dtype=float)
    axes = np.array(plan["inclusion_axes_A"], dtype=float)
    center = box / 2.0
    boundary_meta: dict[str, Any] = {}

    if position == "near_grain_boundary":
        matrix_pos, grain_labels, boundary_meta = _bicrystal_matrix(plan)
        boundary_x = float(boundary_meta["boundary_location"])
        center = np.array(
            [
                boundary_x + axes[0] + CLEARANCE + float(boundary_surface_gap_A),
                0.5 * box[1],
                0.5 * box[2],
            ],
            dtype=float,
        )
        max_x = box[0] - axes[0] - CLEARANCE - MIN_DISTANCE_WARN
        center[0] = min(center[0], max_x)
        if center[0] <= boundary_x:
            raise BuildError("near-grain-boundary inclusion cannot be placed inside the box")
        boundary_meta["inclusion_distance_to_boundary"] = float(abs(center[0] - boundary_x))
        boundary_meta["inclusion_surface_gap_to_boundary_A"] = float(
            abs(center[0] - boundary_x) - axes[0]
        )
    else:
        matrix_pos = _fcc_positions(int(plan["nx"]), int(plan["ny"]), int(plan["nz"]))
        grain_labels = np.array(["single_crystal"] * len(matrix_pos), dtype=object)

    matrix_symbols = np.array(["Al"] * len(matrix_pos), dtype=object)
    matrix_source = np.array(["matrix"] * len(matrix_pos), dtype=object)

    cavity_axes = axes + CLEARANCE
    keep = _ellipsoid_value(matrix_pos, center, cavity_axes) > 1.0
    matrix_pos = matrix_pos[keep]
    matrix_symbols = matrix_symbols[keep]
    matrix_source = matrix_source[keep]
    grain_labels = grain_labels[keep]

    inc_symbols, inc_pos = _inclusion_atoms(center, axes)
    if len(inc_pos) == 0:
        raise BuildError("Stage B inclusion carved to zero atoms")
    inc_source = np.array(["inclusion"] * len(inc_pos), dtype=object)
    inc_grain = np.array(["inclusion"] * len(inc_pos), dtype=object)

    symbols = np.concatenate([matrix_symbols, inc_symbols])
    pos = np.vstack([matrix_pos, inc_pos]) % box
    source = np.concatenate([matrix_source, inc_source])
    grain = np.concatenate([grain_labels, inc_grain])

    matrix_idx = np.where(source == "matrix")[0]
    inclusion_idx = np.where(source == "inclusion")[0]
    tree_inc = cKDTree(pos[inclusion_idx] % box, boxsize=box)
    near = tree_inc.query_ball_point(pos[matrix_idx] % box, r=MIN_DISTANCE_WARN)
    remove_local = [i for i, hits in enumerate(near) if len(hits) > 0]
    remove_global = set(matrix_idx[remove_local].tolist())
    keep_atoms = np.array([i not in remove_global for i in range(len(pos))], dtype=bool)
    removed_near_inclusion = len(remove_global)
    symbols, pos, source, grain = (
        symbols[keep_atoms],
        pos[keep_atoms],
        source[keep_atoms],
        grain[keep_atoms],
    )

    symbols, pos, source, grain = _sort_atoms(symbols, pos, source, grain)
    vacancy_meta: dict[str, Any] = {
        "predefect": predefect,
        "vacancy_count_requested": 0,
        "vacancy_count_actual": 0,
        "seed": int(deterministic_seed),
        "deleted_atom_ids": [],
        "min_distance_to_inclusion_A": None,
        "no_inclusion_atoms_deleted": True,
    }

    if predefect == "vacancies_medium":
        if vacancy_count is None:
            if vacancy_fraction is None:
                raise BuildError("vacancies_medium requires vacancy_count or vacancy_fraction")
            vacancy_count = int(round(float(vacancy_fraction) * int(np.count_nonzero(source == "matrix"))))
        requested = max(1, int(vacancy_count))
        protect_axes = axes + CLEARANCE + STAGEB_VACANCY_PROTECTION_A
        eligible = np.where(
            (source == "matrix") & (_ellipsoid_value(pos, center, protect_axes) > 1.0)
        )[0]
        if len(eligible) < requested:
            raise BuildError(
                f"not enough vacancy-eligible matrix atoms: {len(eligible)} < {requested}"
            )
        rng = np.random.default_rng(int(deterministic_seed))
        chosen = np.sort(rng.choice(eligible, size=requested, replace=False))
        pre_delete_ids = (chosen + 1).astype(int)
        inclusion_positions = pos[source == "inclusion"] % box
        vacancy_tree = cKDTree(inclusion_positions, boxsize=box)
        dists, _ = vacancy_tree.query(pos[chosen] % box, k=1)
        keep_v = np.ones(len(pos), dtype=bool)
        keep_v[chosen] = False
        removed_inclusion = int(np.count_nonzero(source[chosen] == "inclusion"))
        symbols, pos, source, grain = (
            symbols[keep_v],
            pos[keep_v],
            source[keep_v],
            grain[keep_v],
        )
        vacancy_meta = {
            "predefect": predefect,
            "vacancy_count_requested": int(requested),
            "vacancy_count_actual": int(len(chosen)),
            "seed": int(deterministic_seed),
            "deleted_atom_ids": [int(x) for x in pre_delete_ids.tolist()],
            "min_distance_to_inclusion_A": float(np.min(dists)) if len(dists) else None,
            "no_inclusion_atoms_deleted": removed_inclusion == 0,
            "protection_shell_A": float(STAGEB_VACANCY_PROTECTION_A),
        }

    symbols, pos, source, grain = _sort_atoms(symbols, pos % box, source, grain)
    n_total = int(len(pos))
    n_matrix = int(np.count_nonzero(source == "matrix"))
    n_inclusion = int(np.count_nonzero(source == "inclusion"))
    report = _pair_report(symbols, pos, source, box)
    if position == "near_grain_boundary":
        boundary_meta["overlap_cleanup_count"] = int(boundary_meta.get("overlap_cleanup_count", 0))
        boundary_meta["min_pair_distance_after_cleanup"] = report["min_pair_distance_A"]
    else:
        boundary_meta = {}

    out_data = out_dir / f"data.{case_id}.stageB_realism"
    _write_atomic_data(
        out_data,
        symbols,
        pos,
        box,
        title=f"LAMMPS data file for Stage B realism case {case_id}; written by stage_runner.builder",
    )

    meta = {
        "model": "Stage B realism 100k Al matrix with Fe4Al13 ellipsoidal inclusion",
        "case_id": case_id,
        "plan": plan,
        "data_file": str(out_data),
        "structure_mode": "build_stageB_realism_100k",
        "position": position,
        "predefect": predefect,
        "deterministic_seed": int(deterministic_seed),
        "total_atoms": n_total,
        "actual_atom_count": n_total,
        "matrix_atoms": n_matrix,
        "inclusion_atoms": n_inclusion,
        "matrix_max_id": n_matrix,
        "inclusion_id_min": n_matrix + 1,
        "inclusion_id_max": n_total,
        "box_A": box.tolist(),
        "center_A": center.tolist(),
        "inclusion_center": center.tolist(),
        "inclusion_axes_A": axes.tolist(),
        "al_lattice_A": AL_A,
        "type_mapping": {"1": "Al", "2": "Fe"},
        "source_fe4al13": str(paths.AL13FE4_DATA),
        "removed_matrix_atoms_near_inclusion": int(removed_near_inclusion),
        "no_inclusion_atoms_deleted": bool(vacancy_meta["no_inclusion_atoms_deleted"]),
        "boundary": boundary_meta,
        "vacancy": vacancy_meta,
        "grain_label_counts": {
            str(label): int(np.count_nonzero(grain == label)) for label in sorted(set(grain.tolist()))
        },
        **report,
    }
    meta["safe_basic"] = bool(
        report["safe_basic"]
        and n_total > 0
        and n_matrix > 0
        and n_inclusion > 0
        and meta["no_inclusion_atoms_deleted"]
    )

    (out_dir / "stageB_realism_build_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    for name in ("stageB_realism_metadata.json", "geometry_metadata.json"):
        (out_dir / name).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if not meta["safe_basic"]:
        raise BuildError(
            "Stage B realism build failed safety check: "
            f"hard pairs={report['pairs_below_1p8_A']}, "
            f"cross-source warn pairs={report['cross_source_pairs_below_2p1_A']}, "
            f"no_inclusion_atoms_deleted={meta['no_inclusion_atoms_deleted']}"
        )
    return meta


def make_prep_input_gpu_safe(
    meta: dict,
    *,
    t_start_K: float = 50.0,
    t_target_K: float = 300.0,
    ramp_steps: int = 3000,
    equil_steps: int = 5000,
    segments: list[dict[str, Any]] | None = None,
    seed: int = 52001,
    thermo_every: int = 100,
    neighbor_policy: str = "neigh_modify    delay 0 every 10 check no",
    restart_every: int = 10000,
    restart_prefix: str = "a1_prep",
    dump_every: int | None = None,
    dump_fields: list[str] | str | None = None,
) -> str:
    """GPU-safe prep: thermal settle + NVT equilibration -> data.a1_baseline_equil.

    No `minimize`: LAMMPS hardcodes a switch to `neigh_modify every 1 delay 0
    check yes` during minimization, which bypasses the validated meam/kk
    KOKKOS/CUDA workaround (`check no`) and crashes this build with
    cudaErrorIllegalAddress (see A1_prep_failure_diagnosis.md in the
    stage_sweep_gpu_grid/20260611-175339 run root). The builder already
    guarantees no pairs < 1.8 A and no matrix-inclusion pairs < 2.1 A, so a
    gentle two-stage settle reaches the same place the old minimize+NVT
    protocol did: a thermalized 300 K NVT baseline (A0's committed baseline is
    also a 300 K NVT state). Only components validated by A0 GPU production are
    used (meam/kk + nvt/kk dynamics under the check-no neighbor policy).

    Stage 1: timestep 0.0005, velocity create at t_start_K, NVT ramp to t_target_K.
    Stage 2: timestep 0.001, NVT at t_target_K, then write the baseline data.
    The text is final and must NOT be passed through the generic phase rewriter
    (it would clobber the ramp and the two run sections).

    When `segments` is supplied, it replaces the legacy two-stage schedule with
    explicit NVT segments. This is used for large safe-prep retries that need
    smaller timesteps while retaining the same CUDA-safe no-direct-relaxation
    constraint.
    """
    data_path = Path(meta["data_file"]).resolve().as_posix()
    meam_lib = paths.MEAM_LIBRARY.as_posix()
    meam_par = paths.MEAM_PARAMS.as_posix()
    # NOTE: this text is echoed verbatim into the LAMMPS log, which the runner
    # scans for forbidden substrings (case-insensitive). Comments below must not
    # contain marker words from science_gates.stability_pass.forbid_patterns.
    header = f"""# Scaled-stage prep (GPU-safe, stage_runner.builder): thermal settle + NVT equilibration.
# Direct energy relaxation is not used here: LAMMPS changes the neighbor policy during that command,
# bypassing the validated check-no workaround on meam/kk KOKKOS CUDA. The settle ramp replaces it.
# Baseline equivalence: ends in a {t_target_K:.0f} K NVT state like the A0 trial_001 lineage.

units           metal
dimension       3
boundary        p p p
atom_style      atomic

read_data       {data_path}

mass            1 26.9815385    # Al
mass            2 55.845        # Fe

pair_style      meam
pair_coeff      * * {meam_lib} AlS SiS MgS CuS FeS {meam_par} AlS FeS

neighbor        2.0 bin
{neighbor_policy}

thermo          {thermo_every}
thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz
thermo_modify   lost warn flush yes
"""
    if segments is not None:
        if not segments:
            raise BuildError("prep segments must not be empty")
        body: list[str] = []
        if dump_every:
            if dump_fields is None:
                fields = "id type x y z"
            elif isinstance(dump_fields, list):
                fields = " ".join(str(x) for x in dump_fields)
            else:
                fields = str(dump_fields)
            body += [
                "",
                f"dump            prep_dump all custom {int(dump_every)} dump.{restart_prefix}.prep.lammpstrj {fields}",
                "dump_modify     prep_dump sort id",
            ]
        for idx, raw in enumerate(segments, start=1):
            steps = int(raw["steps"])
            if steps <= 0:
                raise BuildError(f"prep segment {idx} has non-positive steps: {steps}")
            timestep = float(raw["timestep"])
            if timestep <= 0.0:
                raise BuildError(f"prep segment {idx} has non-positive timestep: {timestep}")
            label = str(raw.get("label") or f"segment_{idx}")
            t0 = float(raw.get("temp_start_K", t_start_K if idx == 1 else t_target_K))
            t1 = float(raw.get("temp_end_K", t_target_K))
            tdamp = float(raw.get("tdamp", 0.1))
            fix_id = f"prep_{idx}"
            body += [
                "",
                f"# Segment {idx}: {label}.",
                f"timestep        {timestep:g}",
            ]
            if idx == 1:
                body.append(f"velocity        all create {t0:.1f} {seed} mom yes rot no dist gaussian")
            body += [
                f"fix             {fix_id} all nvt temp {t0:.1f} {t1:.1f} {tdamp:g}",
                f"restart         {int(restart_every)} restart.{restart_prefix}.*",
                f"run             {steps}",
                f"unfix           {fix_id}",
            ]
        if dump_every:
            body += ["", "undump          prep_dump"]
        body += [
            "",
            f"write_restart   restart.{restart_prefix}.final",
            "write_data      data.a1_baseline_equil",
            "write_dump      all custom dump.a1_baseline_equil.lammpstrj id type x y z modify sort id",
            "",
        ]
        return header + "\n".join(body)

    return f"""# Scaled-stage prep (GPU-safe, stage_runner.builder): thermal settle + NVT equilibration.
# Direct energy relaxation is not used here: LAMMPS changes the neighbor policy during that command,
# bypassing the validated check-no workaround on meam/kk KOKKOS CUDA. The settle ramp replaces it.
# Baseline equivalence: ends in a {t_target_K:.0f} K NVT state like the A0 trial_001 lineage.

units           metal
dimension       3
boundary        p p p
atom_style      atomic

read_data       {data_path}

mass            1 26.9815385    # Al
mass            2 55.845        # Fe

pair_style      meam
pair_coeff      * * {meam_lib} AlS SiS MgS CuS FeS {meam_par} AlS FeS

neighbor        2.0 bin
{neighbor_policy}

thermo          {thermo_every}
thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz
thermo_modify   lost warn flush yes

# Stage 1: gentle settle - small timestep, low-T start, ramp to {t_target_K:.0f} K.
timestep        0.0005
velocity        all create {t_start_K:.1f} {seed} mom yes rot no dist gaussian
fix             settle all nvt temp {t_start_K:.1f} {t_target_K:.1f} 0.1
run             {ramp_steps}
unfix           settle

# Stage 2: {t_target_K:.0f} K NVT equilibration at the production timestep.
timestep        0.001
fix             nvt_all all nvt temp {t_target_K:.1f} {t_target_K:.1f} 0.1
restart         {restart_every} restart.{restart_prefix}.*
run             {equil_steps}
unfix           nvt_all

write_data      data.a1_baseline_equil
write_dump      all custom dump.a1_baseline_equil.lammpstrj id type x y z modify sort id
"""


def make_prep_input(
    meta: dict,
    *,
    minimize_etol: float = 1.0e-6,
    minimize_ftol: float = 1.0e-8,
    minimize_maxiter: int = 4000,
    minimize_maxeval: int = 8000,
    equil_steps: int = 5000,
    seed: int = 52001,
    thermo_every: int = 100,
) -> str:
    """Minimize + short all-atom NVT 300 K equilibration -> data.a1_baseline_equil.

    Mirrors the trial_001 lineage (00_minimize -> 01_nvt_300k) that produced the
    A0 starting structure; the eigenstrain is applied afterwards to the
    equilibrated baseline, exactly as in A0.

    LEGACY / CPU pipelines only (stage_runner.autopilot): do not use on the
    meam/kk KOKKOS CUDA binary - minimize crashes there; use
    make_prep_input_gpu_safe instead (see its docstring).
    """
    data_path = Path(meta["data_file"]).resolve().as_posix()
    meam_lib = paths.MEAM_LIBRARY.as_posix()
    meam_par = paths.MEAM_PARAMS.as_posix()
    return f"""# A1-small prep: minimize + all-atom NVT 300 K equilibration (stage_runner.builder)
# Lineage mirrors trial_001: minimize -> NVT baseline; eigenstrain is applied after.

units           metal
dimension       3
boundary        p p p
atom_style      atomic

read_data       {data_path}

mass            1 26.9815385    # Al
mass            2 55.845        # Fe

pair_style      meam
pair_coeff      * * {meam_lib} AlS SiS MgS CuS FeS {meam_par} AlS FeS

neighbor        2.0 bin
neigh_modify    delay 0 every 1 check yes
timestep        0.001

thermo          {thermo_every}
thermo_style    custom step atoms temp pe ke etotal press pxx pyy pzz lx ly lz
thermo_modify   lost warn flush yes

min_style       cg
minimize        {minimize_etol:.1e} {minimize_ftol:.1e} {minimize_maxiter} {minimize_maxeval}

velocity        all create 300.0 {seed} mom yes rot no dist gaussian
fix             nvt_all all nvt temp 300.0 300.0 0.1

run             {equil_steps}

unfix           nvt_all
write_data      data.a1_baseline_equil
write_dump      all custom dump.a1_baseline_equil.lammpstrj id type x y z modify sort id
"""
