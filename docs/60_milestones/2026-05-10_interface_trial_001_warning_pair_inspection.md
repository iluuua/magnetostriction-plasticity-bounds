# Milestone: trial_001 warning pair inspection

Дата: 2026-05-10

## Итог

Проверен единственный Al-Fe warning pair ниже 2.1 A после long unloaded NVT.

## Проверено

- OVITO app в `/Applications` не найден.
- Python module `ovito` отсутствует.
- Conda `ovito` падает с `dyld` / `Gui.so`.
- Скриптовая проверка нашла 1 Al-Fe pair ниже 2.1 A.
- Pair 232-260, Al-Fe, internal Fe4Al13 slab.
- Min distance over trajectory: 2.0268 A.
- Frames below 2.1 A: 11 / 21.
- Frames below 1.8 A: 0 / 21.
- Distance is not monotonic collapse.

## Файлы

- `analysis/python/inspect_warning_pairs.py`
- `lammps/02_interface_relax/trial_001/warning_pairs_long_nvt.json`
- `results/tables/interface_trial_001_warning_pair_distance_over_time.csv`
- `results/figures/interface_trial_001_warning_pair_distance_over_time.png`
- `results/tables/interface_trial_001_warning_pair_neighborhood.csv`
- `docs/interface_trial_001_warning_pairs_check.md`

## Риски

- OVITO remains unavailable.
- Warning pair is internal and intermittent, but still unvisualized.
- No physical validation is claimed.

## Следующий шаг

Install official OVITO Basic for macOS or run further unloaded geometry refinement before any 120 MPa scenario.
