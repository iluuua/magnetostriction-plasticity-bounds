# Milestone: interface mismatch scan

Дата: 2026-05-09.

## Итог

- Добавлен `analysis/python/build_flat_interface.py`.
- Сравнены Al (100), (110), (111) и Fe4Al13 (100), (010), (001).
- Созданы `docs/interface_mismatch_candidates.md` и `results/tables/interface_mismatch_candidates.csv`.
- `data.interface` не создавался.
- 120 MPa и stress-сценарии не запускались.

## Лучший численный кандидат

- Al (111) / Fe4Al13 (100)
- max length mismatch: 0.943%
- angle delta: 0.114 deg
- area mismatch: 0.727%
- estimated atoms: 652 по heuristic slab filter

## Ограничения

- Fe4Al13 surface basis взят из relaxed triclinic conventional LAMMPS cell без primitive reduction.
- Это ранжирование, а не физическая валидация интерфейса.
- Перед LAMMPS minimization нужно явно выбрать кандидат и проверить минимальные Al-Fe расстояния.

## Следующий шаг

Выбрать candidate из `docs/interface_mismatch_candidates.md`, затем отдельным скриптом собрать ненагруженный interface trial без 120 MPa.
