#!/usr/bin/env python3

from pathlib import Path
import json
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/data.ellipsoid_nvt_300k"
OUT = ROOT / "results/tables/ellipsoid_inclusion/ellipsoid_trial_001_nvt_300k_distance_report.json"

BOX = np.array([64.8, 64.8, 97.2], dtype=float)
MIN_HARD = 1.80
MIN_WARN = 2.10

def read_lammps_atomic(path: Path):
    lines = path.read_text().splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Atoms"):
            start = i + 2
            break
    if start is None:
        raise RuntimeError("Atoms section not found")

    ids, types, pos = [], [], []
    for line in lines[start:]:
        s = line.strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) < 5 or not parts[0].isdigit():
            break
        ids.append(int(parts[0]))
        types.append(int(parts[1]))
        pos.append([float(parts[2]), float(parts[3]), float(parts[4])])

    return np.array(ids), np.array(types), np.array(pos)

ids, types, pos = read_lammps_atomic(DATA)

tree = cKDTree(pos % BOX, boxsize=BOX)
pairs = tree.query_pairs(r=MIN_WARN)

hard = []
warn = []
alfe_warn = []
min_d = None

for i, j in pairs:
    dvec = pos[i] - pos[j]
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
        if set([int(types[i]), int(types[j])]) == set([1, 2]):
            alfe_warn.append(item)
    if d < MIN_HARD:
        hard.append(item)

report = {
    "data_file": str(DATA.relative_to(ROOT)),
    "total_atoms": int(len(ids)),
    "type_1_Al_atoms": int(np.sum(types == 1)),
    "type_2_Fe_atoms": int(np.sum(types == 2)),
    "min_pair_distance_A": min_d,
    "pairs_below_2p1_A": len(warn),
    "pairs_below_1p8_A": len(hard),
    "Al_Fe_pairs_below_2p1_A": len(alfe_warn),
    "hard_pairs_preview": hard[:20],
    "Al_Fe_warning_pairs_preview": alfe_warn[:20],
    "safe_basic": len(hard) == 0,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

print(json.dumps(report, indent=2))
print(f"Saved: {OUT}")
