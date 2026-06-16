"""Run-local eigenstrain structure regeneration.

Same deterministic transformation as analysis/python/apply_ellipsoid_eigenstrain.py
(inclusion scaled about the box center: eps_x = eps_y = -0.5 * eps_z), but all
outputs go to a caller-supplied run-local directory, never into the tracked
structures/ tree. Box bounds are parsed from the data file header (for the A0
baseline this reproduces the original hardcoded 64.8 x 64.8 x 97.2 box).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from .paths import epsz_dirtag

MIN_HARD = 1.80
MIN_WARN = 2.10


class EigenstrainError(RuntimeError):
    pass


def _find_atoms_section(lines: list[str]) -> tuple[int, int]:
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Atoms"):
            start = i + 2
            break
    if start is None:
        raise EigenstrainError("Atoms section not found")
    end = len(lines)
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) < 5 or not parts[0].isdigit():
            end = i
            break
    return start, end


def _read_box(lines: list[str]) -> tuple[np.ndarray, np.ndarray]:
    lo = [None, None, None]
    hi = [None, None, None]
    pairs = {"xlo": 0, "ylo": 1, "zlo": 2}
    for line in lines:
        parts = line.split()
        if len(parts) >= 4 and parts[2] in pairs and parts[3] == parts[2].replace("lo", "hi"):
            axis = pairs[parts[2]]
            lo[axis] = float(parts[0])
            hi[axis] = float(parts[1])
        if line.strip().startswith("Atoms"):
            break
    if None in lo or None in hi:
        raise EigenstrainError("box bounds not found in data file header")
    return np.array(lo, dtype=float), np.array(hi, dtype=float)


def _read_atoms(lines: list[str], start: int, end: int):
    ids, types, pos = [], [], []
    for line in lines[start:end]:
        s = line.strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) < 5:
            continue
        ids.append(int(parts[0]))
        types.append(int(parts[1]))
        pos.append([float(parts[2]), float(parts[3]), float(parts[4])])
    return np.array(ids), np.array(types), np.array(pos, dtype=float)


def _write_data(lines, start, end, ids, types, pos, out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        for line in lines[:start]:
            f.write(line if line.endswith("\n") else line + "\n")
        for atom_id, atom_type, xyz in zip(ids, types, pos):
            f.write(
                f"{int(atom_id)} {int(atom_type)} "
                f"{xyz[0]:.16f} {xyz[1]:.16f} {xyz[2]:.16f}\n"
            )
        for line in lines[end:]:
            f.write(line if line.endswith("\n") else line + "\n")


def _distance_report(ids, types, pos, box_lo, box_len) -> dict:
    wrapped = (pos - box_lo) % box_len
    tree = cKDTree(wrapped, boxsize=box_len)
    pairs = tree.query_pairs(r=MIN_WARN)

    min_d = None
    hard, warn, alfe_warn = [], [], []
    for i, j in pairs:
        dvec = wrapped[i] - wrapped[j]
        dvec -= box_len * np.round(dvec / box_len)
        d = float(np.linalg.norm(dvec))
        min_d = d if min_d is None else min(min_d, d)
        item = {
            "id_i": int(ids[i]),
            "id_j": int(ids[j]),
            "type_i": int(types[i]),
            "type_j": int(types[j]),
            "distance_A": d,
        }
        if d < MIN_WARN:
            warn.append(item)
            if set([int(types[i]), int(types[j])]) == {1, 2}:
                alfe_warn.append(item)
        if d < MIN_HARD:
            hard.append(item)

    return {
        "min_pair_distance_A": min_d,
        "pairs_below_2p1_A": len(warn),
        "pairs_below_1p8_A": len(hard),
        "Al_Fe_pairs_below_2p1_A": len(alfe_warn),
        "hard_pairs_preview": hard[:20],
        "Al_Fe_warning_pairs_preview": alfe_warn[:20],
        "safe_basic": len(hard) == 0,
    }


def regenerate(
    base_data: Path,
    out_dir: Path,
    eps_z: float,
    *,
    inclusion_id_min: int,
    inclusion_id_max: int,
    expected_inclusion_atoms: int | None = None,
    center: tuple[float, float, float] | None = None,
) -> dict:
    """Write data.ellipsoid_eigenstrain_<tag> + build report JSON into out_dir."""
    base_data = Path(base_data)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    eps_z = float(eps_z)
    eps_x = -0.5 * eps_z
    eps_y = -0.5 * eps_z
    tag = epsz_dirtag(eps_z)
    out_data = out_dir / f"data.ellipsoid_eigenstrain_{tag}"
    out_report = out_dir / f"ellipsoid_eigenstrain_{tag}_build_report.json"

    lines = base_data.read_text(encoding="utf-8", errors="replace").splitlines(True)
    box_lo, box_hi = _read_box(lines)
    box_len = box_hi - box_lo
    ctr = np.array(center, dtype=float) if center is not None else box_lo + 0.5 * box_len

    start, end = _find_atoms_section(lines)
    ids, types, pos = _read_atoms(lines, start, end)

    mask = (ids >= int(inclusion_id_min)) & (ids <= int(inclusion_id_max))
    n_incl = int(mask.sum())
    if expected_inclusion_atoms is not None and n_incl != int(expected_inclusion_atoms):
        raise EigenstrainError(
            f"unexpected inclusion atom count: {n_incl}, expected {expected_inclusion_atoms}"
        )
    if n_incl == 0:
        raise EigenstrainError("inclusion id range selected zero atoms")

    pos2 = pos.copy()
    rel = pos2[mask] - ctr
    rel[:, 0] *= 1.0 + eps_x
    rel[:, 1] *= 1.0 + eps_y
    rel[:, 2] *= 1.0 + eps_z
    pos2[mask] = ctr + rel
    pos2 = box_lo + (pos2 - box_lo) % box_len

    report = {
        "source": str(base_data),
        "output": str(out_data),
        "strain_model": "inclusion eigenstrain relative to original center",
        "inclusion_id_min": int(inclusion_id_min),
        "inclusion_id_max": int(inclusion_id_max),
        "inclusion_atoms": n_incl,
        "eps_x": eps_x,
        "eps_y": eps_y,
        "eps_z": eps_z,
        "box_A": box_len.tolist(),
        "center_A": ctr.tolist(),
    }
    report.update(_distance_report(ids, types, pos2, box_lo, box_len))

    _write_data(lines, start, end, ids, types, pos2, out_data)
    out_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
