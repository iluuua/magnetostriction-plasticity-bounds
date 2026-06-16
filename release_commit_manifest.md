# Release commit manifest

Документ фиксирует, что войдёт в релиз-коммит, что исключено и почему. Staging —
строго выборочный (без `git add -A` / `git add .`).

- **Ветка релиза:** `docs/stageb-focused-results-stagec-1m-report` (от
  `feat/autopilot-A0-A1-production`).
- **База PR:** `main`.
- **Контекст:** focused Stage B 100k завершён и проанализирован; Stage C 1M запущен
  пользователем и считается в фоне (не трогается этим релизом).

## 1. Что будет staged

**Изменённые отслеживаемые файлы:**

- `README.md` — переписан под текущую цепочку расчёта и статус.
- `.gitignore` — добавлены `dump.*`, `restart.*`, `monitor_snapshots/`,
  `status_dump_*.txt`, `.pytest_cache/`, `.venv/`.
- `.codex/state/current_context.md`, `docs/00_index/DOC_INDEX.md`.

**Новые исходники (проверены — только `.py`/`.ps1`/`.yaml`, без мусора):**

- `analysis/python/stage_runner/`, `analysis/python/science_optimizer/`,
  `analysis/python/event_pipeline/`;
- `scripts/`, `tests/`, `configs/`.

**Новые документы и результаты:**

- `docs/reports/stageB_focused_100k_and_stageC_1M_report.md` / `.pdf` / `.tex`;
- `docs/60_milestones/*.md`, `docs/run_plans/*.md`, `docs/paper/`;
- корневые планы `stageB_*.md` (positive-control, seeded, platelet, cyclic,
  no-dislocation, 500k confirmation/preflight);
- `results/stageB_focused_100k_summary.csv` + `.md`;
- `results/run_artifact_manifest.csv`, `results/local_raw_data_inventory.md`;
- `results/stageB_focused_100k_artifacts/`, `results/stageC_1M_queue/`;
- `release_commit_manifest.md` (этот файл).

## 2. Что исключено и почему

| Что | Почему исключено |
|---|---|
| `runs/**/*.lammpstrj` (~2647.8 MB, 188 файлов) | сырые траектории; тяжёлые, регенерируемы; `.gitignore` |
| `runs/**/restart.*` (~786.2 MB, 130 файлов) | бинарные чекпойнты; ~9 MB каждый |
| весь `runs/` (~4132.7 MB) | исключён через `.git/info/exclude` |
| `monitor_snapshots/` (~5.9 MB) | временные снапшоты watchdog |
| `status_dump_20260616_020108.txt` (~0.06 MB) | дамп статуса |
| `.venv/` | локальное окружение |
| `__pycache__/`, `.pytest_cache/` | кэши Python (в т.ч. после `compileall`) |

Малые подтверждающие артефакты из `runs/` (analysis.json, summaries, launch/queue
Stage C) **скопированы** в `results/` и попадают в git оттуда — сам `runs/` не
коммитится.

**Самые большие исключённые файлы:** `dump.chunk*.lammpstrj` ≈ 70.4 MB каждый
(в focused production); `restart.*` ≈ 9.07 MB каждый. Файлов > 20 MB в staged-наборе
нет.

## 3. Проверки перед коммитом

- `compileall analysis scripts tests` — exit 0.
- Юнит-тесты: **81 тест, все OK** (7 файлов; запуск стандартной для проекта формой
  `python tests/test_*.py`, т.к. `pytest` не установлен, а `unittest discover`
  требует path-настройку из `conftest.py`). Тесты планировщика/гейтов —
  planner-only, MD не запускают, активные run roots не трогают.
- PDF-отчёт: существует, открывается, 11 страниц, 139.1 KB (> 100 KB), сигнатура
  `%PDF`, без пропущенных символов.
- DOCX: **не сформирован** — LibreOffice headless на этой машине нестабилен (тихий
  no-op/блокировки); формат опционален, PDF + Markdown предоставлены.
