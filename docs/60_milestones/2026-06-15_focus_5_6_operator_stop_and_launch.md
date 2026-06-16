# Focus 5-6 Operator Stop And Launch

Date: 2026-06-15

## Scope

Stop the old Stage B 100k queue after preservation, then launch only the focused
nearGB vacancies 5-6 run after preflight approval.

## Runtime Result

- Old run root: `runs\stageB_realism_100k\20260613-222836`
- Focused run root: `runs\stageB_nearGB_vacancies_focus_100k\20260615-215533`
- Old LAMMPS PID `2024` stopped with normal `Stop-Process`.
- No force stop was used.
- Old runner PIDs `21884` and `2812` were already absent after the LAMMPS stop.
- Remaining old LAMMPS/runner processes: `0`.
- Focused preflight refreshed to `allowed_to_launch: true`.
- Focused runner launched from `focus_run_command.txt`.
- Focused parent runner PID: `11716`.
- Focused child runner PID: `15260`.
- Focused LAMMPS PID: `19080`.
- Initial focused case: `B3_nearGB_vacancies_medium_eps0025_prep`.

## Safety Boundaries

No 500k, 250k, 700k, or full-factorial run was started. The old run root was
not deleted or overwritten. No OVITO render execution and no ffmpeg encoding was
run. No commit and no `git add -A` were performed.

## Key Artifacts

- `agent_report_focus_5_6_operator_stop_and_launch.md`
- `runs\stageB_realism_100k\20260613-222836\operator_stop_old_queue_before.json`
- `runs\stageB_realism_100k\20260613-222836\operator_stop_old_queue_after.json`
- `runs\stageB_realism_100k\20260613-222836\old_queue_stopped_by_operator.md`
- `runs\stageB_nearGB_vacancies_focus_100k\20260615-215533\focused_launch_record.json`
- `runs\stageB_nearGB_vacancies_focus_100k\20260615-215533\focused_runtime_initial_check.md`
- `runs\stageB_nearGB_vacancies_focus_100k\20260615-215533\event_pipeline_initial_dry_run_report.md`

## Validation

```powershell
.venv\Scripts\python.exe -m compileall analysis scripts tests
.venv\Scripts\python.exe -m unittest discover tests
```

`unittest discover tests` ran 71 tests and returned OK.

## Next Step

Let the focused run continue. Once focused production analysis frames exist,
rerun the event pipeline dry-run with `--allow-incomplete` and inspect
`event_timeline.json` plus `event_window_plan.md` before any manual rendering or
video encoding.

## 2026-06-16 Follow-Up

The focused run is no longer active. Current process scan found no old
runner/LAMMPS and no focused runner/LAMMPS.

Focused prep/smoke completed for both target cases, then the first focused
production chunk failed:

- failed case/chunk:
  `B3_nearGB_vacancies_medium_eps0025_production.chunk0000000_0010000`
- stage status: `failed_production`
- production restart written: `false`
- production log file: missing

The production stdout recorded:

```text
ERROR on proc 0: Cannot open universe log file log.B3_nearGB_vacancies_medium_eps0025_production.chunk0000000_0010000.lammps: No such file or directory
```

Updated artifact:

- `runs\stageB_nearGB_vacancies_focus_100k\20260615-215533\focused_runtime_final_check.md`

Updated next step:

Do not relaunch the same focused root until the production log path failure is
fixed or a shorter fresh focused run root is explicitly approved.
