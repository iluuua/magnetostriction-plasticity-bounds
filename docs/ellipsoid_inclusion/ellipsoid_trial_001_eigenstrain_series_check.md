# Ellipsoid inclusion trial_001 eigenstrain series check

## Status

The ellipsoid Fe4Al13 inclusion in Al matrix eigenstrain series completed as a controlled numerical sanity-run.

This is not final physical validation.

## Cases

| Case | eps_z | Status |
|---|---:|---|
| epsz_p0p00100 | 0.0010 | accepted_script_sanity |
| epsz_p0p00250 | 0.0025 | accepted_script_sanity |
| epsz_p0p00500 | 0.0050 | accepted_script_sanity |
| epsz_p0p01000 | 0.0100 | accepted_script_sanity |

## Summary

All four minimized eigenstrain cases passed script-level sanity checks:

- no ERROR / nan / lost atoms / fatal error in logs;
- Dangerous builds = 0;
- Total wall time present;
- minimized data files exist;
- final dump files exist;
- no hard overlaps below 1.8 A;
- safe_basic = true.

## Main numerical observations

| Case | eps_z | Minimized min pair distance, A | Minimized Al-Fe pairs below 2.1 A | Hard pairs below 1.8 A | Final energy, eV |
|---|---:|---:|---:|---:|---:|
| epsz_p0p00100 | 0.0010 | 2.0223692937594833 | 3 | 0 | -81346.4219686416 |
| epsz_p0p00250 | 0.0025 | 2.02732260776541 | 2 | 0 | -81346.9789455425 |
| epsz_p0p00500 | 0.0050 | 1.9518806269765512 | 4 | 0 | -81348.0111737039 |
| epsz_p0p01000 | 0.0100 | 1.9736532602057004 | 3 | 0 | -81345.0865828122 |

## Output files

Main summary table:

- `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_summary.csv`

Distance reports:

- `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_epsz_p0p00100_minimized_distance_report.json`
- `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_epsz_p0p00250_minimized_distance_report.json`
- `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_epsz_p0p00500_minimized_distance_report.json`
- `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_epsz_p0p01000_minimized_distance_report.json`

Figures:

- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_energy_final.png`
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_min_pair_distance.png`
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_alfe_warning_pairs.png`
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_force_two_norm_final.png`

## Caveats

This is not final physical validation.

The model still has:

- simplified ellipsoid inclusion geometry;
- periodic Al matrix;
- artificial initial cavity/clearance from geometry construction;
- MEAM potential applicability limitations;
- virial stress and force diagnostics only;
- no experimental calibration.

## Verdict

The 0.0010 / 0.0025 / 0.0050 / 0.0100 eigenstrain series is accepted as a controlled numerical sanity-run.

The strongest case, epsz_p0p01000, does not show hard overlaps below 1.8 A and remains script-sane, but it has larger final force residuals than smaller strain cases. Treat it as a numerical stress-test point, not as a final physical claim.
