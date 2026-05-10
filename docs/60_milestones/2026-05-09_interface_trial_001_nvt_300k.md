# Milestone: interface trial_001 unloaded NVT 300 K sanity-check

Дата: 2026-05-09

## Итог

Проведён короткий unloaded NVT sanity-check для минимизированной плоской границы Al / Fe4Al13 `trial_001`.

## Проверено

- `run 5000`, NVT 300 K, `boundary p p f`.
- 120 MPa не применялось.
- `fix addforce` не использовался.
- NPT не использовался.
- `ERROR/nan/lost atoms`: нет.
- `Dangerous builds = 0`.
- Dump: 51 frames, 618 atoms per frame.
- Post-NVT distance check: no pairs below 1.8 A, no Al-Fe pairs below 2.1 A.

## Файлы

- `lammps/02_interface_relax/trial_001/in.interface_nvt_300k`
- `lammps/02_interface_relax/trial_001/log.interface_minimize.lammps`
- `lammps/02_interface_relax/trial_001/log.interface_nvt_300k.lammps`
- `lammps/02_interface_relax/trial_001/data.interface_nvt_300k`
- `lammps/02_interface_relax/trial_001/log_summary_interface_nvt_300k.json`
- `lammps/02_interface_relax/trial_001/interface_nvt_300k_distance_report.json`
- `lammps/02_interface_relax/trial_001/dump_summary_interface_nvt_300k.json`
- `analysis/python/check_interface_distances.py`
- `docs/interface_trial_001_nvt_check.md`

## Риски

- Pressure remains negative on average in fixed-box slab NVT: last-20 mean about -5111 bar.
- Large triclinic skew warning remains.
- OVITO GUI/Python remains unavailable.
- This is a short sanity-run, not physical validation.

## Следующий шаг

Run a longer unloaded NVT or unloaded local stress/strain analysis before preparing any 120 MPa scenario.
