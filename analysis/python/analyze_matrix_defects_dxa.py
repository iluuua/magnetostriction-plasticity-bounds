#!/usr/bin/env python3
"""Defect / dislocation analysis of the Al matrix around the Fe4Al13 inclusion.

Post-processing of EXISTING trajectories only (no new simulation). For each
eigenstrain case it runs CNA (structure classification) + DXA (dislocation
extraction) on the fcc Al matrix and writes a comparison CSV.

Answers the supervisor's core question: does the magnetostriction eigenstrain
produce defects / dislocations in the matrix?

Requires the scriptable OVITO python module (`pip install ovito`, Python <=3.12).
Run:  /path/to/venv/bin/python analysis/python/analyze_matrix_defects_dxa.py
"""
import os, csv, numpy as np
from pathlib import Path
from ovito.io import import_file
from ovito.modifiers import CommonNeighborAnalysisModifier, DislocationAnalysisModifier

# Portable repo root (script lives in analysis/python/), so this works on Mac and PC/WSL alike.
ROOT = str(Path(__file__).resolve().parents[2])
BASE = f"{ROOT}/lammps/04_ellipsoid_inclusion/trial_001"
ER = f"{BASE}/02_eigenstrain_relax"
OUT = f"{ROOT}/results/tables/ellipsoid_inclusion/ellipsoid_trial_001_matrix_defect_dxa.csv"
MATRIX_MAX_ID = 23263  # matrix = ids 1..23263; inclusion = 23264..24259 (build_report.json)

cases = [
    ("baseline_B0_unloaded_NVT", 0.0,    f"{BASE}/01_nvt_300k/dump.ellipsoid_nvt_300k_final.lammpstrj"),
    ("eps_z_0.0010",             0.0010, f"{ER}/epsz_p0p00100_minimize/dump.ellipsoid_eigenstrain_epsz_p0p00100_minimized_final.lammpstrj"),
    ("eps_z_0.0025",             0.0025, f"{ER}/epsz_p0p00250_minimize/dump.ellipsoid_eigenstrain_epsz_p0p00250_minimized_final.lammpstrj"),
    ("eps_z_0.0050",             0.0050, f"{ER}/epsz_p0p00500_minimize/dump.ellipsoid_eigenstrain_epsz_p0p00500_minimized_final.lammpstrj"),
    ("eps_z_0.0100_overload",    0.0100, f"{ER}/epsz_p0p01000_minimize/dump.ellipsoid_eigenstrain_epsz_p0p01000_minimized_final.lammpstrj"),
]
rows = []
for tag, eps, path in cases:
    if not os.path.exists(path):
        print("MISSING", path); continue
    pipe = import_file(path)
    pipe.modifiers.append(CommonNeighborAnalysisModifier())
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)
    data = pipe.compute()

    st = np.asarray(data.particles['Structure Type'])
    if 'Particle Identifier' in data.particles:
        mask = np.asarray(data.particles['Particle Identifier']) <= MATRIX_MAX_ID
    else:
        mask = np.asarray(data.particles['Particle Type']) == 1
    nm = int(mask.sum())
    fcc = int(np.count_nonzero(st[mask] == 1)); hcp = int(np.count_nonzero(st[mask] == 2))
    other = int(np.count_nonzero(st[mask] == 0))
    total_len = float(data.attributes.get('DislocationAnalysis.total_line_length', 0.0))
    if total_len == 0.0 and len(data.dislocations.segments):
        total_len = float(sum(s.length for s in data.dislocations.segments))
    vol = float(data.cell.volume)
    rho = total_len / vol * 1e20 if vol else 0.0
    rows.append([tag, eps, nm, round(100*fcc/nm, 3), round(100*hcp/nm, 4),
                 round(100*other/nm, 3), len(data.dislocations.segments),
                 round(total_len, 2), f"{rho:.3e}"])
    print(rows[-1])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["case", "eps_z", "matrix_atoms", "fcc_pct", "hcp_pct", "other_pct",
                "dislocation_segments", "dislocation_length_A", "dislocation_density_per_m2"])
    w.writerows(rows)
print("written:", OUT)
