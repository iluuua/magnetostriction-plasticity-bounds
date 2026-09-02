#!/usr/bin/env python3
"""Verify a stage-G cell's Al13Fe4 support slab spans the whole box in x and y.
Usage: check_cell_support.py <case dir>"""
import glob, json, sys
import numpy as np
d = sys.argv[1]
f = glob.glob(d + "/*.start.data")[0] if glob.glob(d + "/*.start.data") else glob.glob(d + "/data.*")[0]
meta = json.load(open(glob.glob(d + "/*metadata.json")[0], encoding="utf-8"))
n_al = meta["counts"]["al_matrix"] if "counts" in meta else None
rows, started, lx, ly = [], False, None, None
for ln in open(f, encoding="utf-8", errors="replace"):
    if "xlo xhi" in ln: lx = float(ln.split()[1])
    if "ylo yhi" in ln: ly = float(ln.split()[1])
    if ln.startswith("Atoms"): started = True; continue
    if started and ln.strip() and not ln.startswith("Velocities"):
        p = ln.split()
        if len(p) >= 5:
            try: rows.append([int(p[0]), int(p[1]), float(p[2]), float(p[3]), float(p[4])])
            except ValueError: pass
a = np.array(rows); ids, ty, x, y, z = a.T
incl = (ids > n_al) if n_al else (ty == 2)
sup = incl & (z < 20.0)
hx, _ = np.histogram(x[sup], bins=10, range=(0, lx)); hy, _ = np.histogram(y[sup], bins=8, range=(0, ly))
print("%s: N=%d  inclusion=%d  support=%d" % (d.rstrip('/').split('/')[-1], len(a), incl.sum(), sup.sum()))
print("  support x range %.2f..%.2f of %.2f | y range %.2f..%.2f of %.2f" % (x[sup].min(), x[sup].max(), lx, y[sup].min(), y[sup].max(), ly))
print("  x-deciles:", hx.tolist(), " uniform to %.0f%%" % (100 * (hx.max() - hx.min()) / hx.mean()))
print("  y-octiles:", hy.tolist())
# nearest-neighbour sanity across all atoms (PBC in x,y)
from scipy.spatial import cKDTree
P = a[:, 2:5].copy()
imgs = [P]
for dx in (-lx, lx):
    Q = P.copy(); Q[:, 0] += dx; imgs.append(Q)
for dy in (-ly, ly):
    Q = P.copy(); Q[:, 1] += dy; imgs.append(Q)
allp = np.vstack(imgs)
dist, _ = cKDTree(allp).query(P, k=2)
print("  min interatomic distance (PBC x,y): %.3f A" % dist[:, 1].min())
