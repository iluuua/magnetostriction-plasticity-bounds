# Controlled molecular-dynamics sanity study of Al / Fe4Al13 interface stability and ellipsoidal inclusion eigenstrain response

## Abstract

This work presents a controlled molecular-dynamics sanity study of simplified Al / Fe4Al13 systems. Two model families were tested: a flat Al / Fe4Al13 interface under controlled compressive loading and an ellipsoidal Fe4Al13 inclusion embedded in an Al matrix under imposed inclusion eigenstrain. The objective was not to claim final experimental validation, but to verify numerical stability, identify obvious failure modes, and prepare a reproducible simulation workflow for later physically calibrated studies.

The flat-interface model remained numerically stable through 0 / 60 / 120 / 147 / 200 MPa controlled loading scenarios. No hard overlaps below 1.8 A, no visible interface detachment, no atom ejection, and no whole-block drift were detected in the accepted checks. The 200 MPa case is treated as an upper-bound / failure-probe rather than a final physical loading claim.

The ellipsoidal inclusion model passed an unloaded 300 K NVT baseline and a four-point eigenstrain series with eps_z = 0.0010, 0.0025, 0.0050, and 0.0100. All four minimized eigenstrain cases passed script-level sanity checks: no fatal LAMMPS errors, no lost atoms, Dangerous builds = 0, no hard overlaps below 1.8 A, and valid minimized output files. The eps_z = 0.0100 case is retained as a numerical stress-test point because of its larger final force residuals.

## 1. Introduction

Fe-containing intermetallic compounds are important second phases in aluminium alloys because they can influence local stress concentration, ductility, toughness, and microstructural evolution. In this work, Al13Fe4 / Fe4Al13 is used as the target intermetallic phase for a first simplified atomistic study.

The central physical hypothesis is that deformation of an intermetallic inclusion can perturb the surrounding Al matrix and produce local stress concentration near the inclusion/matrix interface. Since a fully calibrated magneto-mechanical model is outside the scope of this first stage, the present work uses controlled mechanical surrogates: compressive loading for a flat-interface model and imposed inclusion eigenstrain for an ellipsoidal inclusion model.

The aim is methodological: to build a reproducible molecular-dynamics workflow, verify that the simplified systems do not immediately fail numerically, and define a controlled baseline for later physically calibrated simulations.

## 2. Model construction and methods

The simulations were performed with LAMMPS using a MEAM-based Al-Fe potential workflow. The same potential family was used across the flat-interface and ellipsoidal-inclusion branches to keep the numerical comparison internally consistent.

Two simplified model branches were used.

First, a flat Al / Fe4Al13 interface model was constructed, minimized, equilibrated, and subjected to a controlled loading series. The loading cases were 0 / 60 / 120 / 147 / 200 MPa. The 200 MPa case was treated as an upper-bound numerical failure-probe.

Second, an ellipsoidal Fe4Al13 inclusion was embedded in a periodic Al matrix. The box size was 64.8 x 64.8 x 97.2 A. The initial ellipsoid semi-axes were 12 x 12 x 24 A. The final atom count was 24259 atoms, including 24027 Al atoms and 232 Fe atoms. After geometry construction and minimization, the system was equilibrated at 300 K using a short NVT baseline.

The eigenstrain surrogate was applied to inclusion atoms by transforming their coordinates relative to the inclusion center:

r = x - x_center

r'_x = r_x * (1 + eps_x)

r'_y = r_y * (1 + eps_y)

r'_z = r_z * (1 + eps_z)

x' = x_center + r'

The tested cases used:

eps_z = 0.0010 / 0.0025 / 0.0050 / 0.0100

eps_x = eps_y = -0.5 * eps_z

After applying each eigenstrain case, the system was minimized. The outputs were checked through log parsing, distance checks, final data/dump existence, and visual OVITO review.

## 3. Sanity-check criteria

The main stop conditions were:

- fatal LAMMPS errors;
- NaN values;
- lost atoms;
- Dangerous builds greater than zero;
- hard pair overlaps below 1.8 A;
- missing minimized output data;
- visible atom ejection;
- visible interface detachment;
- visible whole-block drift.

Al-Fe contacts below 2.1 A were not treated as immediate failure, but as warning-level contacts requiring monitoring.

Per-atom stress diagnostics were interpreted as comparative virial proxies, not as experimentally calibrated absolute stress fields.

## 4. Flat-interface results

The flat-interface trial_001 model passed the 0 / 60 / 120 / 147 / 200 MPa controlled loading series. Across the accepted runs, no hard overlaps below 1.8 A were detected. OVITO review did not show visible interface detachment, empty interface gap, atom ejection, or whole-block drift.

The 200 MPa run should be interpreted as an upper-bound numerical failure-probe. Its purpose is to demonstrate that the current simplified geometry does not immediately fail under the tested protocol, not to claim that the real material interface is physically validated at this load.

A recurring caveat in the flat-interface branch is the fixed-bottom support artifact: the highest absolute hydrostatic proxy appears near the support region rather than necessarily at the physical interface. Therefore, flat-interface stress profiles are used comparatively only.

## 5. Ellipsoidal inclusion baseline

The ellipsoidal Fe4Al13 inclusion in the Al matrix passed the unloaded 300 K NVT baseline. The final temperature remained near 300 K, Dangerous builds were zero, and no hard pair overlaps below 1.8 A were detected. Al-Fe contacts below 2.1 A were treated as warning-level interface contacts and monitored in later deformation runs.

OVITO cutaway and Fe-only views were used to confirm that the inclusion remained inside the Al matrix and that Fe atoms did not visibly eject or drift as a separate block.

## 6. Ellipsoidal inclusion eigenstrain results

The eigenstrain series with eps_z = 0.0010, 0.0025, 0.0050, and 0.0100 passed script-level sanity checks. No case showed hard overlaps below 1.8 A. The number of Al-Fe warning contacts below 2.1 A remained small across the series.

| Case | eps_z | Minimized min pair distance, A | Al-Fe pairs below 2.1 A | Hard pairs below 1.8 A | Final energy, eV |
|---|---:|---:|---:|---:|---:|
| epsz_p0p00100 | 0.0010 | 2.0223692937594833 | 3 | 0 | -81346.4219686416 |
| epsz_p0p00250 | 0.0025 | 2.02732260776541 | 2 | 0 | -81346.9789455425 |
| epsz_p0p00500 | 0.0050 | 1.9518806269765512 | 4 | 0 | -81348.0111737039 |
| epsz_p0p01000 | 0.0100 | 1.9736532602057004 | 3 | 0 | -81345.0865828122 |

The eps_z = 0.0100 case remained script-sane but showed larger final force residuals than smaller strain cases. It should therefore be treated as a numerical stress-test point rather than a final physical claim.

## 7. Discussion

The results show that the current simplified models are numerically stable enough for a first controlled workflow demonstration. The flat-interface model is useful for testing interface loading protocols, while the ellipsoidal inclusion model provides a first surrogate for studying local response to inclusion eigenstrain.

The most important result is not a final quantitative stress prediction, but a reproducible computational workflow: geometry construction, minimization, baseline equilibration, controlled perturbation, sanity checks, visual review, and summary reporting.

The current work also defines what should be improved next. A physically stronger model would require more realistic inclusion morphology, experimentally grounded orientation relationships, calibrated magnetostriction or eigenstrain amplitudes, and validation against microscopy or mechanical data.

## 8. Limitations

This work does not claim final physical validation. The main limitations are:

- simplified flat-interface and ellipsoidal inclusion geometries;
- idealized periodic Al matrix;
- artificial initial cavity / clearance in the ellipsoid model;
- MEAM potential applicability limits for this exact interface/inclusion problem;
- per-atom virial stress used as comparative diagnostic only;
- no direct calibration to experimental microscopy or mechanical measurements;
- no validated defect/dislocation analysis yet;
- no explicit magnetic-domain or field-dependent magnetostriction tensor.

## 9. Conclusion

The project establishes a reproducible controlled MD workflow for Al / Fe4Al13 interface and inclusion studies. Both the flat-interface loading series and the ellipsoidal inclusion eigenstrain series passed numerical sanity checks. The workflow is ready for article-level presentation as a controlled computational prototype, while final physical validation remains future work.
