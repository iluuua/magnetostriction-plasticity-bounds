# Focus 5-6 Transition Milestone

Date: 2026-06-15

Scope:

- preserved completed Stage B 100k production cases by manifest and small-file copy;
- wrote a safe-stop plan for the old Stage B queue without killing active LAMMPS;
- generated partial completed-case event timeline and render/video dry-run manifests;
- added a focused config template for only nearGB vacancies cases 5-6;
- created the focused run root and preflight artifacts;
- blocked focused launch because the old LAMMPS process and GPU are still active.

Old run root:

- `runs/stageB_realism_100k/20260613-222836`

Preservation artifacts:

- `runs/stageB_realism_100k/20260613-222836/handoff_completed_cases_snapshot/completed_cases_manifest.json`
- `runs/stageB_realism_100k/20260613-222836/handoff_completed_cases_snapshot/completed_cases_summary.md`

Completed production cases preserved:

- `B3_nearGB_perfect_eps0025`
- `B3_nearGB_perfect_eps0100`
- `B3_interior_vacancies_medium_eps0025`

Current case 4 state:

- `B3_interior_vacancies_medium_eps0100_production`
- active LAMMPS PID observed: `2024`
- active chunk observed: `chunk0080000_0090000`
- latest restart recorded in state/safe-stop plan: step `80000`
- live log had reached step `85000`

Focused run root:

- `runs/stageB_nearGB_vacancies_focus_100k/20260615-215533`

Focused setup artifacts:

- `effective_config.yaml`
- `focus_run_command.txt`
- `focus_run_preflight.json`
- `focus_run_preflight.md`
- `focus_run_volume_estimate.json`

Preflight result:

- `allowed_to_launch: false`
- blockers: `active_lammps_detected`, `gpu_not_free`
- no MD, OVITO, or ffmpeg was launched.

Validation:

```powershell
.venv\Scripts\python.exe scripts\run_stage_sweep.py --config configs\stageB_nearGB_vacancies_focus_100k.template.yaml --plan-only
.venv\Scripts\python.exe -m unittest tests.test_focus_transition
.venv\Scripts\python.exe -m compileall analysis scripts tests
.venv\Scripts\python.exe -m unittest discover tests
.venv\Scripts\python.exe scripts\run_event_pipeline_dry_run.py --run-root runs\stageB_realism_100k\20260613-222836 --output-dir runs\stageB_realism_100k\20260613-222836\event_pipeline_partial_completed --allow-incomplete
```

Exact next action:

Wait for the old case 4 to finish cleanly. Do not kill active LAMMPS. Then
rerun:

```powershell
.venv\Scripts\python.exe scripts\prepare_focus_5_6_transition.py --old-run-root runs\stageB_realism_100k\20260613-222836 --focus-run-root runs\stageB_nearGB_vacancies_focus_100k\20260615-215533 --partial-event-output-dir runs\stageB_realism_100k\20260613-222836\event_pipeline_partial_completed
```

If `focus_run_preflight.json` has `allowed_to_launch: true`, run the command in
`focus_run_command.txt`. If the old runner has already started case 5, do not
launch a second focused run; preserve the new old-run state and decide whether
to stop after the current chunk.
