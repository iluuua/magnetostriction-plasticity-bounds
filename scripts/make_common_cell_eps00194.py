#!/usr/bin/env python
"""Build a COMMON-CELL eps00194 seed from the relaxed eps0000 baseline (path-A protocol audit).

Why: independent ``box/relax x y`` gave eps0000/eps00194 different lateral cells (Ly differs 0.05 A)
and different atom counts (113295 vs 113265 -- 30 matrix atoms near the interface removed differently
because the eigenstrained inclusion top sits ~0.097 A higher). For a valid baseline-subtracted
Delta-sigma(r) the two cases must share the SAME lateral cell and the SAME atom set, differing ONLY by
the intended eps_z eigenstrain on the inclusion.

This transforms the eps0000 RELAXED structure: the 7335 inclusion atoms (as-built z < interface_z) are
scaled in z by (1+eps_z) ABOUT z=0 -- exactly the generator's eigenstrain definition
(prepare_stageF_boundary_patch_geometry.py: ``pos[:,2] *= 1+eps_z``) -- while the 105960 matrix atoms
and the box are left untouched. No clip, so the inclusion atom SET is identical (the generator's
clip-after-scale never crossed an atomic layer: inclusion count is 7335 for both eps). Result: identical
113295-atom set, identical box, perturbed only by eps_z. A fixed-box atom-only CPU minimize then follows.
"""
from __future__ import annotations

import sys
from pathlib import Path

EPS_Z = 0.00194          # canonical eps00194 case value (generator GEOMETRIES dict); prompt wrote 0.001942
INTERFACE_Z = 50.0       # fe_depth_A; spatial inclusion (Fe4Al13 block) = z < 50, fcc-Al matrix starts at z = 50
N_TOTAL_EXPECT = 113295
N_FE_EXPECT = 7335       # metadata 'inclusion_atoms' is really the Fe-TYPE count; all Fe must be inside the inclusion

ROOT = Path(r"C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe")
ASBUILT = ROOT / "structures/stageF_boundary_patch/F0_planar_100A_comm_eps0000/data.F0_planar_100A_comm_eps0000"
RELAXED = ROOT / "runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/F0_planar_100A_comm_eps0000/equil/data.F0_planar_100A_comm_eps0000.relaxed"
OUT = ROOT / "runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/F0_planar_100A_comm_eps00194/equil/data.F0_planar_100A_comm_eps00194.common_cell_seed"


def section_bounds(lines: list[str], name: str) -> int:
    for i, l in enumerate(lines):
        if l.strip().startswith(name):
            return i
    return -1


def atom_line_range(lines: list[str]) -> tuple[int, int]:
    a = section_bounds(lines, "Atoms")
    if a < 0:
        raise SystemExit("no Atoms section")
    v = section_bounds(lines, "Velocities")
    end = v if v > a else len(lines)
    return a + 1, end


def main() -> None:
    ab = ASBUILT.read_text().splitlines()
    a0, a1 = atom_line_range(ab)
    inclusion_ids: set[int] = set()
    n_fe_total = n_fe_in_incl = n_fe_in_matrix = 0
    for l in ab[a0:a1]:
        if not l.strip():
            continue
        p = l.split()
        atype, z = int(p[1]), float(p[4])
        is_incl = z < INTERFACE_Z
        if is_incl:
            inclusion_ids.add(int(p[0]))
        if atype == 2:
            n_fe_total += 1
            n_fe_in_incl += int(is_incl)
            n_fe_in_matrix += int(not is_incl)
    print(f"as-built spatial inclusion atoms (z<{INTERFACE_Z}): {len(inclusion_ids)}")
    print(f"Fe atoms: total={n_fe_total} in-inclusion={n_fe_in_incl} in-matrix={n_fe_in_matrix} "
          f"(expect Fe total {N_FE_EXPECT}, matrix 0)")
    if n_fe_total != N_FE_EXPECT or n_fe_in_matrix != 0:
        raise SystemExit(f"FAIL Fe placement: total {n_fe_total} (expect {N_FE_EXPECT}), "
                         f"matrix {n_fe_in_matrix} (expect 0)")

    rel = RELAXED.read_text().splitlines()
    r0, r1 = atom_line_range(rel)
    out: list[str] = []
    header = list(rel[: section_bounds(rel, "Atoms") + 1])  # through 'Atoms # atomic'
    header[0] = ("LAMMPS data common-cell eps00194 seed = relaxed eps0000 + eps_z=%.5f eigenstrain on "
                 "inclusion (z<%.1f), same box; units metal" % (EPS_Z, INTERFACE_Z))
    out.extend(header)
    out.append("")

    n_incl = n_total = 0
    z_incl_before_max = -1e9
    z_incl_after_max = -1e9
    for l in rel[r0:r1]:
        if not l.strip():
            continue
        p = l.split()
        aid, atype = int(p[0]), int(p[1])
        x, y, z = p[2], p[3], float(p[4])
        rest = p[5:]
        n_total += 1
        if aid in inclusion_ids:
            z_incl_before_max = max(z_incl_before_max, z)
            z = z * (1.0 + EPS_Z)
            z_incl_after_max = max(z_incl_after_max, z)
            n_incl += 1
        tail = (" " + " ".join(rest)) if rest else ""
        out.append(f"{aid} {atype} {x} {y} {z:.10f}{tail}")

    print(f"relaxed total atoms: {n_total} (expect {N_TOTAL_EXPECT})")
    print(f"inclusion atoms strained: {n_incl} (expect {len(inclusion_ids)})")
    print(f"inclusion z_max before -> after: {z_incl_before_max:.5f} -> {z_incl_after_max:.5f} "
          f"(+{z_incl_after_max - z_incl_before_max:.5f} A)")
    if n_total != N_TOTAL_EXPECT or n_incl != len(inclusion_ids):
        raise SystemExit("FAIL atom-count invariant")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n")
    print(f"WROTE {OUT}")
    print(f"box lines:\n  " + "\n  ".join(rel[5:8]))


if __name__ == "__main__":
    main()
