# Ellipsoid inclusion trial_001 — NVT 300 K baseline

## Status

Ellipsoid inclusion `trial_001` was minimized and tested by a short NVT 300 K sanity-run.

## Model

- Matrix: Al
- Inclusion: Fe4Al13 / Al13Fe4 ellipsoidal inclusion
- Box: 64.8 x 64.8 x 97.2 A
- Boundary: p p p
- Potential: Jelinek 2012 MEAM, same as flat-interface trials
- Initial inclusion axes: 12 x 12 x 24 A
- Atom count: 24259
- Al atoms: 24027
- Fe atoms: 232

## NVT protocol

- Input: `lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/in.ellipsoid_nvt_300k`
- Source structure: `../00_minimize/data.ellipsoid_minimized`
- Ensemble: NVT
- Target temperature: 300 K
- Timestep: 0.001 ps
- Steps: 5000

## Main result

- Run reached step 5000.
- Final temperature: 300.3553 K.
- Dangerous builds: 0.
- Output files were written:
  - `data.ellipsoid_nvt_300k`
  - `dump.ellipsoid_nvt_300k.lammpstrj`
  - `dump.ellipsoid_nvt_300k_final.lammpstrj`
  - `log.ellipsoid_nvt_300k.lammps`
- Distance sanity:
  - minimum pair distance: 1.9903 A
  - pairs below 1.8 A: 0
  - Al-Fe pairs below 2.1 A: 8
  - safe_basic: true

## Interpretation

The NVT baseline is accepted as a controlled unloaded thermal baseline after manual OVITO review.

The 8 Al-Fe pairs below 2.1 A are warning-level interface contacts, not hard overlaps. They should be monitored in later deformation runs.

## Important caveat

This is not final physical validation.

The model still has:
- simplified ellipsoid geometry;
- periodic Al matrix;
- artificial initial cavity/clearance from geometry construction;
- virial stress diagnostics only.

## Next scientific step

Use this baseline for a magnetostriction surrogate:
- apply controlled eigenstrain / displacement to the Fe4Al13 inclusion;
- relax the system;
- compare local stress and defect indicators before/after deformation.


## OVITO visual review

Manual OVITO review passed:
- cutaway view shows the ellipsoidal inclusion inside the Al matrix;
- Fe-only view shows Fe atoms remain inside the inclusion region;
- full dump review did not show visible atom ejection, matrix collapse, or whole-inclusion drift.
