# Milestone: contact-density check apparent gaps trial_001

Дата: 2026-05-10

## Objective

Проверить, являются ли видимые в OVITO gap/void-like области около Al / Fe4Al13 реальными interface voids или артефактами визуализации/triclinic/open-structure geometry.

## Verified

- 120 MPa не применялось.
- `fix addforce` не использовался.
- stress scenario не создавался.
- NPT не использовался.
- OVITO Basic app найден: `/Applications/Ovito.app`.
- OVITO Python module в conda env недоступен.

## Results

- Script: `analysis/python/check_interface_contact_density.py`
- JSON: `lammps/02_interface_relax/trial_001/interface_contact_density_report.json`
- CSV: `results/tables/interface_trial_001_contact_density_z_profile.csv`
- Figure: `results/figures/interface_trial_001_contact_density_z_profile.png`
- Report: `docs/interface_trial_001_contact_density_check.md`

Key numbers:

- interface z = 40.16445 A, window = +/- 8 A
- near-interface atoms: 42 Al_slab, 52 Fe4Al13_slab
- minimum cross-slab distance = 2.59247 A
- mean 10 smallest cross-slab distances = 2.66203 A
- cross-slab pairs within 2.8 / 3.0 / 3.5 A = 20 / 33 / 48
- largest empty z-gap between occupied bins = 1 A and does not intersect the interface window

## Verdict

The visible OVITO gaps are likely visualization/triclinic/open-structure artifacts rather than a large physical interface void. This does not validate the interface physically and does not authorize loading.

## Next Step

Use OVITO Basic to visually inspect the apparent gap regions and warning pair 232-260, then decide whether trial_001 needs unloaded refinement or trial_002 geometry rebuild before any 120 MPa planning.
