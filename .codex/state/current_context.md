Objective: Stage C 1M-class nearGB vacancies eps0100 queue plan prepared, blocked until focused 100k finishes.

Current checkpoint, 2026-06-16 17:31 +03:00:
- target repo: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe`
- branch: `feat/autopilot-A0-A1-production`
- project-local `AGENTS.md` / `AGENTS.override.md`: not present
- global `C:\Users\dille\.codex\AGENTS.md`: attempted, missing on disk
- active focused root: `runs\stageB_nearGB_vacancies_focus_100k\20260615-215533`
- active focused runner PID at Stage C preflight: `9440`
- active focused child Python PID at Stage C preflight: `15252`
- active focused LAMMPS PID at Stage C preflight: `7148`
- active focused LAMMPS chunk at Stage C preflight: `in.chunk0040000_0050000`
- no Stage C MD launch was performed
- no 500k, no 700k, no full factorial, no OVITO render execution, no ffmpeg, no commit, and no `git add -A`

Stage C prepared:
- selected case: `C1_1M_nearGB_vacancies_medium_eps0100`
- target class: requested `1000000` atoms; configured geometry target `950000`
- estimated atom count: `944812`
- estimated GPU memory: `11.64 GB`
- Stage C run root: `runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123`
- effective config: `runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123\effective_config.yaml`
- preflight JSON: `runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123\stageC_1M_preflight.json`
- preflight MD: `runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123\stageC_1M_preflight.md`
- launch command file: `runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123\stageC_1M_launch_command.txt`
- launch-after-focus command file: `runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123\launch_after_focus_command.txt`
- continuation templates: `continue_to_200k_command.txt`, `continue_to_250k_command.txt`

Preflight result:
- `allowed_to_launch_now`: `false`
- `queue_ready`: `true`
- `blocked_by`: `active_focused_100k_lammps`
- `can_launch_after_current_focus_finishes`: `true`
- disk free at preflight: C `28.132 GB`, B `267.363 GB`
- estimated Stage C storage: dump `1.2 GB`, restart `0.77 GB`, total `3.98 GB`
- expected runtime for 100k Stage C steps: optimistic `~4 days`, expected `~5 days`, pessimistic `~6.5 days`

Implementation changes:
- `analysis\python\stage_runner\gpu_grid.py`
  - registered `stageC_1M_nearGB_vacancies_eps0100_100k` as a GPU-grid config
  - made Stage B realism geometry validation target-relative instead of hard-coded 100k-class only
  - added config-driven `io_policy.dump_fields` for trajectory and final dumps
  - made Stage B realism stage reports use the configured atom target label
- `analysis\python\stage_runner\stagec_1m.py`
  - added Stage C config validation, live process preflight, volume estimation from focused dump/restart samples, command writers, and report helpers
- `configs\stageC_1M_nearGB_vacancies_eps0100_100k.template.yaml`
  - single-case Stage C 1M-class config with dump_every.production `5000`, restart_every `10000`, production_steps `100000`, chunk_steps `10000`, and event gates
- `scripts\prepare_stageC_1M_queue_plan.py`
  - writes the queue root and preflight artifacts without launching MD
- `scripts\launch_stageC_1M_after_focus.py`
  - rechecks no active LAMMPS/focused runner before launching Stage C and refuses if blocked
- `tests\test_stagec_1m_queue.py`
  - covers config scope, atom estimate, dump fields, preflight blockers/root guard, plan-only, and incomplete event dry-run

Event pipeline:
- command run:
  `.venv\Scripts\python.exe scripts\run_event_pipeline_dry_run.py --run-root runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123 --allow-incomplete`
- result: `external_execution: not_run`, frame count `0`, event window `blocked_no_frames`, video `blocked_no_frames`
- manifests and render/video plans were written under `runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123\event_pipeline`

Docs/reports updated:
- `agent_report_stageC_1M_queue_plan.md`
- `docs\60_milestones\2026-06-16_stageC_1M_queue_plan.md`
- `docs\00_index\DOC_INDEX.md`
- `docs\paper\visualization_event_pipeline.md`
- `.codex\state\current_context.md`

Validation:
- `.venv\Scripts\python.exe -m compileall analysis scripts tests` passed
- `.venv\Scripts\python.exe -m unittest discover tests` passed, 81 tests
- launch-after-focus guard was executed during active focused LAMMPS and refused as expected: `launched: false`, `blocked_by: active_focused_100k_lammps`, `queue_ready: true`

Remaining risks:
- Stage C has not launched and must not launch while the focused Stage B run or any LAMMPS process is active.
- The prepared Stage C root is queue-ready, but runtime feasibility still depends on the fresh launch-after-focus preflight and actual GPU availability.
- A previously generated superseded Stage C queue root also exists at `runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173059`; it was not deleted.

Exact next step:
After the focused run finishes or stops, run:
`.venv\Scripts\python.exe scripts\launch_stageC_1M_after_focus.py --focus-run-root runs\stageB_nearGB_vacancies_focus_100k\20260615-215533 --stageC-run-root runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123`

The launch guard must re-run preflight and refuse if any `lmp_kokkos_cuda.exe` or focused runner is active.
