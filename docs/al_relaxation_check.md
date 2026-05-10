# Проверка baseline чистого Al

Дата проверки: 2026-05-09.

## Входные данные

- Структура: `structures/converted/Al/al_fcc.data`
- Число атомов: 4000
- Ячейка до релаксации: 40.5 x 40.5 x 40.5 A
- LAMMPS input: `lammps/00_relax_al/in.relax_al_box`
- Потенциал: `potentials/eam/Al_zhou.eam.alloy`
- `pair_style`: `eam/alloy`

## Команды проверки

```bash
cd /Users/ilua/Documents/ilua-system/projects/physics_md_al_fe/lammps/00_relax_al
grep -E "ERROR|nan|lost atoms|Dangerous builds|Loop time|Total wall time" log.lammps
tail -80 log.lammps
cd /Users/ilua/Documents/ilua-system/projects/physics_md_al_fe
python analysis/python/parse_lammps_log.py lammps/00_relax_al/log.lammps --output lammps/00_relax_al/log_summary_al.json
```

## Результаты

| Параметр | Значение |
|---|---:|
| Начальное давление | 23601.197 bar |
| Давление после `fix box/relax` | -0.0105 bar |
| Размер бокса после `box/relax` | 40.816549 A |
| NPT | 300 K / 0 bar, 5000 steps |
| Финальная температура | 293.998 K |
| Финальное мгновенное давление | 433.669 bar |
| Среднее давление по последним 20 thermo-точкам | 78.488 bar |
| Финальный размер бокса | 41.124818 A |
| Dangerous builds | 0, 0 |
| Lost atoms | не найдено |
| ERROR / nan | не найдено |

## Вывод

Baseline чистого Al пройден. Начальное высокое давление ушло к нулю после `box/relax`, NPT при 300 K не показывает устойчивого давления на десятках тысяч bar, потери атомов и `nan` отсутствуют.
