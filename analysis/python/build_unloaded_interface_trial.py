#!/usr/bin/env python3
"""Build an unloaded Al / Al13Fe4 flat-interface trial structure.

The script builds only an initial geometry for minimization. It does not apply
external stress and does not write any stress-scenario input.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

import build_flat_interface as match


Vector = tuple[float, float, float]
Matrix3 = tuple[Vector, Vector, Vector]


@dataclass(frozen=True)
class Atom:
    atom_id: int
    atom_type: int
    phase: str
    position: Vector


@dataclass(frozen=True)
class BasisAtom:
    atom_type: int
    frac: Vector


@dataclass(frozen=True)
class BulkBasis:
    name: str
    cell: Matrix3
    atoms: list[BasisAtom]


def matrix_vector_add(a: tuple[int, int, int], b: tuple[int, int, int]) -> tuple[int, int, int]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def matrix_vector_scale(s: int, a: tuple[int, int, int]) -> tuple[int, int, int]:
    return (s * a[0], s * a[1], s * a[2])


def coeff_from_surface_matrix(
    surface_coeff1: tuple[int, int, int],
    surface_coeff2: tuple[int, int, int],
    matrix_2d: tuple[tuple[int, int], tuple[int, int]],
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    out = []
    for row in matrix_2d:
        out.append(
            matrix_vector_add(
                matrix_vector_scale(row[0], surface_coeff1),
                matrix_vector_scale(row[1], surface_coeff2),
            )
        )
    return out[0], out[1]


def determinant3(rows: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]) -> int:
    a, b, c = rows
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def inverse3(matrix: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    a, b, c = matrix
    det = (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )
    if abs(det) < 1.0e-12:
        raise ValueError("Singular matrix")
    return (
        (
            (b[1] * c[2] - b[2] * c[1]) / det,
            (a[2] * c[1] - a[1] * c[2]) / det,
            (a[1] * b[2] - a[2] * b[1]) / det,
        ),
        (
            (b[2] * c[0] - b[0] * c[2]) / det,
            (a[0] * c[2] - a[2] * c[0]) / det,
            (a[2] * b[0] - a[0] * b[2]) / det,
        ),
        (
            (b[0] * c[1] - b[1] * c[0]) / det,
            (a[1] * c[0] - a[0] * c[1]) / det,
            (a[0] * b[1] - a[1] * b[0]) / det,
        ),
    )


def row_times_matrix(row: Vector, matrix: Matrix3) -> Vector:
    return (
        row[0] * matrix[0][0] + row[1] * matrix[1][0] + row[2] * matrix[2][0],
        row[0] * matrix[0][1] + row[1] * matrix[1][1] + row[2] * matrix[2][1],
        row[0] * matrix[0][2] + row[1] * matrix[1][2] + row[2] * matrix[2][2],
    )


def frac_to_cart(frac: Vector, cell: Matrix3) -> Vector:
    return row_times_matrix(frac, cell)


def cart_to_frac(cart: Vector, cell: Matrix3) -> Vector:
    return row_times_matrix(cart, inverse3(cell))


def wrap01(value: float) -> float:
    wrapped = value - math.floor(value)
    if wrapped >= 1.0 - 1.0e-10:
        return 0.0
    return wrapped


def parse_lammps_basis(path: Path) -> BulkBasis:
    lines = path.read_text().splitlines()
    info = match.parse_lammps_data(path)
    origin = [0.0, 0.0, 0.0]
    for line in lines:
        parts = line.split()
        if line.strip().endswith("xlo xhi"):
            origin[0] = float(parts[0])
        elif line.strip().endswith("ylo yhi"):
            origin[1] = float(parts[0])
        elif line.strip().endswith("zlo zhi"):
            origin[2] = float(parts[0])

    atoms: list[BasisAtom] = []
    in_atoms = False
    read_atoms = 0
    for line in lines:
        if line.startswith("Atoms"):
            in_atoms = True
            continue
        if not in_atoms or read_atoms >= info.n_atoms:
            continue
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 5 and parts[0].lstrip("-").isdigit():
            atom_type = int(parts[1])
            cart = (float(parts[2]) - origin[0], float(parts[3]) - origin[1], float(parts[4]) - origin[2])
            frac = cart_to_frac(cart, info.cell)
            atoms.append(BasisAtom(atom_type=atom_type, frac=(wrap01(frac[0]), wrap01(frac[1]), wrap01(frac[2]))))
            read_atoms += 1

    if read_atoms != info.n_atoms:
        raise ValueError(f"Read {read_atoms} atoms from {path}, expected {info.n_atoms}")
    return BulkBasis(name=path.name, cell=info.cell, atoms=atoms)


def fcc_al_primitive_basis(al_data: Path) -> tuple[BulkBasis, int, float, Matrix3]:
    info = match.parse_lammps_data(al_data)
    conventional_cell, repeat, lattice_a = match.infer_al_conventional_cell(info)
    primitive_cell = match.fcc_primitive_translations(conventional_cell)
    return BulkBasis(name="Al fcc primitive from relaxed Al", cell=primitive_cell, atoms=[BasisAtom(1, (0.0, 0.0, 0.0))]), repeat, lattice_a, conventional_cell


def find_normal_coeff(
    hkl: tuple[int, int, int],
    normal_cell: Matrix3,
    translation_basis: Matrix3,
    inplane1: tuple[int, int, int],
    inplane2: tuple[int, int, int],
    repeats: int,
    max_coeff: int = 4,
) -> tuple[int, int, int]:
    normal = match.normal_from_hkl(normal_cell, hkl)
    best: tuple[float, tuple[int, int, int]] | None = None
    for coeff in ((i, j, k) for i in range(-max_coeff, max_coeff + 1) for j in range(-max_coeff, max_coeff + 1) for k in range(-max_coeff, max_coeff + 1)):
        if coeff == (0, 0, 0):
            continue
        det = abs(determinant3((inplane1, inplane2, coeff)))
        if det == 0:
            continue
        vec = match.vector_from_coeffs(coeff, translation_basis)
        vec_norm = match.norm(vec)
        if vec_norm < 1.0e-10:
            continue
        alignment = abs(match.dot(vec, normal)) / (vec_norm * match.norm(normal))
        if alignment < 0.25:
            continue
        if match.dot(vec, normal) < 0:
            coeff = (-coeff[0], -coeff[1], -coeff[2])
            vec = match.scale(-1.0, vec)
        score = (1.0 - alignment) * 100.0 + 0.01 * vec_norm + 0.002 * det
        if best is None or score < best[0]:
            best = (score, coeff)
    if best is None:
        raise ValueError(f"Could not find normal coefficient for hkl={hkl}")
    coeff = best[1]
    return (coeff[0] * repeats, coeff[1] * repeats, coeff[2] * repeats)


def build_supercell_atoms(
    basis: BulkBasis,
    transform: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]],
) -> tuple[list[tuple[int, Vector, Vector]], Matrix3]:
    det = abs(determinant3(transform))
    if det == 0:
        raise ValueError("Integer transform is singular")
    transform_float = tuple(tuple(float(x) for x in row) for row in transform)  # type: ignore[assignment]
    inv_transform = inverse3(transform_float)
    new_cell = tuple(match.vector_from_coeffs(row, basis.cell) for row in transform)  # type: ignore[assignment]

    corners = []
    for i in (0, 1):
        for j in (0, 1):
            for k in (0, 1):
                corners.append(
                    (
                        i * transform[0][0] + j * transform[1][0] + k * transform[2][0],
                        i * transform[0][1] + j * transform[1][1] + k * transform[2][1],
                        i * transform[0][2] + j * transform[1][2] + k * transform[2][2],
                    )
                )
    mins = [math.floor(min(c[i] for c in corners)) - 1 for i in range(3)]
    maxs = [math.ceil(max(c[i] for c in corners)) + 1 for i in range(3)]

    atoms: list[tuple[int, Vector, Vector]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for tx in range(mins[0], maxs[0] + 1):
        for ty in range(mins[1], maxs[1] + 1):
            for tz in range(mins[2], maxs[2] + 1):
                for atom_index, atom in enumerate(basis.atoms):
                    base_frac = (atom.frac[0] + tx, atom.frac[1] + ty, atom.frac[2] + tz)
                    new_frac = row_times_matrix(base_frac, inv_transform)
                    if all(-1.0e-9 <= value < 1.0 - 1.0e-9 for value in new_frac):
                        wrapped = (wrap01(new_frac[0]), wrap01(new_frac[1]), wrap01(new_frac[2]))
                        key = (
                            atom_index,
                            round(wrapped[0] * 1.0e8),
                            round(wrapped[1] * 1.0e8),
                            round(wrapped[2] * 1.0e8),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        atoms.append((atom.atom_type, wrapped, frac_to_cart(wrapped, new_cell)))

    expected = det * len(basis.atoms)
    if len(atoms) != expected:
        raise ValueError(f"Built {len(atoms)} atoms for {basis.name}, expected {expected}")
    return atoms, new_cell


def normalize_inplane_transform(
    transform: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]],
    cell: Matrix3,
) -> tuple[tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]], tuple[Vector, Vector]]:
    rows = [transform[0], transform[1]]
    vectors = [match.vector_from_coeffs(rows[0], cell), match.vector_from_coeffs(rows[1], cell)]
    if match.norm(vectors[1]) < match.norm(vectors[0]):
        rows = [rows[1], rows[0]]
        vectors = [vectors[1], vectors[0]]
    if match.angle_deg(vectors[0], vectors[1]) > 90.0:
        rows[1] = (-rows[1][0], -rows[1][1], -rows[1][2])
        vectors[1] = match.scale(-1.0, vectors[1])
    return (rows[0], rows[1], transform[2]), (vectors[0], vectors[1])


def projected_atoms(
    raw_atoms: list[tuple[int, Vector, Vector]],
    raw_cell: Matrix3,
    target_v1: Vector,
    target_v2: Vector,
    z_offset: float,
    phase: str,
    atom_id_start: int,
    lateral_shift: tuple[float, float] = (0.0, 0.0),
) -> tuple[list[Atom], float]:
    normal = match.cross(raw_cell[0], raw_cell[1])
    normal = match.scale(1.0 / match.norm(normal), normal)
    z_values = [match.dot(cart, normal) for _, _, cart in raw_atoms]
    z_min = min(z_values)
    z_max = max(z_values)
    atoms: list[Atom] = []
    for offset, ((atom_type, frac, _cart), z_value) in enumerate(zip(raw_atoms, z_values), start=0):
        f1 = wrap01(frac[0] + lateral_shift[0])
        f2 = wrap01(frac[1] + lateral_shift[1])
        inplane = match.add(match.scale(f1, target_v1), match.scale(f2, target_v2))
        position = (inplane[0], inplane[1], z_offset + (z_value - z_min))
        atoms.append(Atom(atom_id=atom_id_start + offset, atom_type=atom_type, phase=phase, position=position))
    return atoms, z_max - z_min


def pair_distance_2d_periodic(a: Vector, b: Vector, cell_v1: Vector, cell_v2: Vector) -> float:
    best = float("inf")
    base = match.sub(a, b)
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            delta = match.add(base, match.add(match.scale(i, cell_v1), match.scale(j, cell_v2)))
            dist = match.norm(delta)
            if dist < best:
                best = dist
    return best


def distance_report(atoms: list[Atom], cell_v1: Vector, cell_v2: Vector, hard_threshold: float, al_fe_warning: float) -> dict[str, object]:
    min_al_al = float("inf")
    min_fe_fe = float("inf")
    min_al_fe = float("inf")
    min_cross_slab = float("inf")
    al_fe_below_warning = 0
    any_below_hard = 0
    cross_below_hard = 0
    cross_below_warning = 0
    closest_pair: dict[str, object] | None = None

    for idx, atom_i in enumerate(atoms):
        for atom_j in atoms[idx + 1 :]:
            dist = pair_distance_2d_periodic(atom_i.position, atom_j.position, cell_v1, cell_v2)
            if dist < hard_threshold:
                any_below_hard += 1
            if atom_i.phase != atom_j.phase:
                min_cross_slab = min(min_cross_slab, dist)
                if dist < hard_threshold:
                    cross_below_hard += 1
                if dist < al_fe_warning:
                    cross_below_warning += 1
            pair_types = {atom_i.atom_type, atom_j.atom_type}
            if pair_types == {1}:
                min_al_al = min(min_al_al, dist)
            elif pair_types == {2}:
                min_fe_fe = min(min_fe_fe, dist)
            else:
                min_al_fe = min(min_al_fe, dist)
                if dist < al_fe_warning:
                    al_fe_below_warning += 1
            if closest_pair is None or dist < float(closest_pair["distance_A"]):
                closest_pair = {
                    "distance_A": dist,
                    "atom_i": atom_i.atom_id,
                    "atom_j": atom_j.atom_id,
                    "type_i": atom_i.atom_type,
                    "type_j": atom_j.atom_type,
                    "phase_i": atom_i.phase,
                    "phase_j": atom_j.phase,
                }

    return {
        "minimum_Al_Al_distance_A": min_al_al,
        "minimum_Fe_Fe_distance_A": min_fe_fe,
        "minimum_Al_Fe_distance_A": min_al_fe,
        "minimum_cross_slab_distance_A": min_cross_slab,
        "Al_Fe_pairs_below_warning_threshold": al_fe_below_warning,
        "cross_slab_pairs_below_warning_threshold": cross_below_warning,
        "any_pairs_below_hard_overlap_threshold": any_below_hard,
        "cross_slab_pairs_below_hard_overlap_threshold": cross_below_hard,
        "closest_pair": closest_pair,
        "safe_to_write_lammps_data": any_below_hard == 0 and cross_below_warning == 0,
    }


def cross_slab_quick_report(
    al_atoms: list[Atom],
    fe_atoms: list[Atom],
    cell_v1: Vector,
    cell_v2: Vector,
    hard_threshold: float,
    warning_threshold: float,
) -> dict[str, object]:
    al_pos = np.array([atom.position for atom in al_atoms], dtype=float)
    fe_pos = np.array([atom.position for atom in fe_atoms], dtype=float)
    best_sq = np.full((len(al_atoms), len(fe_atoms)), np.inf)
    v1 = np.array(cell_v1, dtype=float)
    v2 = np.array(cell_v2, dtype=float)
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            shift = i * v1 + j * v2
            delta = al_pos[:, None, :] - fe_pos[None, :, :] + shift
            dist_sq = np.einsum("ijk,ijk->ij", delta, delta)
            best_sq = np.minimum(best_sq, dist_sq)
    distances = np.sqrt(best_sq)
    min_cross = float(np.min(distances))
    hard_count = int(np.count_nonzero(distances < hard_threshold))
    warning_count = int(np.count_nonzero(distances < warning_threshold))
    return {
        "minimum_cross_slab_distance_A": min_cross,
        "cross_slab_pairs_below_hard_overlap_threshold": hard_count,
        "cross_slab_pairs_below_warning_threshold": warning_count,
        "safe_cross_slab": hard_count == 0 and warning_count == 0,
    }


def write_lammps_data(path: Path, atoms: list[Atom], lx: float, ly: float, lz: float, xy: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "LAMMPS data file for unloaded Al / Fe4Al13 interface trial_001",
        "",
        f"{len(atoms)} atoms",
        "2 atom types",
        "",
        f"0.0 {lx:.16f} xlo xhi",
        f"0.0 {ly:.16f} ylo yhi",
        f"0.0 {lz:.16f} zlo zhi",
        f"{xy:.16f} 0.0 0.0 xy xz yz",
        "",
        "Masses",
        "",
        "1 26.9815385 # Al",
        "2 55.845 # Fe",
        "",
        "Atoms # atomic",
        "",
    ]
    for atom in atoms:
        x, y, z = atom.position
        lines.append(f"{atom.atom_id} {atom.atom_type} {x:.16f} {y:.16f} {z:.16f}")
    path.write_text("\n".join(lines) + "\n")


def reduce_tilt(v1: Vector, v2: Vector) -> tuple[Vector, Vector, int]:
    lx = v1[0]
    if abs(v1[1]) > 1.0e-10 or abs(v1[2]) > 1.0e-10 or lx <= 0:
        raise ValueError("Tilt reduction expects v1 along +x")
    shift = math.floor(v2[0] / lx + 0.5)
    reduced_v2 = match.sub(v2, match.scale(shift, v1))
    return v1, reduced_v2, shift


def wrap_atoms_to_inplane_cell(atoms: list[Atom], v1: Vector, v2: Vector) -> list[Atom]:
    lx = v1[0]
    xy = v2[0]
    ly = v2[1]
    if lx <= 0 or ly <= 0:
        raise ValueError("Invalid in-plane restricted triclinic cell")
    wrapped: list[Atom] = []
    for atom in atoms:
        x, y, z = atom.position
        s2 = y / ly
        s1 = (x - s2 * xy) / lx
        s1 = wrap01(s1)
        s2 = wrap01(s2)
        new_pos = match.add(match.scale(s1, v1), match.scale(s2, v2))
        wrapped.append(Atom(atom.atom_id, atom.atom_type, atom.phase, (new_pos[0], new_pos[1], z)))
    return wrapped


def write_blocker(path: Path, reasons: list[str], metadata: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Interface build blockers",
        "",
        "Trial `trial_001` was not written as a defensible LAMMPS data file.",
        "",
        "## Reasons",
        "",
    ]
    lines.extend(f"- {reason}" for reason in reasons)
    lines.extend(["", "## Diagnostic metadata", "", "```json", json.dumps(metadata, indent=2, ensure_ascii=False), "```"])
    path.write_text("\n".join(lines) + "\n")


def select_candidate(csv_path: Path, al_hkl: str, fe_hkl: str) -> dict[str, str]:
    with csv_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    candidates = [row for row in rows if row["al_hkl"] == al_hkl and row["fe_hkl"] == fe_hkl]
    if not candidates:
        raise ValueError(f"No mismatch candidate found for Al {al_hkl} / Fe4Al13 {fe_hkl}")
    candidates.sort(key=lambda row: int(row["rank"]))
    return candidates[0]


def count_types(atoms: Iterable[Atom]) -> dict[str, int]:
    counts = {"Al": 0, "Fe": 0}
    for atom in atoms:
        if atom.atom_type == 1:
            counts["Al"] += 1
        elif atom.atom_type == 2:
            counts["Fe"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--al-data", type=Path, default=Path("lammps/00_relax_al/data.al_npt_relaxed"))
    parser.add_argument("--fe-data", type=Path, default=Path("lammps/01_relax_al13fe4/data.al13fe4_npt_relaxed"))
    parser.add_argument("--mismatch-csv", type=Path, default=Path("results/tables/interface_mismatch_candidates.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("structures/interface/flat_interface/trial_001"))
    parser.add_argument("--blockers", type=Path, default=Path("docs/interface_build_blockers.md"))
    parser.add_argument("--al-normal-repeats", type=int, default=5)
    parser.add_argument("--fe-normal-repeats", type=int, default=2)
    parser.add_argument("--hard-overlap", type=float, default=1.8)
    parser.add_argument("--al-fe-warning", type=float, default=2.1)
    parser.add_argument("--bottom-vacuum", type=float, default=5.0)
    parser.add_argument("--top-vacuum", type=float, default=5.0)
    parser.add_argument("--shift-grid", type=int, default=5)
    args = parser.parse_args()

    candidate = select_candidate(args.mismatch_csv, "(111)", "(100)")
    al_matrix_2d = ast.literal_eval(candidate["al_matrix"])
    fe_matrix_2d = ast.literal_eval(candidate["fe_matrix"])

    al_basis, al_repeat, al_lattice_a, al_conventional_cell = fcc_al_primitive_basis(args.al_data)
    fe_basis = parse_lammps_basis(args.fe_data)

    al_surface = match.find_surface_basis("Al", (1, 1, 1), al_conventional_cell, al_basis.cell, 5)
    fe_surface = match.find_surface_basis("Fe4Al13", (1, 0, 0), fe_basis.cell, fe_basis.cell, 5)

    al_u1, al_u2 = coeff_from_surface_matrix(al_surface.source_coeff1, al_surface.source_coeff2, al_matrix_2d)
    fe_u1, fe_u2 = coeff_from_surface_matrix(fe_surface.source_coeff1, fe_surface.source_coeff2, fe_matrix_2d)

    al_u3 = find_normal_coeff((1, 1, 1), al_conventional_cell, al_basis.cell, al_u1, al_u2, args.al_normal_repeats)
    fe_u3 = find_normal_coeff((1, 0, 0), fe_basis.cell, fe_basis.cell, fe_u1, fe_u2, args.fe_normal_repeats)

    al_transform, al_vectors = normalize_inplane_transform((al_u1, al_u2, al_u3), al_basis.cell)
    fe_transform, fe_vectors = normalize_inplane_transform((fe_u1, fe_u2, fe_u3), fe_basis.cell)

    al_raw_atoms, al_raw_cell = build_supercell_atoms(al_basis, al_transform)
    fe_raw_atoms, fe_raw_cell = build_supercell_atoms(fe_basis, fe_transform)

    al_len1, al_len2 = match.norm(al_vectors[0]), match.norm(al_vectors[1])
    fe_len1, fe_len2 = match.norm(fe_vectors[0]), match.norm(fe_vectors[1])
    target_len1 = (al_len1 + fe_len1) / 2.0
    target_len2 = (al_len2 + fe_len2) / 2.0
    target_angle = (match.acute_angle_deg(al_vectors[0], al_vectors[1]) + match.acute_angle_deg(fe_vectors[0], fe_vectors[1])) / 2.0
    target_v1 = (target_len1, 0.0, 0.0)
    target_v2 = (target_len2 * math.cos(math.radians(target_angle)), target_len2 * math.sin(math.radians(target_angle)), 0.0)

    al_atoms_zero, al_thickness = projected_atoms(al_raw_atoms, al_raw_cell, target_v1, target_v2, 0.0, "Al_slab", 1)
    _fe_atoms_zero, fe_thickness = projected_atoms(fe_raw_atoms, fe_raw_cell, target_v1, target_v2, 0.0, "Fe4Al13_slab", len(al_atoms_zero) + 1)

    best: tuple[float, float, tuple[float, float], list[Atom], dict[str, object]] | None = None
    al_atoms, _ = projected_atoms(al_raw_atoms, al_raw_cell, target_v1, target_v2, args.bottom_vacuum, "Al_slab", 1)
    shift_values = [i / args.shift_grid for i in range(args.shift_grid)]
    for gap in [2.15, 2.25, 2.35, 2.45, 2.60, 2.80, 3.00, 3.25, 3.50]:
        for sx in shift_values:
            for sy in shift_values:
                fe_atoms, _ = projected_atoms(
                    fe_raw_atoms,
                    fe_raw_cell,
                    target_v1,
                    target_v2,
                    args.bottom_vacuum + al_thickness + gap,
                    "Fe4Al13_slab",
                    len(al_atoms) + 1,
                    lateral_shift=(sx, sy),
                )
                quick = cross_slab_quick_report(al_atoms, fe_atoms, target_v1, target_v2, args.hard_overlap, args.al_fe_warning)
                if not quick["safe_cross_slab"]:
                    continue
                min_cross = float(quick["minimum_cross_slab_distance_A"])
                score = abs(min_cross - 2.35) + 0.02 * gap
                if best is None or score < best[0]:
                    trial_atoms = al_atoms + fe_atoms
                    report = distance_report(trial_atoms, target_v1, target_v2, args.hard_overlap, args.al_fe_warning)
                    if report["safe_to_write_lammps_data"]:
                        best = (score, gap, (sx, sy), trial_atoms, report)

    diagnostic = {
        "candidate": candidate,
        "al_transform": al_transform,
        "fe_transform": fe_transform,
        "al_atoms_raw": len(al_raw_atoms),
        "fe_atoms_raw": len(fe_raw_atoms),
        "target_inplane": {
            "length1_A": target_len1,
            "length2_A": target_len2,
            "angle_deg": target_angle,
        },
        "thresholds": {
            "hard_overlap_A": args.hard_overlap,
            "al_fe_warning_A": args.al_fe_warning,
        },
    }

    if best is None:
        reasons = [
            "No lateral shift/gap candidate satisfied hard-overlap and cross-slab warning thresholds.",
            f"Hard overlap threshold: {args.hard_overlap} A.",
            f"Cross-slab warning threshold: {args.al_fe_warning} A.",
        ]
        write_blocker(args.blockers, reasons, diagnostic)
        print("BLOCKED: no safe interface geometry found")
        print(f"blockers: {args.blockers}")
        return 2

    _score, gap, lateral_shift, atoms, report = best
    target_v1, reduced_v2, tilt_shift = reduce_tilt(target_v1, target_v2)
    atoms = wrap_atoms_to_inplane_cell(atoms, target_v1, reduced_v2)
    report = distance_report(atoms, target_v1, reduced_v2, args.hard_overlap, args.al_fe_warning)
    if not report["safe_to_write_lammps_data"]:
        reasons = [
            "Geometry became unsafe after triclinic tilt reduction/wrapping.",
            f"Hard-overlap count: {report['any_pairs_below_hard_overlap_threshold']}.",
            f"Cross-slab warning count: {report['cross_slab_pairs_below_warning_threshold']}.",
        ]
        write_blocker(args.blockers, reasons, {**diagnostic, "post_wrap_report": report})
        print("BLOCKED: post-wrap geometry is unsafe")
        print(f"blockers: {args.blockers}")
        return 2
    total_thickness = args.bottom_vacuum + al_thickness + gap + fe_thickness + args.top_vacuum
    lx = target_v1[0]
    xy = reduced_v2[0]
    ly = reduced_v2[1]
    lz = total_thickness

    output_data = args.output_dir / "data.interface_trial"
    metadata_path = args.output_dir / "interface_metadata.json"
    report_path = args.output_dir / "min_distance_report.json"

    write_lammps_data(output_data, atoms, lx, ly, lz, xy)
    type_counts = count_types(atoms)
    metadata = {
        "trial": "trial_001",
        "created_by": "analysis/python/build_unloaded_interface_trial.py",
        "stress_applied": False,
        "candidate": {
            "al_hkl": candidate["al_hkl"],
            "fe_hkl": candidate["fe_hkl"],
            "source_max_length_mismatch_percent": float(candidate["max_len_mismatch_percent"]),
            "source_angle_delta_deg": float(candidate["angle_delta_deg"]),
            "source_estimated_atoms": int(candidate["estimated_atoms"]),
            "al_matrix": candidate["al_matrix"],
            "fe_matrix": candidate["fe_matrix"],
        },
        "actual_atoms": {
            "total": len(atoms),
            "Al_type_1": type_counts["Al"],
            "Fe_type_2": type_counts["Fe"],
            "Al_slab_atoms": len([atom for atom in atoms if atom.phase == "Al_slab"]),
            "Fe4Al13_slab_atoms": len([atom for atom in atoms if atom.phase == "Fe4Al13_slab"]),
        },
        "box": {
            "lx_A": lx,
            "ly_A": ly,
            "lz_A": lz,
            "xy_A": xy,
            "xz_A": 0.0,
            "yz_A": 0.0,
        },
        "build_parameters": {
            "al_normal_repeats": args.al_normal_repeats,
            "fe_normal_repeats": args.fe_normal_repeats,
            "interface_gap_A": gap,
            "fe_lateral_shift_fractional": lateral_shift,
            "bottom_vacuum_A": args.bottom_vacuum,
            "top_vacuum_A": args.top_vacuum,
            "z_boundary_for_lammps_input": "fixed/nonperiodic",
            "triclinic_tilt_reduction_v2_minus_n_v1": tilt_shift,
        },
        "limitations": [
            "Initial geometry only; not a validated physical interface.",
            "Fe4Al13 slab uses relaxed conventional triclinic cell surface basis without primitive centered-lattice reduction.",
            "No 120 MPa loading was applied.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    report_out = {
        **report,
        "thresholds": {
            "hard_overlap_A": args.hard_overlap,
            "al_fe_warning_A": args.al_fe_warning,
        },
    }
    report_path.write_text(json.dumps(report_out, indent=2, ensure_ascii=False) + "\n")

    print(f"output: {output_data}")
    print(f"metadata: {metadata_path}")
    print(f"distance_report: {report_path}")
    print(f"total atoms: {len(atoms)}")
    print(f"Al atom count: {type_counts['Al']}")
    print(f"Fe atom count: {type_counts['Fe']}")
    print(f"box: lx={lx:.6f} ly={ly:.6f} lz={lz:.6f} xy={xy:.6f}")
    print(f"minimum Al-Al distance: {report['minimum_Al_Al_distance_A']:.6f} A")
    print(f"minimum Fe-Fe distance: {report['minimum_Fe_Fe_distance_A']:.6f} A")
    print(f"minimum Al-Fe distance: {report['minimum_Al_Fe_distance_A']:.6f} A")
    print(f"minimum cross-slab distance: {report['minimum_cross_slab_distance_A']:.6f} A")
    print(f"Al-Fe pairs below warning threshold: {report['Al_Fe_pairs_below_warning_threshold']}")
    print(f"cross-slab pairs below warning threshold: {report['cross_slab_pairs_below_warning_threshold']}")
    print(f"any pairs below hard overlap threshold: {report['any_pairs_below_hard_overlap_threshold']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
