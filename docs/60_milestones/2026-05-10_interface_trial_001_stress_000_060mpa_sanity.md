# Milestone: stress_000mpa and stress_060mpa sanity runs for trial_001

Дата: 2026-05-10

## Objective

Run the first real controlled loading sanity tests for `trial_001`: 0 MPa support/control and 60 MPa compression ramp toward Al side.

## Verified

- 120 MPa was not run.
- NPT was not used.
- Unloaded baseline was not overwritten.
- 0 MPa control completed 5000 steps.
- 60 MPa compression completed 10000 steps: 2000-step ramp + 8000-step hold.
- Both logs have no `ERROR`, `nan`, or lost atoms.
- Dangerous builds = 0 for both runs.

## Outputs

- Report: `docs/interface_trial_001_stress_000_060mpa_check.md`
- Comparison CSV: `results/tables/interface_trial_001_stress_000_060mpa_comparison.csv`
- 0 MPa run folder: `lammps/03_interface_stress/stress_000mpa/run_001_control/`
- 60 MPa run folder: `lammps/03_interface_stress/stress_060mpa/run_001_compression_ramp/`

## Key Findings

- 0 MPa control passed sanity check.
- 60 MPa compression ramp passed basic sanity with warning.
- 60 MPa final min Al-Fe distance = 2.03014 A.
- 60 MPa warning pair 232-260 is internal Fe4Al13, not cross-slab.
- No pairs below 1.8 A in either run.
- No cross-slab Al-Fe pairs below 2.1 A in either run.

## Next Step

Inspect 60 MPa dump and pair 232-260 in OVITO Basic before any 120 MPa setup.
