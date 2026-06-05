#!/usr/bin/env python3

from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/data.ellipsoid_nvt_300k"
OUT_DIR = ROOT / "lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/visual_debug"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BOX = np.array([64.8, 64.8, 97.2], dtype=float)
CENTER = np.array([32.4, 32.4, 48.6], dtype=float)
AXES = np.array([12.0, 12.0, 24.0], dtype=float)

def read_lammps_atomic(path: Path):
    lines = path.read_text().splitlines()
    start = None

    for i, line in enumerate(lines):
        if line.strip().startswith("Atoms"):
            start = i + 2
            break

    if start is None:
        raise RuntimeError("Atoms section not found")

    ids = []
    types = []
    pos = []

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

    ids = np.array(ids, dtype=int)
    types = np.array(types, dtype=int)
    pos = np.array(pos, dtype=float)
    symbols = np.where(types == 1, "Al", "Fe")

    return ids, types, symbols, pos

def ellipsoid_value(pos):
    d = (pos - CENTER) / AXES
    return np.sum(d * d, axis=1)

def write_xyz(path: Path, symbols, pos, comment):
    with path.open("w") as f:
        f.write(f"{len(pos)}\n")
        f.write(comment + "\n")
        for sym, xyz in zip(symbols, pos):
            f.write(f"{sym} {xyz[0]:.8f} {xyz[1]:.8f} {xyz[2]:.8f}\n")

ids, types, symbols, pos = read_lammps_atomic(DATA)

ev = ellipsoid_value(pos)

mask_inclusion_region = ev <= 1.25
mask_x_slice = np.abs(pos[:, 0] - CENTER[0]) <= 3.0
mask_y_slice = np.abs(pos[:, 1] - CENTER[1]) <= 3.0
mask_z_slice = np.abs(pos[:, 2] - CENTER[2]) <= 3.0
mask_cutaway_half_x = mask_inclusion_region | (pos[:, 0] <= CENTER[0])
mask_fe_only = types == 2

outputs = [
    ("ellipsoid_nvt_300k_inclusion_region.xyz", mask_inclusion_region, "Atoms near original ellipsoid region after NVT"),
    ("ellipsoid_nvt_300k_x_center_slice_6A.xyz", mask_x_slice, "Central X-slice after NVT"),
    ("ellipsoid_nvt_300k_y_center_slice_6A.xyz", mask_y_slice, "Central Y-slice after NVT"),
    ("ellipsoid_nvt_300k_z_center_slice_6A.xyz", mask_z_slice, "Central Z-slice after NVT"),
    ("ellipsoid_nvt_300k_cutaway_half_x.xyz", mask_cutaway_half_x, "Half cutaway after NVT"),
    ("ellipsoid_nvt_300k_fe_only.xyz", mask_fe_only, "Fe atoms only after NVT"),
]

for filename, mask, comment in outputs:
    out = OUT_DIR / filename
    write_xyz(out, symbols[mask], pos[mask], comment)
    print(f"{filename}: {int(mask.sum())} atoms")

print(f"Output dir: {OUT_DIR}")
