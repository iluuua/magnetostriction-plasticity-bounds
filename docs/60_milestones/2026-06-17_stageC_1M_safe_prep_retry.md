# Stage C 1M Safe-Prep Retry Launch

Date: 2026-06-17

## Scope

Prepared and launched a fresh prep-only retry for:

`C1_1M_nearGB_vacancies_medium_eps0100`

The old failed root was preserved and was not resumed or overwritten:

`runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123`

## Why

The previous Stage C prep failed at `4900/8000` with host allocation failure
after a severe temperature runaway. The retry uses a new run root, a larger
C: pagefile, smaller prep timesteps, longer staged thermalization, and
production disabled.

Direct LAMMPS relaxation remains disabled on the KOKKOS CUDA path because the
local runner forbids it for the validated MEAM neighbor-policy workaround.

## Pagefile

Before changes, diagnostics were saved at:

`diagnostics\pagefile_before_stageC_safe_retry_20260617-055349.txt`

Observed before setting:

- `B:\pagefile.sys`: 2000 / 32000 MB configured.
- `C:\pagefile.sys`: 4000 / 8000 MB configured.
- active `C:\pagefile.sys`: 4000 MB allocated.

Updated setting:

- `C:\pagefile.sys`
- `InitialSize`: 24576 MB
- `MaximumSize`: 32768 MB

After setting, active `AllocatedBaseSize` was already `24576 MB`; no reboot was
required for the active allocation observed in this session.

## Superseded Root

`runs\stageC_1M_nearGB_vacancies_eps0100_safe_prep\20260617-060251`

This root was stopped and preserved. It was still early in prep, but its
generated safe-prep plan used timestep `0.00025` for `hold_300K`. The prompt
requires all three safe-prep segments to use timestep `0.0001`; `0.00025` is
only acceptable as a later optional smoke step after a stable hold.

## Corrected Run Root

`runs\stageC_1M_nearGB_vacancies_eps0100_safe_prep\20260617-063915`

Key artifacts:

- `effective_config.yaml`
- `safe_prep_plan.md`
- `pagefile_preflight.json`
- `launch_command.txt`
- `launch_record.json`
- `state.json`
- `final_report.md`
- `cases\C1_1M_scaleup_100k\C1_1M_nearGB_vacancies_medium_eps0100\prep\...`

## Preflight

- pagefile setting: one `C:\pagefile.sys`, 24576 / 32768 MB.
- active pagefile allocation: 24576 MB.
- C: free after pagefile: `12.52 GB`.
- C: free at latest runtime check: about `12.43 GB`.
- RAM: `17079402496` bytes physical.
- GPU: RTX 3060 12 GB, `509 MiB` used at preflight.
- active MD processes before launch: none.
- actual atom count: `938344`.
- matrix atoms: `900256`.
- inclusion atoms: `38088`.
- vacancy count: `1900`.
- min pair distance: `1.8112150514616776 A`.
- pairs below `1.8 A`: `0`.
- cross-source pairs below `2.1 A`: `0`.
- geometry gate: pass.

## Safe-Prep Protocol

The corrected retry uses explicit small-timestep NVT segments:

- ramp 50 -> 150 K: timestep `0.0001`, `10000` steps, tdamp `0.1`.
- ramp 150 -> 300 K: timestep `0.0001`, `20000` steps, tdamp `0.1`.
- hold 300 K: timestep `0.0001`, `20000` steps, tdamp `0.1`.
- total prep steps: `50000`.
- restart/dump cadence: `2000` steps.
- production: disabled.

The generated LAMMPS input also contains:

- `neigh_modify delay 0 every 10 check no`
- periodic prep dump
- periodic restart
- final `write_restart`
- final `write_data data.a1_baseline_equil`
- final `write_dump`

The launcher now records a safe-prep failure if the completed prep log shows
`Temp > 1000 K` or an adjacent thermo-row temperature jump of about one order of
magnitude.

## Launch

Started in background through the project `.venv`:

- launch PID: `22776`.
- worker child Python PID observed: `24088`.
- LAMMPS PID observed: `22468`.
- LAMMPS command: `lmp_kokkos_cuda.exe -k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off`.

Initial runtime check:

- `lmp_kokkos_cuda.exe` active.
- GPU utilization: `100%`.
- GPU memory used: about `3306 MiB`.
- first log thermo row: step `0`, atoms `938344`, temp `50 K`.
- first post-step thermo row observed: step `100`, atoms `938344`, temp `205.7817 K`.
- no runaway, LAMMPS error, or lost atoms marker was observed at the handoff checkpoint.

## Code Changes

- `analysis\python\stage_runner\builder.py`
  - added optional segmented prep schedules with periodic dump/restart support.
- `analysis\python\stage_runner\gpu_grid.py`
  - passes `prep_segments`, `prep_restart_every`, `prep_dump_every`, and `prep_dump_fields` from config to prep input generation.
- `scripts\launch_stageC_1M_safe_prep_retry.py`
  - new pagefile/resource/geometry preflight and background prep-only launcher.
  - corrected all safe-prep segments to timestep `0.0001`.
  - added post-run temperature runaway guard.
- `tests\test_stagec_1m_queue.py`
  - added segmented safe-prep, launcher prep-only, and temperature guard regression coverage.

## Validation

- `.venv\Scripts\python.exe -m compileall analysis\python\stage_runner scripts tests`
- `.venv\Scripts\python.exe -m unittest tests.test_stagec_1m_queue`

Both passed before the corrected launch. The targeted test module ran 12 tests.

## Remaining Risks

- Corrected safe-prep is still running; it has reached only the first post-step
  thermo row at this checkpoint.
- C: free space is above the prompt minimum but not large: `12.52 GB` after
  pagefile, before ongoing dump/restart growth.
- Production must not be launched automatically after prep success.
- If temperature exceeds `1000 K`, rapidly increases, or the log shows
  `ERROR`, `FATAL`, `Lost atoms`, `NaN`, `cudaError`, or out-of-memory, stop the
  pipeline and record failure.

## Exact Next Action

Monitor:

```powershell
Get-Content -Wait 'runs\stageC_1M_nearGB_vacancies_eps0100_safe_prep\20260617-063915\cases\C1_1M_scaleup_100k\C1_1M_nearGB_vacancies_medium_eps0100\prep\log.C1_1M_nearGB_vacancies_medium_eps0100_prep.lammps'
```

After safe-prep exits, inspect `safe_prep_result.json`, `state.json`, and
`final_report.md`. If the gate is successful, report first and prepare a
separate production command only with explicit approval.
