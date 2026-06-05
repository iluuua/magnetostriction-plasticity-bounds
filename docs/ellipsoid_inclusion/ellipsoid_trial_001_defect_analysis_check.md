# Ellipsoid trial_001 — matrix defect / dislocation analysis (DXA/CNA)

Date: 2026-06-05. Post-processing of existing trajectories only (no new simulation).
Tool: scriptable OVITO (CNA + DXA). Script: `analysis/python/analyze_matrix_defects_dxa.py`.
Output: `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_matrix_defect_dxa.csv`.

## Why this analysis
The supervisor's primary requested output is the **defect structure / dislocations / plastic
zone** in the Al matrix around the Fe4Al13 inclusion after the magnetostriction-equivalent
deformation. No defect analysis existed in the project; this fills that gap on the data already
computed (the eigenstrain series final configurations).

## Method
For each case the fcc Al matrix (atom ids ≤ 23263) is classified by Common Neighbor Analysis
(FCC / HCP / Other) and dislocations are extracted by the Dislocation Analysis Modifier (DXA,
input crystal = FCC). Dislocation density = total line length / cell volume.

## Result

| case | eps_z | FCC % | HCP % (stacking faults) | Other % | dislocation segments | density, 1/m² |
|---|---:|---:|---:|---:|---:|---:|
| baseline (B=0) | 0 | 95.26 | 0.000 | 4.74 | 0 | 0 |
| eigenstrain | 0.0010 | 95.51 | 0.009 | 4.48 | 0 | 0 |
| eigenstrain | 0.0025 | 95.50 | 0.009 | 4.49 | 0 | 0 |
| eigenstrain | 0.0050 | 95.50 | 0.009 | 4.49 | 0 | 0 |
| eigenstrain (overload) | 0.0100 | 95.52 | 0.004 | 4.48 | 0 | 0 |

## Interpretation (honest)
- **No dislocations and no significant stacking faults are generated at any eigenstrain, including
  the eps_z = 0.0100 overload.** Dislocation density is zero throughout.
- The ~4.5 % "Other" atoms are the **static inclusion/matrix interface shell**, not deformation
  defects: the fraction is essentially constant across cases and is actually *highest* in the
  thermal baseline (4.74 %) and *lower* in the minimized strained cases (~4.48 %), i.e.
  minimization removed thermal noise rather than adding defects.
- The matrix response to the imposed inclusion eigenstrain is therefore **essentially elastic**.

## Why (model limitations that cause the null result)
1. **Size.** The matrix is ~6.5 nm across; homogeneous dislocation nucleation typically needs a
   much larger volume (tens of nm) to host a stable loop. The supervisor's target scale is
   ~50 nm and the MD reference (Shi et al., J. Alloys Compd. 2025) uses a 200×200×300 Å (~720k
   atom) box — ~30× larger than this model.
2. **Minimize-only.** Each eigenstrain case was energy-minimized, not run with finite-temperature
   MD. Minimization relaxes to the nearest elastic minimum and cannot surmount the dislocation
   nucleation barrier; nucleation requires thermal activation / sustained driving force.
3. **Eigenstrain amplitude.** eps_z = 0.0025 corresponds to the magnetostriction stress
   σ_m ≈ 147 MPa (ε ≈ σ_m/E); the response is elastic at this and even at 4× overload here.

## Consequence for the article
The current models verify numerical stability but **cannot yet answer the physical question**
(defects/dislocations from magnetostriction). A larger matrix + finite-temperature MD after a
σ_m-grounded eigenstrain is required. This is the main item in the gap-closure plan.
