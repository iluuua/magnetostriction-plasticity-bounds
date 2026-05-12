# Milestone: loading design prepared for trial_001

Дата: 2026-05-10

## Objective

Prepare controlled loading design for Al / Fe4Al13 `trial_001` without running a 120 MPa or any other stress scenario.

## Verified

- No LAMMPS stress run was executed.
- No active `fix addforce` was used.
- No NPT was used.
- Unloaded baseline files were not overwritten.

## Outputs

- Force calculator: `analysis/python/calculate_interface_loading_force.py`
- Force table: `results/tables/interface_trial_001_loading_force_table.csv`
- Design doc: `docs/interface_trial_001_loading_design.md`
- Templates:
  - `lammps/03_interface_stress/stress_000mpa/in.interface_stress_template`
  - `lammps/03_interface_stress/stress_060mpa/in.interface_stress_template`
  - `lammps/03_interface_stress/stress_120mpa/in.interface_stress_template`
  - `lammps/03_interface_stress/stress_147mpa/in.interface_stress_template`
  - `lammps/03_interface_stress/stress_200mpa/in.interface_stress_template`

## Key Numbers

- Interface area: 102.15691288528764 A^2
- Target group: Fe4Al13_slab, z = 40.16445..48.16445 A
- Target atoms: 52
- 120 MPa future per-atom force: 0.0014714153049055854 eV/A

## Next Step

Review the direction and duration of loading after OVITO visual checks, then copy a template into a separate run file for the first controlled low-stress test.
