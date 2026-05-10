# Проверка unloaded interface trial_001

Дата: 2026-05-09

## 1. Кандидат

- Al surface: (111)
- Fe4Al13 surface: (100)
- Источник: `results/tables/interface_mismatch_candidates.csv`
- Source max length mismatch: 0.9434288068775897 %
- Source angle delta: 0.1144388402026486 deg
- Source estimated atoms: 652
- Нагрузка 120 MPa: не применялась

Это численный кандидат по приближённому matching-скрипту, а не доказанная кристаллографически корректная OR.

## 2. Сборка интерфейса

- Builder: `analysis/python/build_unloaded_interface_trial.py`
- Output data: `structures/interface/flat_interface/trial_001/data.interface_trial`
- Metadata: `structures/interface/flat_interface/trial_001/interface_metadata.json`
- Min-distance report: `structures/interface/flat_interface/trial_001/min_distance_report.json`

Фактическая система:

| Параметр | Значение |
|---|---:|
| Всего атомов | 618 |
| Al, type 1 | 522 |
| Fe, type 2 | 96 |
| Al slab atoms | 210 |
| Fe4Al13 slab atoms | 408 |
| Lx, A | 15.315253639464007 |
| Ly, A | 6.670272350047926 |
| Lz, A | 109.21147561319708 |
| xy, A | 4.002516727832912 |
| xz / yz, A | 0 / 0 |

Параметры сборки:

- Al normal repeats: 5
- Fe4Al13 normal repeats: 2
- Initial interface gap: 2.25 A
- Fe lateral shift, fractional: (0.0, 0.8)
- Boundary для LAMMPS input: `p p f`
- Tilt reduction: `v2 -> v2 - v1`

## 3. Минимальные расстояния до LAMMPS

| Проверка | Значение |
|---|---:|
| Minimum Al-Al distance, A | 2.3551235284824075 |
| Minimum Fe-Fe distance, A | 2.609414981367479 |
| Minimum Al-Fe distance, A | 2.27795990170914 |
| Minimum cross-slab distance, A | 2.3551235284824075 |
| Al-Fe pairs below 2.1 A | 0 |
| Cross-slab pairs below 2.1 A | 0 |
| Any pairs below 1.8 A | 0 |

Вывод по геометрии до запуска: жёстких overlap нет, warning threshold для Al-Fe не нарушен.

## 4. LAMMPS minimization

- Input: `lammps/02_interface_relax/trial_001/in.interface_minimize`
- Log: `lammps/02_interface_relax/trial_001/log.lammps`
- Summary: `lammps/02_interface_relax/trial_001/log_summary_interface_trial_001.json`
- Output data: `lammps/02_interface_relax/trial_001/data.interface_minimized`
- Dump: `lammps/02_interface_relax/trial_001/dump.interface_minimize.lammpstrj`
- Final dump: `lammps/02_interface_relax/trial_001/dump.interface_minimized_final.lammpstrj`

Команда запуска:

```bash
cd /Users/ilua/Documents/ilua-system/projects/physics_md_al_fe/lammps/02_interface_relax/trial_001
lmp -in in.interface_minimize
```

Ключевые результаты:

| Параметр | Initial | Final |
|---|---:|---:|
| Step | 0 | 510 |
| PotEng, eV | -2106.9824 | -2143.9047 |
| Press, bar | -11429.925 | -7271.804 |
| Volume, A^3 | 11156.707 | 11156.707 |
| Force two-norm | 25.722145 | 0.31516476 |
| Force max component | 3.4027097 | 0.18026842 |

Проверки лога:

- `ERROR`: нет
- `nan`: нет
- `lost atoms`: нет
- `Dangerous builds`: 0
- Loop time: 18.6819 s, 510 steps, 618 atoms
- Stopping criterion: energy tolerance

LAMMPS напечатал warning о большом skew triclinic box. Это не остановило расчёт, но остаётся геометрическим риском для следующей релаксации.

## 5. Вердикт

`trial_001` допустим как первый unloaded interface baseline для следующего короткого NVT sanity-run без нагрузки.

Ограничения:

- Это не финальная физически валидированная граница.
- Давление после минимизации остаётся сильно отрицательным, потому что запуск был только fixed-box minimization.
- Следующий запуск должен быть коротким NVT при 300 K без 120 MPa и с проверкой лога.
- Stress-сценарии и `fix addforce` пока не запускать.
