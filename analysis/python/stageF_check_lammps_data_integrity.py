#!/usr/bin/env python3
"""Read-only Stage F LAMMPS data integrity and comparison checks."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "docs" / "reports"


@dataclass(frozen=True)
class DataFile:
    path: Path
    title: str
    atom_count_header: int
    atom_types_header: int | None
    masses: dict[int, float]
    box: dict[str, float]
    ids: np.ndarray
    types: np.ndarray
    xyz: np.ndarray

    @property
    def lx(self) -> float:
        return self.box["xhi"] - self.box["xlo"]

    @property
    def ly(self) -> float:
        return self.box["yhi"] - self.box["ylo"]

    @property
    def lz(self) -> float:
        return self.box["zhi"] - self.box["zlo"]


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(type(value).__name__)


def read_data(path: Path) -> DataFile:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    atom_count = None
    atom_types = None
    box: dict[str, float] = {}
    masses: dict[int, float] = {}
    title = lines[0] if lines else ""

    section = None
    waiting_blank = False
    atom_rows: list[tuple[int, int, float, float, float]] = []

    for line in lines:
        s = line.strip()
        if not s:
            if waiting_blank:
                waiting_blank = False
            continue
        parts = s.split()
        if len(parts) >= 2 and parts[1] == "atoms":
            atom_count = int(parts[0])
        elif len(parts) >= 3 and parts[1] == "atom" and parts[2] == "types":
            atom_types = int(parts[0])
        elif len(parts) >= 4 and parts[2] == "xlo" and parts[3] == "xhi":
            box["xlo"], box["xhi"] = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[2] == "ylo" and parts[3] == "yhi":
            box["ylo"], box["yhi"] = float(parts[0]), float(parts[1])
        elif len(parts) >= 4 and parts[2] == "zlo" and parts[3] == "zhi":
            box["zlo"], box["zhi"] = float(parts[0]), float(parts[1])

        if s.startswith("Masses"):
            section = "Masses"
            waiting_blank = True
            continue
        if s.startswith("Atoms"):
            section = "Atoms"
            waiting_blank = True
            continue
        if s.startswith("Velocities"):
            section = "Velocities"
            waiting_blank = True
            continue
        if s[0].isalpha() and not s.startswith(("Masses", "Atoms", "Velocities")):
            section = None
            continue
        if waiting_blank:
            continue

        if section == "Masses" and parts and parts[0].isdigit():
            masses[int(parts[0])] = float(parts[1])
        elif section == "Atoms" and len(parts) >= 5 and parts[0].lstrip("+-").isdigit():
            atom_rows.append((int(parts[0]), int(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])))

    if atom_count is None:
        raise ValueError(f"no atom count in {path}")
    required = {"xlo", "xhi", "ylo", "yhi", "zlo", "zhi"}
    missing = required - set(box)
    if missing:
        raise ValueError(f"missing box bounds in {path}: {sorted(missing)}")

    ids = np.array([r[0] for r in atom_rows], dtype=np.int64)
    types = np.array([r[1] for r in atom_rows], dtype=np.int32)
    xyz = np.array([[r[2], r[3], r[4]] for r in atom_rows], dtype=np.float64)
    return DataFile(path, title, atom_count, atom_types, masses, box, ids, types, xyz)


def type_counts(data: DataFile) -> dict[str, int]:
    unique, counts = np.unique(data.types, return_counts=True)
    return {str(int(k)): int(v) for k, v in zip(unique, counts)}


def basic_checks(data: DataFile, reference: dict[str, Any] | None = None) -> dict[str, Any]:
    ids_unique = len(np.unique(data.ids)) == len(data.ids)
    finite = np.isfinite(data.xyz).all()
    zlo = data.box["zlo"]
    zhi = data.box["zhi"]
    z = data.xyz[:, 2]
    x = data.xyz[:, 0]
    y = data.xyz[:, 1]
    result: dict[str, Any] = {
        "path": rel(data.path),
        "exists": data.path.exists(),
        "nonzero": data.path.stat().st_size > 0,
        "title": data.title,
        "atom_count_header": data.atom_count_header,
        "atom_lines": int(len(data.ids)),
        "atom_count_matches_lines": data.atom_count_header == len(data.ids),
        "duplicate_atom_ids": not ids_unique,
        "finite_coordinates": bool(finite),
        "box": {**data.box, "Lx_A": data.lx, "Ly_A": data.ly, "Lz_A": data.lz},
        "type_counts": type_counts(data),
        "masses": {str(k): v for k, v in sorted(data.masses.items())},
        "z_range": {"min": float(z.min()), "max": float(z.max())},
        "x_range": {"min": float(x.min()), "max": float(x.max())},
        "y_range": {"min": float(y.min()), "max": float(y.max())},
        "outside_nonperiodic_z_count": int(((z < zlo) | (z > zhi)).sum()),
        "near_z_boundary_1A_count": int(((z - zlo < 1.0) | (zhi - z < 1.0)).sum()),
    }
    if reference:
        result["reference_comparison"] = {
            "Lx_ref_A": reference["Lx_A"],
            "Ly_ref_A": reference["Ly_A"],
            "atoms_ref": reference["atoms_total"],
            "Al_ref": reference["Al_type1"],
            "Fe_ref": reference["Fe_type2"],
            "dLx_A": float(data.lx - reference["Lx_A"]),
            "dLy_A": float(data.ly - reference["Ly_A"]),
            "d_atoms": int(len(data.ids) - reference["atoms_total"]),
            "same_lx_ly_within_1e-4": bool(abs(data.lx - reference["Lx_A"]) <= 1e-4 and abs(data.ly - reference["Ly_A"]) <= 1e-4),
            "same_atom_count": bool(len(data.ids) == reference["atoms_total"]),
            "same_type_counts": bool(type_counts(data).get("1") == reference["Al_type1"] and type_counts(data).get("2") == reference["Fe_type2"]),
        }
    return result


def pbc_delta(delta: np.ndarray, box: np.ndarray, periodic: tuple[bool, bool, bool]) -> np.ndarray:
    out = delta.copy()
    for axis, is_periodic in enumerate(periodic):
        if is_periodic:
            length = box[axis]
            out[:, axis] -= np.rint(out[:, axis] / length) * length
    return out


def nearest_neighbor(data: DataFile, cutoff: float = 4.0) -> dict[str, Any]:
    xyz = data.xyz
    ids = data.ids
    types = data.types
    box_lengths = np.array([data.lx, data.ly, data.lz], dtype=np.float64)
    lo = np.array([data.box["xlo"], data.box["ylo"], data.box["zlo"]], dtype=np.float64)
    nx = max(1, int(math.floor(data.lx / cutoff)))
    ny = max(1, int(math.floor(data.ly / cutoff)))
    nz = max(1, int(math.floor(data.lz / cutoff)))

    scaled = xyz - lo
    ix = np.floor((scaled[:, 0] % data.lx) / data.lx * nx).astype(int)
    iy = np.floor((scaled[:, 1] % data.ly) / data.ly * ny).astype(int)
    iz = np.floor(np.clip(scaled[:, 2], 0.0, np.nextafter(data.lz, 0.0)) / data.lz * nz).astype(int)
    cells: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for idx, key in enumerate(zip(ix, iy, iz)):
        cells[key].append(idx)

    min_d2 = float("inf")
    min_pair: tuple[int, int] | None = None
    min_alfe_d2 = float("inf")
    min_alfe_pair: tuple[int, int] | None = None
    count_lt_18 = 0
    count_lt_20 = 0
    count_alfe_lt_20 = 0

    for (cx, cy, cz), base_indices in cells.items():
        for dx in (-1, 0, 1):
            ncx = (cx + dx) % nx
            for dy in (-1, 0, 1):
                ncy = (cy + dy) % ny
                for dz in (-1, 0, 1):
                    ncz = cz + dz
                    if ncz < 0 or ncz >= nz:
                        continue
                    neighbor_indices = cells.get((ncx, ncy, ncz))
                    if not neighbor_indices:
                        continue
                    for i in base_indices:
                        # Avoid double counting.
                        candidates = [j for j in neighbor_indices if j > i]
                        if not candidates:
                            continue
                        diff = xyz[np.array(candidates)] - xyz[i]
                        diff = pbc_delta(diff, box_lengths, (True, True, False))
                        d2 = np.einsum("ij,ij->i", diff, diff)
                        within = d2 <= cutoff * cutoff
                        if not np.any(within):
                            continue
                        cand = np.array(candidates)[within]
                        d2w = d2[within]
                        local_min_idx = int(np.argmin(d2w))
                        if float(d2w[local_min_idx]) < min_d2:
                            min_d2 = float(d2w[local_min_idx])
                            min_pair = (int(i), int(cand[local_min_idx]))
                        count_lt_18 += int((d2w < 1.8 * 1.8).sum())
                        count_lt_20 += int((d2w < 2.0 * 2.0).sum())
                        alfe = types[cand] != types[i]
                        if np.any(alfe):
                            alfe_d2 = d2w[alfe]
                            alfe_cand = cand[alfe]
                            count_alfe_lt_20 += int((alfe_d2 < 2.0 * 2.0).sum())
                            alfe_min_idx = int(np.argmin(alfe_d2))
                            if float(alfe_d2[alfe_min_idx]) < min_alfe_d2:
                                min_alfe_d2 = float(alfe_d2[alfe_min_idx])
                                min_alfe_pair = (int(i), int(alfe_cand[alfe_min_idx]))

    def pair_record(pair: tuple[int, int] | None, d2: float) -> dict[str, Any] | None:
        if pair is None:
            return None
        i, j = pair
        return {
            "distance_A": math.sqrt(d2),
            "atom_ids": [int(ids[i]), int(ids[j])],
            "types": [int(types[i]), int(types[j])],
            "xyz_i": xyz[i].tolist(),
            "xyz_j": xyz[j].tolist(),
        }

    return {
        "cutoff_A": cutoff,
        "cell_grid": [nx, ny, nz],
        "min_neighbor": pair_record(min_pair, min_d2),
        "count_pairs_lt_1p8_A": int(count_lt_18),
        "count_pairs_lt_2p0_A": int(count_lt_20),
        "min_Al_Fe_neighbor": pair_record(min_alfe_pair, min_alfe_d2),
        "count_Al_Fe_pairs_lt_2p0_A": int(count_alfe_lt_20),
    }


def compare_by_atom_id(reference: DataFile, target: DataFile) -> dict[str, Any]:
    ref_order = np.argsort(reference.ids)
    tgt_order = np.argsort(target.ids)
    ref_ids = reference.ids[ref_order]
    tgt_ids = target.ids[tgt_order]
    same_ids = np.array_equal(ref_ids, tgt_ids)
    if not same_ids:
        common = np.intersect1d(ref_ids, tgt_ids)
        return {"same_atom_ids": False, "common_atom_ids": int(common.size)}

    ref_xyz = reference.xyz[ref_order]
    tgt_xyz = target.xyz[tgt_order]
    raw_delta = tgt_xyz - ref_xyz
    box = np.array([reference.lx, reference.ly, reference.lz], dtype=np.float64)
    delta = pbc_delta(raw_delta, box, (True, True, False))
    distances = np.linalg.norm(delta, axis=1)
    p95, p99 = np.percentile(distances, [95, 99])
    max_idx = int(np.argmax(distances))
    type_mismatch = int((reference.types[ref_order] != target.types[tgt_order]).sum())
    return {
        "same_atom_ids": True,
        "type_mismatch_count": type_mismatch,
        "max_displacement_A": float(distances[max_idx]),
        "p95_displacement_A": float(p95),
        "p99_displacement_A": float(p99),
        "mean_displacement_A": float(distances.mean()),
        "max_displacement_atom_id": int(ref_ids[max_idx]),
        "max_displacement_type": int(reference.types[ref_order][max_idx]),
        "max_displacement_vector_A": delta[max_idx].tolist(),
    }


def write_reports(result: dict[str, Any], diff: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    integrity_json = REPORTS_DIR / "stageF_F0_commensurate_ppf_eps00194_data_integrity.json"
    diff_json = REPORTS_DIR / "stageF_F0_commensurate_ppf_eps00194_vs_eps0000_diff.json"
    integrity_json.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=json_default) + "\n", encoding="utf-8")
    diff_json.write_text(json.dumps(diff, indent=2, ensure_ascii=False, default=json_default) + "\n", encoding="utf-8")

    eps = result["eps00194"]
    nn = result["eps00194_nearest_neighbor"]
    ref_nn = result["eps0000_nearest_neighbor"]
    decision = "PASS" if result["pass"] else "FAIL"
    md = f"""# Stage F F0 commensurate ppf eps00194 data integrity

- Timestamp: {result['timestamp']}
- Decision: **{decision}**.
- Data file: `{eps['path']}`

## Header / Counts
- File exists and nonzero: `{eps['exists'] and eps['nonzero']}`
- Atom count header/lines: `{eps['atom_count_header']}` / `{eps['atom_lines']}`
- Type counts: `{eps['type_counts']}`
- Duplicate atom IDs: `{eps['duplicate_atom_ids']}`
- Finite coordinates: `{eps['finite_coordinates']}`
- Nonperiodic-z outside count: `{eps['outside_nonperiodic_z_count']}`

## Common Cell
- Lx: `{eps['box']['Lx_A']}`
- Ly: `{eps['box']['Ly_A']}`
- Same Lx/Ly as eps0000 within 1e-4 A: `{eps['reference_comparison']['same_lx_ly_within_1e-4']}`
- Same atom/type counts as eps0000: `{eps['reference_comparison']['same_atom_count'] and eps['reference_comparison']['same_type_counts']}`

## Nearest Neighbors
- eps00194 min NN: `{nn['min_neighbor']['distance_A'] if nn['min_neighbor'] else None}` A
- eps00194 pairs <1.8 A: `{nn['count_pairs_lt_1p8_A']}`
- eps00194 pairs <2.0 A: `{nn['count_pairs_lt_2p0_A']}`
- eps00194 min Al-Fe: `{nn['min_Al_Fe_neighbor']['distance_A'] if nn['min_Al_Fe_neighbor'] else None}` A
- eps0000 min NN: `{ref_nn['min_neighbor']['distance_A'] if ref_nn['min_neighbor'] else None}` A
- eps0000 min Al-Fe: `{ref_nn['min_Al_Fe_neighbor']['distance_A'] if ref_nn['min_Al_Fe_neighbor'] else None}` A

No data mutation was performed by this check.
"""
    (REPORTS_DIR / "stageF_F0_commensurate_ppf_eps00194_data_integrity.md").write_text(md, encoding="utf-8")

    d = diff["data_diff"]
    input_diff = diff["input_diff"]
    md2 = f"""# Stage F F0 commensurate ppf eps00194 vs eps0000 diff

- Timestamp: {diff['timestamp']}

## Input Diff
- Only expected command-level differences: `{input_diff['only_expected_differences']}`
- Differing normalized command lines: `{len(input_diff['differences'])}`

## Data Diff
- Same atom IDs: `{d['same_atom_ids']}`
- Type mismatch count: `{d.get('type_mismatch_count')}`
- Mean displacement: `{d.get('mean_displacement_A')}` A
- p95 displacement: `{d.get('p95_displacement_A')}` A
- p99 displacement: `{d.get('p99_displacement_A')}` A
- Max displacement: `{d.get('max_displacement_A')}` A at atom `{d.get('max_displacement_atom_id')}`
"""
    (REPORTS_DIR / "stageF_F0_commensurate_ppf_eps00194_vs_eps0000_diff.md").write_text(md2, encoding="utf-8")


def normalize_input(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # Normalize case-specific paths and comments, preserve behavior.
        s = s.replace("F0_planar_100A_comm_eps0000", "<CASE>")
        s = s.replace("F0_planar_100A_comm_eps00194", "<CASE>")
        s = s.replace("eps0000", "<EPS>")
        s = s.replace("eps00194", "<EPS>")
        s = s.replace("C:/Users/dille/Documents/ilua-system/projects/physics_md_al_fe/runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/", "<RUN>/")
        out.append(s)
    return out


def compare_inputs(eps0000_input: Path, eps00194_input: Path) -> dict[str, Any]:
    a = normalize_input(eps0000_input)
    b = normalize_input(eps00194_input)
    diffs = []
    for idx in range(max(len(a), len(b))):
        left = a[idx] if idx < len(a) else None
        right = b[idx] if idx < len(b) else None
        if left != right:
            diffs.append({"index": idx, "eps0000": left, "eps00194": right})
    expected_fragments = ("read_data", "dump", "restart", "write_restart", "write_data")
    only_expected = all(
        ((d["eps0000"] or "").split()[0] in expected_fragments or (d["eps00194"] or "").split()[0] in expected_fragments)
        for d in diffs
    )
    return {
        "eps0000_input": rel(eps0000_input),
        "eps00194_input": rel(eps00194_input),
        "differences": diffs,
        "only_expected_differences": only_expected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eps0000-data", type=Path, required=True)
    parser.add_argument("--eps00194-data", type=Path, required=True)
    parser.add_argument("--eps0000-input", type=Path, required=True)
    parser.add_argument("--eps00194-input", type=Path, required=True)
    args = parser.parse_args()

    eps0000 = read_data(args.eps0000_data)
    eps00194 = read_data(args.eps00194_data)
    reference = {
        "Lx_A": eps0000.lx,
        "Ly_A": eps0000.ly,
        "atoms_total": int(len(eps0000.ids)),
        "Al_type1": int((eps0000.types == 1).sum()),
        "Fe_type2": int((eps0000.types == 2).sum()),
    }
    eps0000_basic = basic_checks(eps0000)
    eps00194_basic = basic_checks(eps00194, reference)
    eps0000_nn = nearest_neighbor(eps0000)
    eps00194_nn = nearest_neighbor(eps00194)
    pass_checks = (
        eps00194_basic["exists"]
        and eps00194_basic["nonzero"]
        and eps00194_basic["atom_count_matches_lines"]
        and not eps00194_basic["duplicate_atom_ids"]
        and eps00194_basic["finite_coordinates"]
        and eps00194_basic["outside_nonperiodic_z_count"] == 0
        and eps00194_basic["reference_comparison"]["same_lx_ly_within_1e-4"]
        and eps00194_basic["reference_comparison"]["same_atom_count"]
        and eps00194_basic["reference_comparison"]["same_type_counts"]
        and eps00194_nn["count_pairs_lt_1p8_A"] == 0
    )
    integrity = {
        "timestamp": now(),
        "pass": bool(pass_checks),
        "eps0000": eps0000_basic,
        "eps00194": eps00194_basic,
        "eps0000_nearest_neighbor": eps0000_nn,
        "eps00194_nearest_neighbor": eps00194_nn,
    }
    diff_report = {
        "timestamp": now(),
        "input_diff": compare_inputs(args.eps0000_input, args.eps00194_input),
        "data_diff": compare_by_atom_id(eps0000, eps00194),
    }
    write_reports(integrity, diff_report)
    print(json.dumps({"pass": integrity["pass"], "min_nn": eps00194_nn["min_neighbor"], "pairs_lt_1p8": eps00194_nn["count_pairs_lt_1p8_A"]}, indent=2, default=json_default))
    return 0 if integrity["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
