# Проверка standalone Fe4Al13 / Al13Fe4

Дата проверки: 2026-05-09.

## Структура

- Источник: Crystallography Open Database, COD `1571554`
- URL: `https://www.crystallography.net/cod/1571554.cif`
- Локальный CIF: `structures/raw/Al13Fe4/al13fe4.cif`
- POSCAR-копия: `structures/raw/Al13Fe4/POSCAR`
- LAMMPS data: `structures/converted/Al13Fe4/al13fe4.data`
- Metadata: `structures/converted/Al13Fe4/al13fe4_metadata.json`
- Формула после парсинга: Al13Fe4
- Полная ячейка: Al78 Fe24, 102 атома
- Пространственная группа из CIF: C2/m, IT 12
- Параметры исходной ячейки: a=15.498 A, b=8.0814 A, c=12.488 A, beta=107.79 deg, V=1489.277 A^3
- LAMMPS atom types: Al = 1, Fe = 2

## Потенциал

- Потенциал: Jelinek / Groh / Horstemeyer et al. 2012 MEAM
- Источник: NIST IPR / OpenKIM
- Локальные файлы:
  - `potentials/meam/Jelinek_2012/Jelinek_2012_meamf`
  - `potentials/meam/Jelinek_2012/Jelinek_2012_meam.alsimgcufe`
- `pair_style`: `meam`
- `pair_coeff`:

```lammps
pair_coeff * * ../../potentials/meam/Jelinek_2012/Jelinek_2012_meamf AlS SiS MgS CuS FeS ../../potentials/meam/Jelinek_2012/Jelinek_2012_meam.alsimgcufe AlS FeS
```

В файле параметров есть явный Al-Fe cross-term `lattce(1,5)`, `delta(1,5)`, `alpha(1,5)`, `re(1,5)`, поэтому это не комбинация отдельных Al и Fe потенциалов.

## LAMMPS run

- Папка: `lammps/01_relax_al13fe4/`
- Input: `lammps/01_relax_al13fe4/in.relax_al13fe4`
- Sanity run 1000 steps сохранён в `lammps/01_relax_al13fe4/trial_1000/`
- Финальный run: minimization + `fix box/relax tri 0.0` + NPT 300 K / 0 bar, 5000 steps
- JSON summary: `lammps/01_relax_al13fe4/log_summary_al13fe4.json`

Команды проверки:

```bash
cd /Users/ilua/Documents/ilua-system/projects/physics_md_al_fe/lammps/01_relax_al13fe4
grep -E "ERROR|nan|lost atoms|Dangerous builds|Loop time|Total wall time" log.lammps
tail -100 log.lammps
cd /Users/ilua/Documents/ilua-system/projects/physics_md_al_fe
python analysis/python/parse_lammps_log.py lammps/01_relax_al13fe4/log.lammps --output lammps/01_relax_al13fe4/log_summary_al13fe4.json
python analysis/python/check_lammpstrj.py lammps/01_relax_al13fe4/dump.al13fe4_npt.lammpstrj
```

## Результаты

| Параметр | Значение |
|---|---:|
| Начальное давление | 89312.163 bar |
| Давление после `box/relax` | -9.427 bar |
| Объём после `box/relax` | 1607.294 A^3 |
| Ячейка после `box/relax` | Lx=16.654113 A, Ly=7.878296 A, Lz=12.250151 A |
| Tilt после `box/relax` | xy=0.058671, xz=-3.985108, yz=0.055551 |
| NPT | 300 K / 0 bar, 5000 steps |
| Финальная температура | 308.505 K |
| Финальное мгновенное давление | -61.795 bar |
| Средняя температура по NPT thermo-точкам | 295.597 K |
| Среднее давление по NPT thermo-точкам | 262.658 bar |
| Среднее давление по последним 20 thermo-точкам | 293.629 bar |
| Min/max мгновенного давления в NPT | -10101.56 / 10686.799 bar |
| Финальный объём | 1624.405 A^3 |
| Финальная ячейка | Lx=16.801682 A, Ly=7.866266 A, Lz=12.290597 A |
| Dangerous builds | 0, 0 |
| Lost atoms | не найдено |
| ERROR / nan | не найдено |
| Состав после релаксации | 78 Al, 24 Fe |
| Dump read check | 51 frames, 102 atoms/frame |

## Техническое замечание

После записи `Total wall time` процесс `lmp` не вернулся в shell и был остановлен сигналом. Лог и финальные data/dump-файлы уже были записаны; это зафиксировано как технический нюанс запуска, а не как ошибка физического расчёта.

## Вывод

Standalone Fe4Al13 / Al13Fe4 прошёл базовую проверку устойчивости на выбранном MEAM-потенциале: minimization и `box/relax` сошлись, NPT 5000 steps не привёл к `nan`, потере атомов или разрушению состава. Мгновенное давление сильно флуктуирует из-за малой 102-атомной ячейки, поэтому результат следует считать sanity baseline, а не окончательной валидацией потенциала для интерметаллида.
