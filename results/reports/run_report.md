# Отчёт по MD-каркасу Al / Fe4Al13

## 1. Краткий итог

| Блок | Статус |
|---|---|
| Baseline чистого Al | пройден |
| OVITO | `/Applications/Ovito.app` найден; Python module `ovito` недоступен |
| Структура Fe4Al13 | найдена в COD и сконвертирована |
| Al-Fe потенциал | найден и подключён MEAM Jelinek 2012 |
| Standalone Fe4Al13 | sanity-run пройден |
| Интерфейс | `trial_001` прошёл minimization, unloaded NVT, time-averaged stress, warning-pair и contact-density checks |
| Loading design | force table и TEMPLATE ONLY inputs подготовлены |
| First stress sanity runs | 0 MPa control и 60 MPa compression ramp запущены и проанализированы |
| 120 MPa сценарий | compression-ramp выполнен и принят как controlled sanity-run |

## 2. Окружение

- OS: macOS 26.2, build 25C56
- Conda env: `alfe-md` at `/opt/anaconda3/envs/alfe-md`
- Python: `/opt/anaconda3/envs/alfe-md/bin/python`, Python 3.11.15
- LAMMPS: `/opt/anaconda3/envs/alfe-md/bin/lmp`, 29 Aug 2024
- ASE: 3.28.0
- pymatgen: 2026.5.4
- OVITO Basic GUI app: `/Applications/Ovito.app`
- OVITO conda package: не найден в `conda list ovito`
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

Текущий статус:

- `/Applications/Ovito.app` найден; пользователь подтвердил, что OVITO Basic for macOS Intel открывает визуальную проверку.
- `conda list ovito` не показывает установленный conda package.
- `which ovito` в shell не находит CLI.
- Python module `ovito` не импортируется.

Проверка dump выполнена fallback-скриптом `analysis/python/check_lammpstrj.py`:

- Al dump: 50 frames, 4000 atoms/frame
- Fe4Al13 dump: 51 frames, 102 atoms/frame

Вывод: визуальная проверка теперь возможна через `/Applications/Ovito.app`, но автоматический OVITO Python/CLI analysis в conda env всё ещё недоступен.

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

Unloaded baseline был зафиксирован до controlled loading. Позже отдельно выполнены 0 MPa, 60 MPa и 120 MPa controlled sanity-runs без NPT.

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

Contact-density check for visible OVITO gaps:

- Script: `analysis/python/check_interface_contact_density.py`
- JSON: `lammps/02_interface_relax/trial_001/interface_contact_density_report.json`
- z-density table: `results/tables/interface_trial_001_contact_density_z_profile.csv`
- z-density figure: `results/figures/interface_trial_001_contact_density_z_profile.png`
- Report: `docs/interface_trial_001_contact_density_check.md`

Result:

- Interface window: z = 40.16445 +/- 8 A
- Atoms near interface: 42 Al_slab, 52 Fe4Al13_slab
- Minimum cross-slab distance: 2.59247 A
- Mean of 10 smallest cross-slab distances: 2.66203 A
- Cross-slab pairs within 2.8 / 3.0 / 3.5 A: 20 / 33 / 48
- Largest empty z-gap between occupied bins: 1.0 A, not intersecting the interface window
- Empty 1 A bins inside interface window: 2
- Al-side density drop vs bulk-like Al: 38.99%; Fe4Al13-side density drop: 3.05%

Loading design prepared earlier:

- Script: `analysis/python/calculate_interface_loading_force.py`
- Force table: `results/tables/interface_trial_001_loading_force_table.csv`
- Design doc: `docs/interface_trial_001_loading_design.md`
- Templates:
  - `lammps/03_interface_stress/stress_000mpa/in.interface_stress_template`
  - `lammps/03_interface_stress/stress_060mpa/in.interface_stress_template`
  - `lammps/03_interface_stress/stress_120mpa/in.interface_stress_template`
  - `lammps/03_interface_stress/stress_147mpa/in.interface_stress_template`
  - `lammps/03_interface_stress/stress_200mpa/in.interface_stress_template`

Loading design numbers:

- Target region: Fe4Al13_slab near interface, z = 40.16445..48.16445 A
- Monitor region: Al_slab near interface, z = 32.16445..40.16445 A
- Target atoms: 52 (40 Al type 1, 12 Fe type 2)
- Monitor atoms: 42
- Interface area: 102.15691288528764 A^2 = 1.0215691288528763 nm^2
- 120 MPa force used in controlled sanity-run: F_total = 1.2258829546234515e-10 N, F_atom = 2.3574672204297145e-12 N = 0.0014714153049055854 eV/A
- 147 MPa force used in controlled sanity-run: F_total = 1.5017066194137282e-10 N, F_atom = 2.8878973450264004e-12 N = 0.001802483748509342 eV/A

First controlled stress sanity runs:

- Report: `docs/interface_trial_001_stress_000_060mpa_check.md`
- Comparison table: `results/tables/interface_trial_001_stress_000_060mpa_comparison.csv`
- 0 MPa input: `lammps/03_interface_stress/stress_000mpa/run_001_control/in.interface_stress_000mpa_control`
- 0 MPa log: `lammps/03_interface_stress/stress_000mpa/run_001_control/log.interface_stress_000mpa_control.lammps`
- 60 MPa input: `lammps/03_interface_stress/stress_060mpa/run_001_compression_ramp/in.interface_stress_060mpa_compression_ramp`
- 60 MPa log: `lammps/03_interface_stress/stress_060mpa/run_001_compression_ramp/log.interface_stress_060mpa_compression_ramp.lammps`

Setup:

- fixed bottom support: lowest 4 A of Al slab, 28 atoms
- mobile atoms: 590
- NVT applied only to mobile atoms
- NPT not used
- 0 MPa control: no `fix addforce`, 5000 steps
- 60 MPa: compression toward Al side, `F_atom = -0.0007357076524527927 eV/A`, 2000-step ramp + 8000-step hold
- 120 MPa: compression toward Al side, `F_atom = -0.0014714153049055854 eV/A`, 5000-step ramp + 10000-step hold
- 147 MPa: compression toward Al side, `F_atom = -0.001802483748509342 eV/A`, 5000-step ramp + 10000-step hold

Results:

- 0 MPa: no `ERROR/nan/lost atoms`, `Dangerous builds = 0`, final mobile T = 303.74875 K, last-20 mean mobile T = 302.899688 K
- 60 MPa: no `ERROR/nan/lost atoms`, `Dangerous builds = 0/0`, final mobile T = 302.08918 K, last-20 mean mobile T = 297.7903305 K
- 120 MPa: no `ERROR/nan/lost atoms`, `Dangerous builds = 0/0`, final mobile T = 293.65646 K, last-20 mean mobile T = 297.48696 K
- 147 MPa: no `ERROR/nan/lost atoms`, `Dangerous builds = 0/0`, final mobile T = 294.48127 K, last-20 mean mobile T = 302.107156 K
- 0 MPa distance check: min Al-Fe = 2.12986 A, pairs < 1.8 A = 0, Al-Fe pairs < 2.1 A = 0
- 60 MPa distance check: min Al-Fe = 2.03014 A, pairs < 1.8 A = 0, Al-Fe pairs < 2.1 A = 1, cross-slab Al-Fe pairs < 2.1 A = 0
- 120 MPa distance check: min Al-Fe = 2.02326 A, min cross-slab Al-Fe = 2.55695 A, pairs < 1.8 A = 0, cross-slab Al-Fe pairs < 2.1 A = 0
- 147 MPa distance check: min Al-Fe = 2.02418 A, min cross-slab Al-Fe = 2.59304 A, pairs < 1.8 A = 0, cross-slab Al-Fe pairs < 2.1 A = 0
- 60 MPa warning pair: atoms 232-260, internal Fe4Al13, min/max/mean over frames = 1.95964 / 2.24931 / 2.08611 A, frames < 1.8 A = 0
- 120 MPa warning pair: atoms 232-260, internal Fe4Al13, min/max/mean over frames = 1.97567 / 2.20526 / 2.07879 A, frames < 1.8 A = 0, monotonic collapse = false
- 147 MPa warning pair: atoms 232-260, internal Fe4Al13, min/max/mean over frames = 1.95615 / 2.21681 / 2.07316 A, frames < 1.8 A = 0, monotonic collapse = false

120/147 MPa outputs:

- Check doc: `docs/interface_trial_001_stress_120mpa_check.md`
- Comparison table: `results/tables/interface_trial_001_stress_000_060_120mpa_comparison.csv`
- Input/log folder: `lammps/03_interface_stress/stress_120mpa/run_001_compression_ramp/`
- Stress profile: `results/tables/interface_trial_001_stress_120mpa_compression_ramp_stress_profile.csv`
- Warning-pair trace: `results/tables/interface_trial_001_stress_120mpa_warning_pair_distance_over_time.csv`
- 147 MPa check doc: `docs/interface_trial_001_stress_147mpa_check.md`
- 147 MPa comparison table: `results/tables/interface_trial_001_stress_000_060_120_147mpa_comparison.csv`
- 147 MPa input/log folder: `lammps/03_interface_stress/stress_147mpa/run_001_compression_ramp/`
- 147 MPa stress profile: `results/tables/interface_trial_001_stress_147mpa_compression_ramp_stress_profile.csv`
- 147 MPa warning-pair trace: `results/tables/interface_trial_001_stress_147mpa_warning_pair_distance_over_time.csv`

## Interface trial_001 — controlled loading status

| Scenario | Status | Key result | Verdict |
|---|---|---|---|
| 0 MPa control | completed | no numerical catastrophe | baseline passed |
| 60 MPa compression-ramp | completed | no hard overlaps, no interface detachment, warning pair internal | sanity-run passed |
| 120 MPa compression-ramp | completed | no hard overlaps, no cross-slab Al-Fe <2.1 A, warning pair internal | sanity-run passed |
| 147 MPa compression-ramp | completed | no script-level stop conditions, warning pair internal, OVITO review passed | sanity-run passed |
| 200 MPa | not run | intentionally blocked until explicit decision | pending |

### 147 MPa conclusion

147 MPa compression-ramp is accepted as a controlled sanity-run after manual OVITO review, not as final physical validation.

The main remaining caveat is that the highest absolute hydrostatic proxy still appears near the fixed-bottom support, indicating a boundary-condition artifact.

Manual OVITO review of frames 0, 50, 100, and 150 passed: pair 232-260 remains inside the Fe4Al13 slab, no visible monotonic collapse, no visible interface detachment, no empty interface gap, no whole-block drift, and no atom ejection. Red atoms in the screenshots are selection/coloring markers, not a stress-map and not automatically defects.

Вывод: `trial_001` выдержал longer unloaded NVT и получил time-averaged unloaded stress baseline. Contact-density check показывает, что видимые OVITO gaps не похожи на большой физический interface void. 0 MPa control, 60 MPa, 120 MPa и 147 MPa compression ramp пройдены как controlled sanity-runs. Предупреждающая Al-Fe пара 232-260 остаётся внутренним контактом Fe4Al13, а не контактом через интерфейс. Это всё ещё не физически валидированная межфазная граница.

## 9. Риски

- Потенциал: MEAM Jelinek 2012 содержит Al-Fe cross-interactions и прошёл sanity-run, но не является автоматически валидированным именно для Al13Fe4/Al interface.
- Структура: COD CIF 2024 года корректно парсится как Al78Fe24, но нужно визуально проверить геометрию в установленном OVITO Basic.
- Размер: 102 атома для Fe4Al13 слишком мало для выводов о дефектах, дислокациях или статистике давления.
- Окружение: pyenv/conda конфликт остаётся, рабочий фикс через PATH обязателен.
- OVITO: `/Applications/Ovito.app` найден и пригоден для ручной визуальной проверки; Python module/CLI в conda env отсутствуют.
- LAMMPS process: после записи `Total wall time` для Fe4Al13 процесс не вернулся в shell и был остановлен сигналом; файлы расчёта записаны.
- Интерфейс: `trial_001` имеет большой triclinic skew warning; после long NVT fixed-box pressure остаётся отрицательным в среднем около -4308 bar. После 20000 steps есть один внутренний Al-Fe warning pair ниже 2.1 A: он не cross-slab, не падает ниже 1.8 A и не показывает монотонного схлопывания. Contact-density check не нашёл большого interface void, но Al-side density near interface проседает относительно bulk-like Al и требует визуального контроля.
- Loading design: 0/60/120/147 MPa реализованы как отдельные controlled runs; 200 MPa template остаётся только подготовленным и не запускался.
- Stress sanity: 147 MPa сохраняет внутренний warning pair 232-260 в Fe4Al13; он не cross-slab и не hard-overlap. Manual OVITO review passed, but 200 MPa still requires a separate explicit decision.
- Boundary artifact: максимум абсолютного hydrostatic proxy для 147 MPa находится в fixed-bottom support bin z=5..10 A, а не в interface bin; stress/atom остаётся сравнительным virial proxy.

## 10. Следующие шаги

1. Решить, нужен ли 200 MPa научно, или лучше остановиться и оформлять результаты 0/60/120/147 MPa.
2. Если 200 MPa всё-таки нужен, запускать только как отдельный controlled run, не batch-режимом.
3. Перед higher-load run сохранить 147 MPa как reference/checkpoint и не перезаписывать unloaded, 0 MPa, 60 MPa, 120 MPa или 147 MPa outputs.
