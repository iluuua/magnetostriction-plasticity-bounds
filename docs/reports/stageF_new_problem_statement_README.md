# Stage F — новая постановка: навигация (README)

Дата: 2026-07-06. Пакет отчётов по новой постановке расчёта Fe₄Al₁₃/Al (F0 planar boundary patch, CPU comparable pair).

## С чего начать (порядок чтения)

1. **Короткая версия** — `stageF_new_problem_statement_short_ru.md` (1–2 страницы: что, почему, формулы, 5 чисел, вывод).
2. **Главный отчёт** — `stageF_new_problem_statement_report_ru.md` (полная постановка, геометрия, формулы, результаты, ограничения, выводы).
3. **Перепроверенные числа** — `stageF_new_statement_verified_numbers.md` / `.json` (таблицы с source path на каждое число).
4. **Инвентаризация источников** — `stageF_new_statement_source_inventory.md` / `.json`.

## Где что лежит

- **Главный отчёт:** `docs/reports/stageF_new_problem_statement_report_ru.md`
- **Короткая версия:** `docs/reports/stageF_new_problem_statement_short_ru.md`
- **CSV с числами:**
  - `docs/reports/stageF_cpu_results_delta_sigma_profile.csv`
  - `docs/reports/stageF_cpu_results_eps0000_sigma_profile.csv`, `..._eps00194_sigma_profile.csv`
  - `docs/reports/stageF_cpu_results_delta_defect_profile.csv`
  - `docs/reports/stageF_cpu_results_eps0000_defect_profile.csv`, `..._eps00194_defect_profile.csv`
- **JSON-сводки:** `stageF_cpu_results_key_stress_numbers.json`, `..._key_plasticity_numbers.json`, `..._sigma_summary.json`, `..._defect_summary.json`, `..._residual_plasticity_check.json`, `..._production_verification.json`
- **Figures:** `docs/reports/figures/stageF_cpu_results_*.png`
  - напряжения: `sigma_vm_last20.png`, `delta_sigma_vm_last20.png`, `sigma_zz_last20.png`, `sigma_vm_p95_last20.png`
  - дефекты: `defect_other_final.png`, `defect_hcp_final.png`, `defect_nonfcc_final.png`, `delta_defect_nonfcc_final.png`

## Какие файлы смотреть первыми

- Для быстрого ответа: короткая версия + `sigma_vm_last20.png` и `delta_sigma_vm_last20.png`.
- Для проверки чисел: `stageF_new_statement_verified_numbers.md`.

## Что НЕ использовать для физического вывода

- `sigma_vm_p95_last20.png` и любые p95 atom-level абсолютные значения — шумный proxy, только для формы, не для абсолютных MPa.
- Слой `total σ_vm > 120 MPa = 121.068 Å` — это virial proxy до края доступного Al slab, НЕ толщина пластической зоны.
- Предыдущие meeting-oriented отчёты (`stageF_cpu_results_*criteria*`, `*executive*`, `*talk_track*`, `*brief*`) — использованы только как источник чисел, не как физический вывод.
- Любые GPU-данные — GPU production не получена; в физический результат не входит.
- Figures 2026-06-29 (`stageF_above_yield_layer.png`, `stageF_sigma_decay_*`, `stageF_hcp_other_by_distance.png`, `stageF_temporal_plastic_layer.png`) — из более ранней ветки, не текущий результат.

## Предупреждение

**Старая ветка m m f (open lateral) невалидна.** Ранняя постановка `F0_planar_100A_open_lateral` (граничные условия `m m f`, свободные боковые) была нестабильна (разгон shrink-wrap бокса, падения) и не даёт физического результата. Текущий валидный результат — только commensurate `p p f` pair из production root `runs\stageF_F0_planar_100A_ppf_commensurate\20260630-010748\cpu_fallback_production_20260701-001918`. Не смешивать ветки и не смешивать CPU/GPU в одной Δ-паре.
