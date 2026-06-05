# Source map — project blocks → files, key numbers, safe/unsafe claims

Date: 2026-06-04. Scope: full-reality (both branches). Every number below was read from a
local file; the source path is given. "Unsafe claims" = statements the data does **not**
support and that must not appear as asserted fact in the article.

Legend: **P** = primary source, **S** = secondary source.

---

## Block 1 — Problem statement / motivation
- **P** `README.md` (§1–7), `docs/interface_plan.md`
- Framing: magnetic field → magnetostrictive deformation of Fe4Al13 inclusion → local stress at
  inclusion/matrix boundary → Al-matrix deformation → possible local defects.
- Safe: "the magnetic field is **not** modeled; its action is replaced by a mechanical surrogate
  (local loading for the flat interface; imposed inclusion eigenstrain for the ellipsoid)."
- Unsafe: any claim that magnetostriction, magnetic domains, or field dependence were simulated.
- Open: README still names "120 MPa" as the base scenario; reality now spans 0–200 MPa.

## Block 2 — Al structure source
- **P** `docs/al_relaxation_check.md`. Key: `structures/converted/Al/al_fcc.data`, 4000 atoms,
  fcc, initial 40.5³ Å; potential `potentials/eam/Al_zhou.eam.alloy`, `pair_style eam/alloy`.
- Safe: pure-Al baseline uses **EAM (Zhou)**, distinct from the interface MEAM.
- Unsafe: claiming the Al baseline used the MEAM potential.

## Block 3 — Fe4Al13 / Al13Fe4 structure source
- **P** `docs/al13fe4_relaxation_check.md`. Key: **COD 1571554**
  (`https://www.crystallography.net/cod/1571554.cif`), local `structures/raw/Al13Fe4/al13fe4.cif`
  + POSCAR; formula Al13Fe4, full cell **Al78 Fe24 = 102 atoms**, space group **C2/m (IT 12)**,
  a=15.498, b=8.0814, c=12.488 Å, β=107.79°, V=1489.277 Å³; LAMMPS types Al=1, Fe=2.
- Safe: structure provenance is COD 1571554.
- Unsafe: equating "Fe4Al13", "Al13Fe4", "FeAl3" as identical without noting they are
  naming variants/approximations of the same Fe-Al intermetallic family.

## Block 4 — Potentials
- **P** `docs/al13fe4_relaxation_check.md`, `potentials/README.md` (referenced), `references.md`.
- Interface/inclusion: **Jelinek/Groh/Horstemeyer 2012 MEAM** (Al-Si-Mg-Cu-Fe), files
  `potentials/meam/Jelinek_2012/Jelinek_2012_meamf` + `..._meam.alsimgcufe`, `pair_style meam`.
  Explicit Al-Fe cross-terms `lattce(1,5)`, `delta(1,5)`, `alpha(1,5)`, `re(1,5)` (a true alloy
  potential, not two single-element potentials). OpenKIM `MO_262519520678_001`, NIST IPR.
- Pure-Al baseline: EAM Zhou (`Al_zhou.eam.alloy`).
- Unsafe: claiming the MEAM was validated/calibrated for *this exact* interface/inclusion.

## Block 5 — Relaxation of pure Al
- **P** `docs/al_relaxation_check.md`, `lammps/00_relax_al/`.
- Key: P 23601→-0.0105 bar after `box/relax`; NPT 300 K/0 bar 5000 steps; final T 293.998 K;
  last-20 mean P 78.488 bar; box 40.5→40.8165→41.1248 Å; Dangerous builds 0,0; no lost atoms/ERROR/nan.
- Safe: "completed without ERROR/nan/lost atoms; pressure relaxed to ~0."
- Unsafe: presenting 41.12 Å as a validated experimental lattice constant.

## Block 6 — Relaxation of standalone Fe4Al13
- **P** `docs/al13fe4_relaxation_check.md`, `lammps/01_relax_al13fe4/`.
- Key: P 89312→-9.43 bar after box/relax; NPT 300 K 5000 steps; final T 308.5 K; mean P 262.7 bar;
  instantaneous P range −10101.6…+10686.8 bar; composition 78 Al / 24 Fe preserved; Dangerous 0,0;
  51 frames × 102 atoms; no lost atoms/ERROR/nan.
- Caveat in source: 102-atom cell → strong pressure fluctuation → **sanity baseline, not final
  potential validation**. Technical note: `lmp` did not return to shell after `Total wall time`
  (files written first), recorded as a run nuance, not a physics error.
- Unsafe: claiming the MEAM potential is validated for the intermetallic from this run.

## Block 7 — Mismatch scan / orientation selection
- **P** `docs/interface_mismatch_candidates.md`, `results/tables/interface_mismatch_candidates.csv`.
- Key: best candidate **Al(111)/Fe4Al13(100)**, max length mismatch **0.943 %**, angle delta
  **0.114°**, area mismatch 0.727 %, estimated atoms 652, rank 1, score 1.819.
- Source explicitly states: "these numbers do not validate an interface; they only rank candidates."
- Unsafe: claiming a crystallographically proven orientation relationship (OR).

## Block 8 — Interface trial_001 construction
- **P** `docs/interface_trial_001_check.md`, `structures/interface/flat_interface/trial_001/`.
- Key: **618 atoms** (522 Al type 1, 96 Fe type 2; Al slab 210, Fe4Al13 slab 408);
  Lx 15.315, Ly 6.670, Lz 109.211 Å, xy tilt 4.0025; Al normal repeats 5, Fe4Al13 repeats 2;
  initial gap 2.25 Å; Fe lateral shift (0, 0.8); **boundary `p p f`**.
- Pre-run min distances: Al-Al 2.355, Fe-Fe 2.609, Al-Fe 2.278 Å; pairs<2.1 = 0, <1.8 = 0.
- Unsafe: presenting the built geometry as an experimentally observed interface.

## Block 9 — Interface minimization
- **P** `docs/interface_trial_001_check.md`, `lammps/02_interface_relax/trial_001/`.
- Key: step 0→510; PotEng −2106.98→−2143.90 eV; Press −11429.9→−7271.8 bar; force two-norm
  25.72→0.315; max comp 3.40→0.180; no ERROR/nan/lost; Dangerous 0; energy-tolerance stop.
- LAMMPS warned about large triclinic skew (geometric risk, did not stop the run).
- Unsafe: treating the residual negative pressure as physical (it is a fixed-box minimization).

## Block 10 — Short unloaded NVT (5000 steps)
- **P** `docs/interface_trial_001_nvt_check.md`.
- Key: NVT only, `p p f`, 300 K, 5000 steps, dt 0.001 ps; loop 68.9 s; Dangerous 0; 51 frames;
  T 300→300.86 (last-20 mean 300.0); Press last-20 mean −5110.9 bar; post-NVT distances
  Al-Fe 2.283, cross-slab 2.535 Å; pairs<1.8 = 0, Al-Fe<2.1 = 0, cross-slab<2.1 = 0.
- Safe: "stable by basic criteria." Unsafe: "interface physically validated."

## Block 11 — Long unloaded NVT (20000 steps)
- **P** `docs/interface_trial_001_time_averaged_stress.md` (§2–4).
- Key: 20000 steps (chosen over 50000 for runtime), `p p f`, nvt 300 K; loop 297.2 s (wall 4:57);
  Dangerous 0; final T 294.65 K (last-20 302.5, overall 302.4, range 280–330); Press final −4816,
  last-20 −4404, overall −4308 bar (range −8976…+124); 21 trajectory + 21 stress frames;
  post distances Al-Fe 2.027, cross-slab 2.592 Å; pairs<1.8 = 0, Al-Fe<2.1 = 1 (internal), cross<2.1 = 0.
- Source `data.interface_nvt_300k_long` is the reference state for **all loading runs**.

## Block 12 — Time-averaged unloaded stress profile
- **P** `docs/interface_trial_001_time_averaged_stress.md` (§5–6),
  `results/tables/interface_trial_001_time_averaged_stress_profile.csv`.
- Method: 21 stress frames, z-bin 5 Å, `compute stress/atom NULL virial`, σ = −Σstress/bin_vol.
- Key (time-averaged): interface z 40.16445 Å; Al-side bin z37.5 hydro −1.283±0.727 GPa, σ_zz −0.877;
  Fe-side bin z42.5 hydro −0.879±0.519, σ_zz −0.012; **highest |hydro| at z7.5 (Al free side)
  −3.466±0.485 GPa**. Time-averaging reduces interface-near magnitudes vs single-frame.
- Single-frame counterpart in `docs/interface_trial_001_unloaded_diagnostics.md`: phase hydro
  Al −1.540 / Fe4Al13 −0.711 GPa; highest |hydro| z7.5 −3.590 GPa.
- Safe: "comparative virial proxy." Unsafe: "absolute experimentally validated stress field."

## Block 13 — Contact-density check
- **P** `docs/interface_trial_001_contact_density_check.md`,
  `results/tables/interface_trial_001_contact_density_z_profile.csv`.
- Key: interface z 40.164, window ±8 Å; cross-slab min 2.592 Å; cross-slab pairs within
  2.3/2.5/2.8/3.0/3.5 Å = 0/0/20/33/48; largest empty z-gap 1 Å at z7–8 (not at interface);
  Al-slab interface density 0.0669 vs bulk 0.1096 atoms/Å³ (**38.99 % drop**); Fe4Al13 3.05 % drop.
- Verdict: `contact_present_visible_gaps_likely_visualization_or_structure_artifact`.
- Unsafe: claiming a confirmed physical interface void.

## Block 14 — Loading design
- **P** `docs/interface_trial_001_loading_design.md`,
  `results/tables/interface_trial_001_loading_force_table.csv`.
- Key: interface z 40.16445 Å; in-plane area 102.157 Å² (1.0216 nm²); target group = Fe4Al13_slab
  z 40.16…48.16 Å (52 atoms: 40 Al-type + 12 Fe-type); Al-side monitor z 32.16…40.16 (42 atoms);
  F_atom (eV/Å): 0 MPa 0; 60 →−0.0007357; 120 →−0.0014714; 147 →−0.0018025; 200 →−0.0024524;
  F_total = σ·A, F_atom = F_total/N, 1 eV/Å = 1.602e-9 N; load direction −z (toward Al).

## Block 15 — 0 MPa control
- **P** `docs/interface_trial_001_stress_000_060mpa_check.md`.
- Key: control run, 5000 steps (51 frames); fixed-bottom = lowest 4 Å of Al_slab (z≤9.71), 28
  fixed / 590 mobile atoms; `fix setforce 0 0 0`; NVT on mobile; no ERROR/Dangerous; final T 290.0;
  last-20 mean P −4321 bar; distances pairs<1.8 = 0, Al-Fe<2.1 = 0; interface z 40.360,
  Al-side hydro −0.888 / Fe-side −0.833 GPa.
- Safe: "baseline control passed." Role: reference for the loaded runs.

## Block 16 — 60 MPa compression-ramp
- **P** `docs/interface_trial_001_stress_000_060mpa_check.md`.
- Key: ramp 0→F over 2000 steps + 8000 hold = 10000 steps (101 frames); F_atom −0.0007357 eV/Å;
  no ERROR; Dangerous 0/0; pairs<1.8 = 0; **Al-Fe<2.1 = 1 (internal pair 232-260)**; cross<2.1 = 0;
  warning pair min/max/mean 1.960/2.249/2.086 Å, frames<2.1 57/101, <1.8 0/101, monotonic false;
  interface z 40.344, Al-side hydro −0.944 / Fe-side −0.813 GPa.

## Block 17 — 120 MPa compression-ramp
- **P** `docs/interface_trial_001_stress_120mpa_check.md`.
- Key: protocol 5000 ramp + 10000 hold = 15000 steps (151 frames); F_atom −0.0014714 eV/Å;
  no ERROR/nan/lost; Dangerous 0/0; min Al-Fe 2.0233, cross-slab 2.5259, cross-slab Al-Fe 2.5569 Å;
  pairs<1.8 = 0, Al-Fe<2.1 = 1, cross<2.1 = 0, safe_basic True; warning pair min 1.976 mean 2.079,
  frames<2.1 106, <1.8 0, monotonic false; interface z 40.2615; Al-side hydro −0.8366 / Fe-side
  −0.8353 GPa; highest |hydro| z5–10 −4.1900 GPa (fixed-bottom artifact); OVITO frames 0/50/100/150 clean.

## Block 18 — 147 MPa compression-ramp
- **P** `docs/interface_trial_001_stress_147mpa_check.md`,
  `docs/60_milestones/2026-05-11_interface_trial_001_stress_147mpa_sanity.md`.
- Key: 15000 steps (151 frames); F_atom −0.0018025 eV/Å; no ERROR/nan/lost; Dangerous 0/0; final
  mobile T 294.48 (last-20 302.1); mean P −4278 bar; min Al-Fe 2.0242, cross-slab 2.5018, cross-slab
  Al-Fe 2.5930 Å; pairs<1.8 = 0, Al-Fe<2.1 = 1, cross<2.1 = 0, safe_basic True; warning pair min
  1.9562 mean 2.0732, frames<2.1 104, <1.8 0, monotonic false; interface z 40.2794; Al-side hydro
  −0.7885 σ_zz −0.3664 / Fe-side −0.8201 σ_zz −0.1898 GPa; highest |hydro| z5–10 −4.1946 GPa (artifact);
  **manual OVITO review passed** (no detachment/gap/ejection/drift).

## Block 18b — 200 MPa upper-bound / failure-probe  *(uncommitted)*
- **P** `docs/interface_trial_001_stress_200mpa_check.md`,
  `docs/60_milestones/2026-05-12_interface_trial_001_stress_200mpa_upper_bound.md`,
  `results/tables/interface_trial_001_stress_000_060_120_147_200mpa_comparison.csv`.
- Key: 15000 steps (151 frames); F_atom −0.0024524 eV/Å; no ERROR/nan/lost; Dangerous 0/0;
  min Al-Fe 2.0232, cross-slab 2.4587, cross-slab Al-Fe 2.4999 Å; pairs<1.8 = 0, cross<2.1 = 0,
  safe_basic True; warning pair min 1.9126 mean 2.0797, frames<2.1 99, <1.8 0, monotonic false;
  interface z 40.2844; Al-side hydro −0.7892 σ_zz −0.2664 / Fe-side −0.7687 σ_zz −0.1956 GPa;
  highest |hydro| z5–10 −4.1797 GPa (artifact); manual OVITO review passed.
- **Mandatory framing**: controlled **upper-bound / numerical failure-probe**, not a physical
  strength claim. Unsafe: "the interface withstands 200 MPa" as a material property.

## Block 19 — OVITO manual review
- **P** the 120/147/200 MPa check docs, `docs/ellipsoid_inclusion/*` ("OVITO visual review" sections).
- Key: reviewed frames 0/50/100/150 (flat) using selections `ParticleIdentifier==232||260` and
  `Position.Z>32 && <48`; ellipsoid cutaway + Fe-only views. Findings: no visible detachment, empty
  gap, atom ejection, whole-block drift, or pair collapse.
- **Critical caveat**: OVITO **screenshots are not in the repo**. The 120/147/200 check docs list
  *suggested* paths `results/figures/ovito_review_{120,147,200}mpa/` that **do not exist on disk**.
  Safe: "no visible failure was observed in the inspected frames." Unsafe: citing screenshot files
  as present evidence.

## Block 20 — Known limitations
- **P** every check doc's caveat section; `docs/article/eigenstrain_model.md`;
  `results/tables/article/article_key_results_summary.csv`.
- Simplified flat/ellipsoid geometry; fixed-bottom support; persistent negative fixed-box pressure;
  large triclinic skew; ~39 % Al interface-density drop; virial stress = comparative proxy only;
  highest |hydro| sits at the support (boundary artifact); MEAM not calibrated for this exact problem;
  ellipsoid has an artificial 2.2 Å clearance; no experimental calibration; no validated defect/
  dislocation analysis; no magnetic field / domains / anisotropic magnetostriction tensor.

## Block 21 — Open blockers
- OVITO screenshots not saved to repo (manual review only).
- No experimental / microscopy comparison.
- No defect/dislocation (e.g. DXA/CNA) analysis performed.
- Single interface trial (`trial_001`) and single ellipsoid trial; no alternative orientations/sizes.
- Loading protocols are not uniform (0 MPa = 5000 steps, 60 MPa = 10000, 120/147/200 = 15000).
- ~136 MB of raw artifacts uncommitted with no `.gitignore` (data-loss / repo-bloat risk).

## Block 22 — Figures and tables for the article
- See `docs/article/figures_tables_plan.md` (this audit) and `docs/article/figure_plan.md`,
  `selected_figures_checklist.md` (existing). Present figures: flat-interface stress profiles
  (000/060/120/147/200), warning-pair distance plots, time-averaged/unloaded/contact-density
  profiles, ellipsoid eigenstrain energy / min-pair / Al-Fe / force plots, article_selected 2–6.
  Missing: OVITO screenshots, article_selected figure_1a/1b/1c/1d.

---

## Block 23 — Ellipsoid inclusion construction  *(uncommitted)*
- **P** `structures/interface/ellipsoid_inclusion/trial_001/ellipsoid_trial_001_metadata.json`
  + `..._build_report.json`.
- Key: box **64.8 × 64.8 × 97.2 Å** (exact multiples of Al a=4.05 Å), center (32.4, 32.4, 48.6);
  ellipsoid axes **12 × 12 × 24 Å** (key `ellipsoid_axes_A`; the manuscript and
  `simulation_parameters_summary.csv` call these "semi-axes" — **terminology conflict, to verify**);
  total **24259 atoms** (Al 24027, Fe 232; matrix 23263, inclusion 996); boundary `p p p`;
  **clearance 2.2 Å**; build-time pairs<2.1 = 0, <1.8 = 0; source `structures/converted/Al13Fe4/al13fe4.data`.

## Block 24 — Ellipsoid minimization  *(uncommitted)*
- **P** `lammps/04_ellipsoid_inclusion/trial_001/00_minimize/` (`in.`, `log.`, `data.ellipsoid_minimized`).
- Output structures written; feeds the NVT baseline. (Detailed log numbers in the log file.)

## Block 25 — Ellipsoid NVT 300 K baseline  *(uncommitted)*
- **P** `docs/ellipsoid_inclusion/ellipsoid_trial_001_nvt_300k_baseline.md`.
- Key: NVT, 300 K, dt 0.001 ps, 5000 steps; reached step 5000; final T **300.3553 K**; Dangerous 0;
  min pair **1.9903 Å**; pairs<1.8 = 0; **Al-Fe<2.1 = 8 (warning-level interface contacts)**;
  safe_basic true; OVITO cutaway + Fe-only review passed (inclusion stays inside matrix, no ejection/drift).

## Block 26 — Eigenstrain model  *(uncommitted)*
- **P** `docs/article/eigenstrain_model.md`.
- Key: per-inclusion-atom transform r' = r·(1+ε); **ε_x = ε_y = −0.5·ε_z** (volume-preserving-like,
  ε_x+ε_y+ε_z ≈ 0); inclusion atom ID range 23264–24259 (996 atoms, 232 Fe).
- **Mandatory framing**: a numerical surrogate for inclusion deformation, **not** a calibrated
  magnetic-field / magnetostriction-tensor model. Correct claim: "tests numerical stability and
  local atomistic response to controlled inclusion deformation."

## Block 27 — Eigenstrain series (ε_z = 0.0010 / 0.0025 / 0.0050 / 0.0100)  *(uncommitted)*
- **P** `docs/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_check.md`,
  `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_summary.csv`.
- Key (minimize-only, no NVT after each case): all 4 `accepted_script_sanity`; no ERROR/nan/lost/fatal;
  Dangerous 0; no pairs<1.8.

  | ε_z | min pair Å | Al-Fe<2.1 | <1.8 | final E, eV | force two-norm final |
  |---|---:|---:|---:|---:|---:|
  | 0.0010 | 2.0224 | 3 | 0 | −81346.42 | 2.99 |
  | 0.0025 | 2.0273 | 2 | 0 | −81346.98 | 3.16 |
  | 0.0050 | 1.9519 | 4 | 0 | −81348.01 | 1.13 |
  | 0.0100 | 1.9737 | 3 | 0 | −81345.09 | 6.57 |

- ε_z = 0.0100 = **numerical stress-test point** (larger final force residual), not a physical claim.

## Block 28 — Article draft pack  *(uncommitted)*
- **P** `docs/article/final_manuscript_v1.md` (117 lines, EN, IMRaD, both branches),
  `article_results_draft.md`, `figure_plan.md`, `references.md`, `eigenstrain_model.md`,
  `article_checklist.md`, `selected_figures_checklist.md`;
  `results/tables/article/article_key_results_summary.csv` + `simulation_parameters_summary.csv`.
- Use as the **base** for `article_en.md` (extend to full international structure) and
  `article_ru.md` (proper Russian scientific rewrite, not literal translation).
