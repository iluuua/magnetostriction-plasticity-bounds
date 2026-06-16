# Production pipeline master plan (Al + Fe4Al13, magnetostriction mechanical channel)

Updated: 2026-06-12 (after A0 24k completion; A1 target trimmed to A1_custom_100k).

Mission context: we test the mechanical channel of magnetostriction —
`magnetic field → magnetostriction/eigenstrain of the inclusion → local stress →
Al defects/dislocations/plastic zone`. The direct magnetic field is NOT modeled
(see section C); it is replaced by an eigenstrain surrogate applied to the
inclusion.

## A. Current exact model

- Al fcc matrix + Fe4Al13 ellipsoidal inclusion (axis ratio 1:1:2), single crystal.
- MEAM (Jelinek 2012 AlSiMgCuFe) atomistic dynamics in LAMMPS.
- Finite-T MD: NVT at 300 K, held-inclusion protocol in eps production runs
  (inclusion atoms frozen in the eigenstrained shape; matrix integrates).
- Eigenstrain surrogate: inclusion coordinates scaled by
  eps_x = eps_y = −0.5·eps_z, eps_z about the inclusion center (volume-quasi-preserving
  tetragonal distortion mimicking magnetostriction).
- eps_z sweep; A0 24k completed at eps = 0 / 0.0010 / 0.0025 / 0.0050 / 0.0100
  (all smoke + all 100k-step production successful, chunked, no hangs).
- DXA/CNA defect analysis (OVITO): FCC/HCP/OTHER fractions of the matrix,
  dislocation count/length/density, stacking-fault indicator, plastic-zone shell
  statistics.
- Chunked GPU production: LAMMPS KOKKOS/CUDA (meam/kk), 10k-step chunks,
  restart+resume, watchdog (25 min no-progress kill, one retry), validated
  neighbor workaround `neigh_modify delay 0 every 10 check no`.
- Prep for built (non-A0) sizes: GPU-safe two-stage thermal settle
  (0.5 fs ramp 50→300 K, then 1 fs NVT 300 K) — **no minimize on GPU**
  (minimize crashes meam/kk CUDA; see A1_prep_failure_diagnosis.md in the
  20260611-175339 run root).

## B. Current approximation (what the model is NOT yet)

- Magnetic field replaced by eigenstrain: no field, no spins, no domains.
- Magnetostriction is a scalar eps_z (tetragonal), not derived from spin/domain
  structure or magnetoelastic tensors.
- Ideal ellipsoid inclusion (sharp interface, ideal stoichiometric Fe4Al13).
- One inclusion per box (no interaction between inclusions).
- Mostly ideal Al matrix: single crystal, no grain boundaries, no polycrystal,
  no pre-existing defects (vacancies/dislocations) yet.
- Nanoscale model (10–16 nm boxes, 2–8 nm inclusions), not the micron-scale real
  inclusion; size effects are probed by the A-stage atom-count ladder.
- NVT only (no barostat coupling study yet), 300 K only.
- A1+ baselines are thermally settled, not energy-minimized (GPU minimize is
  impossible on this build); interface CNA counts may carry a small systematic
  offset vs the minimized A0 baseline — eps cases must be compared against the
  same stage's baseline.

## C. Direct magnetic field / spin-lattice future track

status: **disabled_future_track** (do not implement or launch)

requires (all currently missing):

- magnetic_moments_muB (Fe in Fe4Al13/FeAl environment)
- exchange_constants_Jij_meV
- spin_lattice_coupling
- dJ_dr
- magnetostriction_tensor
- magnetoelastic_constants_B1_B2
- elastic_constants_C11_C12_C44 (for the intermetallic, validated)
- magnetic_anisotropy_K1_K2_Ku
- field_orientation
- domain_structure
- validated_spin_lattice_potential (Al–Fe, SPIN-package compatible)
- experimental_validation_data

Until every item above is parameterized and validated, the eigenstrain surrogate
remains the production mechanism. Any attempt to run a SPIN production without
these parameters is a hard stop condition.

## D. Stage B parameter axes (represented, disabled until the Stage A gate)

All axes below are **disabled**; enabling any of them requires the Stage A gate
plus manual approval (see `manual_approval_required` in
`configs/stage_sweep_gpu_A1_100k_smoke_production.yaml`).

- inclusion_size_nm: [2, 4, 6]
- shapes: ["sphere", "ellipsoid_1_1_2", "platelet"]
- positions: ["grain_interior", "near_grain_boundary"]
- predefect_variants: ["perfect", "vacancies_low", "vacancies_medium", "seed_dislocation_if_available"]
- inclusion_counts: [1, 2, 4]
- compositions: ["Fe4Al13", "FeAl", "Fe3Al"]
- orientation_variants: ["baseline", "orientation_sweep_future"]
- temperatures_K: [300] now, future [250, 300, 350]
- cyclic_exposure: disabled_future_track

## E. Criticality table (impact on observing the real defect mechanism)

| axis | criticality |
| --- | --- |
| grain boundary / position | 10/10 |
| polycrystal | 10/10 |
| inclusion size | 9/10 |
| predefects | 9/10 |
| shape | 8/10 |
| concentration (inclusion count) | 8/10 |
| composition (Fe4Al13/FeAl/Fe3Al) | 8/10 |
| orientation | 8/10 |
| cyclic exposure | 7/10 |
| temperature | 6/10 |

## F. Stage A gate logic

- **A0 24k: completed.** 5/5 eps production stable; defect analysis shows no
  dislocations and no HCP growth at any eps (plastic-zone counts at noise level).
- **Next: A1_custom_100k trimmed gate** (this config). Skip 80k/120k and the
  short fidelity entirely; run smoke (2000) → production (100000) at ~100k atoms
  for the priority eps only: 0.0025 (physical_main) and 0.0100 (overload).
  eps = 0 / 0.0010 / 0.0050 at 100k are manual-only options.
- Gate outcomes:
  - If **eps=0.0025 has signal** (dislocations, HCP/OTHER growth, plastic zone):
    recommend A1_medium 200k/250k or a 500k confirmation — after manual approval.
  - If **eps=0.0100 has signal but eps=0.0025 does not**: recommend eps=0.0050
    at 100k OR an A1_medium overload case — after manual approval.
  - If **neither has signal**: pivot to realism instead of blind size escalation:
    near_grain_boundary position, vacancies_medium predefects,
    seed_dislocation_if_available, polycrystal_future. Do **not** recommend a
    blind 700k ideal monocrystal.
- Hard rails regardless of outcome: Stage B, A1_medium, A2 500k/700k, SPIN field,
  and composition sweeps stay disabled without manual approval; A0 results are
  never rerun or overwritten.

## Operational reference

- Active config: `configs/stage_sweep_gpu_A1_100k_smoke_production.yaml`
- Runner: `scripts/run_stage_sweep.py` → `analysis/python/stage_runner/gpu_grid.py`
- Run roots: `runs/stage_sweep_gpu_A1_100k/<timestamp>/`
- A0 reference run root (read-only): `runs/stage_sweep_gpu_grid/20260611-175339/`
- Failure diagnosis that shaped the prep protocol:
  `runs/stage_sweep_gpu_grid/20260611-175339/A1_prep_failure_diagnosis.md`
- Layered optimizer (planner-only, never launches MD):
  `scripts/run_layered_optimizer.py` + `configs/layered_optimizer_policy.yaml`
