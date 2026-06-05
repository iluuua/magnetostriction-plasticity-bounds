# Figure plan for article

## Figure 1 — Model geometry

Use:
- ellipsoid inclusion cutaway screenshot;
- Fe-only ellipsoid inclusion screenshot;
- optional flat-interface screenshot.

Message:
The study uses two simplified controlled geometries: a flat Al / Fe4Al13 interface and an ellipsoidal Fe4Al13 inclusion inside an Al matrix.

## Figure 2 — Flat-interface loading series

Use:
- `results/tables/interface_trial_001_stress_000_060_120_147_200mpa_comparison.csv`
- optional screenshots from 120 / 147 / 200 MPa OVITO review.

Message:
The flat-interface model remained numerically stable through 0 / 60 / 120 / 147 / 200 MPa controlled loading.

## Figure 3 — Flat-interface stress profile

Use:
- `results/figures/interface_trial_001_stress_200mpa_compression_ramp_stress_profile.png`
- optionally compare with 120 / 147 MPa stress-profile figures.

Message:
Stress/atom is interpreted comparatively. Highest hydrostatic proxy near fixed-bottom support is a boundary-condition artifact.

## Figure 4 — Ellipsoid eigenstrain final energy

Use:
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_energy_final.png`

Message:
The minimized potential energy changes across imposed inclusion eigenstrain cases.

## Figure 5 — Ellipsoid eigenstrain contact sanity

Use:
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_min_pair_distance.png`
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_alfe_warning_pairs.png`

Message:
No hard overlaps below 1.8 A were observed; Al-Fe contacts below 2.1 A remain warning-level contacts.

## Figure 6 — Final force residual

Use:
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_force_two_norm_final.png`

Message:
The eps_z = 0.0100 case remains script-sane but has larger final force residuals, so it should be treated as a numerical stress-test point.
