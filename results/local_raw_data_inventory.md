# Инвентаризация локальных «сырых» данных (не в git)

Тяжёлые данные молекулярной динамики хранятся **только локально** и не попадают в
репозиторий. Здесь зафиксировано, где они лежат, почему исключены и какими малыми
файлами заменены в git.

## 1. Где лежат полные dumps / restarts / logs

Базовый каталог расчётов (целиком исключён через `.git/info/exclude` строкой `runs/`):

```
C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\
```

Focused Stage B 100k:

```
runs\stageB_nearGB_vacancies_focus_100k\20260615-215533\
  cases\B3_nearGB_vacancies_focus_100k\<case>\production\
    dump.chunk*.lammpstrj      # траектории, ~70.4 MB на файл
    restart.<step>             # бинарные чекпойнты, ~9 MB на файл
    log.chunk*.lammps          # логи LAMMPS по порциям
    data.final, dump.final.lammpstrj
  state.json                   # полное состояние прогона (~217 KB)
```

Stage C 1M (активный расчёт):

```
runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123\
  cases\... , structures\... , logs\...   # появляются по мере счёта
  state.json
```

Объём данных (на момент релиза):

| Категория | Объём | Файлов |
|---|---:|---:|
| `runs/` всего | ~4132.7 MB | 2004 |
| focused run root | ~1757.1 MB | 263 |
| Stage C run root (растёт) | ~63.3 MB | 40 |
| `*.lammpstrj` (траектории) | ~2647.8 MB | 188 |
| `restart.*` (чекпойнты) | ~786.2 MB | 130 |
| `monitor_snapshots/` | ~5.9 MB | 39 |

## 2. Почему они не коммитятся

- Траектории `*.lammpstrj` и restart-файлы тяжёлые (десятки–сотни МБ) и
  регенерируемы из конфигурации и стартовых структур.
- Хранение их в git раздуло бы репозиторий на гигабайты без научной пользы:
  ключевые числа уже извлечены анализом (DXA/CNA) в малые файлы.
- `monitor_snapshots/` и `status_dump_*.txt` — временные снимки мониторинга.
- `.venv/` — локальное окружение, воспроизводится из зависимостей.

Исключение задано в `.gitignore` (`*.lammpstrj`, `dump.*`, `restart.*`,
`monitor_snapshots/`, `status_dump_*.txt`, `__pycache__/`, `.pytest_cache/`,
`.venv/`) и в `.git/info/exclude` (целиком `runs/`).

## 3. Какие малые файлы заменяют их в репозитории

| Сырьё (локально) | Замена в git |
|---|---|
| `runs/.../production/analysis.json` | `results/stageB_focused_100k_artifacts/analysis_eps0025.json`, `analysis_eps0100.json` |
| `runs/.../tables/defect_summary.csv` | `results/stageB_focused_100k_artifacts/defect_summary.csv` |
| `runs/.../final_report.md`, `hang_recovery_report.md` | одноимённые файлы в `results/stageB_focused_100k_artifacts/` |
| полный прогон | `results/stageB_focused_100k_summary.csv` + `.md` (синтез) |
| структуры/eigenstrain | `results/stageB_focused_100k_artifacts/eigenstrain_build_eps*.json` |
| Stage C launch/queue | `results/stageC_1M_queue/*` |
| научное описание | `docs/reports/stageB_focused_100k_and_stageC_1M_report.(md|pdf|docx)` |

## 4. Как воспроизвести расчёт

Из корня проекта, при активном GPU-LAMMPS (KOKKOS/CUDA, `meam/kk`):

```powershell
# Focused Stage B 100k (оба варианта eps_z = 0.0025 и 0.0100):
.venv\Scripts\python.exe scripts\run_stage_sweep.py `
  --config configs\stageB_nearGB_vacancies_focus_100k.template.yaml `
  --run-dir runs\stageB_nearGB_vacancies_focus_100k\<новый-таймстамп> `
  --run-stage B3_nearGB_vacancies_focus_100k --gpu
```

Детерминизм геометрии обеспечен сидами: eps0025 — `73005`, eps0100 — `73006`
(200 вакансий, защитная оболочка 4 Å вокруг включения). Конфигурация полностью
управляет числом шагов, eps, порогами и анализом.

## 5. Где лежит Stage C 1M queue root

```
runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123\
```

Stage C на момент релиза **запущен и считается** (PID 20944, кейс
`C1_1M_nearGB_vacancies_medium_eps0100`, ≈ 944 812 атомов, контрольная точка
100 000 шагов). Малые launch/queue-артефакты скопированы в
`results/stageC_1M_queue/` (preflight, volume estimate, launch records, команды
продолжения до 200k/250k, effective config). Результаты Stage C будут оформлены
отдельным последующим PR после контрольной точки 100k.
