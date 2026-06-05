#!/usr/bin/env python3

from pathlib import Path
import json
import sys
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]

BASE_DATA = ROOT / "lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/data.ellipsoid_nvt_300k"

OUT_ROOT = ROOT / "structures/interface/ellipsoid_inclusion/trial_001/eigenstrain"
OUT_ROOT.mkdir(parents=True, exist_ok=True)

BOX = np.array([64.8, 64.8, 97.2], dtype=float)
CENTER = np.array([32.4, 32.4, 48.6], dtype=float)

INCLUSION_ID_MIN = 23264
INCLUSION_ID_MAX = 24259

MIN_HARD = 1.80
MIN_WARN = 2.10

EPS_Z = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0025
EPS_X = -0.5 * EPS_Z
EPS_Y = -0.5 * EPS_Z

TAG = f"epsz_{EPS_Z:+.5f}".replace("+", "p").replace("-", "m").replace(".", "p")
OUT_DIR = OUT_ROOT / TAG
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_DATA = OUT_DIR / f"data.ellipsoid_eigenstrain_{TAG}"
OUT_REPORT = OUT_DIR / f"ellipsoid_eigenstrain_{TAG}_build_report.json"


def find_atoms_section(lines):
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Atoms"):
            start = i + 2
            break

    if start is None:
        raise RuntimeError("Atoms section not found")

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


def read_atoms(lines, start, end):
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


def write_data(lines, start, end, ids, types, pos, out_path):
    with out_path.open("w") as f:
        for line in lines[:start]:
            f.write(line if line.endswith("\n") else line + "\n")

        for atom_id, atom_type, xyz in zip(ids, types, pos):
            f.write(
                f"{int(atom_id)} {int(atom_type)} "
                f"{xyz[0]:.16f} {xyz[1]:.16f} {xyz[2]:.16f}\n"
            )

        for line in lines[end:]:
            f.write(line if line.endswith("\n") else line + "\n")


def distance_report(ids, types, pos):
    wrapped = pos % BOX
    tree = cKDTree(wrapped, boxsize=BOX)
    pairs = tree.query_pairs(r=MIN_WARN)

    min_d = None
    hard = []
    warn = []
    alfe_warn = []

    for i, j in pairs:
        dvec = wrapped[i] - wrapped[j]
        dvec -= BOX * np.round(dvec / BOX)
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


lines = BASE_DATA.read_text().splitlines(True)
start, end = find_atoms_section(lines)
ids, types, pos = read_atoms(lines, start, end)

mask_inclusion = (ids >= INCLUSION_ID_MIN) & (ids <= INCLUSION_ID_MAX)

if int(mask_inclusion.sum()) != 996:
    raise RuntimeError(f"Unexpected inclusion atom count: {int(mask_inclusion.sum())}, expected 996")

pos2 = pos.copy()
rel = pos2[mask_inclusion] - CENTER

rel[:, 0] *= 1.0 + EPS_X
rel[:, 1] *= 1.0 + EPS_Y
rel[:, 2] *= 1.0 + EPS_Z

pos2[mask_inclusion] = CENTER + rel
pos2 = pos2 % BOX

report = {
    "source": str(BASE_DATA.relative_to(ROOT)),
    "output": str(OUT_DATA.relative_to(ROOT)),
    "strain_model": "inclusion eigenstrain relative to original center",
    "inclusion_id_min": INCLUSION_ID_MIN,
    "inclusion_id_max": INCLUSION_ID_MAX,
    "inclusion_atoms": int(mask_inclusion.sum()),
    "eps_x": EPS_X,
    "eps_y": EPS_Y,
    "eps_z": EPS_Z,
    "box_A": BOX.tolist(),
    "center_A": CENTER.tolist(),
}

report.update(distance_report(ids, types, pos2))

write_data(lines, start, end, ids, types, pos2, OUT_DATA)
OUT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

print(json.dumps(report, indent=2))
print(f"Saved data: {OUT_DATA}")
print(f"Saved report: {OUT_REPORT}")
