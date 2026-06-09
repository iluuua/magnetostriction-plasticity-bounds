# Stage A0 — finite-T NVT, ellipsoid inclusion (24,259 atoms)

**Purpose.** Add the missing ingredient — **finite-temperature MD** — to the ellipsoid eigenstrain
series. The earlier series was *minimize-only* and gave **zero dislocations** at every eigenstrain
(see `docs/ellipsoid_inclusion/ellipsoid_trial_001_defect_analysis_check.md`). A0 re-runs the same
eigenstrain cases at 300 K with the inclusion held in its eigenstrained shape (sustained
magnetostriction push), then asks via OVITO DXA whether dislocations / a plastic zone appear.

**This is a small-model A0 (24 k atoms, ~6.5 nm).** It is expected to remain largely elastic; its
real job is to (a) validate the finite-T protocol end-to-end on the PC and (b) confirm whether size,
not just the minimize-only choice, is the blocker. The physically conclusive run is Stage A1
(larger matrix) — see `docs/run_plans/stage_A0_finite_t_ellipsoid_plan.md`.

## Inputs in this folder
- `in.nvt_eps_0000` — control (no eigenstrain; reads the equilibrated NVT baseline)
- `in.nvt_eps_0010 / 0025 / 0050 / 0100` — eigenstrain ε_z = 0.0010 / 0.0025 / 0.0050 / 0.0100
  (ε_z = 0.0025 ≈ σ_m/E, the magnetostriction-equivalent strain at B = 0.7 T)

## Prerequisites on the PC
1. LAMMPS with the **MEAM** package (CPU build — MEAM is not GPU-accelerated).
2. Starting structure `lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/data.ellipsoid_nvt_300k`
   (included in this sync).
3. The eigenstrained structures for ε_z > 0 are **regenerated** from the baseline (they are not
   shipped): run the eigenstrain generator once per case (needs `numpy`, `scipy`):
   ```bash
   cd <repo root>
   for e in 0.0010 0.0025 0.0050 0.0100; do python analysis/python/apply_ellipsoid_eigenstrain.py $e; done
   ```
   This writes `structures/interface/ellipsoid_inclusion/trial_001/eigenstrain/epsz_*/data.*`.

## Run (from this directory)
```bash
cd lammps/05_finite_t_ellipsoid/stage_A0_24k
# smoke test first: edit "run 100000" -> "run 2000" in in.nvt_eps_0000, then:
lmp -in in.nvt_eps_0000          # control; confirm it runs, no errors, T~300 K
# then production for all cases:
for f in in.nvt_eps_0000 in.nvt_eps_0010 in.nvt_eps_0025 in.nvt_eps_0050 in.nvt_eps_0100; do lmp -in $f; done
```
`lmp` = your LAMMPS binary (e.g. `lmp`, `lmp_serial`, or `mpirun -np N lmp`).

## Analyze (defects / dislocations)
After the runs, point the DXA/CNA script at the new trajectories (extend its `cases` list to the
`dump.nvt_eps_*_final.lammpstrj` files) and run with the OVITO venv:
```bash
.venv/bin/python analysis/python/analyze_matrix_defects_dxa.py
```
Compare FCC% / HCP% / Other% and dislocation density vs the minimize-only baseline.

## Notes / caveats
- "Held inclusion" idealizes a *sustained* field-on push; the frozen inclusion surface can carry a
  slightly artificial stress (same caveat class as the flat-interface fixed-bottom support). A
  ramped/continued eigenstrain is a Stage A1 refinement.
- Outputs (`*.lammpstrj`, `data.nvt_eps_*_final`) are gitignored and stay local.
- Do not overwrite the existing `04_ellipsoid_inclusion` data; A0 writes only inside this folder.
