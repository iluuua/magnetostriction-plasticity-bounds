# Milestone: unloaded interface trial_001 minimized

Дата: 2026-05-09

## Итог

Построен и минимизирован первый маленький unloaded flat interface trial для Al / Fe4Al13: Al(111) / Fe4Al13(100).

## Проверено

- До LAMMPS нет hard overlaps ниже 1.8 A.
- Al-Fe pairs ниже 2.1 A: 0.
- LAMMPS minimization завершилась без `ERROR`, `nan`, lost atoms.
- `Dangerous builds = 0`.
- 120 MPa не применялось.

## Файлы

- `analysis/python/build_unloaded_interface_trial.py`
- `structures/interface/flat_interface/trial_001/data.interface_trial`
- `structures/interface/flat_interface/trial_001/interface_metadata.json`
- `structures/interface/flat_interface/trial_001/min_distance_report.json`
- `lammps/02_interface_relax/trial_001/in.interface_minimize`
- `lammps/02_interface_relax/trial_001/data.interface_minimized`
- `lammps/02_interface_relax/trial_001/log_summary_interface_trial_001.json`
- `docs/interface_trial_001_check.md`

## Риски

- Большой triclinic skew в интерфейсной ячейке.
- Остаточное давление после fixed-box minimization около -7272 bar.
- Интерфейс ещё не проверен при 300 K.

## Следующий шаг

Подготовить короткий unloaded NVT sanity-run для `data.interface_minimized`, затем проверить лог и траекторию. Stress-сценарии не запускать.
