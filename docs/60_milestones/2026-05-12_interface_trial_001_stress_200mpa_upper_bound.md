# Milestone — interface trial_001 200 MPa upper-bound run

## Summary

The 200 MPa compression-ramp scenario completed and was accepted as a controlled upper-bound / failure-probe after manual OVITO review.

## Main result

No numerical catastrophe was detected:

- no ERROR / nan / lost atoms
- Dangerous builds = 0 / 0
- no hard overlaps below 1.8 A
- no cross-slab Al-Fe contacts below 2.1 A
- warning pair 232-260 remains internal to Fe4Al13 and does not collapse monotonically
- manual OVITO review found no visible interface detachment, empty interface gap, atom ejection, or whole-block drift

## Important caveat

This is not final physical validation. The stress profile is a virial proxy and the maximum hydrostatic proxy remains near the fixed-bottom support, which is an artificial boundary condition.
