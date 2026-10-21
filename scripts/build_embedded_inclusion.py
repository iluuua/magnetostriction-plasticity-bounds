#!/usr/bin/env python3
"""Build an Al13Fe4 inclusion fully surrounded by an Al matrix in a periodic cell.

There is no substrate: the inclusion is carved from an Al13Fe4 crystal and
placed at the centre of a fully periodic Al box, and the Al atoms that overlap
it are removed.

Orientation. The Al matrix has x = [1-10], y = [11-2], z = [111], so the (111)
slip planes are horizontal and the slip direction of a full dislocation is x.
The Al13Fe4 crystal keeps the orientation of the earlier interface cells: its a
axis along x and its b axis along y.

Shapes:
  sphere      radius R, finite in every direction; no lattice matching needed
  cylinder_y  circular cross-section of radius R in the xz plane, infinite and
              periodic along y; the Al13Fe4 block is scaled along y so that an
              integer number of b periods spans Ly (8 b over 13 Al periods is
              -0.26 %)

Atom IDs: matrix atoms first (1..N_AL), inclusion atoms after, as in the
earlier inputs. Types: 1 Al, 2 Fe, 3 Mg, 4 Si (Mg and Si are declared but
absent, so the MEAM pair_coeff line of the earlier inputs applies unchanged).

    python scripts/build_embedded_inclusion.py --shape sphere --radius 25 \
        --nx 44 --ny 25 --nl 54 --out structures/embedded_inclusion/sphere_R25
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
AL13FE4_DATA = ROOT / "structures/converted/Al13Fe4/al13fe4.data"

AL_A = 4.05
PX = AL_A / math.sqrt(2.0)          # 2.863782, x period along [1-10], equal to |b|
PY = AL_A * math.sqrt(6.0) / 2.0    # 4.960075, y period along [11-2]
D111 = AL_A / math.sqrt(3.0)        # 2.338269, spacing of (111) planes
CLEARANCE_A = 2.2                   # Al atoms closer than this to the inclusion are removed
MIN_HARD_A = 1.8
MASSES = {1: 26.9815385, 2: 55.845, 3: 24.305, 4: 28.0855}


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       text=True).strip()
    except Exception:
        return "unknown"


def read_al13fe4_cell(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Types, Cartesian positions and the three cell vectors of the source cell."""
    lines = path.read_text(encoding="utf-8").splitlines()
    lo_hi, tilt, start = {}, (0.0, 0.0, 0.0), None
    for i, line in enumerate(lines):
        p = line.split()
        if len(p) >= 4 and p[-2] in ("xlo", "ylo", "zlo"):
            lo_hi[p[-2][0]] = (float(p[0]), float(p[1]))
        elif len(p) >= 6 and p[-3:] == ["xy", "xz", "yz"]:
            tilt = tuple(float(v) for v in p[:3])
        elif line.strip().startswith("Atoms"):
            start = i + 2
            break
    xy, xz, yz = tilt
    cell = np.array([[lo_hi["x"][1] - lo_hi["x"][0], 0.0, 0.0],
                     [xy, lo_hi["y"][1] - lo_hi["y"][0], 0.0],
                     [xz, yz, lo_hi["z"][1] - lo_hi["z"][0]]])
    types, pos = [], []
    for line in lines[start:]:
        p = line.split()
        if len(p) < 5:
            if types:
                break
            continue
        types.append(int(p[1]))
        pos.append([float(v) for v in p[2:5]])
    return np.array(types), np.array(pos), cell


def al_matrix(nx: int, ny: int, nl: int) -> np.ndarray:
    """Periodic fcc Al block, x=[1-10], y=[11-2], z=[111], ABC stacking."""
    if nl % 3:
        raise ValueError("the number of (111) layers must be a multiple of 3 for z periodicity")
    lx, ly = nx * PX, ny * PY
    i, j = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
    base = np.stack([i.ravel() * PX, j.ravel() * PY], axis=1)
    sites = []
    for k in range(nl):
        off = (k % 3) * PY / 3.0
        for sx, sy in ((0.0, 0.0), (PX / 2.0, PY / 2.0)):
            xy = base + np.array([sx, sy + off])
            sites.append(np.column_stack([xy[:, 0] % lx, xy[:, 1] % ly,
                                          np.full(len(xy), (k + 0.5) * D111)]))
    return np.vstack(sites)


def shape_value(pos: np.ndarray, centre: np.ndarray, shape: str, radius: float,
                ly: float) -> np.ndarray:
    """< 1 inside the inclusion. For cylinder_y the y coordinate is ignored."""
    d = pos - centre
    if shape == "sphere":
        return np.sum(d * d, axis=1) / radius ** 2
    if shape == "cylinder_y":
        return (d[:, 0] ** 2 + d[:, 2] ** 2) / radius ** 2
    raise ValueError(shape)


def carve_inclusion(shape: str, radius: float, centre: np.ndarray, lx: float, ly: float,
                    ny_fe: int | None) -> tuple[np.ndarray, np.ndarray, dict]:
    types0, pos0, cell = read_al13fe4_cell(AL13FE4_DATA)
    info: dict = {"source": str(AL13FE4_DATA.relative_to(ROOT)),
                  "cell_vectors_A": cell.tolist()}
    span = np.array([2 * radius + 2 * cell[0, 0], (ly if shape == "cylinder_y" else 2 * radius)
                     + 2 * cell[1, 1], 2 * radius + 2 * cell[2, 2]])
    reps = np.ceil(span / np.abs(np.diag(cell))).astype(int) + 2
    shifts = np.array([i * cell[0] + j * cell[1] + k * cell[2]
                       for i in range(-reps[0] // 2, reps[0] // 2 + 1)
                       for j in range(-reps[1] // 2, reps[1] // 2 + 1)
                       for k in range(-reps[2] // 2, reps[2] // 2 + 1)])
    pos = (pos0[None, :, :] + shifts[:, None, :]).reshape(-1, 3)
    types = np.tile(types0, len(shifts))
    if shape == "cylinder_y":
        # an integer number of b periods must span Ly, otherwise the rod has a seam
        b = cell[1, 1]
        n_b = ny_fe if ny_fe else int(round(ly / b))
        scale = ly / (n_b * b)
        pos[:, 1] *= scale
        info.update({"n_b_periods_along_y": n_b, "y_scale": scale,
                     "y_misfit_pct": (scale - 1.0) * 100.0})
        pos[:, 1] = np.mod(pos[:, 1], ly)
        # one copy of each site modulo Ly
        key = np.round(np.column_stack([pos[:, 0], pos[:, 1] % ly, pos[:, 2]]) / 1e-3).astype(np.int64)
        _, idx = np.unique(key, axis=0, return_index=True)
        pos, types = pos[np.sort(idx)], types[np.sort(idx)]
    # place a crystal site-free point at the centre: shift the block so its own
    # centroid of the carved set sits at the cell centre
    pos = pos - pos.mean(axis=0) + centre if shape == "sphere" else pos
    if shape == "cylinder_y":
        pos[:, [0, 2]] += centre[[0, 2]] - pos[:, [0, 2]].mean(axis=0)
    keep = shape_value(pos, centre, shape, radius, ly) <= 1.0
    pos, types = pos[keep], types[keep]
    n_al, n_fe = int(np.sum(types == 1)), int(np.sum(types == 2))
    info.update({"n_al": n_al, "n_fe": n_fe, "al_to_fe": n_al / max(n_fe, 1),
                 "ideal_al_to_fe": 13 / 4})
    return pos, types, info


def pbc_nearest(a: np.ndarray, b: np.ndarray, box: np.ndarray) -> np.ndarray:
    """Distance from every point of a to the nearest point of b, fully periodic."""
    tree = cKDTree(np.mod(b, box), boxsize=box)
    d, _ = tree.query(np.mod(a, box), k=1)
    return d


def write_data(path: Path, pos: np.ndarray, types: np.ndarray, box: np.ndarray, title: str) -> None:
    out = [f"# {title}", "", f"{len(pos)} atoms", "4 atom types", "",
           f"0.0 {box[0]:.8f} xlo xhi", f"0.0 {box[1]:.8f} ylo yhi",
           f"0.0 {box[2]:.8f} zlo zhi", "", "Masses", ""]
    out += [f"{t} {m}" for t, m in MASSES.items()]
    out += ["", "Atoms # atomic", ""]
    out += [f"{i + 1} {t} {p[0]:.8f} {p[1]:.8f} {p[2]:.8f}"
            for i, (t, p) in enumerate(zip(types, pos))]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shape", choices=["sphere", "cylinder_y"], default="sphere")
    ap.add_argument("--radius", type=float, default=25.0, help="inclusion radius, A")
    ap.add_argument("--nx", type=int, default=44, help="Al periods along x (2.8638 A each)")
    ap.add_argument("--ny", type=int, default=25, help="Al periods along y (4.9601 A each)")
    ap.add_argument("--nl", type=int, default=54, help="(111) layers along z (2.3383 A each)")
    ap.add_argument("--ny-fe", type=int, default=None, help="cylinder_y: b periods along y")
    ap.add_argument("--out", type=Path, required=True, help="output directory")
    a = ap.parse_args()

    box = np.array([a.nx * PX, a.ny * PY, a.nl * D111])
    centre = box / 2.0
    if 2 * a.radius + 2 * CLEARANCE_A >= min(box[0], box[2]) or (
            a.shape == "sphere" and 2 * a.radius + 2 * CLEARANCE_A >= box[1]):
        raise SystemExit("the inclusion does not fit in the box")

    al = al_matrix(a.nx, a.ny, a.nl)
    inc, inc_t, inc_info = carve_inclusion(a.shape, a.radius, centre, box[0], box[1], a.ny_fe)
    d = pbc_nearest(al, inc, box)
    inside = shape_value(al, centre, a.shape, a.radius, box[1]) <= 1.0
    keep = (d >= CLEARANCE_A) & ~inside
    al = al[keep]

    # sanity: no close pairs inside the inclusion or across the interface
    d_cross = pbc_nearest(al, inc, box)
    t_inc = cKDTree(np.mod(inc, box), boxsize=box)
    d_inc = t_inc.query(np.mod(inc, box), k=2)[0][:, 1]
    t_al = cKDTree(np.mod(al, box), boxsize=box)
    d_al = t_al.query(np.mod(al, box), k=2)[0][:, 1]
    if d_cross.min() < MIN_HARD_A or d_inc.min() < MIN_HARD_A or d_al.min() < MIN_HARD_A:
        raise SystemExit("close pair below %.1f A: cross %.3f inclusion %.3f matrix %.3f"
                         % (MIN_HARD_A, d_cross.min(), d_inc.min(), d_al.min()))

    pos = np.vstack([al, inc])
    types = np.concatenate([np.ones(len(al), dtype=int), inc_t])
    a.out.mkdir(parents=True, exist_ok=True)
    name = a.out.name
    write_data(a.out / f"data.{name}", pos, types, box,
               f"Al13Fe4 {a.shape} R={a.radius} A in a periodic Al box; matrix IDs 1..{len(al)}")

    vol_inc = (4.0 / 3.0 * math.pi * a.radius ** 3 if a.shape == "sphere"
               else math.pi * a.radius ** 2 * box[1])
    meta = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_head": git_head(),
        "builder": "scripts/build_embedded_inclusion.py",
        "shape": a.shape, "radius_A": a.radius,
        "box_A": box.tolist(), "periods": {"nx": a.nx, "ny": a.ny, "nl": a.nl},
        "centre_A": centre.tolist(),
        "orientation": {"x": "[1-10]", "y": "[11-2]", "z": "[111]",
                        "Al13Fe4": "a along x, b along y"},
        "n_atoms": int(len(pos)), "n_matrix": int(len(al)), "n_inclusion": int(len(inc)),
        "N_AL": int(len(al)),
        "inclusion": inc_info,
        "volume_fraction": vol_inc / float(np.prod(box)),
        "clearance_A": CLEARANCE_A,
        "min_distance_A": {"matrix_inclusion": float(d_cross.min()),
                           "inclusion_inclusion": float(d_inc.min()),
                           "matrix_matrix": float(d_al.min())},
        "matrix_removed": int(np.count_nonzero(~keep)),
        "types": {"1": "Al", "2": "Fe", "3": "Mg (absent)", "4": "Si (absent)"},
    }
    (a.out / f"{name}_metadata.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("n_atoms", "n_matrix", "n_inclusion",
                                            "volume_fraction", "min_distance_A")}, indent=1))
    print("inclusion Al:Fe = %d:%d (%.2f, ideal 3.25)" % (inc_info["n_al"], inc_info["n_fe"],
                                                         inc_info["al_to_fe"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
