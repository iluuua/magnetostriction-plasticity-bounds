# Отчёт по MD-каркасу Al / Fe4Al13

## 1. Краткий итог

| Блок | Статус |
|---|---|
| Baseline чистого Al | пройден |
| OVITO | conda package установлен, GUI/Python module нерабочие |
| Структура Fe4Al13 | найдена в COD и сконвертирована |
| Al-Fe потенциал | найден и подключён MEAM Jelinek 2012 |
| Standalone Fe4Al13 | sanity-run пройден |
| Интерфейс | `trial_001` прошёл minimization, unloaded NVT, time-averaged stress baseline и warning-pair inspection |
| 120 MPa сценарий | не применялся, stress-сценарии не запускались |

## 2. Окружение

- OS: macOS 26.2, build 25C56
- Conda env: `alfe-md` at `/opt/anaconda3/envs/alfe-md`
- Python: `/opt/anaconda3/envs/alfe-md/bin/python`, Python 3.11.15
- LAMMPS: `/opt/anaconda3/envs/alfe-md/bin/lmp`, 29 Aug 2024
- ASE: 3.28.0
- pymatgen: 2026.5.4
- OVITO conda package: 3.14.1
- OVITO Python module: `ModuleNotFoundError: No module named 'ovito'`
- Репозиторный validator `.codex/test-command`: отсутствует; вместо него выполнены `python -m py_compile analysis/python/*.py`, оба `parse_lammps_log.py` summary и чтение dump fallback-скриптом.

Рабочий shell-префикс:

```bash
cd /Users/ilua/Documents/ilua-system/projects/physics_md_al_fe
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate alfe-md
export PATH="/opt/anaconda3/envs/alfe-md/bin:$PATH"
rehash
```

## 3. Проверка чистого Al

- Input: `lammps/00_relax_al/in.relax_al_box`
- Структура: `structures/converted/Al/al_fcc.data`
- Потенциал: `potentials/eam/Al_zhou.eam.alloy`
- Атомов: 4000
- Команда анализа: `python analysis/python/parse_lammps_log.py lammps/00_relax_al/log.lammps --output lammps/00_relax_al/log_summary_al.json`

Ключевые результаты:

- Начальное давление: 23601.197 bar
- После `box/relax`: -0.0105 bar, L=40.816549 A
- NPT: 300 K / 0 bar, 5000 steps
- Финал NPT: T=293.998 K, P=433.669 bar, L=41.124818 A
- Среднее давление по последним 20 thermo-точкам: 78.488 bar
- `Dangerous builds = 0`, lost atoms нет, `ERROR/nan` нет

Вывод: baseline Al пройден.

## 4. OVITO

Команда установки:

```bash
conda install -c conda-forge ovito -y
```

Первый запуск упал из-за повреждённого conda cache; после `conda clean --packages -y` установка завершилась. `which ovito` указывает на `/opt/anaconda3/envs/alfe-md/bin/ovito`.

Проблемы:

- `ovito --help` падает с `dyld: Symbol not found ... Gui.so`.
- Python module `ovito` не импортируется.

Проверка dump выполнена fallback-скриптом `analysis/python/check_lammpstrj.py`:

- Al dump: 50 frames, 4000 atoms/frame
- Fe4Al13 dump: 51 frames, 102 atoms/frame

Вывод: dump-файлы есть и читаются на уровне LAMMPS headers, но OVITO GUI/Python пока нельзя считать рабочими.

## 5. Структура Fe4Al13

- Источник: COD `1571554`, `https://www.crystallography.net/cod/1571554.cif`
- Локальный CIF: `structures/raw/Al13Fe4/al13fe4.cif`
- POSCAR: `structures/raw/Al13Fe4/POSCAR`
- Конвертер: `analysis/python/convert_al13fe4_to_lammps.py`
- LAMMPS data: `structures/converted/Al13Fe4/al13fe4.data`
- Metadata: `structures/converted/Al13Fe4/al13fe4_metadata.json`

Параметры:

- Формула: Al13Fe4
- Полная ячейка: Al78 Fe24
- Атомов: 102
- C2/m, IT 12
- a=15.498 A, b=8.0814 A, c=12.488 A, beta=107.79 deg
- Типы LAMMPS: Al=1, Fe=2

## 6. Потенциал Al-Fe

Проверены источники NIST IPR и OpenKIM. Выбран baseline-кандидат:

- Jelinek, Groh, Horstemeyer et al. 2012 MEAM
- DOI: `10.1103/PhysRevB.85.245102`
- Локальные файлы:
  - `potentials/meam/Jelinek_2012/Jelinek_2012_meamf`
  - `potentials/meam/Jelinek_2012/Jelinek_2012_meam.alsimgcufe`

LAMMPS поддерживает `pair_style meam`. Использованный `pair_coeff`:

```lammps
pair_coeff * * ../../potentials/meam/Jelinek_2012/Jelinek_2012_meamf AlS SiS MgS CuS FeS ../../potentials/meam/Jelinek_2012/Jelinek_2012_meam.alsimgcufe AlS FeS
```

Ограничение: это baseline-кандидат. Он запустился и не разрушил Fe4Al13 в sanity-run, но для научного результата ещё нужна валидация свойств Fe4Al13 и интерфейса.

## 7. Проверка Fe4Al13

- Input: `lammps/01_relax_al13fe4/in.relax_al13fe4`
- Финальный log: `lammps/01_relax_al13fe4/log.lammps`
- JSON summary: `lammps/01_relax_al13fe4/log_summary_al13fe4.json`
- 1000-step trial сохранён в `lammps/01_relax_al13fe4/trial_1000/`

Ключевые результаты:

- Начальное давление: 89312.163 bar
- После triclinic `box/relax`: -9.427 bar
- NPT: 300 K / 0 bar, 5000 steps
- Финал NPT: T=308.505 K, P=-61.795 bar, V=1624.405 A^3
- Среднее давление по NPT thermo-точкам: 262.658 bar
- Последние 20 thermo-точек: среднее T=298.750 K, среднее P=293.629 bar
- Мгновенные флуктуации давления: -10101.56 до 10686.799 bar
- `Dangerous builds = 0`, lost atoms нет, `ERROR/nan` нет
- Состав после релаксации: 78 Al, 24 Fe

Вывод: Fe4Al13 standalone sanity-run пройден. Давление сильно флуктуирует из-за малой 102-атомной ячейки, но структура не взорвалась, состав сохранился, box-relax и NPT дошли до конца.

## 8. Интерфейс Al / Fe4Al13

Нагрузка 120 MPa не применялась. Stress-сценарии не запускались.

Сначала выполнен mismatch-анализ:

- Скрипт: `analysis/python/build_flat_interface.py`
- Отчёт: `docs/interface_mismatch_candidates.md`
- Таблица: `results/tables/interface_mismatch_candidates.csv`

Лучший численный кандидат в текущем приближении:

- Al (111) / Fe4Al13 (100)
- max length mismatch: 0.943%
- angle delta: 0.114 deg
- area mismatch: 0.727%
- estimated atoms by heuristic slab filter: 652

На основе этого кандидата собран первый unloaded trial:

- Builder: `analysis/python/build_unloaded_interface_trial.py`
- Data: `structures/interface/flat_interface/trial_001/data.interface_trial`
- Metadata: `structures/interface/flat_interface/trial_001/interface_metadata.json`
- Min-distance report: `structures/interface/flat_interface/trial_001/min_distance_report.json`
- LAMMPS input: `lammps/02_interface_relax/trial_001/in.interface_minimize`
- Log summary: `lammps/02_interface_relax/trial_001/log_summary_interface_trial_001.json`
- Проверка: `docs/interface_trial_001_check.md`

Фактическая система:

- 618 atoms total
- Al type 1: 522
- Fe type 2: 96
- Box: Lx=15.315 A, Ly=6.670 A, Lz=109.211 A, xy=4.003 A
- Minimum Al-Fe distance before minimization: 2.278 A
- Al-Fe pairs below 2.1 A: 0
- Any pairs below hard overlap 1.8 A: 0

LAMMPS minimization:

- 510 steps, stopping criterion = energy tolerance
- PotEng: -2106.9824 -> -2143.9047 eV
- Press: -11429.925 -> -7271.804 bar
- `ERROR/nan/lost atoms`: нет
- `Dangerous builds = 0`
- Output: `lammps/02_interface_relax/trial_001/data.interface_minimized`

Короткий unloaded NVT 300 K:

- Input: `lammps/02_interface_relax/trial_001/in.interface_nvt_300k`
- Preserved minimization log: `lammps/02_interface_relax/trial_001/log.interface_minimize.lammps`
- NVT log: `lammps/02_interface_relax/trial_001/log.interface_nvt_300k.lammps`
- Summary: `lammps/02_interface_relax/trial_001/log_summary_interface_nvt_300k.json`
- Distance report: `lammps/02_interface_relax/trial_001/interface_nvt_300k_distance_report.json`
- Dump summary: `lammps/02_interface_relax/trial_001/dump_summary_interface_nvt_300k.json`
- Проверка: `docs/interface_trial_001_nvt_check.md`

NVT results:

- 5000 steps, NVT 300 K, `boundary p p f`
- `fix addforce`: не использовался
- NPT: не использовался
- 120 MPa: не применялось
- Final T: 300.862 K
- Last-20 mean T: 299.996 K
- Final PotEng: -2120.7239 eV
- Last-20 mean PotEng: -2120.5509 eV
- Final pressure: -6539.318 bar
- Last-20 mean pressure: -5110.945 bar
- `ERROR/nan/lost atoms`: нет
- `Dangerous builds = 0`
- Dump: 51 frames, 618 atoms/frame

Post-NVT distance check:

- Minimum Al-Al distance: 2.495 A
- Minimum Fe-Fe distance: 2.650 A
- Minimum Al-Fe distance: 2.283 A
- Minimum cross-slab distance: 2.535 A
- Minimum cross-slab Al-Fe distance: 2.647 A
- Pairs below 1.8 A: 0
- Al-Fe pairs below 2.1 A: 0

Unloaded local diagnostics:

- LAMMPS input: `lammps/02_interface_relax/trial_001/in.interface_unloaded_diagnostics`
- LAMMPS log: `lammps/02_interface_relax/trial_001/log.interface_unloaded_diagnostics.lammps`
- Stress dump: `lammps/02_interface_relax/trial_001/dump.interface_unloaded_stress_run0.lammpstrj`
- Dump summary: `lammps/02_interface_relax/trial_001/dump_summary_interface_unloaded_diagnostics.json`
- JSON summary: `lammps/02_interface_relax/trial_001/interface_unloaded_diagnostics_summary.json`
- Stress profile: `results/tables/interface_trial_001_unloaded_stress_profile.csv`
- Strain profile: `results/tables/interface_trial_001_unloaded_strain_profile.csv`
- Per-atom table: `results/tables/interface_trial_001_unloaded_atom_diagnostics.csv`
- Figures:
  - `results/figures/interface_trial_001_unloaded_stress_profile.png`
  - `results/figures/interface_trial_001_unloaded_strain_profile.png`
- Проверка: `docs/interface_trial_001_unloaded_diagnostics.md`

Diagnostics method:

- LAMMPS `run 0`, no atom motion
- `compute stress/atom NULL virial`
- z-bin width: 5 A
- interface z estimate: 39.695 A
- stress conversion: `sigma = -sum(stress_atom) / bin_volume`, bar to GPa
- strain proxy: custom single-frame local affine fit from minimized to NVT geometry, not OVITO Atomic Strain

Diagnostics results:

- LAMMPS diagnostics log: no `ERROR/nan/lost atoms`, `Dangerous builds = 0`
- Diagnostic dump: 1 frame, 618 atoms/frame
- Phase hydrostatic proxy: Al slab -1.540 GPa, Fe4Al13 slab -0.711 GPa
- Interface-near hydrostatic proxy:
  - Al-side bin z=37.5 A: -1.978 GPa
  - Fe4Al13-side bin z=42.5 A: -1.248 GPa
- Mean VM strain proxy: Al slab 0.0363, Fe4Al13 slab 0.0839
- Highest mean strain proxy bin: z=87.5 A in Fe4Al13, 0.1293

Longer unloaded NVT and time-averaged stress:

- Input: `lammps/02_interface_relax/trial_001/in.interface_nvt_300k_long_unloaded`
- Log: `lammps/02_interface_relax/trial_001/log.interface_nvt_300k_long.lammps`
- Summary: `lammps/02_interface_relax/trial_001/log_summary_interface_nvt_300k_long.json`
- Final data: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k_long`
- Trajectory dump: `lammps/02_interface_relax/trial_001/dump.interface_nvt_300k_long.lammpstrj`
- Stress dump: `lammps/02_interface_relax/trial_001/dump.interface_nvt_300k_long_stress.lammpstrj`
- Distance report: `lammps/02_interface_relax/trial_001/interface_nvt_300k_long_distance_report.json`
- Time-averaged summary: `lammps/02_interface_relax/trial_001/interface_time_averaged_stress_summary.json`
- Time-averaged stress table: `results/tables/interface_trial_001_time_averaged_stress_profile.csv`
- Time-averaged stress figure: `results/figures/interface_trial_001_time_averaged_stress_profile.png`
- Проверка: `docs/interface_trial_001_time_averaged_stress.md`

Long NVT settings and results:

- 20000 steps were used instead of 50000 because 50000 was estimated at about 11-12 min on the local Mac.
- NVT 300 K, `boundary p p f`
- `fix addforce`: не использовался
- NPT: не использовался
- 120 MPa: не применялось
- `ERROR/nan/lost atoms`: нет
- `Dangerous builds = 0`
- Final T: 294.648 K
- Last-20 mean T: 302.511 K
- Overall mean pressure: -4308.360 bar
- Pressure range: -8975.943 to 124.437 bar
- PotEng drift first-to-last: -2.299 eV
- Trajectory/stress dumps: 21 frames, 618 atoms/frame

Post-long-NVT distance check:

- Minimum Al-Al distance: 2.510 A
- Minimum Fe-Fe distance: 2.609 A
- Minimum Al-Fe distance: 2.027 A
- Minimum cross-slab distance: 2.592 A
- Pairs below 1.8 A: 0
- Al-Fe pairs below 2.1 A: 1
- Cross-slab Al-Fe pairs below 2.1 A: 0

Time-averaged interface-near stress proxy:

- Interface z estimate: 40.164 A
- Al-side bin z=37.5 A: hydrostatic -1.283 +/- 0.727 GPa, sigma_zz -0.877 +/- 0.922 GPa
- Fe4Al13-side bin z=42.5 A: hydrostatic -0.879 +/- 0.519 GPa, sigma_zz -0.012 +/- 1.117 GPa
- Highest absolute hydrostatic mean: Al free-surface-side bin z=7.5 A, -3.466 +/- 0.485 GPa

Warning-pair inspection after long NVT:

- Script: `analysis/python/inspect_warning_pairs.py`
- Report: `docs/interface_trial_001_warning_pairs_check.md`
- JSON: `lammps/02_interface_relax/trial_001/warning_pairs_long_nvt.json`
- Distance table: `results/tables/interface_trial_001_warning_pair_distance_over_time.csv`
- Distance figure: `results/figures/interface_trial_001_warning_pair_distance_over_time.png`
- Neighborhood table: `results/tables/interface_trial_001_warning_pair_neighborhood.csv`

Result:

- Warning pair: atom ids 232-260, Al-Fe, both inside `Fe4Al13_slab`
- Final distance: 2.02695 A
- Distance over 21 frames: min 2.02680 A, max 2.35309 A, mean 2.11698 A
- Frames below 2.1 A: 11 / 21
- Frames below 1.8 A: 0 / 21
- Monotonic collapse: no
- Cross-slab warning pairs below 2.1 A: 0

Вывод: `trial_001` выдержал longer unloaded NVT и получил time-averaged unloaded stress baseline. Предупреждающая Al-Fe пара после long NVT оказалась внутренним контактом Fe4Al13, а не контактом через интерфейс; это monitor-only warning для unloaded baseline, но не разрешение на физически валидированную нагрузку. Это всё ещё не физически валидированная межфазная граница и не основание сразу прикладывать 120 MPa.

## 9. Риски

- Потенциал: MEAM Jelinek 2012 содержит Al-Fe cross-interactions и прошёл sanity-run, но не является автоматически валидированным именно для Al13Fe4/Al interface.
- Структура: COD CIF 2024 года корректно парсится как Al78Fe24, но нужно визуально проверить геометрию после установки рабочей OVITO-среды.
- Размер: 102 атома для Fe4Al13 слишком мало для выводов о дефектах, дислокациях или статистике давления.
- Окружение: pyenv/conda конфликт остаётся, рабочий фикс через PATH обязателен.
- OVITO: conda package установлен, но GUI падает с `dyld`, Python module отсутствует; `/Applications` не содержит OVITO app. Для визуальной проверки нужно отдельно поставить официальный OVITO Basic for macOS.
- LAMMPS process: после записи `Total wall time` для Fe4Al13 процесс не вернулся в shell и был остановлен сигналом; файлы расчёта записаны.
- Интерфейс: `trial_001` имеет большой triclinic skew warning; после long NVT fixed-box pressure остаётся отрицательным в среднем около -4308 bar. После 20000 steps есть один внутренний Al-Fe warning pair ниже 2.1 A: он не cross-slab, не падает ниже 1.8 A и не показывает монотонного схлопывания, но требует визуального контроля/доработки перед любой нагрузкой.

## 10. Следующие шаги

1. Починить OVITO отдельно: поставить официальный `.dmg` или отдельный Python module, затем открыть `dump.al13fe4_npt.lammpstrj`.
2. Визуально проверить long NVT, stress dump и локальную область пары 232-260 в OVITO после починки GUI/Python.
3. При необходимости выполнить дополнительную unloaded refinement/minimization или пересборку геометрии, если визуальная проверка покажет некорректный Fe4Al13-локальный контакт.
4. Только после устойчивого unloaded поведения отдельно проектировать `stress_120mpa`; на текущем шаге 120 MPa не применялось.
