# Milestone — interface trial_001 120 MPa sanity-run

## Summary

The 120 MPa compression-ramp scenario completed successfully as a controlled numerical sanity-run.

## What was checked

- LAMMPS stability
- dangerous short contacts
- cross-slab contacts
- warning pair 232-260
- local stress-profile proxy
- OVITO visual geometry

## Main result

No numerical catastrophe was detected:

- no ERROR / nan / lost atoms
- Dangerous builds = 0 / 0
- no hard overlaps below 1.8 A
- no cross-slab Al-Fe contacts below 2.1 A
- warning pair 232-260 remains internal to Fe4Al13 and does not collapse monotonically
- no visual interface detachment in OVITO

## Important caveat

This is not final physical validation. The stress profile is a virial proxy and the maximum hydrostatic proxy occurs near the fixed-bottom support, which is an artificial boundary condition.

