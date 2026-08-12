# 2026-06-18 Stage D Local Interface 100k Prepare

## Scope

Prepared Stage D (этап D) as a 100k-class local inclusion/matrix mechanics check after the physicist discussion.

The model is intentionally simple:

- homogeneous aluminum matrix;
- Fe4Al13 ellipsoidal inclusion inside the matrix;
- no grain boundary;
- no vacancies in the base variants;
- inclusion eigenstrain is directed along Z.

## Files Changed

- `configs/stageD_local_interface_100k_mechanics.template.yaml`
- `scripts/prepare_stageD_local_interface_100k.py`
- `analysis/python/stage_runner/gpu_grid.py`
- `docs/00_index/DOC_INDEX.md`
- `docs/60_milestones/2026-06-18_stageD_local_interface_100k_prepare.md`
- `.codex/state/current_context.md`

## Runtime Artifacts

Prepared run root:

`runs/stageD_local_interface_100k_mechanics/20260618-215638`

Prepared cases:

- `D1_local_interface_control_eps0000`: control variant, eps_z equals 0.0000.
- `D1_local_interface_physical_eps0025`: physically close variant, eps_z equals 0.0025.
- `D1_local_interface_overload_eps0100`: overload variant, eps_z equals 0.0100.

Here `eps_z` means the relative inclusion eigenstrain along Z.

Each case has:

- generated 104809-atom geometry;
- prep input for LAMMPS (the molecular dynamics program);
- command file for a future prep launch;
- `summary.json`;
- placeholder `analysis.csv`, `stress_profiles.csv`, `structure_profiles.csv`;
- Russian `final_report.md` explaining that the run is prepared but not started.

Root artifacts include:

- `stageD_status.json`;
- `stageD_interpretation_report.md`;
- `case_index.csv`;
- `launch_smoke_when_safe.txt`;
- `check_env_command.txt`.

## Why It Was Not Launched

The Stage C one-million-class safe-prep is still running:

- active process: `lmp_kokkos_cuda.exe`, PID `22468`;
- latest Stage C thermo row recorded by the prepare script: step `44700` of `50000`;
- temperature: about `297.24 K`;
- latest restart: step `44000`;
- video card utilization: `100 percent`;
- free disk on C: about `9.04 GiB`, below the Stage D threshold of `20 GiB`.

The prompt explicitly forbids starting a new heavy calculation while the same video card is occupied. No Stage D LAMMPS process was launched.

## Validation

- `.venv\Scripts\python.exe -m py_compile scripts\prepare_stageD_local_interface_100k.py analysis\python\stage_runner\gpu_grid.py`
- `.venv\Scripts\python.exe scripts\run_stage_sweep.py --config configs\stageD_local_interface_100k_mechanics.template.yaml --plan-only`
- `.venv\Scripts\python.exe scripts\prepare_stageD_local_interface_100k.py`
- `.venv\Scripts\python.exe scripts\prepare_stageD_local_interface_100k.py --run-dir runs\stageD_local_interface_100k_mechanics\20260618-215638`
- `.venv\Scripts\python.exe -m unittest tests.test_stagec_1m_queue`

The plan-only validation passed. The three prepared geometries are feasible under the configured 12 GiB video memory profile.

## Exact Next Action

After Stage C exits and disk free space is back above the configured threshold, run only prep plus the short smoke check:

`.venv\Scripts\python.exe scripts\run_stage_sweep.py --config runs\stageD_local_interface_100k_mechanics\20260618-215638\effective_config.yaml --run-dir runs\stageD_local_interface_100k_mechanics\20260618-215638 --run-stage D1_local_interface_100k --gpu --smoke-only`

This command must not be run while the current Stage C LAMMPS process is alive or while disk free space is below the threshold.

## Resource Gate Update, 2026-06-19 23:30 +03:00

Stage C and resources were checked again before any Stage D launch:

- no live LAMMPS process was found;
- no live `lmp_kokkos_cuda.exe` process was found;
- the Stage C LAMMPS log reached step `50000` of `50000`;
- the final Stage C temperature was `300.28417 K`;
- `restart.C1_1M_nearGB_vacancies_medium_eps0100_prep.final` is present;
- `restart.C1_1M_nearGB_vacancies_medium_eps0100_prep.50000` is present;
- `data.a1_baseline_equil` is present;
- `case_metadata.json` reports `status=success` and `success=true`;
- `safe_prep_result.json` still reports `status=safe_prep_failed` with blocker `prep failed`;
- no `ERROR`, `nan`, `lost atoms`, `cudaError`, or `illegal memory` markers were found in actual log/stdout/stderr files;
- C: free space is about `8.34 GiB`, below the `20 GiB` Stage D threshold;
- GPU utilization was about `33 percent`, with `557 MiB` of `12288 MiB` used.

Stage D was not launched. The current status is `blocked_waiting_for_disk_and_stageC_gate`.

Safe cleanup candidates were listed but not deleted:

- `C:\Users\dille\AppData\Local\Temp`: about `5.16 GiB`;
- `C:\Users\dille\.cache`: about `4.68 GiB`;
- `C:\Users\dille\AppData\Local\NVIDIA\DXCache`: about `1.28 GiB`;
- `C:\Users\dille\AppData\Local\pip\Cache`: about `0.25 GiB`.

Updated run-root reports:

- `stageD_runtime_status.md`;
- `stageD_queue_report.md`;
- `stageD_smoke_result.md`;
- `stageD_execution_report.md`;
- `stageD_interpretation_report.md`;
- `stageD_analysis_summary.json`;
- `stageD_status.json`;
- `stageD_launch_queue.json`;
- `state.json`;
- case-level `prep\summary.json` for all three variants.

Do not run Stage D until C: free space is at least `20 GiB` and the Stage C aggregate gate contradiction is resolved or explicitly accepted.

Validation after report update:

- `git diff --check` passed in the project repo;
- Stage D JSON files and three case-level `prep\summary.json` files parsed successfully;
- `.venv\Scripts\python.exe -m py_compile scripts\prepare_stageD_local_interface_100k.py analysis\python\stage_runner\gpu_grid.py` passed;
- `.venv\Scripts\python.exe scripts\run_stage_sweep.py --config configs\stageD_local_interface_100k_mechanics.template.yaml --plan-only` passed;
- `.venv\Scripts\python.exe -m unittest tests.test_stagec_1m_queue` passed with 12 tests.

## Smoke-only Disk Override Start, 2026-06-20 00:18 +03:00

The user explicitly allowed starting only the short smoke check with less than `20 GiB` free on C. The `20 GiB` threshold remains the requirement for the full Stage D production run. A temporary `5 GiB` lower threshold was accepted only for smoke-only.

Actions:

- created `runs\stageD_local_interface_100k_mechanics\20260618-215638\effective_config.smoke_disk_override.yaml`;
- changed only `resources.min_free_disk_gb_before_stage` to `5` in that copy;
- did not change `effective_config.yaml`;
- did not change `configs\stageD_local_interface_100k_mechanics.template.yaml`;
- did not touch `pagefile.sys`;
- launched only `--smoke-only`, not full Stage D.

Stage C was accepted as complete for this smoke-only gate because real logs, final files, and `case_metadata.json` confirm success. The stale aggregate `safe_prep_result.json` still says `safe_prep_failed`, but the prompt explicitly allowed treating it as stale under these conditions.

Smoke-only command:

```powershell
.venv\Scripts\python.exe scripts\run_stage_sweep.py --config runs\stageD_local_interface_100k_mechanics\20260618-215638\effective_config.smoke_disk_override.yaml --run-dir runs\stageD_local_interface_100k_mechanics\20260618-215638 --run-stage D1_local_interface_100k --gpu --smoke-only
```

Observed primary result:

- runner PID: `23708`;
- child Python PID: `23856`;
- LAMMPS PID: `15932`;
- current case: `D1_local_interface_control_eps0000`;
- current phase: `prep`;
- latest checked step: `1400`;
- latest checked temperature: `94.838825 K`;
- no `ERROR`, `nan`, `lost atoms`, `cudaError`, or `illegal memory` markers found so far;
- latest C: free space: about `8.61 GiB`;
- latest GPU: about `99 percent`, `1047 MiB` of `12288 MiB`, `64 C`.

The smoke-only run was still in progress at this checkpoint. Full Stage D must not be launched until smoke-only exits cleanly and logs, restart/dump files, and disk space are checked.

Validation after smoke-only start:

- `git diff --check` passed;
- Stage D JSON status/report files parsed successfully;
- `.venv\Scripts\python.exe -m py_compile scripts\prepare_stageD_local_interface_100k.py analysis\python\stage_runner\gpu_grid.py` passed;
- `.venv\Scripts\python.exe -m unittest tests.test_stagec_1m_queue` passed with 12 tests.

## Smoke-only Result, 2026-06-20 03:30 +03:00

The smoke-only runner completed with `result: OK`. Stage status is `success_smoke_only`; gate decision is `requires_manual_review`.

Completed cases:

- `D1_local_interface_control_eps0000_prep`: 8000 steps, final temp `301.80967 K`, max temp `305.05124 K`;
- `D1_local_interface_control_eps0000_smoke`: 2000 steps, final temp `287.00146 K`, max temp `292.20202 K`;
- `D1_local_interface_physical_eps0025_prep`: 8000 steps, final temp `300.75071 K`, max temp `322.08417 K`;
- `D1_local_interface_physical_eps0025_smoke`: 2000 steps, final temp `286.50996 K`, max temp `292.18992 K`;
- `D1_local_interface_overload_eps0100_prep`: 8000 steps, final temp `7.2142645 K`, max temp `37086.592 K`;
- `D1_local_interface_overload_eps0100_smoke`: 2000 steps, final temp `285.62717 K`, max temp `297.85243 K`.

No `ERROR`, `nan`, `lost atoms`, `cudaError`, or `illegal memory` markers were found in actual Stage D log/stdout/stderr files.

Dump files and final smoke data/dump files were written for all three variants. Restart files were not written because restart cadence is `10000` steps and the phases are shorter.

The full Stage D run was not launched. It remains blocked because:

- `D1_local_interface_overload_eps0100_prep` exceeded the `1000 K` danger threshold, including `37086.592 K` at step `4300`;
- C: free space at the latest check is about `7.68 GiB`, below the default `20 GiB` full-run threshold.

Final validation:

- `git diff --check` passed;
- updated JSON status/report files parsed successfully;
- `.venv\Scripts\python.exe -m py_compile scripts\prepare_stageD_local_interface_100k.py analysis\python\stage_runner\gpu_grid.py` passed;
- `.venv\Scripts\python.exe -m unittest tests.test_stagec_1m_queue` passed with 12 tests.

Prepared full-run command, not executed:

```powershell
.venv\Scripts\python.exe scripts\run_stage_sweep.py --config runs\stageD_local_interface_100k_mechanics\20260618-215638\effective_config.full_control_physical_only.yaml --run-dir runs\stageD_local_interface_100k_mechanics\20260618-215638 --run-stage D1_local_interface_100k --gpu
```

Next safe step: do not launch `eps0100`; use only the safe full config after disk and operator approval are resolved.

## Queue Update, 2026-06-18 23:49 +03:00

Stage C was checked again before any Stage D launch:

- `lmp_kokkos_cuda.exe` is still alive at PID `22468`;
- latest visible Stage C step is `46700` of `50000`;
- latest visible temperature is about `301.58 K`;
- latest restart file is `restart.C1_1M_nearGB_vacancies_medium_eps0100_prep.46000`;
- final restart and final data files are not present yet;
- no `ERROR`, `nan`, `lost atoms`, `cudaError`, or `illegal memory` markers were found;
- video card utilization is `100 percent`;
- C: free space is about `9.25 GiB`, below the `20 GiB` Stage D threshold.

Stage D was not launched. The queue artifacts were added under the existing run root:

- `QUEUE_READY_STAGE_D.md`;
- `stageD_launch_queue.json`;
- `stageD_queue_report.md`;
- `stageD_runtime_status.md`.

Additional validation passed:

- `.venv\Scripts\python.exe -m py_compile scripts\prepare_stageD_local_interface_100k.py analysis\python\stage_runner\gpu_grid.py`;
- `.venv\Scripts\python.exe scripts\run_stage_sweep.py --config configs\stageD_local_interface_100k_mechanics.template.yaml --plan-only`;
- `.venv\Scripts\python.exe -m unittest tests.test_stagec_1m_queue`, 12 tests.

## Overload Instability Review And Safe Full Config, 2026-06-20 17:35 +03:00

The overload smoke-only result was reviewed around steps `4100-6600`.

Finding:

- `D1_local_interface_control_eps0000` remains stable;
- `D1_local_interface_physical_eps0025` remains stable;
- `D1_local_interface_overload_eps0100` is unstable in prep and is excluded from recommended full launch.

The overload instability starts after the transition from the first settle/ramp segment to the second NVT segment at timestep `0.001`:

- step `4100`: `898.9653 K`;
- step `4200`: `27734.415 K`;
- step `4300`: `37086.592 K`, `TotEng=160599.83`, `Press=320612.65`;
- step `6500`: `1500.0303 K`.

No `ERROR`, `nan`, `lost atoms`, `cudaError`, or `illegal memory` markers were found, but the temperature/energy/pressure spikes make the result physically unreliable.

Updated run-root artifacts:

- `stageD_overload_instability_report.md`;
- `effective_config.full_control_physical_only.yaml`;
- `stageD_smoke_result.md`;
- `stageD_execution_report.md`;
- `stageD_interpretation_report.md`;
- `stageD_runtime_status.md`;
- `stageD_queue_report.md`;
- `stageD_status.json`;
- `stageD_launch_queue.json`.

Safe full config:

`runs\stageD_local_interface_100k_mechanics\20260618-215638\effective_config.full_control_physical_only.yaml`

It contains only:

- `D1_local_interface_control_eps0000`;
- `D1_local_interface_physical_eps0025`.

The config enables `run_production_after_smoke_pass: true`, keeps the full-run disk threshold at `20 GiB`, and omits `D1_local_interface_overload_eps0100` from `cases`, `eps_z`, and `production_case_ids`.

Full Stage D was not launched. Current C: free space is about `8.00 GiB`, below the `20 GiB` threshold.

Prepared command, not executed:

```powershell
.venv\Scripts\python.exe scripts\run_stage_sweep.py --config runs\stageD_local_interface_100k_mechanics\20260618-215638\effective_config.full_control_physical_only.yaml --run-dir runs\stageD_local_interface_100k_mechanics\20260618-215638 --run-stage D1_local_interface_100k --gpu
```

Next safe step: free C: to at least `20 GiB` or get a separate explicit full-run override, then run only the prepared control+physical command if approved. Do not run `eps0100` full without changing the scheme.

## Full Control+Physical Launch, 2026-06-21 15:44 +03:00

The user explicitly authorized full Stage D launch with RAM + pagefile and with disk below the earlier `20 GiB` planning threshold. The hard stops for this run are `3 GiB` free on C: before launch and `2 GiB` commit headroom before launch, with `1 GiB` commit headroom as an emergency monitor threshold during the run.

The safe full config was updated only in the run root:

`runs\stageD_local_interface_100k_mechanics\20260618-215638\effective_config.full_control_physical_only.yaml`

Changes:

- `resources.min_free_disk_gb_before_stage` is `3`;
- the empty `overload_eps_z` key was removed from the safe launch config;
- the config still contains only `D1_local_interface_control_eps0000` and `D1_local_interface_physical_eps0025`;
- `D1_local_interface_overload_eps0100` remains excluded because smoke-only prep reached about `37086.592 K`.

Launch command:

```powershell
.venv\Scripts\python.exe scripts\run_stage_sweep.py --config runs\stageD_local_interface_100k_mechanics\20260618-215638\effective_config.full_control_physical_only.yaml --run-dir runs\stageD_local_interface_100k_mechanics\20260618-215638 --run-stage D1_local_interface_100k --gpu
```

Launch state after the 120-second check:

- full run launched: yes;
- runner PID: `2156`;
- child Python PID: `7516`;
- LAMMPS PID: `17220`;
- current case: `D1_local_interface_control_eps0000`;
- current phase: `production`;
- current step: `0`;
- temperature: `287.83776 K`;
- disk free: about `7.40 GiB`;
- commit headroom: about `26.82 GiB`;
- GPU: NVIDIA GeForce RTX 3060, `100 percent`, `1068/12288 MiB`, `62 C`;
- active log: `runs\stageD_local_interface_100k_mechanics\20260618-215638\cases\D1_local_interface_100k\D1_local_interface_control_eps0000\production\log.chunk0000000_0010000.lammps`.

Do not start another LAMMPS or `run_stage_sweep.py` process while this run is active.

Latest post-launch snapshot at 2026-06-21 15:48 +03:00:

- current step: `1000`;
- temperature: `289.15002 K`;
- GPU: NVIDIA GeForce RTX 3060, `98 percent`, `1068/12288 MiB`, `65 C`;
- no active production `ERROR`, `nan`, `lost atoms`, `cudaError`, or `illegal memory` markers were found.

## Post-run Analysis Completed, 2026-06-22

The full control+physical Stage D production run completed and was analyzed from existing final dumps only. No new LAMMPS calculation, eps0100 run, render, ffmpeg job, git commit, or push was performed.

Completed full-run cases:

- `D1_local_interface_control_eps0000`: `10000/10000` production steps, final temperature `287.51957 K`, final pressure `554.156 MPa`.
- `D1_local_interface_physical_eps0025`: `10000/10000` production steps, final temperature `288.30629 K`, final pressure `596.466 MPa`.

Excluded full-run case:

- `D1_local_interface_overload_eps0100`: excluded because smoke-only prep reached about `37086.592 K`; it is not physically reliable evidence of plasticity.

Post-run analysis:

- `scripts/run_stage_sweep.py --analyze-only` completed successfully on existing `dump.final.lammpstrj` files.
- `analysis/python/stage_runner/analysis_runner.py` now writes DXA, CNA, PTM, and final-dump virial stress proxy metrics.
- Actual log/stdout/stderr scan found no `ERROR`, `nan`, `lost atoms`, `cudaError`, or `illegal memory` markers.
- DXA found `0` dislocation segments and `0 A` total line length in both completed cases.
- CNA OTHER increased from `2870` to `3165` matrix atoms.
- PTM OTHER increased from `2713` to `3000` matrix atoms.
- Defect atoms beyond the 1.3 interface shell increased from `2` to `323`.

Interpretation:

- Stage D supports Variant B: early structural/plastic rearrangement precursor around the inclusion.
- It does not support a claim of developed dislocation plasticity.
- HCP/stacking-fault evidence remains weak because HCP atoms beyond the 1.3 shell are `0`.
- Stress values are final-dump virial proxy values; use them for relative comparison, not calibrated absolute yield claims.
