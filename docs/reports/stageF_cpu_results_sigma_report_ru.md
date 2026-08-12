# Stage F CPU results: sigma(r) report

Дата: 2026-07-02T07:38:17+03:00

## Краткий вывод

CPU fallback pair дает валидный post-processing ответ на главный запрос Пшонкина: `sigma(r)` построен от плоской границы `z = 50.0 A` в Al matrix, отдельно для `eps0000` и `eps00194`, плюс baseline-subtracted delta `eps00194 - eps0000`.

Главная оговорка: это local virial stress proxy, а не калиброванное continuum-напряжение. Поэтому надежнее читать форму профиля и baseline delta, чем абсолютные p95 atom-level значения.

## Thickness checks

Final frame:

| case | mean VM layer A | p95 VM layer A | |zz| mean layer A | near 0-10A VM MPa | far 50A+ VM MPa |
| --- | --- | --- | --- | --- | --- |
| eps0000 | 120 | 120 | 8 | 1146.1 | 1004.5 |
| eps00194 | 120 | 120 | 8 | 1175.1 | 945.819 |

Last 20% window:

| case | mean VM layer A | p95 VM layer A | |zz| mean layer A | near 0-10A VM MPa | far 50A+ VM MPa |
| --- | --- | --- | --- | --- | --- |
| eps0000 | 121.068 | 121.068 | 121.068 | 1042.5 | 803.219 |
| eps00194 | 121.068 | 121.068 | 121.068 | 1117.9 | 739.733 |

Peak absolute baseline delta in last-20%-mean `sigma_vm_mean`: `578.422 MPa`.

## Что можно сказать Пшонкину

- `sigma(r)` построен в нужной геометрии: `r=0` на interface, `+Z` в Al matrix.
- Слой относительно `120 MPa` есть по local virial proxy, но p95 atom-level proxy шумный; cutoff нельзя превращать в точную физическую длину без оговорки.
- Baseline delta CPU-only показывает изменение поля напряжений от eigenstrain, без смешивания CPU/GPU.

## Figures

- `docs\reports\figures\stageF_cpu_results_sigma_vm_last20.png`
- `docs\reports\figures\stageF_cpu_results_sigma_zz_last20.png`
- `docs\reports\figures\stageF_cpu_results_sigma_vm_p95_last20.png`
- `docs\reports\figures\stageF_cpu_results_delta_sigma_vm_last20.png`

## Files

- `docs/reports/stageF_cpu_results_eps0000_sigma_profile.csv`
- `docs/reports/stageF_cpu_results_eps00194_sigma_profile.csv`
- `docs/reports/stageF_cpu_results_delta_sigma_profile.csv`
- `docs/reports/stageF_cpu_results_sigma_summary.json`
