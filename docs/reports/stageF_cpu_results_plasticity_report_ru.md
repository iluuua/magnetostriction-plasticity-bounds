# Stage F CPU results: defect/plasticity report

Дата: 2026-07-02T07:38:26+03:00

## Краткий вывод

CNA/DXA post-processing выполнен через OVITO `3.15.4` для `step 0` и `step 50000` по обеим CPU cases. Анализ ограничен Al matrix (`type=1`, `z >= 50.0 A`) и теми же `r`-bins.

`Dmin2` не заявлен: это свойство не было сохранено в dump, а в этом отчете не вводилась отдельная reference-strain процедура.

## Frame summary

| case | step | matrix atoms | HCP | OTHER | non-FCC | DXA segments | DXA line A |
| --- | --- | --- | --- | --- | --- | --- | --- |
| eps0000 | 0 | 81645.0 | 0 | 2910.0 | 2910.0 | 0 | 0 |
| eps0000 | 50000.0 | 82509.0 | 1 | 3028.0 | 3029.0 | 0 | 0 |
| eps00194 | 0 | 82125.0 | 0 | 2535.0 | 2535.0 | 0 | 0 |
| eps00194 | 50000.0 | 82573.0 | 0 | 3126.0 | 3126.0 | 0 | 0 |

## Интерпретация

CNA/OTHER около interface и свободной поверхности трактуется как локальное нарушение решетки/топологии. Сам по себе такой сигнал не равен доказанной пластической зоне. DXA line length в финале, если появляется, должен читаться только вместе с устойчивостью во времени; текущий defect block имеет `step 0` и `step 50000`, поэтому не доказывает persistent dislocation dynamics.

## Figures

- `docs\reports\figures\stageF_cpu_results_defect_other_final.png`
- `docs\reports\figures\stageF_cpu_results_defect_hcp_final.png`
- `docs\reports\figures\stageF_cpu_results_defect_nonfcc_final.png`
- `docs\reports\figures\stageF_cpu_results_delta_defect_nonfcc_final.png`

## Files

- `docs/reports/stageF_cpu_results_eps0000_defect_profile.csv`
- `docs/reports/stageF_cpu_results_eps00194_defect_profile.csv`
- `docs/reports/stageF_cpu_results_delta_defect_profile.csv`
- `docs/reports/stageF_cpu_results_defect_summary.json`
