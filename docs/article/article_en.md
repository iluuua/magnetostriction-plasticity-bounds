# A controlled molecular-dynamics study of the numerical stability of the Al / Fe4Al13 interface and the eigenstrain response of an ellipsoidal Fe4Al13 inclusion in an Al matrix

*Working scientific draft. Full-reality scope: both study branches (flat interface and ellipsoidal
inclusion). Source of truth: local repository files. Every significant number carries its source
path. This draft extends `docs/article/final_manuscript_v1.md` to a complete IMRaD structure and
supersedes v1.*

---

## 1. Title

A controlled molecular-dynamics study of the numerical stability of the Al(111) / Fe4Al13(100)
interface and the eigenstrain response of an ellipsoidal Fe4Al13 inclusion in an Al matrix.

## 2. Abstract

This work presents a controlled molecular-dynamics (MD) study of two simplified Al / Fe4Al13 model
systems: (1) a flat Al(111) / Fe4Al13(100) interface under controlled compressive loading and (2) an
ellipsoidal Fe4Al13 inclusion embedded in a periodic Al matrix under an imposed inclusion eigenstrain.
The objective was **not** final experimental validation, but to verify numerical stability, identify
obvious failure modes, and prepare a reproducible simulation workflow for later physically calibrated
studies.

The flat-interface model remained numerically stable across the controlled loading series
0 / 60 / 120 / 147 / 200 MPa: no hard overlaps below 1.8 Å, no visible interface detachment, no atom
ejection, and no whole-block drift were detected in the accepted checks (source:
`results/tables/interface_trial_001_stress_000_060_120_147_200mpa_comparison.csv`). The 200 MPa case
is treated as a **controlled upper-bound / numerical failure-probe**, not as a physical strength claim.
The ellipsoidal model passed an unloaded 300 K NVT baseline and a four-point eigenstrain series
(eps_z = 0.0010 / 0.0025 / 0.0050 / 0.0100); all four minimized cases passed script-level sanity checks
(source: `docs/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_check.md`). The eps_z = 0.0100
case is retained as a numerical stress-test point because of its larger final force residual.

**Limitation.** These are controlled numerical sanity-runs; per-atom stress is interpreted as a
comparative virial proxy. Final physical validation remains future work.

## 3. Keywords

molecular dynamics; LAMMPS; MEAM; aluminium; Fe4Al13 / Al13Fe4 intermetallic; interface; eigenstrain;
comparative virial stress proxy; numerical stability; controlled sanity-run.

## 4. Introduction

Fe-containing intermetallic phases are common second phases in aluminium alloys, where they influence
local stress concentration, ductility, toughness, and microstructural evolution. Here, the Fe4Al13 /
Al13Fe4 phase is treated as the target intermetallic for a first simplified atomistic study (source:
`README.md` §1). The central physical hypothesis is that deformation of an intermetallic inclusion can
locally perturb the Al matrix and create stress concentration near the inclusion/matrix boundary.

Because a fully calibrated magneto-mechanical model is outside the scope of this first stage, the study
uses controlled mechanical surrogates: compressive loading for the flat-interface model and an imposed
inclusion eigenstrain for the ellipsoidal model (source: `README.md` §3.2;
`docs/article/eigenstrain_model.md`). The magnetic field is not modeled directly. The aim is
methodological: to build a reproducible MD workflow, confirm the simplified systems do not immediately
fail numerically, and define a controlled baseline for later physically calibrated work.

## 5. Research objective and tasks

**Objective:** build a controlled, reproducible MD workflow for Al / Fe4Al13 systems and verify the
numerical stability of two simplified geometries.

**Tasks:** (1) relax pure-Al and standalone-Fe4Al13 baselines; (2) mismatch analysis and interface
orientation selection; (3) build, minimize, and equilibrate (unloaded NVT) the flat interface;
(4) unloaded stress/contact-density diagnostics; (5) a controlled 0–200 MPa loading series with
stability checks and manual OVITO review; (6) build and equilibrate the ellipsoidal inclusion; (7) an
eigenstrain series with stability checks.

## 6. Materials and Methods

Simulations used **LAMMPS**. The interface and inclusion branches used the Jelinek / Groh / Horstemeyer
2012 MEAM potential (Al-Si-Mg-Cu-Fe), `pair_style meam`, with explicit Al-Fe cross-terms `lattce(1,5)`,
`delta(1,5)`, `alpha(1,5)`, `re(1,5)` — a true alloy potential, not a combination of single-element
potentials (source: `docs/al13fe4_relaxation_check.md`). The pure-Al baseline used the EAM Zhou
potential (`Al_zhou.eam.alloy`, `pair_style eam/alloy`) (source: `docs/al_relaxation_check.md`).

Per-atom stress was computed with `compute stress/atom NULL virial` and is interpreted as a
**comparative virial proxy**, not an absolute experimentally validated stress (source:
`docs/interface_trial_001_time_averaged_stress.md` §5). Stop conditions were: fatal LAMMPS errors; NaN;
lost atoms; Dangerous builds > 0; hard overlaps below 1.8 Å; missing output; and visible atom ejection,
interface detachment, or whole-block drift in OVITO. Al-Fe contacts below 2.1 Å were treated as
warning-level contacts to monitor, not as immediate failure (source:
`docs/article/final_manuscript_v1.md` §3).

## 7. Computational Model

Two simplified branches share a single MEAM potential family for internal consistency:
**(1)** a flat Al(111) / Fe4Al13(100) interface (trial_001), boundary `p p f`, fixed-bottom Al support,
NVT thermostat on mobile atoms; **(2)** an ellipsoidal Fe4Al13 inclusion in a periodic Al matrix,
boundary `p p p`, with an imposed inclusion eigenstrain followed by minimization.

## 8. Initial Structure Preparation

**Pure Al.** `structures/converted/Al/al_fcc.data`, 4000 atoms, fcc, initial cell 40.5³ Å. After
`box/relax` the pressure dropped from 23601 to ≈ 0 bar; NPT 300 K / 0 bar for 5000 steps gave final
T 293.998 K and final box 41.1248 Å; Dangerous builds 0,0; no ERROR/nan/lost atoms (source:
`docs/al_relaxation_check.md`).

**Standalone Fe4Al13 / Al13Fe4.** Structure source: Crystallography Open Database entry **COD 1571554**;
full cell Al78 Fe24 = 102 atoms, space group C2/m (IT 12), a = 15.498 Å, b = 8.0814 Å, c = 12.488 Å,
β = 107.79° (source: `docs/al13fe4_relaxation_check.md`). Minimization + `box/relax` + NPT 300 K
(5000 steps) completed without ERROR/nan/lost atoms; the 78 Al / 24 Fe composition was preserved. The
small 102-atom cell produces strong instantaneous pressure fluctuation (range −10101.6…+10686.8 bar),
so this is a sanity baseline, not a potential validation.

## 9. Interface Orientation Selection and Mismatch Analysis

Ranking low-index Al/Fe4Al13 surface combinations with an approximate matching script gave the
best candidate **Al(111) / Fe4Al13(100)**: maximum length mismatch 0.943 %, angle delta 0.114°, area
mismatch 0.727 %, estimated atoms 652 (rank 1) (source: `docs/interface_mismatch_candidates.md`;
`results/tables/interface_mismatch_candidates.csv`). The source explicitly states these numbers do not
validate an interface; they only rank candidates.

## 10. Construction of the Al(111) / Fe4Al13(100) Interface

The trial_001 interface contains **618 atoms** (522 Al type 1, 96 Fe type 2; Al slab 210, Fe4Al13 slab
408); Lx = 15.315 Å, Ly = 6.670 Å, Lz = 109.211 Å, xy tilt = 4.0025 Å; initial interface gap 2.25 Å;
boundary `p p f` (source: `docs/interface_trial_001_check.md`). Before the run there were no hard
overlaps (min Al-Fe 2.278 Å; pairs < 2.1 Å = 0; < 1.8 Å = 0). Minimization converged by energy tolerance
(force two-norm 25.72 → 0.315; PotEng −2106.98 → −2143.90 eV). LAMMPS warned about a large triclinic
skew (a geometric risk that did not stop the run).

## 11. Molecular Dynamics Setup

Ensemble NVT (flat branch: mobile atoms; ellipsoid baseline: all atoms); T = 300 K; timestep 0.001 ps
(`units metal`). The flat interface used a short (5000-step) and a long (20000-step) unloaded NVT; the
long run produced the reference state `data.interface_nvt_300k_long` used for all loading scenarios
(source: `docs/interface_trial_001_nvt_check.md`; `docs/interface_trial_001_time_averaged_stress.md`).
The ellipsoid box is 64.8 × 64.8 × 97.2 Å (multiples of a_Al = 4.05 Å), center (32.4, 32.4, 48.6),
inclusion axes 12 × 12 × 24 Å, boundary `p p p`, **24259 atoms** (Al 24027, Fe 232; matrix 23263,
inclusion 996), NVT 300 K for 5000 steps (source:
`structures/interface/ellipsoid_inclusion/trial_001/ellipsoid_trial_001_metadata.json`;
`docs/ellipsoid_inclusion/ellipsoid_trial_001_nvt_300k_baseline.md`). *Note:* the 12 × 12 × 24 Å values
appear as "axes" in metadata and "semi-axes" in the manuscript/parameters CSV — flagged in
Reproducibility Notes (to verify).

### 11-bis. Eigenstrain surrogate (branch 2)

For each inclusion atom, coordinates relative to the inclusion center are transformed as r′ = r·(1 + ε),
with ε_x = ε_y = −0.5·ε_z (an approximately volume-preserving transform, ε_x + ε_y + ε_z ≈ 0); the system
is then minimized (source: `docs/article/eigenstrain_model.md`). This is a numerical surrogate for
inclusion deformation, **not** a calibrated magnetostriction model: it excludes magnetic-field direction
dependence, an anisotropic magnetostriction tensor, domain structure, and experimental amplitude
calibration.

## 12. Local Loading Protocol

Loading was applied to a near-interface Fe4Al13 region (z = 40.16…48.16 Å, 52 atoms: 40 Al-type +
12 Fe-type) along −z (toward Al); the support is a fixed bottom Al layer (28 fixed, 590 mobile atoms)
with `fix setforce 0 0 0` (source: `docs/interface_trial_001_loading_design.md`;
`docs/interface_trial_001_stress_000_060mpa_check.md`). In-plane area 102.157 Å². Per-atom force
(F = σ·A / N): 0 / −0.0007357 / −0.0014714 / −0.0018025 / −0.0024524 eV/Å for 0 / 60 / 120 / 147 /
200 MPa (source: `results/tables/interface_trial_001_loading_force_table.csv`). Protocols: 0 MPa =
5000 steps; 60 MPa = 2000 ramp + 8000 hold; 120/147/200 MPa = 5000 ramp + 10000 hold. The protocol
difference is accounted for in interpretation.

## 13. Numerical Stability Checks

Each run was checked for: ERROR/nan/lost atoms; Dangerous builds; minimum interatomic distances
(thresholds 1.8 Å hard overlap, 2.1 Å Al-Fe warning); cross-slab contacts; the behavior of warning pair
232-260; the virial stress profile; and a manual OVITO review of frames 0/50/100/150.

## 14. Results

*Facts only, from logs/tables/check documents; interpretation is deferred to Section 15.*

### 14.1 Flat interface: 0–200 MPa loading series
(source: `results/tables/interface_trial_001_stress_000_060_120_147_200mpa_comparison.csv` and per-MPa
check documents)

| Scenario | Steps | ERROR/nan/lost | Dangerous | pairs < 1.8 Å | cross-slab Al-Fe < 2.1 Å | warning pair min Å / monotonic? | OVITO |
|---|---:|---|---|---:|---:|---|---|
| 0 MPa control | 5000 | none | 0 | 0 | 0 | — | passed |
| 60 MPa | 10000 | none | 0/0 | 0 | 0 | 1.960 / no | passed |
| 120 MPa | 15000 | none | 0/0 | 0 | 0 | 1.976 / no | review passed |
| 147 MPa | 15000 | none | 0/0 | 0 | 0 | 1.956 / no | review passed |
| 200 MPa | 15000 | none | 0/0 | 0 | 0 | 1.913 / no | review passed |

Virial stress profile (near-interface bins), 147 MPa example: Al-side (z 35–40 Å) hydrostatic proxy
−0.7885 GPa, σ_zz −0.3664 GPa; Fe-side (z 40–45 Å) −0.8201 / −0.1898 GPa; largest |hydrostatic| at bin
z 5–10 Å, −4.1946 GPa (source: `docs/interface_trial_001_stress_147mpa_check.md`). For 200 MPa:
Al-side −0.7892 / −0.2664 GPa, Fe-side −0.7687 / −0.1956 GPa, largest |hydrostatic| z 5–10 Å −4.1797 GPa
(source: `docs/interface_trial_001_stress_200mpa_check.md`).

### 14.2 Unloaded flat-interface diagnostics
Long NVT (20000 steps): Dangerous 0; pairs < 1.8 Å = 0; cross-slab Al-Fe < 2.1 Å = 0; one internal
Al-Fe pair < 2.1 Å (source: `docs/interface_trial_001_time_averaged_stress.md`). Time-averaged profile:
Al-side (z 37.5 Å) hydro −1.283 ± 0.727 GPa; Fe-side (z 42.5 Å) −0.879 ± 0.519 GPa; largest |hydro| at
z 7.5 Å (free Al side) −3.466 ± 0.485 GPa. Contact density: min cross-slab 2.592 Å; Al interface density
drop ≈ 38.99 %; status: visible gaps likely a visualization/structure artifact (source:
`docs/interface_trial_001_contact_density_check.md`).

### 14.3 Ellipsoidal inclusion: baseline and eigenstrain
NVT 300 K baseline (5000 steps): final T 300.3553 K; Dangerous 0; min pair 1.9903 Å; pairs < 1.8 Å = 0;
Al-Fe < 2.1 Å = 8 (warning-level) (source: `docs/ellipsoid_inclusion/ellipsoid_trial_001_nvt_300k_baseline.md`).

Eigenstrain series (minimize-only, no NVT after each case) (source:
`results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_summary.csv`):

| eps_z | min pair, Å | Al-Fe < 2.1 Å | < 1.8 Å | final energy, eV | force two-norm (final) |
|---:|---:|---:|---:|---:|---:|
| 0.0010 | 2.0224 | 3 | 0 | −81346.42 | 2.99 |
| 0.0025 | 2.0273 | 2 | 0 | −81346.98 | 3.16 |
| 0.0050 | 1.9519 | 4 | 0 | −81348.01 | 1.13 |
| 0.0100 | 1.9737 | 3 | 0 | −81345.09 | 6.57 |

All four cases: no ERROR/nan/lost/fatal, Dangerous 0, no overlap < 1.8 Å.

## 15. Discussion

*Interpretation of Section 14, deliberately separated from the results.*

**Why the 0 MPa control matters.** Run with the same support, boundary, and thermostat but no applied
load, the 0 MPa control is the reference against which loaded runs are read. Without it, changes in proxy
quantities could not be separated from support and thermostat effects.

**Why 60/120/147 MPa are controlled sanity-runs.** These runs test that the simplified model does not
fail numerically under increasing load (no nan/lost atoms/overlap); they do not measure a real material
strength. They are controlled (fixed support, known per-atom force) and reproducible, but carry geometry
and boundary-condition simplifications.

**Why warning pair 232-260 is not direct evidence of interface failure.** Pair 232-260 is **internal**
to the Fe4Al13 slab (both atoms in the Fe4Al13 phase), not cross-slab; the contact is intermittent, does
not collapse monotonically, and never drops below 1.8 Å in any sampled frame (source:
`docs/interface_trial_001_warning_pairs_check.md`). Its excursions below 2.1 Å therefore flag internal
Fe4Al13 structure to monitor, not failure of the Al/Fe4Al13 boundary.

**Why the virial profile is not an absolute stress.** `compute stress/atom NULL virial` yields a per-atom
virial whose normalization to bin volume is approximate, especially near free surfaces and under triclinic
skew. The profiles are therefore used **comparatively** between scenarios, not as absolute experimental
stresses.

**Why the hydrostatic-proxy maximum at the support is likely a boundary artifact.** In every loaded run
the largest |hydrostatic| falls in the z 5–10 Å bin — the fixed-bottom support region, not the interface
(source: per-MPa check docs). Fixing atoms imposes an artificial local stress, so this maximum is read as
a boundary-condition artifact.

**Why final physical validation cannot be claimed.** The models are simplified (flat/ellipsoidal geometry,
fixed-bottom support, an artificial 2.2 Å clearance in the ellipsoid), the MEAM potential is not calibrated
for this exact problem, there is no comparison to experiment/microscopy, and there is no validated defect
analysis. The results are therefore numerical-stability and workflow validation, not a final physical
prediction.

**Ellipsoid branch.** The eigenstrain series shows a controlled local inclusion response with no numerical
catastrophe; the eps_z = 0.0100 case has a larger force residual and is treated as a numerical stress-test
point. It is a numerical surrogate, not evidence of real magnetostriction.

## 16. Model Limitations

(1) not final physical validation; (2) simplified geometries in both branches; (3) fixed-bottom support
and persistent negative fixed-box pressure; (4) large triclinic skew (flat cell); (5) artificial 2.2 Å
initial clearance in the ellipsoid (source:
`structures/interface/ellipsoid_inclusion/trial_001/ellipsoid_trial_001_build_report.json`); (6) per-atom
virial used as a comparative diagnostic only; (7) the largest |hydro| sits at the support (artifact);
(8) MEAM not calibrated for this interface/inclusion; (9) a single trial per branch, no alternative
orientations/sizes; (10) non-uniform loading protocols; (11) no experiment/microscopy comparison; (12) no
validated defect/dislocation analysis; (13) no explicit magnetic-domain or field-dependent model; (14)
manual OVITO review only — screenshots are not saved in the repository.

## 17. Conclusions

A reproducible controlled MD workflow was established for Al / Fe4Al13 systems, covering the flat
Al(111) / Fe4Al13(100) interface and an ellipsoidal Fe4Al13 inclusion in an Al matrix. Both branches
passed numerical sanity checks: the 0–200 MPa loading series and the eps_z = 0.0010–0.0100 eigenstrain
series showed no numerical catastrophe, no hard overlaps, no lost atoms, and no visible failure in the
inspected OVITO frames. The stress profiles are comparative virial proxies. Final physical validation
remains future work.

## 18. Future Work

Calibrate eigenstrain/magnetostriction amplitude against experiment; test alternative interface
orientations and inclusion sizes/morphologies; run loaded ellipsoid simulations after eigenstrain
(currently minimize-only); perform validated defect/dislocation analysis (CNA/DXA); compare with
microscopy/mechanical data; assess sensitivity to the interatomic potential and model size; and save OVITO
screenshots as archived artifacts.

## 19. Data and Code Availability

Local repository `iluuua/physics_md_al_fe`. Summary tables:
`results/tables/article/article_key_results_summary.csv`,
`results/tables/article/simulation_parameters_summary.csv`, the 0–200 MPa comparison CSV, and
`results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_summary.csv`. Scripts:
`analysis/python/`. Some raw artifacts (`.lammpstrj` trajectories, `data.*` structures) are uncommitted at
the time of writing; the storage strategy is in `docs/audit/git_commit_plan.md`.

## 20. Reproducibility Notes

LAMMPS, `units metal`, dt = 0.001 ps, T = 300 K. Potentials: EAM Zhou (Al baseline), MEAM Jelinek 2012
(interface/inclusion). Boundaries `p p f` (flat), `p p p` (ellipsoid). Loading reference state:
`data.interface_nvt_300k_long`. **To verify:** (a) ellipsoid "axes" vs "semi-axes" terminology for
12 × 12 × 24 Å; (b) OVITO screenshots not saved — attach manually if needed; (c) the 0/60 MPa protocols
are shorter than 120/147/200 MPa.

## 21. References

1. LAMMPS documentation — minimize. https://docs.lammps.org/minimize.html
2. LAMMPS documentation — compute stress/atom. https://docs.lammps.org/compute_stress_atom.html
3. OpenKIM — MEAM_LAMMPS_JelinekGrohHorstemeyer_2012_AlSiMgCuFe (MO_262519520678_001).
4. NIST Interatomic Potentials Repository — Jelinek 2012 Al-Si-Mg-Cu-Fe MEAM.
5. Crystallography Open Database, entry COD 1571554 (Fe4Al13 / Al13Fe4).

### References to verify (not independently verified in this audit)
- SpringerMaterials — Al13Fe4 / Fe4Al13 crystal structure (source: `docs/article/references.md`).
- Feng et al. 2023 — mechanism of Fe-rich intermetallic compound formation in high-Fe Al alloys.
- Que et al. 2024 — Al13Fe4 and grain refinement / Fe-containing IMCs in Al alloys.

*No additional sources were invented. Bibliographic details of the verifiable references come from
`docs/article/references.md`.*

## 22. Supplementary Materials

See `docs/article/figures_tables_plan.md`. Key tables: 0–200 MPa comparison; loading force table;
eigenstrain series summary; article key-results / simulation parameters. Key figures: 0/60/120/147/200 MPa
stress profiles; warning-pair distance; time-averaged/unloaded/contact-density profiles; eigenstrain
energy / min-pair / Al-Fe / force-residual. **Missing:** OVITO screenshots and the Figure 1A–1D geometry
renders (see `docs/audit/repo_consistency_report.md`).
