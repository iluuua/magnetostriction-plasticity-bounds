# Ellipsoid inclusion trial_001 — eigenstrain epsz_p0p00250 check

## Status

The first magnetostriction-surrogate eigenstrain case was completed as a controlled minimization sanity-run.

## Input

- Baseline: `lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/data.ellipsoid_nvt_300k`
- Eigenstrain output: `structures/interface/ellipsoid_inclusion/trial_001/eigenstrain/epsz_p0p00250/data.ellipsoid_eigenstrain_epsz_p0p00250`
- Relaxed output: `lammps/04_ellipsoid_inclusion/trial_001/02_eigenstrain_relax/epsz_p0p00250_minimize/data.ellipsoid_eigenstrain_epsz_p0p00250_minimized`

## Eigenstrain model

- Inclusion atom ID range: 23264–24259
- Inclusion atoms: 996
- Fe atoms in inclusion range: 232
- eps_z: +0.0025
- eps_x: -0.00125
- eps_y: -0.00125

## Pre-minimization distance sanity

- Minimum pair distance: 1.9894813232200677 A
- Pairs below 1.8 A: 0
- Al-Fe pairs below 2.1 A: 8
- safe_basic: true

## Minimization result

- LAMMPS reached `Total wall time`.
- Minimization stopped by energy tolerance.
- Iterations: 93
- Force evaluations: 205
- Energy initial: -80399.7241095406 eV
- Energy final: -81346.9789455425 eV
- Force two-norm: 104.29715 -> 3.1637806
- Force max component: 2.0318048 -> 1.3894486
- Dangerous builds: 0
- Output data and dump files were written.

## Output files

- `log.ellipsoid_eigenstrain_epsz_p0p00250_minimize.lammps`
- `dump.ellipsoid_eigenstrain_epsz_p0p00250_minimize.lammpstrj`
- `dump.ellipsoid_eigenstrain_epsz_p0p00250_minimized_final.lammpstrj`
- `data.ellipsoid_eigenstrain_epsz_p0p00250_minimized`
- `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_epsz_p0p00250_minimized_distance_report.json`

## Caveat

This is not final physical validation.

This run is a controlled numerical sanity-run for a simplified magnetostriction surrogate. Per-atom stress must be treated as a comparative virial proxy, not as an experimentally validated absolute stress field.

## Next

If OVITO cutaway and Fe-only views show no visible failure, proceed to a small strain series:
- eps_z = 0.0010
- eps_z = 0.0025
- eps_z = 0.0050
- eps_z = 0.0100


## Post-minimization distance sanity

- Minimum pair distance: 2.02732260776541 A
- Pairs below 1.8 A: 0
- Al-Fe pairs below 2.1 A: 2
- safe_basic: true

## Current verdict

The epsz_p0p00250 eigenstrain-relax case is accepted as a controlled numerical sanity-run, after manual OVITO cutaway and Fe-only visual review.
