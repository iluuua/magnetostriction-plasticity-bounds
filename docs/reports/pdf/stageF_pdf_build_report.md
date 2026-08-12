# Stage F PDF — build report

Дата: 2026-07-06. Режим: только оформление в PDF, без запуска MD/LAMMPS/GPU.

## Как собирался PDF

- Конвейер: Markdown → самособранный HTML (+CSS, figures в base64) → PDF.
- Backend: headless **Edge (Chromium)** через DevTools Protocol `Page.printToPDF`.
  - Браузер: `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`.
  - Запуск браузера — через PowerShell `Start-Process` (прямой запуск из Python `subprocess` делегировался уже запущенному пользовательскому Edge и не срабатывал — задокументировано).
  - Печать — Python-подкоманда `scripts/stageF_render_new_statement_pdf.py printpdf <ws_url> <out_pdf>` подключается к CDP и вызывает `Page.printToPDF`.
- Параметры страницы: **A4 portrait**, поля ~**20 мм**, колонтитул с номером страницы «Стр. N / M».
- Markdown→HTML — собственный конвертер (заголовки, таблицы с выравниванием, блоки формул, вложенные списки, bold, inline code, hr, картинки), без внешнего пакета `markdown`.
- Fallback (не понадобился): `--print-to-pdf` CLI без номеров страниц.

## Результаты

| Документ | Страниц | Размер PDF | Figures | Формулы | 5 чисел |
| --- | ---: | ---: | ---: | :---: | :---: |
| `stageF_new_problem_statement_report_ru.pdf` | 14 | 932 475 B | 6 | да | да |
| `stageF_new_problem_statement_short_ru.pdf` | 2 | 149 628 B | 0 | да (кратко) | да |
| `stageF_new_problem_statement_figures_appendix_ru.pdf` | 4 | 587 076 B | 6 | — | — |

HTML-исходники сохранены рядом (`*_report_ru.html`, `*_short_ru.html`, `*_figures_appendix_ru.html`).

## Figures

Все 6 отобранных figures найдены и встроены (base64):
`delta_sigma_vm_last20`, `sigma_zz_last20`, `sigma_vm_last20`, `sigma_vm_p95_last20`, `delta_defect_nonfcc_final`, `defect_other_final`. Отсутствующих figures нет; битых ссылок нет. Каждая подпись описывает, что показано и какой вывод поддерживает, без утверждений о доказанной пластичности.

## Примечания

- Числовые выводы не менялись. Добавлена только safe-wording строка «пластическая деформация не подтверждена» в блок «Итог» титульной части.
- Имя научрука в PDF/HTML отсутствует.
- Никакие MD/LAMMPS/GPU/eps005/F1/F0_300A не запускались.
