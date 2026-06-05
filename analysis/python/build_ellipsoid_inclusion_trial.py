#!/usr/bin/env python3

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


ROOT = Path(__file__).resolve().parents[2]

OUT_DIR = ROOT / "structures/interface/ellipsoid_inclusion/trial_001"
OUT_DATA = OUT_DIR / "data.ellipsoid_trial_001"
OUT_XYZ = OUT_DIR / "ellipsoid_trial_001.xyz"
OUT_META = OUT_DIR / "ellipsoid_trial_001_metadata.json"
OUT_REPORT = OUT_DIR / "ellipsoid_trial_001_build_report.json"

AL13FE4_DATA = ROOT / "structures/converted/Al13Fe4/al13fe4.data"

AL_A = 4.05

# ВАЖНО: размеры box кратны Al lattice constant.
# Это убирает 0.9 A periodic overlap на границах.
NX, NY, NZ = 16, 16, 24
BOX = np.array([NX * AL_A, NY * AL_A, NZ * AL_A], dtype=float)
CENTER = BOX / 2.0

# Первый аккуратный эллипсоид.
AXES = np.array([12.0, 12.0, 24.0], dtype=float)

# Насколько расширяем полость в Al вокруг включения.
CLEARANCE = 2.20

MIN_DISTANCE_HARD = 1.80
MIN_DISTANCE_WARN = 2.10


def ellipsoid_value(pos: np.ndarray, center: np.ndarray, axes: np.ndarray) -> np.ndarray:
    d = (pos - center) / axes
    return np.sum(d * d, axis=1)


def parse_lammps_atomic_data(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Reads a minimal LAMMPS atomic data file.

    Returns:
      symbols: array[str], Al/Fe
      positions: Nx3 float
      cell_vectors: 3x3 float, restricted triclinic vectors if present
    """
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()

    xlo = xhi = ylo = yhi = zlo = zhi = None
    xy = xz = yz = 0.0

    masses = {}
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
        raise RuntimeError(f"Could not parse box bounds from {path}")
    if atoms_start is None:
        raise RuntimeError(f"Could not find Atoms section in {path}")

    a_vec = np.array([xhi - xlo, 0.0, 0.0])
    b_vec = np.array([xy, yhi - ylo, 0.0])
    c_vec = np.array([xz, yz, zhi - zlo])
    cell = np.vstack([a_vec, b_vec, c_vec])

    atom_types = []
    positions = []

    for line in text[atoms_start:]:
        s = line.strip()
        if not s:
            continue
        if s[0].isalpha():
            break

        parts = s.split()
        if len(parts) < 5:
            continue

        atom_type = int(parts[1])
        x, y, z = map(float, parts[2:5])
        atom_types.append(atom_type)
        positions.append([x, y, z])

    atom_types = np.array(atom_types, dtype=int)
    positions = np.array(positions, dtype=float)

    # В проекте уже принято: type 1 = Al, type 2 = Fe.
    symbols = np.where(atom_types == 1, "Al", "Fe")

    return symbols, positions, cell


def build_al_matrix() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    basis = np.array([
        [0.0, 0.0, 0.0],
        [0.5, 0.5, 0.0],
        [0.5, 0.0, 0.5],
        [0.0, 0.5, 0.5],
    ]) * AL_A

    positions = []
    for i in range(NX):
        for j in range(NY):
            for k in range(NZ):
                origin = np.array([i, j, k], dtype=float) * AL_A
                for b in basis:
                    positions.append(origin + b)

    positions = np.array(positions, dtype=float)
    symbols = np.array(["Al"] * len(positions), dtype=object)
    source = np.array(["matrix"] * len(positions), dtype=object)
    return symbols, positions, source


def build_fe4al13_ellipsoid() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    symbols0, pos0, cell0 = parse_lammps_atomic_data(AL13FE4_DATA)

    # Repeat Fe4Al13 crystal enough to cover the ellipsoid volume.
    cell_lengths = np.linalg.norm(cell0, axis=1)
    reps = np.ceil((2.0 * AXES + 10.0) / cell_lengths).astype(int) + 2
    reps = np.maximum(reps, 3)

    all_symbols = []
    all_pos = []

    for i in range(int(reps[0])):
        for j in range(int(reps[1])):
            for k in range(int(reps[2])):
                shift = i * cell0[0] + j * cell0[1] + k * cell0[2]
                all_symbols.append(symbols0)
                all_pos.append(pos0 + shift)

    symbols = np.concatenate(all_symbols)
    pos = np.vstack(all_pos)

    # Center repeated crystal around target center.
    current_center = 0.5 * (pos.min(axis=0) + pos.max(axis=0))
    pos = pos + (CENTER - current_center)

    mask = ellipsoid_value(pos, CENTER, AXES) <= 1.0
    symbols = symbols[mask]
    pos = pos[mask]

    source = np.array(["inclusion"] * len(pos), dtype=object)
    return symbols, pos, source


def periodic_delta(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    d = a - b
    d -= BOX * np.round(d / BOX)
    return d


def remove_al_cavity(al_symbols: np.ndarray, al_pos: np.ndarray, al_source: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cavity_axes = AXES + CLEARANCE
    keep = ellipsoid_value(al_pos, CENTER, cavity_axes) > 1.0
    return al_symbols[keep], al_pos[keep], al_source[keep]


def remove_matrix_atoms_near_inclusion(
    symbols: np.ndarray,
    pos: np.ndarray,
    source: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    matrix_idx = np.where(source == "matrix")[0]
    inclusion_idx = np.where(source == "inclusion")[0]

    if len(matrix_idx) == 0 or len(inclusion_idx) == 0:
        return symbols, pos, source, {"removed_matrix_atoms_near_inclusion": 0}

    tree_inc = cKDTree(pos[inclusion_idx], boxsize=BOX)
    near = tree_inc.query_ball_point(pos[matrix_idx], r=MIN_DISTANCE_WARN)

    remove_matrix_local = [i for i, hits in enumerate(near) if len(hits) > 0]
    remove_global = set(matrix_idx[remove_matrix_local].tolist())

    keep = np.array([i not in remove_global for i in range(len(pos))], dtype=bool)

    return (
        symbols[keep],
        pos[keep],
        source[keep],
        {"removed_matrix_atoms_near_inclusion": len(remove_global)},
    )


def distance_report(symbols: np.ndarray, pos: np.ndarray, source: np.ndarray) -> dict:
    tree = cKDTree(pos, boxsize=BOX)
    pairs = tree.query_pairs(r=MIN_DISTANCE_WARN)

    warn_pairs = []
    hard_pairs = []
    min_d = None

    for i, j in pairs:
        d = float(np.linalg.norm(periodic_delta(pos[i], pos[j])))
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
        if d < MIN_DISTANCE_HARD:
            hard_pairs.append(item)

    cross_pairs = [
        p for p in warn_pairs
        if p["source_i"] != p["source_j"]
    ]

    report = {
        "total_atoms": int(len(pos)),
        "al_atoms": int(np.sum(symbols == "Al")),
        "fe_atoms": int(np.sum(symbols == "Fe")),
        "matrix_atoms": int(np.sum(source == "matrix")),
        "inclusion_atoms": int(np.sum(source == "inclusion")),
        "box_A": BOX.tolist(),
        "center_A": CENTER.tolist(),
        "ellipsoid_axes_A": AXES.tolist(),
        "clearance_A": CLEARANCE,
        "pairs_below_2p1_A": int(len(warn_pairs)),
        "pairs_below_1p8_A": int(len(hard_pairs)),
        "cross_source_pairs_below_2p1_A": int(len(cross_pairs)),
        "min_pair_distance_A": min_d,
        "warning_pairs_preview": warn_pairs[:30],
    }

    return report


def write_lammps_data(path: Path, symbols: np.ndarray, pos: np.ndarray) -> None:
    # Force clean type convention:
    # 1 = Al
    # 2 = Fe
    type_map = {"Al": 1, "Fe": 2}

    with path.open("w", encoding="utf-8") as f:
        f.write("LAMMPS data file for ellipsoid_trial_001; written by custom builder\n\n")
        f.write(f"{len(pos)} atoms\n")
        f.write("2 atom types\n\n")
        f.write(f"0.0 {BOX[0]:.16f} xlo xhi\n")
        f.write(f"0.0 {BOX[1]:.16f} ylo yhi\n")
        f.write(f"0.0 {BOX[2]:.16f} zlo zhi\n\n")

        f.write("Masses\n\n")
        f.write("1 26.9815385 # Al\n")
        f.write("2 55.845 # Fe\n\n")

        f.write("Atoms # atomic\n\n")
        for idx, (sym, xyz) in enumerate(zip(symbols, pos), start=1):
            atom_type = type_map[str(sym)]
            x, y, z = xyz
            f.write(f"{idx} {atom_type} {x:.16f} {y:.16f} {z:.16f}\n")


def write_xyz(path: Path, symbols: np.ndarray, pos: np.ndarray) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write(f"{len(pos)}\n")
        f.write("ellipsoid_trial_001 Al matrix + Fe4Al13 inclusion\n")
        for sym, xyz in zip(symbols, pos):
            f.write(f"{sym} {xyz[0]:.16f} {xyz[1]:.16f} {xyz[2]:.16f}\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    al_symbols, al_pos, al_source = build_al_matrix()
    inc_symbols, inc_pos, inc_source = build_fe4al13_ellipsoid()

    al_symbols, al_pos, al_source = remove_al_cavity(al_symbols, al_pos, al_source)

    symbols = np.concatenate([al_symbols, inc_symbols])
    pos = np.vstack([al_pos, inc_pos])
    source = np.concatenate([al_source, inc_source])

    symbols, pos, source, cleanup = remove_matrix_atoms_near_inclusion(symbols, pos, source)

    # Wrap all atoms safely into box.
    pos = pos % BOX

    # Sort: matrix Al first, inclusion Al, inclusion Fe.
    rank = np.array([
        0 if (src == "matrix" and sym == "Al") else
        1 if (src == "inclusion" and sym == "Al") else
        2
        for sym, src in zip(symbols, source)
    ])
    order = np.lexsort((pos[:, 2], pos[:, 1], pos[:, 0], rank))
    symbols = symbols[order]
    pos = pos[order]
    source = source[order]

    report = distance_report(symbols, pos, source)
    report.update(cleanup)
    report["safe_basic"] = (
        report["pairs_below_1p8_A"] == 0
        and report["cross_source_pairs_below_2p1_A"] == 0
    )
    report["notes"] = [
        "Corrected trial_001 builder: custom LAMMPS writer, no atom type 0.",
        "Box dimensions are exact multiples of Al FCC lattice constant to avoid periodic boundary hard overlaps.",
        "This is geometry/sanity prototype, not final physical validation.",
    ]

    metadata = {
        "model": "Al matrix with Fe4Al13 ellipsoidal inclusion",
        "trial": "ellipsoid_trial_001",
        "box_A": BOX.tolist(),
        "center_A": CENTER.tolist(),
        "ellipsoid_axes_A": AXES.tolist(),
        "al_lattice_A": AL_A,
        "type_mapping": {"1": "Al", "2": "Fe"},
        "source_fe4al13": str(AL13FE4_DATA.relative_to(ROOT)),
        "boundary_recommendation": "p p p",
        "status": "rebuilt with corrected type mapping and periodic-compatible Al box",
    }

    write_lammps_data(OUT_DATA, symbols, pos)
    write_xyz(OUT_XYZ, symbols, pos)
    OUT_META.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    OUT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Saved: {OUT_DATA}")
    print(f"Saved: {OUT_XYZ}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
