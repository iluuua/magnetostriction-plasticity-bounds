# Stage F PDF package

Пакет PDF по новой постановке расчёта Fe₄Al₁₃/Al (локальная модель границы). Дата: 2026-07-06. Только оформление; новые MD-расчёты не запускались.

## 1. Главный PDF

- `stageF_new_problem_statement_report_ru.pdf` — полный отчёт (14 страниц, A4, с титульной страницей, содержанием, таблицей «5 главных чисел», формулами, результатами, ограничениями, выводами и 6 иллюстрациями).

## 2. Короткая версия

- `stageF_new_problem_statement_short_ru.pdf` — 2 страницы: что считали, почему, формулы, 5 чисел, вывод, следующий шаг. Удобно отправить отдельно.

## 3. HTML sources

- `stageF_new_problem_statement_report_ru.html`
- `stageF_new_problem_statement_short_ru.html`
- `stageF_new_problem_statement_figures_appendix_ru.html`

## 4. Приложение иллюстраций

- `stageF_new_problem_statement_figures_appendix_ru.pdf` — 6 ключевых figures с подписями (4 страницы).

## 5. Validation / build

- `stageF_pdf_validation_report.md` / `.json` — страницы, размеры, кириллица, проверка содержимого, forbidden-wording scan, превью.
- `stageF_pdf_build_report.md` / `.json` — как собирался PDF (Markdown → HTML → headless Edge CDP).
- `stageF_pdf_source_preflight.md` / `.json` — проверка готовности исходников.
- Превью: `preview_full_page_1.png`, `preview_full_page_2.png`, `preview_short_page_1.png`.

## 6. Source reports (оригиналы)

- `../stageF_new_problem_statement_report_ru.md`
- `../stageF_new_problem_statement_short_ru.md`
- `../stageF_new_statement_verified_numbers.md` / `.json` — числа с source-путями.
- `../stageF_new_statement_source_inventory.md` / `.json`
- Числовые сводки: `../stageF_cpu_results_key_stress_numbers.json`, `../stageF_cpu_results_key_plasticity_numbers.json`.
- CSV-профили: `../stageF_cpu_results_*_profile.csv`.
- Figures: `../figures/stageF_cpu_results_*.png`.

## Что смотреть первым

1. `stageF_new_problem_statement_short_ru.pdf` — быстрый обзор.
2. `stageF_new_problem_statement_report_ru.pdf` — полная версия.

## Чего НЕ использовать для физического вывода

- p95 atom-level абсолютные значения (`sigma_vm_p95_last20.png`) — шумный proxy, только для формы, не для абсолютных MPa.
- Слой `total σ_vm > 120 MPa = 121.068 Å` — это virial proxy до края доступного Al slab, НЕ толщина пластической зоны.
- Любые GPU-данные — GPU production не получена, в физический результат не входит.

## Предупреждение

Старая ветка **m m f (open lateral)** невалидна (нестабильный слэб, падения). Текущий валидный результат — только commensurate **p p f** CPU-пара из `runs\stageF_F0_planar_100A_ppf_commensurate\20260630-010748\cpu_fallback_production_20260701-001918`. Не смешивать ветки и не смешивать CPU/GPU в одной Δ-паре.
