#!/usr/bin/env python3

from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]

TAG = sys.argv[1] if len(sys.argv) > 1 else "epsz_p0p00250"

DATA = ROOT / f"lammps/04_ellipsoid_inclusion/trial_001/02_eigenstrain_relax/{TAG}_minimize/data.ellipsoid_eigenstrain_{TAG}_minimized"
OUT_DIR = ROOT / f"lammps/04_ellipsoid_inclusion/trial_001/02_eigenstrain_relax/{TAG}_minimize/visual_debug"
OUT_DIR.mkdir(parents=True, exist_ok=True)

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

mask_inclusion_region = ev <= 1.35
mask_cutaway_half_x = mask_inclusion_region | (pos[:, 0] <= CENTER[0])
mask_x_slice = np.abs(pos[:, 0] - CENTER[0]) <= 3.0
mask_y_slice = np.abs(pos[:, 1] - CENTER[1]) <= 3.0
mask_z_slice = np.abs(pos[:, 2] - CENTER[2]) <= 3.0
mask_fe_only = types == 2

outputs = [
    (f"ellipsoid_eigenstrain_{TAG}_inclusion_region.xyz", mask_inclusion_region, f"Atoms near ellipsoid region after {TAG}"),
    (f"ellipsoid_eigenstrain_{TAG}_cutaway_half_x.xyz", mask_cutaway_half_x, f"Half cutaway after {TAG}"),
    (f"ellipsoid_eigenstrain_{TAG}_x_center_slice_6A.xyz", mask_x_slice, f"Central X-slice after {TAG}"),
    (f"ellipsoid_eigenstrain_{TAG}_y_center_slice_6A.xyz", mask_y_slice, f"Central Y-slice after {TAG}"),
    (f"ellipsoid_eigenstrain_{TAG}_z_center_slice_6A.xyz", mask_z_slice, f"Central Z-slice after {TAG}"),
    (f"ellipsoid_eigenstrain_{TAG}_fe_only.xyz", mask_fe_only, f"Fe atoms only after {TAG}"),
]

for filename, mask, comment in outputs:
    out = OUT_DIR / filename
    write_xyz(out, symbols[mask], pos[mask], comment)
    print(f"{filename}: {int(mask.sum())} atoms")

print(f"Output dir: {OUT_DIR}")
