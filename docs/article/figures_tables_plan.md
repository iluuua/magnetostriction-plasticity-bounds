# Figures and tables plan

Date: 2026-06-04. Built on `docs/article/figure_plan.md` and `selected_figures_checklist.md`, verified
against files actually present on disk. Bilingual captions; safe vs unsafe interpretation per figure.

> **Availability flags:** ✅ present in repo · ⚠️ referenced but **absent** (must be produced/attached).

---

## Main-text figures

### Figure 1 — Model geometry
- Files: ⚠️ `results/figures/article_selected/figure_1a_flat_interface*.png` (absent),
  ⚠️ `figure_1b_ellipsoid_cutaway.png`, `figure_1c_ellipsoid_fe_only.png`,
  `figure_1d_ellipsoid_epsz_p0p01000_cutaway.png` (all **absent** on disk; only figures 2–6 exist).
  Source XYZ slices for rendering exist under `lammps/04_ellipsoid_inclusion/trial_001/.../visual_debug/`
  and `structures/interface/ellipsoid_inclusion/trial_001/visual_debug/`.
- Shows: the two studied geometries (flat Al/Fe4Al13 interface; ellipsoidal Fe4Al13 inclusion in Al).
- Why it matters: establishes that the study uses two simplified controlled geometries.
- Caption RU: «Рис. 1. Две упрощённые модельные геометрии: плоская граница Al(111)/Fe₄Al₁₃(100) и
  эллипсоидное включение Fe₄Al₁₃ в матрице Al (cutaway и Fe-only виды).»
- Caption EN: "Fig. 1. The two simplified model geometries: the flat Al(111)/Fe4Al13(100) interface and
  the ellipsoidal Fe4Al13 inclusion in an Al matrix (cutaway and Fe-only views)."
- Safe: "simplified prototype geometries." Unsafe: presenting them as experimental microstructures.
- **Action:** render Figure 1 in OVITO from the existing XYZ/data files before submission.

### Figure 2 — Flat-interface stress profile (200 MPa)
- File: ✅ `results/figures/article_selected/figure_2_flat_interface_200mpa_stress_profile.png`
  (= `results/figures/interface_trial_001_stress_200mpa_compression_ramp_stress_profile.png`).
- Shows: z-profile of the comparative virial stress proxy at the 200 MPa upper-bound run.
- Caption RU: «Рис. 2. z-профиль virial-напряжения (comparative proxy) при 200 MPa. Наибольший по
  модулю гидростатический proxy у фиксированной нижней опоры (z≈5–10 Å) — likely boundary artifact.»
- Caption EN: "Fig. 2. z-profile of the comparative virial stress proxy at 200 MPa. The largest
  |hydrostatic| proxy sits at the fixed-bottom support (z≈5–10 Å) and is a likely boundary artifact."
- Safe: comparative proxy; support maximum is an artifact. Unsafe: absolute/experimental stress.

### Figure 3 — Eigenstrain final energy
- File: ✅ `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_energy_final.png`
  (= article_selected/figure_3).
- Shows: minimized potential energy vs eps_z (0.0010/0.0025/0.0050/0.0100).
- Caption RU: «Рис. 3. Финальная минимизированная потенциальная энергия для серии eigenstrain ε_z.»
- Caption EN: "Fig. 3. Final minimized potential energy across the eigenstrain series (eps_z)."
- Safe: numerical trend across a controlled surrogate. Unsafe: a calibrated energy–field relationship.

### Figure 4 — Eigenstrain minimum pair distance
- File: ✅ `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_min_pair_distance.png`.
- Shows: minimized minimum pair distance vs eps_z (all ≥ 1.95 Å, none < 1.8 Å).
- Caption RU: «Рис. 4. Минимальное межатомное расстояние после минимизации; жёстких overlap < 1.8 Å нет.»
- Caption EN: "Fig. 4. Minimized minimum interatomic distance; no hard overlaps below 1.8 Å."
- Safe: no hard overlaps. Unsafe: proof of physical integrity.

### Figure 5 — Eigenstrain Al-Fe warning contacts
- File: ✅ `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_alfe_warning_pairs.png`.
- Shows: count of Al-Fe contacts below 2.1 Å vs eps_z (small, 2–4).
- Caption RU: «Рис. 5. Число Al-Fe контактов ниже 2.1 Å (warning-уровень) по серии eigenstrain.»
- Caption EN: "Fig. 5. Number of Al-Fe contacts below the 2.1 Å warning threshold across the series."
- Safe: warning-level contacts to monitor. Unsafe: a failure/fracture count.

### Figure 6 — Eigenstrain final force residual
- File: ✅ `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_force_two_norm_final.png`.
- Shows: final force two-norm vs eps_z; eps_z = 0.0100 has the largest residual.
- Caption RU: «Рис. 6. Финальный force two-norm; случай ε_z = 0.0100 — численная stress-test точка.»
- Caption EN: "Fig. 6. Final force two-norm; the eps_z = 0.0100 case is a numerical stress-test point."
- Safe: numerical convergence quality. Unsafe: a physical strength/yield indicator.

### Figure 7 (optional) — Warning-pair distance over time (147 / 200 MPa)
- Files: ✅ `results/figures/interface_trial_001_stress_147mpa_warning_pair_distance_over_time.png`,
  ✅ `..._200mpa_warning_pair_distance_over_time.png`.
- Caption RU: «Рис. 7. Расстояние внутренней пары Fe₄Al₁₃ 232-260 по кадрам; контакт перемежающийся,
  без монотонного схлопывания, не ниже 1.8 Å.»
- Caption EN: "Fig. 7. Distance of the internal Fe4Al13 pair 232-260 over frames; intermittent contact,
  no monotonic collapse, never below 1.8 Å."
- Safe: internal, monitor-only. Unsafe: cross-slab interface failure.

### OVITO review screenshots — ⚠️ NOT in repository
The 120/147/200 MPa check docs list `results/figures/ovito_review_{120,147,200}mpa/...png`, but these
folders **do not exist on disk**. Manual screenshots must be attached if required for submission. Do not
cite them as present files (claims register U07).

---

## Main-text tables

### Table 1 — Mismatch candidates
- File: ✅ `results/tables/interface_mismatch_candidates.csv`.
- Columns to show: Al hkl, Fe4Al13 hkl, max mismatch %, angle delta, area mismatch %, estimated atoms, rank.
- Caption RU: «Табл. 1. Ранжирование кандидатов ориентации; лучший — Al(111)/Fe₄Al₁₃(100), mismatch 0.943 %.»
- Caption EN: "Table 1. Ranked orientation candidates; best is Al(111)/Fe4Al13(100), 0.943 % mismatch."
- Article use: justify the chosen orientation as a numeric selection, not a proven OR.

### Table 2 — Loading force table
- File: ✅ `results/tables/interface_trial_001_loading_force_table.csv`.
- Columns: scenario, sigma (MPa), F_total (N), F_atom (N), F_atom (eV/Å).
- Caption RU: «Табл. 2. Перевод заданного напряжения в силу на атом для 0/60/120/147/200 MPa.»
- Caption EN: "Table 2. Target stress to per-atom force for 0/60/120/147/200 MPa."

### Table 3 — Loading-series comparison (0–200 MPa)
- File: ✅ `results/tables/interface_trial_001_stress_000_060_120_147_200mpa_comparison.csv`.
- Columns: scenario, steps, force, ERROR/nan/lost, dangerous, pairs<1.8, cross-slab Al-Fe<2.1, warning-pair
  stats, visual_review_status, verdict.
- Caption RU: «Табл. 3. Сводка контролируемых нагрузок 0–200 MPa; без overlap < 1.8 Å и cross-slab
  контактов < 2.1 Å; 200 MPa — upper-bound/failure-probe.»
- Caption EN: "Table 3. Controlled 0–200 MPa loading summary; no overlaps < 1.8 Å, no cross-slab contacts
  < 2.1 Å; 200 MPa is an upper-bound/failure-probe."
- Article use: the central evidence table for Branch 1. Note the differing step protocols.

### Table 4 — Eigenstrain series summary
- File: ✅ `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_summary.csv`.
- Caption RU: «Табл. 4. Сводка серии eigenstrain: min pair, Al-Fe < 2.1 Å, энергия, force residual.»
- Caption EN: "Table 4. Eigenstrain series summary: min pair, Al-Fe < 2.1 Å, energy, force residual."

### Table 5 (supporting) — Key results + simulation parameters
- Files: ✅ `results/tables/article/article_key_results_summary.csv`,
  ✅ `results/tables/article/simulation_parameters_summary.csv`.
- Article use: methods/parameters appendix; mirrors Sections 6–12.

---

## Supplementary figures (present, optional)
Per-load stress profiles ✅ `interface_trial_001_stress_{000,060,120,147}mpa_*_stress_profile.png`;
✅ time-averaged, unloaded stress/strain, contact-density z-profile; warning-pair distance plots
(060/120). All are comparative virial proxies / diagnostic plots — same safe/unsafe framing as Figure 2.
