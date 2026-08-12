# Stage E4 700k: полный анализ финального расчета Al + Fe4Al13

Дата отчета: 2026-06-28

700k run root: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_700k_dxa_confirm\20260625-102200`

Задача: проверить, подтверждается ли дислокационный сигнал на увеличенной системе Al + Fe4Al13 при деформации включения по оси Z, `eps_z = 0.001942`.

## Краткий вывод

Расчет 700k завершен штатно: production дошел до `80000/80000` шагов, `production_returncode = 0`, post-processing завершен, финальные `dump.final.lammpstrj`, `data.final` и `restart.80000` присутствуют. Фактический размер системы `710216` атомов, из них `681763` атома в алюминиевой матрице и `28453` атома во включении.

Температура стабильна: финальная `288.38079 K`, максимум `292.46617 K`, что далеко ниже sanity stop `1000 K`. CUDA/LAMMPS аварий по готовым статусам и stderr-файлам не найдено; все восемь production-чанков завершились успешно с первой попытки.

Главный физический результат: финальный DXA для 700k не нашел дислокационных сегментов (`0` сегментов, `0.0 Å` суммарной длины). При этом локальная дефектная зона у интерфейса сохраняется: в CNA `7889` OTHER-атомов в матрице (`1.157%`) и только `3` HCP-атома (`0.0004%`). Дефектность почти полностью сосредоточена у интерфейса 0-5 Å и на малых cap-областях вдоль оси Z; в объеме матрицы признаков устойчивой дислокационной линии или развитой пластической зоны нет.

Сравнение с 510k важно: 510k physical eps001942 давал один короткий DXA-сегмент `1/6<112>` длиной `8.47 Å`, а control eps0 давал `0` сегментов. 700k не воспроизвел этот сегмент в финальном кадре, поэтому лучшая интерпретация - система находится на пороге зарождения, а дислокационный сигнал может быть короткоживущим или чувствительным к размеру, времени и порогам распознавания.

## Что проверяли

Проверялась однородная алюминиевая матрица с одним включением Fe4Al13. Деформация включения по Z (`eps_z = 0.001942`) используется как механический эквивалент магнитострикционного воздействия: включение передает напряжение на матрицу, а основной интерес представляет интерфейс Fe4Al13/Al.

Цель проверки: понять, формируется ли дислокация или устойчивая пластическая зона около интерфейса на системе крупнее 250k/510k.

Термины в отчете:

- DXA: анализ дислокаций по атомной конфигурации.
- CNA: анализ локального кристаллического окружения.
- PTM: сопоставление локальной атомной структуры с шаблонами кристаллических решеток.
- HCP: атомы с локальным окружением, характерным для гексагональной плотноупакованной структуры.
- OTHER: атомы с нераспознанным или дефектным локальным окружением.
- von Mises: эквивалентное напряжение по Мизесу.

## Корректность расчета 700k

| Показатель | Значение |
| --- | ---: |
| Stage | `E4_700k_dxa_confirm` |
| Case | `E4_phys001942_700k_80k` |
| Target atoms | `700000` |
| Actual atoms | `710216` |
| Matrix atoms | `681763` |
| Inclusion atoms | `28453` |
| Box, A | `198.45 x 198.45 x 299.7` |
| Box, nm | `19.845 x 19.845 x 29.97` |
| eps_z | `0.001942` |
| Production steps | `80000/80000` |
| Smoke return code | `0` |
| Production return code | `0` |
| Analysis status | `analysis_completed` |
| Final temperature, K | `288.38079` |
| Max temperature, K | `292.46617` |
| Final global pressure, bar | `8895.0734` |
| Final global pressure, MPa | `889.50734` |
| Final Pzz, bar | `9474.1953` |
| Final Pzz, MPa | `947.41953` |
| Production wall time, s | `198999.949` |
| Production wall time, h | `55.28` |
| Timesteps/s | `0.402` |
| GPU/runtime | LAMMPS KOKKOS CUDA, RTX 3060 |
| Neighbor workaround | `neigh_modify delay 0 every 10 check no` |

Финальные выходы присутствуют:

| Файл | Наличие | Размер |
| --- | --- | ---: |
| `production\dump.final.lammpstrj` | есть | `63725206` bytes |
| `production\data.final` | есть | `95550646` bytes |
| `production\restart.80000` | есть | `62500038` bytes |
| `production\analysis.json` | есть | `29728` bytes |

Проверка production-чанков:

| Chunk | Attempt | Status | Exit | Step | Wall s | t/s | Restart |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `0000000_0010000` | 1 | success | 0 | 10000 | 24992.786 | 0.400 | yes |
| `0010000_0020000` | 1 | success | 0 | 20000 | 24953.307 | 0.401 | yes |
| `0020000_0030000` | 1 | success | 0 | 30000 | 24958.931 | 0.401 | yes |
| `0030000_0040000` | 1 | success | 0 | 40000 | 24862.922 | 0.402 | yes |
| `0040000_0050000` | 1 | success | 0 | 50000 | 24861.053 | 0.402 | yes |
| `0050000_0060000` | 1 | success | 0 | 60000 | 24670.328 | 0.405 | yes |
| `0060000_0070000` | 1 | success | 0 | 70000 | 24828.152 | 0.403 | yes |
| `0070000_0080000` | 1 | success | 0 | 80000 | 24872.342 | 0.402 | yes |

Watchdog/recovery events: none. `resumed_from_restart_step = None`.

Live process scan перед отчетом не показал активного LAMMPS или production runner для `stageE_700k_dxa_confirm`. Поле `active_processes` в старом status JSON содержит исторический worker PID, но актуальный process scan показал только саму проверочную PowerShell-команду.

## Главные численные результаты 700k

### Базовые числа

| Метрика | Значение |
| --- | ---: |
| Actual atoms | `710216` |
| Matrix atoms | `681763` |
| Inclusion atoms | `28453` |
| Cell volume, A^3 | `11802906.02925` |
| Mean atomic volume, A^3 | `16.618755` |
| Final step | `80000` |
| Max temperature, K | `292.46617` |
| Final temperature, K | `288.38079` |
| Final global pressure, MPa | `889.50734` |
| Disk free C:, GiB | `28.019` |
| Disk free B:, GiB | `254.34` |

### Структура матрицы

| Метод | FCC atoms | FCC % | HCP atoms | HCP % | OTHER atoms | OTHER % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CNA | 673871 | 98.8420 | 3 | 0.0004 | 7889 | 1.1570 |
| PTM | 674374 | 98.9162 | 5 | 0.0007 | 7384 | 1.0831 |

HCP-сигнал крайне мал: `3` CNA HCP-атома в матрице, `3` отдельных HCP-кластера по одному атому. Это не похоже на устойчивую stacking-fault plane. OTHER-сигнал образует один доминирующий кластер: `7883` атома из `7889`, что соответствует интерфейсной дефектной оболочке.

### Дислокационный анализ

| Метрика DXA | Значение |
| --- | ---: |
| Dislocation segments | `0` |
| Total line length, A | `0.0` |
| Dislocation density, m^-2 | `0.0` |
| Burgers `1/6<112>` length, A | `0.0` |
| Burgers `1/2<110>` length, A | `0.0` |
| Burgers other length, A | `0.0` |

Интерпретация DXA: финальный 700k кадр не подтверждает дислокационный сегмент. Это не отменяет локального механического отклика интерфейса, но не дает основания считать устойчивую дислокационную линию или сетку установленной.

### Дефектная зона

| Метрика | Значение |
| --- | ---: |
| Matrix defect atoms total | `7892` |
| Defect atoms beyond 1.3 shell | `6` |
| HCP atoms beyond 1.3 shell | `0` |
| Max normalized ellipsoid distance | `2.8475739493` |
| Median normalized ellipsoid distance | `1.03334290598` |

Нормированная дистанция `1.0` соответствует интерфейсной оболочке включения. Медиана `1.0333` показывает, что дефекты главным образом сидят на интерфейсе. `6` OTHER-атомов за пределами `1.3` shell - это слабый дальний хвост, но не развитая пластическая зона.

## Радиальный профиль от интерфейса

Локальные напряжения ниже являются proxy по вириальному тензору LAMMPS `c_st[1..6]`: `-sum(c_st)/estimated_zone_volume`, `1 bar = 0.1 MPa`. Абсолютные MPa приближенные; надежнее сравнивать зоны между собой.

| Shell from interface, A | Atoms | HCP | OTHER | HCP % | OTHER % | Pzz MPa | von Mises MPa |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0-5 | 5478 | 2 | 5286 | 0.0365 | 96.4951 | -837.653 | 404.408 |
| 5-15 | 23000 | 1 | 2597 | 0.0043 | 11.2913 | 810.577 | 41.476 |
| 15-30 | 51974 | 0 | 0 | 0.0000 | 0.0000 | 1087.763 | 44.843 |
| >30 | 601311 | 0 | 6 | 0.0000 | 0.0010 | 914.032 | 18.369 |

Вывод по радиальному профилю: максимальная дефектность находится в оболочке `0-5 Å` от интерфейса, где OTHER `96.4951%` и von Mises proxy `404.408 MPa`. На `5-15 Å` дефектность резко падает до `11.2913%`, а после `15 Å` практически исчезает. Это интерфейсная локализация, а не распространение пластики в объем матрицы.

## Профиль вдоль оси Z

На оси Z наиболее информативны cap-области около концов включения. Полная серия содержит много пустых бинов внутри объема включения; ниже дана выжимка по дефектным и высоконапряженным областям.

| z_rel range, A | Atoms | HCP | OTHER | OTHER % | Pzz MPa | von Mises MPa | Комментарий |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| -80..-70 | 511 | 0 | 209 | 40.9002 | -99.231 | 609.535 | нижний cap, дефектная оболочка |
| -70..-60 | 45 | 0 | 45 | 100.0000 | -616.570 | 2176.648 | нижний пик von Mises на малой группе |
| 60..70 | 48 | 0 | 48 | 100.0000 | 317.585 | 2744.166 | верхний пик von Mises на малой группе |
| 70..80 | 513 | 0 | 207 | 40.3509 | -184.538 | 527.736 | верхний cap, дефектная оболочка |

Максимумы напряжения совпадают с малыми дефектными cap-областями на концах включения. Это согласуется с передачей напряжения от включения на матрицу, но дефектные области остаются локальными.

## Сравнение с 250k baseline

Baseline: `runs\stageE_250k_single_physical_longrun\20260623-205439`

250k расчет завершен: `254055` атомов, `120000/120000` шагов, `production_returncode = 0`, max temp `291.552 K`. Финальный DXA: `0` сегментов, `0.0 Å`. CNA: FCC `239404` (`98.25%`), HCP `7` (`0.0029%`), OTHER `4258` (`1.747%`).

Радиальный профиль 250k:

| Shell A | Atoms | HCP | OTHER | Pzz MPa | von Mises MPa |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0-5 | 3005 | 6 | 2894 | -582.896 | 368.194 |
| 5-15 | 13531 | 1 | 1362 | 837.326 | 57.388 |
| 15-30 | 33965 | 0 | 0 | 914.985 | 87.474 |
| >30 | 193168 | 0 | 2 | 875.171 | 16.174 |

Вывод по 250k: локальная интерфейсная перестройка есть, но DXA-сегментов нет. Дефектность максимум в `0-5 Å`, в дальней матрице почти отсутствует.

## Сравнение с 510k baseline

Baseline: `runs\stageE_homogeneous_inclusion_scaleup_v2\20260622-224433`

510k v2 расчет завершен: `510375` атомов, physical eps001942 дошел до `10000/10000` шагов, max temp `291.98355 K`, production status completed. Control eps0 подтвержден файлами и имел `0` DXA-сегментов.

Физический case eps001942 дал:

| Метрика | Значение |
| --- | ---: |
| DXA segments | `1` |
| Total line length, A | `8.47` |
| Burgers | `1/6<112>` |
| Burgers length, A | `8.470555` |
| Dislocation density, m^-2 | `9.979240393274844e13` |
| CNA HCP atoms | `12` |
| CNA OTHER atoms | `6079` |
| Defect atoms beyond 1.3 shell | `0` |
| Interface 0-5 Å von Mises, MPa | `220.807` |

Вывод по 510k: короткий зародыш частичной дислокации был зафиксирован только в physical eps001942, при control eps0 сегментов не было. Но это был короткий локальный сигнал, не развитая сеть и не доказательство распространенной пластической зоны.

## Итоговая сравнительная таблица

| Run | Actual atoms | Steps | eps_z | Max temp K | DXA segments | Total line A | Burgers | Defect localization | Conclusion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| 250k longrun | 254055 | 120000 | 0.001942 | 291.552 | 0 | 0.0 | none | interface 0-5 Å; far matrix nearly clean | локальная интерфейсная перестройка без DXA-сегмента |
| 510k v2 physical | 510375 | 10000 | 0.001942 | 291.98355 | 1 | 8.47 | `1/6<112>` | interface-local; no developed matrix plasticity | короткий зародыш частичной дислокации |
| 700k E4 | 710216 | 80000 | 0.001942 | 292.46617 | 0 | 0.0 | none | interface 0-5 Å and small Z-cap hotspots | пороговое локальное состояние; финальный DXA-сегмент не подтвержден |

## Физическая интерпретация

Напряжение от включения действительно передается в матрицу: радиальный профиль 700k показывает сильный контраст между интерфейсной оболочкой `0-5 Å` и дальней матрицей, а Z-профиль показывает cap-hotspots на концах включения. Главный риск и физический интерес остается на интерфейсе Fe4Al13/Al.

700k не дал финального DXA-сегмента. Поэтому 510k-сегмент нельзя считать устойчиво воспроизведенным в финальном состоянии увеличенной системы. Более аккуратная интерпретация: система находится около порога зарождения; сегмент может быть transient, чувствительным к размеру, времени релаксации, температурной траектории или порогам DXA.

Данные 700k усиливают вывод о локальном интерфейсном механическом отклике, но не подтверждают устойчивую дислокационную линию/сеть. Развитая пластическая зона считается установленной только при устойчивой линии или сети и распространении дефектов в матрицу; здесь этого нет.

## Что следует из данных

- 700k production и анализ завершены корректно.
- Система оставалась термически стабильной, перегрева нет.
- Финальный 700k DXA не нашел дислокационных сегментов.
- Интерфейсная дефектная оболочка выражена сильно: OTHER `96.4951%` в `0-5 Å`.
- Дефекты резко убывают с расстоянием от интерфейса.
- В дальней матрице `>30 Å` остается только `6` OTHER-атомов и `0` HCP-атомов.
- Z-cap hotspots совпадают с малыми дефектными областями на концах включения.
- 510k physical eps001942 остается единственным расчетом из трех, где финальный DXA зафиксировал короткий `1/6<112>` сегмент.

## Что не следует утверждать

- Нельзя утверждать наличие устойчивой развитой пластической зоны.
- Нельзя утверждать макроскопическое разрушение или объемное распространение дефектов.
- Нельзя утверждать универсальность результата для всех геометрий, параметров eps_z, температурных траекторий и размеров.
- Нельзя считать отсутствие финального 700k DXA-сегмента доказательством отсутствия эффекта: данные совместимы с пороговым или transient-сигналом.

## Ограничения

- Локальные напряжения рассчитаны как virial proxy и имеют приближенную абсолютную шкалу.
- DXA/CNA/PTM чувствительны к порогам распознавания, размеру системы, времени и температурной истории.
- Один короткий сегмент в 510k был слабым, но важным сигналом; 700k показывает, что его устойчивость требует проверки по промежуточным кадрам.
- В 700k анализировался финальный кадр; transient-сегменты между `10000` и `80000` шагами могли появляться и исчезать.

## Рекомендации

- Не запускать новый MD сразу. Следующий шаг - анализ промежуточных dump-кадров `10k/20k/.../80k` только post-processing-ом, без нового production.
- Если промежуточные кадры покажут кратковременный DXA-сегмент, зафиксировать момент появления/исчезновения и сравнить с Z-cap hotspots.
- Если промежуточные кадры также не покажут сегменты, трактовать серию как локальный интерфейсный отклик на пороге зарождения.
- Следующий MD-расчет запускать только после ручного решения пользователя.
- Не делать full factorial / grid sweep без отдельного обсуждения.

## Приложение: использованные файлы

Ключевые 700k файлы:

- `runs\stageE_700k_dxa_confirm\20260625-102200\stageE_700k_final_summary.json`
- `runs\stageE_700k_dxa_confirm\20260625-102200\stageE_700k_dxa_confirm_status.json`
- `runs\stageE_700k_dxa_confirm\20260625-102200\cases\E4_700k_dxa_confirm\E4_phys001942_700k_80k\production\analysis.json`
- `runs\stageE_700k_dxa_confirm\20260625-102200\production_summary.csv`
- `runs\stageE_700k_dxa_confirm\20260625-102200\tables\defect_summary.csv`
- `runs\stageE_700k_dxa_confirm\20260625-102200\tables\runtime_summary.csv`
- `runs\stageE_700k_dxa_confirm\20260625-102200\hang_recovery_report.md`
- `runs\stageE_700k_dxa_confirm\20260625-102200\summaries\E4_700k_dxa_confirm_report.md`
- `runs\stageE_700k_dxa_confirm\20260625-102200\summaries\E4_700k_dxa_confirm_gate_report.md`

Baseline 250k:

- `runs\stageE_250k_single_physical_longrun\20260623-205439\stageE_250k_final_summary.json`
- `runs\stageE_250k_single_physical_longrun\20260623-205439\stageE_250k_dxa_summary.md`
- `runs\stageE_250k_single_physical_longrun\20260623-205439\stageE_250k_physics_verdict.md`
- `runs\stageE_250k_single_physical_longrun\20260623-205439\stageE_250k_stress_transfer_report.md`
- `runs\stageE_250k_single_physical_longrun\20260623-205439\cases\E3_250k_longrun\E3_phys001942_250k_120k\production\analysis.json`

Baseline 510k:

- `runs\stageE_homogeneous_inclusion_scaleup_v2\20260622-224433\stageE_v2_analysis_summary.json`
- `runs\stageE_homogeneous_inclusion_scaleup_v2\20260622-224433\stageE_v2_boundary_dislocation_report.md`
- `runs\stageE_homogeneous_inclusion_scaleup_v2\20260622-224433\stageE_v2_physics_verdict.md`
- `runs\stageE_homogeneous_inclusion_scaleup_v2\20260622-224433\stageE_v2_stress_transfer_report.md`
- `runs\stageE_homogeneous_inclusion_scaleup_v2\20260622-224433\attempts\a500k\cases\E2v2\E2_phys00194\production\analysis.json`
- `runs\stageE_homogeneous_inclusion_scaleup_v2\20260622-224433\attempts\a500k\cases\E2v2\E2_ctl0\production\analysis.json`

## Приложение: dump/restart/data файлы 700k

| Файл | Размер, bytes |
| --- | ---: |
| `prep\dump.a1_baseline_equil.lammpstrj` | 23823169 |
| `prep\dump.E4_phys001942_700k_80k_prep.prep.lammpstrj` | 21335168 |
| `prep\restart.E4_phys001942_700k_80k_prep.final` | 62499914 |
| `production\data.final` | 95550646 |
| `production\dump.chunk0000000_0010000.lammpstrj` | 129272212 |
| `production\dump.chunk0010000_0020000.lammpstrj` | 127453396 |
| `production\dump.chunk0020000_0030000.lammpstrj` | 127449132 |
| `production\dump.chunk0030000_0040000.lammpstrj` | 127450205 |
| `production\dump.chunk0040000_0050000.lammpstrj` | 127449918 |
| `production\dump.chunk0050000_0060000.lammpstrj` | 127450380 |
| `production\dump.chunk0060000_0070000.lammpstrj` | 127449661 |
| `production\dump.chunk0070000_0080000.lammpstrj` | 127449716 |
| `production\dump.final.lammpstrj` | 63725206 |
| `production\restart.10000` | 62500038 |
| `production\restart.20000` | 62500038 |
| `production\restart.30000` | 62500038 |
| `production\restart.40000` | 62500038 |
| `production\restart.50000` | 62500038 |
| `production\restart.60000` | 62500038 |
| `production\restart.70000` | 62500038 |
| `production\restart.80000` | 62500038 |
| `smoke\dump.E4_phys001942_700k_80k_smoke.lammpstrj` | 65541422 |
| `smoke\dump.E4_phys001942_700k_80k_smoke_final.lammpstrj` | 63936952 |

Всего в run root: `117` файлов, `2259981259` bytes (`2.105 GiB`). Удаление raw-файлов в этой задаче не выполнялось.

## Команды для повторной проверки

```powershell
cd C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe
$root = 'C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_700k_dxa_confirm\20260625-102200'
Get-Content -Raw "$root\stageE_700k_final_summary.json"
Get-Content -Raw "$root\cases\E4_700k_dxa_confirm\E4_phys001942_700k_80k\production\analysis.json"
Get-Content -Raw "$root\tables\defect_summary.csv"
Get-Content -Raw "$root\production_summary.csv"
```

Проверка активных процессов:

```powershell
Get-CimInstance Win32_Process |
Where-Object {
  $_.CommandLine -and (
    $_.CommandLine -like '*stageE_700k_dxa_confirm*' -or
    $_.CommandLine -like '*run_stage_sweep.py*' -or
    $_.Name -like 'lmp_kokkos_cuda*'
  )
} |
Select-Object ProcessId, ParentProcessId, Name, CommandLine |
Format-List
```
