# Eigenstrain surrogate model

## Purpose

The ellipsoidal inclusion branch uses a controlled eigenstrain surrogate to approximate inclusion deformation.

This model does not claim to reproduce a fully calibrated magnetic-field-dependent magnetostriction law. Instead, it imposes small controlled geometric strains on the Fe4Al13 inclusion and then relaxes the atomistic system.

## Coordinate transformation

For each atom in the inclusion ID range, its position relative to the inclusion center is transformed as:

r = x - x_center

r'_x = r_x * (1 + eps_x)

r'_y = r_y * (1 + eps_y)

r'_z = r_z * (1 + eps_z)

x' = x_center + r'

The tested cases use:

eps_z = 0.0010 / 0.0025 / 0.0050 / 0.0100

eps_x = eps_y = -0.5 * eps_z

This gives a simple volume-preserving-like deformation surrogate:

eps_x + eps_y + eps_z ≈ 0

## Interpretation

The imposed eigenstrain is used as a numerical perturbation of the inclusion geometry. After applying the transformation, the full system is minimized with LAMMPS.

The response is evaluated through:

- hard-overlap checks below 1.8 A;
- Al-Fe warning contacts below 2.1 A;
- final minimized potential energy;
- final force residuals;
- OVITO visual checks;
- comparative stress/atom diagnostics.

## Limitation

This is not a calibrated magnetic-field model.

The current surrogate does not include:

- magnetic field direction dependence;
- anisotropic magnetostriction tensor fitted to experiment;
- magnetic domain structure;
- experimental calibration of strain amplitude;
- validated plastic defect analysis.

The correct claim is:

The eigenstrain series tests numerical stability and local atomistic response to controlled inclusion deformation.
