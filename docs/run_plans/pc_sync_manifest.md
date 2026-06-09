# PC sync manifest — Al / Fe₄Al₁₃ MD, continue Stage A0/A1 on Windows/WSL

Date: 2026-06-05. Branch: `sync/pc-stage-a0` (forked from `main` @ 263e493). This file is the
**single handoff doc**: it carries the scientific context, the file map, what to pull, and how to
start, so Stage A0 can continue on the PC (and in a fresh chat) without the Mac.

---

## Purpose
Sync everything needed to run **finite-temperature Stage A0** (and prepare Stage A1) of the Al /
Fe₄Al₁₃ inclusion study on a Windows/WSL PC with an RTX 3060 Ti. Raw trajectories and the
supervisor's copyrighted source PDFs are deliberately excluded (see below).

## Where we are (TL;DR for whoever picks this up)
- **Project:** MD of an Al matrix containing a Fe₄Al₁₃ (Al₁₃Fe₄ / FeAl₃) intermetallic inclusion.
  Physical driver = **magnetostriction** of the inclusion in a magnetic field → local stress at the
  inclusion/matrix boundary → **dislocations / plastic zone** in the Al matrix. The magnetic field
  is NOT modeled; it is replaced by an **eigenstrain** (inclusion deformation) surrogate.
- **Two branches built so far:** (1) flat Al(111)/Fe₄Al₁₃(100) interface, loads 0/60/120/147/200 MPa;
  (2) ellipsoid Fe₄Al₁₃ inclusion (24,259 atoms), eigenstrain series ε_z = 0.0010/0.0025/0.0050/0.0100.
- **The gap we found:** the supervisor's #1 requested output is the **defect/dislocation structure**.
  We had never computed it. When we finally ran OVITO DXA/CNA on the existing data →
  **0 dislocations, ~0 stacking faults at every ε_z incl. 0.01 overload; matrix response elastic.**
  Cause: model too small (~6.5 nm) **and** minimize-only (no finite-T dynamics).
- **This sync's job:** ship the finite-T A0 protocol (templates + plan + starting structure) so the
  PC can re-run at 300 K with the inclusion held (sustained push), and then scale up (A1).

## Physical constants (from the supervisor's own paper — all real, do not invent)
B = 0.7 T; λ_m = 2.1·10⁸ N/(T·m²); **σ_m = λ_m·B = 147 MPa**; matrix **yield = 120 MPa**
(σ_m > yield ⇒ plasticity); E = 75.7→67.9 GPa; Taylor coeff 0.07→0.25; ΔE_s 0.67→0.78 J/m³;
grain ~60 µm, inclusion ~5 µm. ⇒ our 120 & 147 MPa are the paper's yield and magnetostriction
stress; ε_z = 0.0025 ≈ σ_m/E. Full assessment: `docs/_local/assessment_and_plan_ru.md` (Mac-only,
not synced — it discusses the supervisor relationship).

## Required on PC
- **Python 3.12** (for the OVITO wheel; 3.13 not yet supported) + venv.
- `pip install numpy scipy pandas matplotlib ovito` (scipy needed by the eigenstrain generator;
  ovito provides CNA + DXA).
- **LAMMPS with the MEAM package** (CPU build — MEAM is not GPU-accelerated). conda-forge `lammps`
  is the easiest; or build with `-DPKG_MEAM=on`. (GPU/EAM is a later A1 option, see compute note.)
- **Potentials** — included in the repo (`potentials/`), no separate download.
- **Starting structure** `data.ellipsoid_nvt_300k` — included (force-added).

## Included in Git (this branch)
- Docs: `docs/audit/*` (forensic audit + 45-claim register), `docs/article/*` (RU/EN articles,
  figures/tables plan, manifest of v1→v2), `docs/ellipsoid_inclusion/*`, `docs/interface*`,
  `docs/00_index/DOC_INDEX.md`, `docs/run_plans/*` (this file + the A0 plan), `README.md`,
  `results/reports/run_report.md`, `.codex/state/current_context.md`.
- Scripts: `analysis/python/*.py` — build/check/plot ellipsoid + eigenstrain, and
  **`analyze_matrix_defects_dxa.py`** (OVITO DXA/CNA; portable repo-root, runs on PC).
- Results (small/medium): `results/tables/**/*.csv`, `results/**/*.json`, `results/figures/**/*.png`.
- Potentials: `potentials/` (EAM Zhou + MEAM Jelinek 2012 + README).
- LAMMPS inputs/logs/summaries: `lammps/**/in.*`, `lammps/**/*.lammps`, `lammps/**/*summary*.json`;
  finite-T templates `lammps/05_finite_t_ellipsoid/stage_A0_24k/in.nvt_eps_*` + its README.
- **Starting structures (force-added, small):**
  `lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/data.ellipsoid_nvt_300k` (3.0 MB, the A0
  start), `.../00_minimize/data.ellipsoid_minimized` (1.9 MB),
  `structures/interface/ellipsoid_inclusion/trial_001/data.ellipsoid_trial_001` (1.6 MB).

## Deliberately excluded (NOT in Git)
- `*.lammpstrj` raw trajectories (incl. the 79 MB ellipsoid NVT dump) and all heavy `data.*` /
  eigenstrain `data.*` (regenerable on PC, see below).
- `*.xyz` visual-debug slices; `.DS_Store`; `*.pyc` / `__pycache__`; temp files.
- `docs/_local/` (private notes); `pshonkin_materials_ishodniki/` (copyrighted Elsevier PDFs +
  the supervisor's unpublished manuscript — must not be published).

## If data files are missing on PC
- The **eigenstrained** structures for ε_z > 0 are regenerated, not shipped:
  `for e in 0.0010 0.0025 0.0050 0.0100; do python analysis/python/apply_ellipsoid_eigenstrain.py $e; done`
  (reads the shipped `data.ellipsoid_nvt_300k`; needs numpy+scipy; deterministic).
- The raw trajectories used in the original DXA analysis stay on the Mac; the PC produces its own
  trajectories when it runs A0. The supervisor's PDFs are on the Mac under
  `pshonkin_materials_ishodniki/` (transfer manually if reading is needed; do not commit).

## PC bootstrap
```bash
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/iluuua/physics_md_al_fe.git
cd physics_md_al_fe
git fetch origin
git switch sync/pc-stage-a0
cat docs/run_plans/pc_sync_manifest.md

python3.12 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install numpy scipy pandas matplotlib ovito

git status --short
find docs/run_plans -maxdepth 2 -type f | sort
find analysis/python -maxdepth 2 -type f | sort
```

## What to run on PC, in order
1. **Read-only audit first:** read `docs/run_plans/stage_A0_finite_t_ellipsoid_plan.md`,
   `docs/ellipsoid_inclusion/ellipsoid_trial_001_defect_analysis_check.md`,
   `docs/audit/claims_register.md`. Confirm `data.ellipsoid_nvt_300k` is present.
2. **Regenerate eigenstrained structures** (command above).
3. **A0 smoke test:** in `lammps/05_finite_t_ellipsoid/stage_A0_24k/in.nvt_eps_0000` change
   `run 100000` → `run 2000`, then `lmp -in in.nvt_eps_0000`. Confirm: no errors, T≈300 K, files written.
4. **A0 production:** run all 5 `in.nvt_eps_*` (100 ps each; ~1–2 h total on CPU).
5. **Defect analysis:** extend the `cases` list in `analysis/python/analyze_matrix_defects_dxa.py`
   to the A0 `dump.nvt_eps_*_final.lammpstrj`, then `.venv/bin/python analysis/python/analyze_matrix_defects_dxa.py`.
   Compare dislocation density vs the minimize-only baseline.
6. If A0 is still elastic (expected at 24k), proceed to **Stage A1** (larger matrix) per the plan.

## Compute estimate
See the table in `docs/run_plans/stage_A0_finite_t_ellipsoid_plan.md`. Summary: **A0 ≈ 1–2 h on
CPU** (MEAM is CPU-only; the RTX 3060 Ti does not accelerate MEAM). Reaching the supervisor's target
scale (tens of nm / ~1M atoms) is only GPU-practical if we switch the matrix to an EAM Al-Fe
potential — a decision for the supervisor.

## Open decisions for the supervisor (the meeting)
1. Confirm finite-T MD is required (not minimize-only) — our DXA null result is the evidence.
2. ε = σ_m/E ≈ 0.002 as the magnetostriction strain, or a direct λ_s for Fe₄Al₁₃?
3. Model size / compute: MEAM-CPU (multi-day at scale) vs EAM-GPU (fast, less exact cross-term)?
4. Single-crystal matrix now, polycrystal (grain boundaries) later (his Step 3)?
5. Provide SEM/EDS + anisotropy/orientation stress data he promised.
6. Target journal + the headline result he wants (nucleation threshold? ρ_dislocation vs ε? plastic zone?).

## Success criterion
After `git pull` + `git switch sync/pc-stage-a0`, the PC has every script / doc / input / potential /
starting structure needed to run Stage A0 and prepare A1 — without the Mac, except the explicitly
excluded raw trajectories (regenerable) and the supervisor's reference PDFs.
