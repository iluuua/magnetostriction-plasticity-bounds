# Stage F — новая постановка: инвентаризация источников

Дата: 2026-07-06

Назначение: зафиксировать, какие уже существующие файлы Stage F CPU results использованы как источники чисел для отчёта по новой постановке задачи. Новые MD-расчёты не запускались.

Production root:
`runs\stageF_F0_planar_100A_ppf_commensurate\20260630-010748\cpu_fallback_production_20260701-001918`

Cases:
- `F0_planar_100A_comm_eps0000_cpu_zhi200` — baseline;
- `F0_planar_100A_comm_eps00194_cpu_zhi200` — physical case.

## Прочитанные MD-отчёты (нейтральные)

| Файл | Роль |
| --- | --- |
| `docs/reports/stageF_cpu_results_sigma_report_ru.md` | описание σ(r), толщины слоёв |
| `docs/reports/stageF_cpu_results_plasticity_report_ru.md` | CNA/DXA frame summary |
| `docs/reports/stageF_cpu_results_residual_plasticity_check_ru.md` | вердикт остаточной пластичности |
| `docs/reports/stageF_cpu_results_next_step_decision_ru.md` | решение по следующему шагу |
| `docs/reports/stageF_cpu_results_dump_inventory.md` | инвентарь dump/restart, пути |
| `docs/reports/stageF_cpu_results_key_stress_numbers.md` | сводка ключевых чисел по напряжениям |
| `docs/reports/stageF_cpu_results_key_plasticity_numbers.md` | сводка ключевых чисел по дефектам |
| `docs/reports/stageF_cpu_results_production_verification.md` | подтверждение чистого завершения production |

## Предыдущие отчёты (meeting-oriented, использованы только как источник чисел)

Эти файлы прочитаны как данные; их формулировки и названия не переносятся в новый отчёт:
`stageF_cpu_results_pshonkin_report_ru.md`, `..._pshonkin_criteria_answers_ru.md`, `..._pshonkin_criteria_map_ru.md`, `..._pshonkin_executive_brief_ru.md`, `..._pshonkin_meeting_brief_ru.md`, `..._pshonkin_talk_track_ru.md`, `..._best_figures_for_pshonkin.md`, `..._safe_wording_ru.md`, `..._executive_extraction_inventory.md`.

## Прочитанные CSV

| Файл | Роль | Проверка |
| --- | --- | --- |
| `docs/reports/stageF_cpu_results_delta_sigma_profile.csv` | Δσ(r), окна initial/final/last20_mean, 114 строк | pandas OK, peak Δσ_vm=578.422 @ r=1 Å |
| `docs/reports/stageF_cpu_results_delta_defect_profile.csv` | Δf_дефектов(r) | pandas OK, ΔOTHER(final)=0.035964 @ r=3 Å |
| `docs/reports/stageF_cpu_results_eps0000_sigma_profile.csv` | baseline σ(r) | источник |
| `docs/reports/stageF_cpu_results_eps00194_sigma_profile.csv` | physical σ(r) | источник |
| `docs/reports/stageF_cpu_results_eps0000_defect_profile.csv` | baseline defect(r) | источник |
| `docs/reports/stageF_cpu_results_eps00194_defect_profile.csv` | physical defect(r) | источник |

## Прочитанные JSON

- `docs/reports/stageF_cpu_results_key_stress_numbers.json`
- `docs/reports/stageF_cpu_results_key_plasticity_numbers.json`
- `docs/reports/stageF_cpu_results_sigma_summary.json`
- `docs/reports/stageF_cpu_results_defect_summary.json`
- `docs/reports/stageF_cpu_results_residual_plasticity_check.json`
- `docs/reports/stageF_cpu_results_next_step_decision.json`
- `docs/reports/stageF_cpu_results_pshonkin_criteria_answers.json`
- `docs/reports/stageF_cpu_results_production_verification.json`
- `docs/reports/stageF_cpu_results_dump_inventory.json`

## Найденные figures (текущие, Stage F CPU)

- `docs/reports/figures/stageF_cpu_results_sigma_vm_last20.png`
- `docs/reports/figures/stageF_cpu_results_sigma_zz_last20.png`
- `docs/reports/figures/stageF_cpu_results_sigma_vm_p95_last20.png`
- `docs/reports/figures/stageF_cpu_results_delta_sigma_vm_last20.png`
- `docs/reports/figures/stageF_cpu_results_defect_other_final.png`
- `docs/reports/figures/stageF_cpu_results_defect_hcp_final.png`
- `docs/reports/figures/stageF_cpu_results_defect_nonfcc_final.png`
- `docs/reports/figures/stageF_cpu_results_delta_defect_nonfcc_final.png`

Figures 2026-06-29 (`stageF_above_yield_layer.png`, `stageF_hcp_other_by_distance.png`, `stageF_sigma_decay_components.png`, `stageF_sigma_decay_vm.png`, `stageF_temporal_plastic_layer.png`) относятся к более ранней ветке и в физический вывод текущего отчёта не входят.

## Ожидаемых файлов нет

- Dmin2 / atomic-strain reference: не сохранён в CPU dump, не вычислялся, отдельно не заявляется.
- GPU production comparable pair: отсутствует (backend blocker); в физический результат не входит.
- eps005 / F1 / F0_300A production: не запускались, данных нет.

## Основные источники чисел

- Напряжения: `stageF_cpu_results_key_stress_numbers.json` + `stageF_cpu_results_sigma_summary.json` + `stageF_cpu_results_delta_sigma_profile.csv`.
- Пластичность/дефекты: `stageF_cpu_results_key_plasticity_numbers.json` + `stageF_cpu_results_defect_summary.json` + `stageF_cpu_results_residual_plasticity_check.json` + `stageF_cpu_results_delta_defect_profile.csv`.
- Протокол/геометрия: `stageF_cpu_results_production_verification.json` + `stageF_cpu_results_dump_inventory.md`.
