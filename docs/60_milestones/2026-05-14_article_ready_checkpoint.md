# Milestone — article-ready computational checkpoint

## Summary

The project now contains two completed controlled numerical study branches:

1. Flat Al / Fe4Al13 interface loading series:
   - 0 MPa
   - 60 MPa
   - 120 MPa
   - 147 MPa
   - 200 MPa upper-bound / failure-probe

2. Ellipsoidal Fe4Al13 inclusion in Al matrix:
   - unloaded 300 K NVT baseline
   - eigenstrain surrogate series:
     - eps_z = 0.0010
     - eps_z = 0.0025
     - eps_z = 0.0050
     - eps_z = 0.0100

## Article-ready artifacts

- `docs/article/article_results_draft.md`
- `docs/article/figure_plan.md`
- `docs/article/article_checklist.md`
- `results/tables/article/article_key_results_summary.csv`
- `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_summary.csv`
- `docs/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_check.md`
- `docs/ellipsoid_inclusion/ellipsoid_trial_001_nvt_300k_baseline.md`

## Main verdict

The current results are accepted as controlled numerical sanity-runs suitable for article drafting.

## Important caveat

This is not final physical validation.

The article must explicitly state that:
- stress/atom is a comparative virial proxy;
- the geometries are simplified;
- the ellipsoid model is a magnetostriction surrogate;
- no experimental calibration has been performed yet.
