#!/usr/bin/env python3
"""Build the strained cell as a perturbation of the relaxed control.

Stage G13 lesson (3 Sept 2026): a control and a strained cell that each pass
through their own thermal relaxation end in different states of the
long-wavelength slab mode (the film's breathing mode carries ~100 MPa at a
force of 1e-4 eV/A per atom, invisible to any force criterion) and in
different arrangements of the interfacial Al layer. Their difference is then
not the field of the strained ridge. Instead: relax the control once
(protocol v3), then displace the ridge atoms of THAT state by the eigenstrain
and minimise. The interface layer and the slab mode are identical in the two
cells by construction; only the local response to the ridge is relaxed.

Reads the control's final dump (x y z), writes LAMMPS data files:
  <tag>_ctl.data   the control state as read (rounded exactly like the strained one)
  <tag>_fld.data   the same with the ridge (inclusion atoms with z > z_ridge)
                   displaced by eps* about the ridge centroid
"""
from __future__ import annotations
import argparse, io, json, math
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]
TILT_DEG = 45.0


def read_dump(path: Path):
    L = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    i = next(k for k, l in enumerate(L) if l.startswith("ITEM: ATOMS"))
    cols = L[i].split()[2:]
    ib = next(k for k, l in enumerate(L) if l.startswith("ITEM: BOX BOUNDS"))
    box = [tuple(map(float, L[ib + 1 + j].split()[:2])) for j in range(3)]
    a = np.array([[float(x) for x in l.split()] for l in L[i + 1:] if l.strip()])
    a = a[np.argsort(a[:, 0])]
    ix = {c: j for j, c in enumerate(cols)}
    return a[:, ix["id"]].astype(int), a[:, ix["type"]].astype(int), a[:, [ix["x"], ix["y"], ix["z"]]], box


def read_masses(start_data: Path):
    L = io.open(start_data, encoding="utf-8").read().splitlines()
    i = next(k for k, l in enumerate(L) if l.strip() == "Masses")
    out = []
    for l in L[i + 1:]:
        p = l.split()
        if len(p) == 2:
            out.append((int(p[0]), float(p[1])))
        elif out and not l.strip():
            break
    ntypes = int(next(l for l in L if "atom types" in l).split()[0])
    return ntypes, out


def write_data(path: Path, comment: str, ids, types, pos, box, ntypes, masses):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"# {comment}\n\n{len(ids)} atoms\n{ntypes} atom types\n\n")
        fh.write("%.10f %.10f xlo xhi\n%.10f %.10f ylo yhi\n%.10f %.10f zlo zhi\n\n" % (*box[0], *box[1], *box[2]))
        fh.write("Masses\n\n" + "".join("%d %s\n" % (t, m) for t, m in masses) + "\nAtoms # atomic\n\n")
        for i, t, r in zip(ids, types, pos):
            fh.write("%d %d %.8f %.8f %.8f\n" % (i, t, r[0], r[1], r[2]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-dump", type=Path, required=True)
    ap.add_argument("--start-data", type=Path, required=True, help="the as-built data file (masses, types)")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--tag", default="pert")
    ap.add_argument("--n-al", type=int, required=True, help="matrix atoms come first; ids above are inclusion")
    ap.add_argument("--eps", type=float, default=1.94e-3)
    ap.add_argument("--z-ridge", type=float, default=20.0, help="inclusion atoms above this z form the ridge")
    a = ap.parse_args()

    ids, types, pos, box = read_dump(a.control_dump)
    ntypes, masses = read_masses(a.start_data)
    lx, ly = box[0][1] - box[0][0], box[1][1] - box[1][0]
    pos[:, 0] = np.mod(pos[:, 0] - box[0][0], lx) + box[0][0]
    pos[:, 1] = np.mod(pos[:, 1] - box[1][0], ly) + box[1][0]
    a.out_dir.mkdir(parents=True, exist_ok=True)
    write_data(a.out_dir / f"{a.tag}_ctl.data", f"control state of {a.control_dump.name}", ids, types, pos, box, ntypes, masses)

    t = math.radians(TILT_DEG)
    u = np.array([math.sin(t), 0.0, math.cos(t)])
    E = 1.5 * np.outer(u, u) - 0.5 * np.eye(3)
    ridge = (ids > a.n_al) & (pos[:, 2] > a.z_ridge)
    c = pos[ridge].mean(axis=0)
    pos2 = pos.copy()
    pos2[ridge] += a.eps * ((pos[ridge] - c) @ E)
    write_data(a.out_dir / f"{a.tag}_fld.data",
               f"control state of {a.control_dump.name} + ridge eigenstrain eps={a.eps} tilt 45 about ({c[0]:.2f},{c[1]:.2f},{c[2]:.2f})",
               ids, types, pos2, box, ntypes, masses)
    meta = {"control_dump": str(a.control_dump), "n_al": a.n_al, "eps": a.eps, "tilt_deg": TILT_DEG,
            "ridge_atoms": int(ridge.sum()), "ridge_centroid": c.round(3).tolist(),
            "max_ridge_displacement_A": float(np.abs(pos2[ridge] - pos[ridge]).max()),
            "eigenstrain_tensor": (a.eps * E).round(7).tolist(), "z_ridge": a.z_ridge}
    (a.out_dir / f"{a.tag}_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
