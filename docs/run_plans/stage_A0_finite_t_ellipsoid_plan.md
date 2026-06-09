# Stage A0 / A1 — finite-T ellipsoid eigenstrain run plan

Date: 2026-06-05. Goal: produce the supervisor's primary deliverable — **defect / dislocation
structure and plastic zone in the Al matrix** caused by the magnetostriction-equivalent
deformation of the Fe₄Al₁₃ inclusion. No LAMMPS was run while writing this plan.

## Why this stage exists (the gap)
The committed eigenstrain series was **minimize-only** and produced **zero dislocations / ~zero
stacking faults** at every ε_z incl. the 0.01 overload (`results/tables/ellipsoid_inclusion/
ellipsoid_trial_001_matrix_defect_dxa.csv`). Two causes: (1) minimization can't cross the
nucleation barrier; (2) the matrix (~6.5 nm) is too small to host a dislocation loop. A0 fixes (1);
A1 fixes (2).

## Physical anchoring (from Pshonkin's paper — see `docs/_local/assessment_and_plan_ru.md`)
- B = 0.7 T; magnetostriction stress σ_m = λ_m·B = **147 MPa** (λ_m = 2.1·10⁸ N/(T·m²)).
- Matrix yield = **120 MPa**; σ_m (147) > yield (120) ⇒ dislocation generation expected experimentally.
- Eigenstrain ↔ stress: ε ≈ σ_m/E ≈ 147 MPa / 70 GPa ≈ **0.0021** ⇒ ε_z = 0.0025 is the
  magnetostriction-equivalent case; 0.0050 / 0.0100 are overload probes; 0.0010 is sub-threshold.

## Stage A0 (this sync, 24k atoms — protocol validation)
- **Starting structure:** `lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/data.ellipsoid_nvt_300k`
  (24,259 atoms; Al matrix ids 1–23263, inclusion ids 23264–24259; box 64.8×64.8×97.2 Å, p p p).
- **Eigenstrain cases:** ε_z = 0 / 0.0010 / 0.0025 / 0.0050 / 0.0100 (ε_x = ε_y = −0.5 ε_z).
- **Regenerate eigenstrained structures** (deterministic, needs numpy+scipy):
  `for e in 0.0010 0.0025 0.0050 0.0100; do python analysis/python/apply_ellipsoid_eigenstrain.py $e; done`
- **Run:** `lammps/05_finite_t_ellipsoid/stage_A0_24k/in.nvt_eps_{0000,0010,0025,0050,0100}` —
  held-inclusion NVT at 300 K, 100 ps each (smoke-test at 2000 steps first). MEAM, CPU.
- **Expected outputs:** `dump.nvt_eps_*.lammpstrj` (trajectory), `data.nvt_eps_*_final`,
  thermo log. (All gitignored — stay local.)
- **Analyze:** OVITO DXA/CNA via `analysis/python/analyze_matrix_defects_dxa.py` (extend its
  `cases` list to the A0 dumps). Report FCC%/HCP%/Other%, dislocation density & types, and the
  plastic-zone extent around the inclusion, vs the minimize-only baseline.
- **Expected result:** likely still near-elastic at 24k (size-limited). A0 confirms the protocol
  works and isolates size as the remaining blocker → triggers A1.

## Stage A1 (next, larger matrix — the conclusive run)
- **Build a larger Al matrix** with an elongated Fe₄Al₁₃ inclusion (target ~20–50 nm box; the MD
  reference Shi et al. 2025 used 200×200×300 Å ≈ 720k atoms; Atomsk for the matrix lattice).
- **Held / ramped eigenstrain** at ε_z ≈ 0.0025 (σ_m-equivalent) plus an overload series to find the
  **dislocation-nucleation threshold** (the headline physical result).
- **Finite-T NVT** at 300 K; DXA → dislocation density vs ε, dislocation types (Shockley 1/6⟨112⟩
  etc.), plastic-zone size; before/after comparison.
- **Connect to experiment:** map the MD dislocation-density rise to the measured latent-energy /
  Taylor-coefficient rise (ΔE_s 0.67→0.78; Taylor 0.07→0.25) — the atomistic mechanism of the
  thermoplastic effect.

## Compute-time estimate (PC: RTX 3060 Ti + CPU, WSL2)
**Key fact: MEAM (`pair_style meam`) is CPU-only in LAMMPS — the GPU does NOT accelerate it.** So A0
runs on CPU cores; the RTX helps only if we switch the matrix to a GPU-accelerated EAM potential
(a decision for the supervisor — accuracy of the MEAM Al-Fe cross-term vs scale/speed of EAM+GPU).

Rough, assumption-stated (MEAM ≈ 3–5× slower than EAM; ~100–200 timesteps/s for 24k atoms on a
modern multicore CPU):

| Stage | atoms | potential / HW | per case | 5 cases |
|---|---:|---|---|---|
| A0 smoke (2k steps) | 24k | MEAM / CPU | ~0.5–2 min | ~5–10 min |
| A0 production (100k steps) | 24k | MEAM / CPU | ~10–25 min | **~1–2 h** |
| A1 MEAM / CPU | ~250k | MEAM / CPU | ~3–8 h | ~1–2 days |
| A1 MEAM / CPU | ~1M | MEAM / CPU | ~1–3 days | multi-day |
| A1 EAM / **GPU (3060 Ti)** | ~250k–1M | EAM / GPU | ~0.5–3 h | ~3–12 h |

Takeaways: **A0 is cheap (~1–2 h, do it now).** A1 at the supervisor's target scale is only
practical on the GPU if we move to an EAM Al-Fe potential; with MEAM it is CPU-bound and multi-day.
This is the main resource decision to settle with him.
