#!/usr/bin/env python3
"""Rank low-index Al / Al13Fe4 flat-interface lattice matches.

This script deliberately does not write a final `data.interface` file.  It only
estimates in-plane 2D supercell matches that can be reviewed before building a
physical interface model.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


Vector = tuple[float, float, float]
Matrix3 = tuple[Vector, Vector, Vector]


AL_ORIENTATIONS = [(1, 0, 0), (1, 1, 0), (1, 1, 1)]
FE_ORIENTATIONS = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]


@dataclass(frozen=True)
class LammpsDataInfo:
    path: Path
    n_atoms: int
    type_counts: dict[str, int]
    cell: Matrix3


@dataclass(frozen=True)
class SurfaceBasis:
    phase: str
    hkl: tuple[int, int, int]
    v1: Vector
    v2: Vector
    length1: float
    length2: float
    angle_deg: float
    area: float
    source_coeff1: tuple[int, int, int]
    source_coeff2: tuple[int, int, int]


@dataclass(frozen=True)
class Supercell2D:
    phase: str
    hkl: tuple[int, int, int]
    matrix: tuple[tuple[int, int], tuple[int, int]]
    det: int
    length1: float
    length2: float
    angle_deg: float
    area: float
    coeff_norm: int


def add(a: Vector, b: Vector) -> Vector:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vector, b: Vector) -> Vector:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(s: float, a: Vector) -> Vector:
    return (s * a[0], s * a[1], s * a[2])


def dot(a: Vector, b: Vector) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vector, b: Vector) -> Vector:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a: Vector) -> float:
    return math.sqrt(dot(a, a))


def angle_deg(a: Vector, b: Vector) -> float:
    denom = norm(a) * norm(b)
    if denom == 0:
        return 0.0
    cosine = max(-1.0, min(1.0, dot(a, b) / denom))
    return math.degrees(math.acos(cosine))


def acute_angle_deg(a: Vector, b: Vector) -> float:
    angle = angle_deg(a, b)
    return min(angle, 180.0 - angle)


def vector_from_coeffs(coeffs: tuple[int, int, int], basis: Matrix3) -> Vector:
    out = (0.0, 0.0, 0.0)
    for coeff, vec in zip(coeffs, basis):
        out = add(out, scale(coeff, vec))
    return out


def reciprocal_rows(cell: Matrix3) -> Matrix3:
    a, b, c = cell
    volume = dot(a, cross(b, c))
    if abs(volume) < 1.0e-12:
        raise ValueError("Cell volume is too small")
    return (
        scale(1.0 / volume, cross(b, c)),
        scale(1.0 / volume, cross(c, a)),
        scale(1.0 / volume, cross(a, b)),
    )


def normal_from_hkl(cell: Matrix3, hkl: tuple[int, int, int]) -> Vector:
    rec = reciprocal_rows(cell)
    return add(add(scale(hkl[0], rec[0]), scale(hkl[1], rec[1])), scale(hkl[2], rec[2]))


def parse_lammps_data(path: Path) -> LammpsDataInfo:
    lines = path.read_text().splitlines()
    n_atoms = None
    xlo = xhi = ylo = yhi = zlo = zhi = None
    xy = xz = yz = 0.0

    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "atoms":
            n_atoms = int(parts[0])
        elif line.strip().endswith("xlo xhi"):
            xlo, xhi = float(parts[0]), float(parts[1])
        elif line.strip().endswith("ylo yhi"):
            ylo, yhi = float(parts[0]), float(parts[1])
        elif line.strip().endswith("zlo zhi"):
            zlo, zhi = float(parts[0]), float(parts[1])
        elif line.strip().endswith("xy xz yz"):
            xy, xz, yz = float(parts[0]), float(parts[1]), float(parts[2])

    if None in (n_atoms, xlo, xhi, ylo, yhi, zlo, zhi):
        raise ValueError(f"Could not parse LAMMPS data header: {path}")

    type_counts: dict[str, int] = {}
    in_atoms = False
    read_atoms = 0
    for line in lines:
        if line.startswith("Atoms"):
            in_atoms = True
            continue
        if not in_atoms or read_atoms >= n_atoms:
            continue
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0].lstrip("-").isdigit():
            type_counts[parts[1]] = type_counts.get(parts[1], 0) + 1
            read_atoms += 1

    cell: Matrix3 = (
        (xhi - xlo, 0.0, 0.0),
        (xy, yhi - ylo, 0.0),
        (xz, yz, zhi - zlo),
    )
    return LammpsDataInfo(path=path, n_atoms=n_atoms, type_counts=type_counts, cell=cell)


def infer_al_conventional_cell(info: LammpsDataInfo) -> tuple[Matrix3, int, float]:
    cells_float = info.n_atoms / 4.0
    repeat = round(cells_float ** (1.0 / 3.0))
    if repeat <= 0 or abs(repeat**3 - cells_float) > 1.0e-6:
        # Fallback: use the whole relaxed box as a conventional cell.
        return info.cell, 1, norm(info.cell[0])
    cell = tuple(tuple(component / repeat for component in vec) for vec in info.cell)  # type: ignore[assignment]
    lengths = [norm(vec) for vec in cell]
    return cell, repeat, sum(lengths) / 3.0


def fcc_primitive_translations(conventional_cell: Matrix3) -> Matrix3:
    a, b, c = conventional_cell
    return (
        scale(0.5, add(b, c)),
        scale(0.5, add(a, c)),
        scale(0.5, add(a, b)),
    )


def find_surface_basis(
    phase: str,
    hkl: tuple[int, int, int],
    normal_cell: Matrix3,
    translation_basis: Matrix3,
    max_coeff: int,
) -> SurfaceBasis:
    normal = normal_from_hkl(normal_cell, hkl)
    normal_norm = norm(normal)
    candidates: list[tuple[float, tuple[int, int, int], Vector]] = []
    seen: set[tuple[int, int, int]] = set()

    for coeffs in itertools.product(range(-max_coeff, max_coeff + 1), repeat=3):
        if coeffs == (0, 0, 0):
            continue
        vec = vector_from_coeffs(coeffs, translation_basis)
        vec_norm = norm(vec)
        if vec_norm < 1.0e-8:
            continue
        if abs(dot(normal, vec)) > 1.0e-7 * max(1.0, normal_norm * vec_norm):
            continue
        key = tuple(round(x * 1.0e6) for x in vec)
        reverse_key = tuple(round(-x * 1.0e6) for x in vec)
        if key in seen or reverse_key in seen:
            continue
        seen.add(key)
        candidates.append((vec_norm, coeffs, vec))

    if len(candidates) < 2:
        raise ValueError(f"Could not find two in-plane vectors for {phase} {hkl}")

    candidates.sort(key=lambda item: item[0])
    best = None
    for first in candidates[:80]:
        for second in candidates[:80]:
            if first is second:
                continue
            area = norm(cross(first[2], second[2]))
            if area < 1.0e-6:
                continue
            angle = acute_angle_deg(first[2], second[2])
            # Prefer compact primitive-ish cells, but avoid very skinny bases.
            skinny_penalty = max(0.0, 35.0 - angle) + max(0.0, angle - 90.0)
            score = area + 0.05 * (first[0] + second[0]) + 0.2 * skinny_penalty
            candidate = (score, area, first, second, angle)
            if best is None or candidate < best:
                best = candidate

    if best is None:
        raise ValueError(f"Could not find non-collinear in-plane vectors for {phase} {hkl}")

    _, area, first, second, angle = best
    return SurfaceBasis(
        phase=phase,
        hkl=hkl,
        v1=first[2],
        v2=second[2],
        length1=norm(first[2]),
        length2=norm(second[2]),
        angle_deg=angle,
        area=area,
        source_coeff1=first[1],
        source_coeff2=second[1],
    )


def generate_supercells(
    basis: SurfaceBasis,
    max_entry: int,
    max_det: int,
    max_count: int,
) -> list[Supercell2D]:
    found: dict[tuple[int, float, float, float], Supercell2D] = {}
    values = range(-max_entry, max_entry + 1)
    for a, b, c, d in itertools.product(values, repeat=4):
        det = a * d - b * c
        det_abs = abs(det)
        if det_abs == 0 or det_abs > max_det:
            continue
        v1 = add(scale(a, basis.v1), scale(b, basis.v2))
        v2 = add(scale(c, basis.v1), scale(d, basis.v2))
        if norm(v1) < 1.0e-8 or norm(v2) < 1.0e-8:
            continue
        area = norm(cross(v1, v2))
        if area < 1.0e-8:
            continue
        len1, len2 = norm(v1), norm(v2)
        if len2 < len1:
            len1, len2 = len2, len1
        angle = acute_angle_deg(v1, v2)
        key = (det_abs, round(len1, 4), round(len2, 4), round(angle, 3))
        coeff_norm = abs(a) + abs(b) + abs(c) + abs(d)
        cell = Supercell2D(
            phase=basis.phase,
            hkl=basis.hkl,
            matrix=((a, b), (c, d)),
            det=det_abs,
            length1=len1,
            length2=len2,
            angle_deg=angle,
            area=area,
            coeff_norm=coeff_norm,
        )
        old = found.get(key)
        if old is None or (cell.coeff_norm, cell.matrix) < (old.coeff_norm, old.matrix):
            found[key] = cell

    cells = list(found.values())
    cells.sort(key=lambda item: (item.det, item.area, item.length2, item.coeff_norm))
    return cells[:max_count]


def mismatch_percent(a: float, b: float) -> float:
    return abs(a - b) / ((a + b) / 2.0) * 100.0


def hkl_label(hkl: tuple[int, int, int]) -> str:
    return f"({hkl[0]}{hkl[1]}{hkl[2]})"


def matrix_label(matrix: tuple[tuple[int, int], tuple[int, int]]) -> str:
    return f"[[{matrix[0][0]},{matrix[0][1]}],[{matrix[1][0]},{matrix[1][1]}]]"


def rank_matches(
    al_cells_by_hkl: dict[tuple[int, int, int], list[Supercell2D]],
    fe_cells_by_hkl: dict[tuple[int, int, int], list[Supercell2D]],
    atom_limit: int,
    al_atom_factor: int,
    fe_atom_factor: int,
    al_thickness: int,
    fe_thickness: int,
    top_per_pair: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for al_hkl in AL_ORIENTATIONS:
        for fe_hkl in FE_ORIENTATIONS:
            pair_rows: list[dict[str, object]] = []
            for al_cell in al_cells_by_hkl[al_hkl]:
                for fe_cell in fe_cells_by_hkl[fe_hkl]:
                    estimated_atoms = (
                        al_atom_factor * al_cell.det * al_thickness
                        + fe_atom_factor * fe_cell.det * fe_thickness
                    )
                    if estimated_atoms > atom_limit:
                        continue
                    m1 = mismatch_percent(al_cell.length1, fe_cell.length1)
                    m2 = mismatch_percent(al_cell.length2, fe_cell.length2)
                    area_mismatch = mismatch_percent(al_cell.area, fe_cell.area)
                    angle_delta = abs(al_cell.angle_deg - fe_cell.angle_deg)
                    max_len_mismatch = max(m1, m2)
                    if angle_delta > 15.0 or max_len_mismatch > 25.0 or area_mismatch > 80.0:
                        continue
                    score = (
                        math.sqrt(m1 * m1 + m2 * m2)
                        + angle_delta
                        + 0.2 * area_mismatch
                        + 0.0005 * estimated_atoms
                    )
                    if max_len_mismatch <= 5.0 and angle_delta <= 3.0 and area_mismatch <= 8.0:
                        status = "reasonable"
                    elif max_len_mismatch <= 10.0 and angle_delta <= 5.0 and area_mismatch <= 15.0:
                        status = "borderline"
                    else:
                        status = "poor"
                    pair_rows.append(
                        {
                            "al_hkl": hkl_label(al_hkl),
                            "fe_hkl": hkl_label(fe_hkl),
                            "al_matrix": matrix_label(al_cell.matrix),
                            "fe_matrix": matrix_label(fe_cell.matrix),
                            "al_det": al_cell.det,
                            "fe_det": fe_cell.det,
                            "al_len1_A": al_cell.length1,
                            "fe_len1_A": fe_cell.length1,
                            "mismatch1_percent": m1,
                            "al_len2_A": al_cell.length2,
                            "fe_len2_A": fe_cell.length2,
                            "mismatch2_percent": m2,
                            "max_len_mismatch_percent": max_len_mismatch,
                            "al_angle_deg": al_cell.angle_deg,
                            "fe_angle_deg": fe_cell.angle_deg,
                            "angle_delta_deg": angle_delta,
                            "al_area_A2": al_cell.area,
                            "fe_area_A2": fe_cell.area,
                            "area_mismatch_percent": area_mismatch,
                            "estimated_atoms": estimated_atoms,
                            "score": score,
                            "status": status,
                        }
                    )
            pair_rows.sort(key=lambda row: (row["score"], row["estimated_atoms"]))
            rows.extend(pair_rows[:top_per_pair])

    rows.sort(key=lambda row: (row["score"], row["estimated_atoms"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def fmt(value: object, digits: int = 3) -> str:
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "al_hkl",
        "fe_hkl",
        "al_matrix",
        "fe_matrix",
        "al_det",
        "fe_det",
        "al_len1_A",
        "fe_len1_A",
        "mismatch1_percent",
        "al_len2_A",
        "fe_len2_A",
        "mismatch2_percent",
        "max_len_mismatch_percent",
        "al_angle_deg",
        "fe_angle_deg",
        "angle_delta_deg",
        "al_area_A2",
        "fe_area_A2",
        "area_mismatch_percent",
        "estimated_atoms",
        "score",
        "status",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(
    path: Path,
    rows: list[dict[str, object]],
    surface_bases: Iterable[SurfaceBasis],
    al_info: LammpsDataInfo,
    fe_info: LammpsDataInfo,
    al_repeat: int,
    al_lattice_a: float,
    atom_limit: int,
    al_thickness: int,
    fe_thickness: int,
    max_display: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    reasonable = [row for row in rows if row["status"] == "reasonable"]
    borderline = [row for row in rows if row["status"] == "borderline"]
    best_by_pair: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row["al_hkl"]), str(row["fe_hkl"]))
        best_by_pair.setdefault(key, row)

    lines: list[str] = []
    lines.append("# Кандидаты mismatch для плоской границы Al / Fe4Al13")
    lines.append("")
    lines.append("Дата расчёта: 2026-05-09.")
    lines.append("")
    lines.append("Финальный `data.interface` этим скриптом не создаётся. Таблица нужна только для выбора ориентации и размера in-plane supercell перед отдельной сборкой ненагруженного интерфейса.")
    lines.append("")
    lines.append("## Входные структуры")
    lines.append("")
    lines.append(f"- Al: `{al_info.path}`, atoms={al_info.n_atoms}, inferred fcc repeat={al_repeat}, relaxed conventional a≈{al_lattice_a:.6f} A")
    lines.append(f"- Fe4Al13: `{fe_info.path}`, atoms={fe_info.n_atoms}, type_counts={fe_info.type_counts}")
    lines.append(f"- Atom estimate filter: `<={atom_limit}` atoms using heuristic slab thickness Al={al_thickness} conventional cells, Fe4Al13={fe_thickness} cells.")
    lines.append("")
    lines.append("## Метод и ограничения")
    lines.append("")
    lines.append("- Al surface lattice uses fcc primitive translations inferred from the relaxed Al conventional cell.")
    lines.append("- Fe4Al13 surface lattice uses the relaxed triclinic conventional LAMMPS cell; centered-lattice primitive reductions are not applied.")
    lines.append("- 2D supercells are integer 2x2 combinations of the approximate surface basis vectors.")
    lines.append("- Mismatch is reported independently for two sorted in-plane vector lengths plus the acute in-plane angle.")
    lines.append("- Reasonable means max length mismatch <= 5%, angle delta <= 3 deg, and area mismatch <= 8%.")
    lines.append("- These numbers do not validate an interface; they only rank candidates for the next explicit build step.")
    lines.append("")
    lines.append("## Approximate primitive surface bases")
    lines.append("")
    lines.append("| Phase | hkl | len1 A | len2 A | angle deg | area A^2 | coeff1 | coeff2 |")
    lines.append("|---|---|---:|---:|---:|---:|---|---|")
    for basis in surface_bases:
        lines.append(
            "| "
            + " | ".join(
                [
                    basis.phase,
                    hkl_label(basis.hkl),
                    fmt(basis.length1),
                    fmt(basis.length2),
                    fmt(basis.angle_deg),
                    fmt(basis.area),
                    str(basis.source_coeff1),
                    str(basis.source_coeff2),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Best candidate per orientation pair")
    lines.append("")
    lines.append("| Al | Fe4Al13 | status | max mismatch % | angle delta deg | area mismatch % | estimated atoms | Al matrix | Fe matrix | rank |")
    lines.append("|---|---|---|---:|---:|---:|---:|---|---|---:|")
    for al_hkl in [hkl_label(hkl) for hkl in AL_ORIENTATIONS]:
        for fe_hkl in [hkl_label(hkl) for hkl in FE_ORIENTATIONS]:
            row = best_by_pair.get((al_hkl, fe_hkl))
            if row is None:
                lines.append(f"| {al_hkl} | {fe_hkl} | no candidate |  |  |  |  |  |  |  |")
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        al_hkl,
                        fe_hkl,
                        str(row["status"]),
                        fmt(row["max_len_mismatch_percent"]),
                        fmt(row["angle_delta_deg"]),
                        fmt(row["area_mismatch_percent"]),
                        str(row["estimated_atoms"]),
                        str(row["al_matrix"]),
                        str(row["fe_matrix"]),
                        str(row["rank"]),
                    ]
                )
                + " |"
            )
    lines.append("")
    lines.append(f"## Ranked candidates, top {min(max_display, len(rows))}")
    lines.append("")
    lines.append("| Rank | Al | Fe4Al13 | status | m1 % | m2 % | angle delta | area mismatch % | atoms | Al matrix | Fe matrix | score |")
    lines.append("|---:|---|---|---|---:|---:|---:|---:|---:|---|---|---:|")
    for row in rows[:max_display]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["rank"]),
                    str(row["al_hkl"]),
                    str(row["fe_hkl"]),
                    str(row["status"]),
                    fmt(row["mismatch1_percent"]),
                    fmt(row["mismatch2_percent"]),
                    fmt(row["angle_delta_deg"]),
                    fmt(row["area_mismatch_percent"]),
                    str(row["estimated_atoms"]),
                    str(row["al_matrix"]),
                    str(row["fe_matrix"]),
                    fmt(row["score"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    if reasonable:
        best = reasonable[0]
        lines.append(
            "Есть кандидаты, проходящие численный фильтр `reasonable`. Лучший кандидат: "
            f"Al {best['al_hkl']} / Fe4Al13 {best['fe_hkl']}, "
            f"max mismatch={best['max_len_mismatch_percent']:.3f}%, "
            f"angle delta={best['angle_delta_deg']:.3f} deg, "
            f"estimated_atoms={best['estimated_atoms']}."
        )
        lines.append("Несмотря на это, `data.interface` не создан: нужен явный выбор кандидата и отдельная проверка межатомных расстояний на границе.")
    elif borderline:
        best = borderline[0]
        lines.append(
            "Строго reasonable-кандидатов нет, но есть borderline-кандидаты. Лучший borderline: "
            f"Al {best['al_hkl']} / Fe4Al13 {best['fe_hkl']}, "
            f"max mismatch={best['max_len_mismatch_percent']:.3f}%, "
            f"angle delta={best['angle_delta_deg']:.3f} deg."
        )
        lines.append("Сборку интерфейса нужно остановить до ручного решения: возможно, надо расширить supercell search или использовать primitive cell Fe4Al13.")
    else:
        lines.append("Под заданными ограничениями не найдено даже borderline-кандидатов. Блокер: нужен другой набор ориентаций, primitive reduction Fe4Al13 или больший supercell search.")
    lines.append("")
    lines.append("## Следующий шаг")
    lines.append("")
    lines.append("Выбрать один кандидат из таблицы, затем отдельным скриптом собрать ненагруженный интерфейс, проверить минимальные Al-Fe расстояния и запустить только minimization. 120 MPa пока не применять.")
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--al-data", type=Path, default=Path("lammps/00_relax_al/data.al_npt_relaxed"))
    parser.add_argument("--fe-data", type=Path, default=Path("lammps/01_relax_al13fe4/data.al13fe4_npt_relaxed"))
    parser.add_argument("--csv", type=Path, default=Path("results/tables/interface_mismatch_candidates.csv"))
    parser.add_argument("--md", type=Path, default=Path("docs/interface_mismatch_candidates.md"))
    parser.add_argument("--atom-limit", type=int, default=20_000)
    parser.add_argument("--al-thickness-cells", type=int, default=8)
    parser.add_argument("--fe-thickness-cells", type=int, default=2)
    parser.add_argument("--surface-coeff", type=int, default=5)
    parser.add_argument("--supercell-entry", type=int, default=6)
    parser.add_argument("--max-det", type=int, default=36)
    parser.add_argument("--max-supercells-per-surface", type=int, default=1200)
    parser.add_argument("--top-per-pair", type=int, default=20)
    parser.add_argument("--markdown-top", type=int, default=40)
    args = parser.parse_args()

    al_info = parse_lammps_data(args.al_data)
    fe_info = parse_lammps_data(args.fe_data)
    al_cell, al_repeat, al_lattice_a = infer_al_conventional_cell(al_info)
    al_translation_basis = fcc_primitive_translations(al_cell)
    fe_cell = fe_info.cell

    surface_bases: list[SurfaceBasis] = []
    al_bases: dict[tuple[int, int, int], SurfaceBasis] = {}
    fe_bases: dict[tuple[int, int, int], SurfaceBasis] = {}

    for hkl in AL_ORIENTATIONS:
        basis = find_surface_basis("Al", hkl, al_cell, al_translation_basis, args.surface_coeff)
        al_bases[hkl] = basis
        surface_bases.append(basis)

    for hkl in FE_ORIENTATIONS:
        basis = find_surface_basis("Fe4Al13", hkl, fe_cell, fe_cell, args.surface_coeff)
        fe_bases[hkl] = basis
        surface_bases.append(basis)

    al_cells_by_hkl = {
        hkl: generate_supercells(basis, args.supercell_entry, args.max_det, args.max_supercells_per_surface)
        for hkl, basis in al_bases.items()
    }
    fe_cells_by_hkl = {
        hkl: generate_supercells(basis, args.supercell_entry, args.max_det, args.max_supercells_per_surface)
        for hkl, basis in fe_bases.items()
    }

    rows = rank_matches(
        al_cells_by_hkl,
        fe_cells_by_hkl,
        atom_limit=args.atom_limit,
        al_atom_factor=4,
        fe_atom_factor=fe_info.n_atoms,
        al_thickness=args.al_thickness_cells,
        fe_thickness=args.fe_thickness_cells,
        top_per_pair=args.top_per_pair,
    )

    write_csv(args.csv, rows)
    write_markdown(
        args.md,
        rows,
        surface_bases,
        al_info,
        fe_info,
        al_repeat,
        al_lattice_a,
        args.atom_limit,
        args.al_thickness_cells,
        args.fe_thickness_cells,
        args.markdown_top,
    )

    print(f"Al relaxed data: {args.al_data}")
    print(f"Fe4Al13 relaxed data: {args.fe_data}")
    print(f"Al inferred repeat: {al_repeat}, a = {al_lattice_a:.6f} A")
    print(f"candidates written: {len(rows)}")
    print(f"csv: {args.csv}")
    print(f"markdown: {args.md}")
    if rows:
        best = rows[0]
        print(
            "best: "
            f"Al {best['al_hkl']} / Fe4Al13 {best['fe_hkl']}, "
            f"status={best['status']}, "
            f"max_mismatch={best['max_len_mismatch_percent']:.3f}%, "
            f"angle_delta={best['angle_delta_deg']:.3f} deg, "
            f"estimated_atoms={best['estimated_atoms']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
