# Article draft — Al / Fe4Al13 molecular-dynamics sanity study

## Working title

Controlled molecular-dynamics sanity study of Al / Fe4Al13 interface stability and ellipsoidal inclusion eigenstrain response

## Abstract draft

This work presents a controlled molecular-dynamics sanity study of simplified Al / Fe4Al13 systems. Two model families were tested: a flat Al / Fe4Al13 interface under controlled compressive loading and an ellipsoidal Fe4Al13 inclusion embedded in an Al matrix under imposed inclusion eigenstrain. The objective was not to claim final experimental validation, but to verify numerical stability, identify obvious failure modes, and prepare a reproducible simulation workflow for later physically calibrated studies.

The flat-interface model remained numerically stable through 0 / 60 / 120 / 147 / 200 MPa controlled loading scenarios. No hard overlaps below 1.8 A, no visible interface detachment, no atom ejection, and no whole-block drift were detected in the accepted checks. The 200 MPa case is treated as an upper-bound / failure-probe rather than a final physical loading claim.

The ellipsoidal inclusion model passed an unloaded 300 K NVT baseline and a four-point eigenstrain series with eps_z = 0.0010, 0.0025, 0.0050, and 0.0100. All four minimized eigenstrain cases passed script-level sanity checks: no fatal LAMMPS errors, no lost atoms, Dangerous builds = 0, no hard overlaps below 1.8 A, and valid minimized output files. The eps_z = 0.0100 case is retained as a numerical stress-test point because of its larger final force residuals.

## Introduction draft

Aluminum alloys containing Fe-Al intermetallic phases are relevant for studying local stress concentration, interface stability, and defect formation around inclusions. In the present work, Fe4Al13 / Al13Fe4 is treated as the target intermetallic phase embedded in or contacting an Al matrix. The study focuses on building a controlled atomistic workflow rather than reproducing the full experimental microstructure.

The key physical motivation is the hypothesis that deformation of an intermetallic inclusion can locally perturb the Al matrix and create stress concentration near the inclusion/matrix boundary. As a first computational approximation, this work uses simplified mechanical surrogates: controlled loading for the flat-interface model and imposed inclusion eigenstrain for the ellipsoidal inclusion model.

## Methods draft

The simulations were performed with LAMMPS using a MEAM-based Al-Fe potential workflow. The initial models were constructed as simplified numerical prototypes rather than experimentally complete microstructural reconstructions.

For the flat-interface branch, an Al / Fe4Al13 interface model was minimized, equilibrated, and subjected to a controlled loading series. The loading scenarios were used to check numerical stability and visible interface integrity under increasing compressive load.

For the ellipsoidal inclusion branch, an Fe4Al13 inclusion was embedded in a periodic Al matrix. After geometry construction and minimization, the system was equilibrated at 300 K using a short NVT baseline. A controlled eigenstrain surrogate was then applied to the inclusion by modifying the inclusion geometry along the z direction and minimizing each resulting structure.

The main stop conditions were:
- fatal LAMMPS errors;
- NaN values;
- lost atoms;
- Dangerous builds greater than zero;
- hard overlaps below 1.8 A;
- visible atom ejection;
- visible interface detachment or whole-block drift.

Per-atom stress diagnostics were treated as comparative virial proxies and not as experimentally calibrated absolute stress fields.

## Results draft — flat interface

The flat-interface trial_001 model passed the 0 / 60 / 120 / 147 / 200 MPa controlled loading series. Across the accepted runs, no hard overlaps below 1.8 A were detected. OVITO review did not show visible interface detachment, empty interface gap, atom ejection, or whole-block drift. The warning pair previously observed in Fe4Al13 remained an internal contact and did not show monotonic collapse.

The 200 MPa run should be interpreted as an upper-bound numerical failure-probe. Its purpose is to demonstrate that the current simplified geometry does not immediately fail under the tested protocol, not to claim that the real material interface is physically validated at this load.

## Results draft — ellipsoidal inclusion

The ellipsoidal Fe4Al13 inclusion in the Al matrix passed the unloaded 300 K NVT baseline. The final temperature remained near 300 K, Dangerous builds were zero, and no hard pair overlaps below 1.8 A were detected. Al-Fe contacts below 2.1 A were treated as warning-level interface contacts and monitored in later deformation runs.

The eigenstrain series with eps_z = 0.0010, 0.0025, 0.0050, and 0.0100 passed script-level sanity checks. No case showed hard overlaps below 1.8 A. The number of Al-Fe warning contacts below 2.1 A remained small across the series. The eps_z = 0.0100 case remained numerically sane but showed a larger final force residual, so it is treated as a stress-test case.

## Discussion draft

The results show that the current simplified models are numerically stable enough for a first controlled workflow demonstration. The flat-interface model is useful for testing interface loading protocols, while the ellipsoidal inclusion model provides a first surrogate for studying local response to inclusion eigenstrain.

The most important limitation is that the current models are not physically complete. The flat-interface model uses a simplified interface and fixed-bottom support. The ellipsoidal model uses simplified inclusion geometry, periodic Al matrix, artificial initial clearance, and no experimental calibration. Therefore, the results should be presented as numerical sanity checks and workflow validation, not as final physical predictions.

## Limitations draft

This work does not claim final physical validation. The main limitations are:

- simplified flat-interface and ellipsoidal inclusion geometries;
- idealized periodic Al matrix;
- artificial initial cavity / clearance in the ellipsoid model;
- MEAM potential applicability limits for this exact interface/inclusion problem;
- per-atom virial stress used as comparative diagnostic only;
- no direct calibration to experimental microscopy or mechanical measurements;
- no validated defect/dislocation analysis yet.

## Conclusion draft

The project establishes a reproducible controlled MD workflow for Al / Fe4Al13 interface and inclusion studies. Both the flat-interface loading series and the ellipsoidal inclusion eigenstrain series passed numerical sanity checks. The workflow is ready for article-level presentation as a controlled computational prototype, while final physical validation remains future work.
