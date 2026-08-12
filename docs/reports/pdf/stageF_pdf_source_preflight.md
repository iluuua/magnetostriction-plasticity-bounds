# Stage F PDF — preflight исходников

Дата: 2026-07-06. Режим: только оформление в PDF, без пересчёта MD/LAMMPS.

## Наличие source-файлов

Все основные исходники найдены:
- `docs/reports/stageF_new_problem_statement_report_ru.md` — есть;
- `docs/reports/stageF_new_problem_statement_short_ru.md` — есть;
- `docs/reports/stageF_new_statement_verified_numbers.md` / `.json` — есть;
- `docs/reports/stageF_cpu_results_key_stress_numbers.json` — есть;
- `docs/reports/stageF_cpu_results_key_plasticity_numbers.json` — есть;
- `docs/reports/stageF_new_problem_statement_README.md` — есть.

Figures (6 отобранных) найдены: `delta_sigma_vm_last20`, `sigma_zz_last20`, `sigma_vm_last20`, `sigma_vm_p95_last20`, `delta_defect_nonfcc_final`, `defect_other_final` (все `.png`).

Отсутствующих обязательных source-файлов нет — подмена по маске не потребовалась. Данные не выдумывались.

## Обязательные разделы полного отчёта

Все 11 разделов присутствуют (Краткий вывод; Новая постановка задачи; Геометрия и расчётная схема; Использованные формулы; Как обрабатывались данные; Результаты по напряжениям; Результаты по пластическим деформациям и дефектам; Интерпретация; Ограничения; Выводы и следующий шаг; Файлы-источники). `sections_missing_count = 0`.

## Проверка запрещённых формулировок

Просканированы 4 нарративных источника (`report_ru`, `short_ru`, `verified_numbers.md`, `README`). Проверенные фразы: «Пшонкин», «пластическая деформация доказана», «дислокации подтверждены», «stable dislocation confirmed», «developed dislocation proven», «plastic deformation proven», «full 20 micron MD», «full 5 micron inclusion modeled», «смоделировали 5 мкм», «полная микронная модель».

Результат: **0 попаданий, clean.** Формулировки правки не требуют (safe wording уже используется: «остаточная пластичность не подтверждена», «развитые дислокационные линии не обнаружены», «local virial stress proxy», «локальная модель границы»).

## Блокеры

Нет. Verdict: `ready_for_pdf_build`.
