# Milestone — interface trial_001 147 MPa sanity-run

## Summary

The 147 MPa compression-ramp scenario completed and was accepted as a controlled numerical sanity-run after manual OVITO review.

## What was checked

- LAMMPS stability
- dangerous short contacts
- cross-slab contacts
- warning pair 232-260
- local stress-profile proxy
- comparison with 120 MPa
- OVITO visual geometry

## Main result

No script-level numerical catastrophe was detected:

- no ERROR / nan / lost atoms
- Dangerous builds = 0 / 0
- no hard overlaps below 1.8 A
- no cross-slab Al-Fe contacts below 2.1 A
- warning pair 232-260 remains internal to Fe4Al13 and does not collapse monotonically
- manual OVITO review found no visible interface detachment, empty interface gap, atom ejection, or whole-block drift

## Important caveat

This is not final physical validation. The stress profile is a virial proxy and the maximum hydrostatic proxy remains near the fixed-bottom support.
