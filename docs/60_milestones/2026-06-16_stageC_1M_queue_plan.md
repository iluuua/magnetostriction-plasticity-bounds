# Stage C 1M Queue Plan

Date: 2026-06-16

## Scope

Prepared a production-ready Stage C 1M-class queue plan for exactly one case:

`C1_1M_nearGB_vacancies_medium_eps0100`

This is the scale-up version of the strongest focused candidate:
near-grain-boundary placement, `vacancies_medium`, and overload eigenstrain
`eps_z = 0.0100`.

No MD launch was performed.

## Run Root

`runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123`

Created artifacts:

- `effective_config.yaml`
- `stageC_1M_preflight.json`
- `stageC_1M_preflight.md`
- `stageC_1M_volume_estimate.json`
- `stageC_1M_launch_command.txt`
- `launch_after_focus_command.txt`
- `continue_to_200k_command.txt`
- `continue_to_250k_command.txt`
- `README_STAGEC_1M.md`
- `event_pipeline\event_timeline.*`
- `event_pipeline\event_window_plan.*`
- `event_pipeline\*_frame_manifest.*`
- `event_pipeline\videos\video_plan.*`

## Preflight Result

- `allowed_to_launch_now`: `false`
- `queue_ready`: `true`
- `blocked_by`: `active_focused_100k_lammps`
- `can_launch_after_current_focus_finishes`: `true`

The focused run was still active during preflight:

- focused runner PID: `9440`
- focused child Python PID: `15252`
- focused LAMMPS PID: `7148`
- current focused LAMMPS chunk in process command:
  `in.chunk0040000_0050000`

## Runtime And Storage Estimate

- requested target atoms: `1000000`
- configured case atom target: `950000`
- estimated atoms: `944812`
- estimated GPU memory: `11.64 GB`
- expected runtime for 100k steps:
  optimistic `~4 days`, expected `~5 days`, pessimistic `~6.5 days`
- dump policy: production dump every `5000` steps plus final dump
- restart policy: restart every `10000` steps
- estimated dump volume: `1.2 GB`
- estimated restart volume: `0.77 GB`
- estimated total storage: `3.98 GB`
- disk free at preflight: C `28.132 GB`, B `267.363 GB`

The storage estimate used observed focused Stage B dump/restart byte density.

## Launch Command After Focus

Run only after the focused Stage B run is complete or stopped and no LAMMPS
process is active:

```powershell
.venv\Scripts\python.exe scripts\launch_stageC_1M_after_focus.py --focus-run-root runs\stageB_nearGB_vacancies_focus_100k\20260615-215533 --stageC-run-root runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123
```

The script rechecks active LAMMPS/focused processes and refuses launch if any
are found.

## Continuation Policy

The Stage C run stops at 100k. Continuation is not automatic.

- If `confirmed_DXA`: prepare an event-window high-frequency rerun, not blind continuation.
- If no DXA but a strong precursor exists: continuation to 200k/250k can be reviewed using the command templates in the run root.
- If no DXA and no precursor exists: stop scaling and prepare positive-control/seeded/cyclic branch.

## Event Pipeline

The incomplete queued root was dry-run with:

```powershell
.venv\Scripts\python.exe scripts\run_event_pipeline_dry_run.py --run-root runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123 --allow-incomplete
```

Result:

- `external_execution`: `not_run`
- frame count: `0`
- event-window status: `blocked_no_frames`
- video status: `blocked_no_frames`

This is expected before Stage C produces analysis frames.

## Validation

- `.venv\Scripts\python.exe -m compileall analysis scripts tests` passed.
- `.venv\Scripts\python.exe -m unittest discover tests` passed, 81 tests.
- The launch-after-focus guard was executed in the active focused state and
  refused as expected with `blocked_by: active_focused_100k_lammps`,
  `queue_ready: true`, and `launched: false`.

## Files Changed

- `analysis\python\stage_runner\gpu_grid.py`
- `analysis\python\stage_runner\stagec_1m.py`
- `configs\stageC_1M_nearGB_vacancies_eps0100_100k.template.yaml`
- `scripts\prepare_stageC_1M_queue_plan.py`
- `scripts\launch_stageC_1M_after_focus.py`
- `tests\test_stagec_1m_queue.py`
- `agent_report_stageC_1M_queue_plan.md`
- `docs\paper\visualization_event_pipeline.md`
- `docs\00_index\DOC_INDEX.md`
- `.codex\state\current_context.md`

## Remaining Risk

Stage C has not been launched. The only intended blocker is the active focused
100k run. After that run ends, the launch-after-focus script must be used so it
can re-run preflight and refuse if another LAMMPS process is active.
