# Stage E4 700k DXA Confirm Launch

Date: 2026-06-25

## Scope

Prepared and launched one gated production baseline:

- stage: `E4_700k_dxa_confirm`
- case: `E4_phys001942_700k_80k`
- target atoms: `700000`
- actual atoms from smoke: `710216`
- eps_z: `0.001942`
- production steps: `80000`
- dump/restart cadence: `10000/10000`
- system: homogeneous Al matrix plus one Fe4Al13 inclusion

No control, 250k, 500k, 1M, eps0025/0100, grain-boundary, vacancy, polycrystal, OVITO render, ffmpeg, git commit, or cleanup was run.

## Run Root

`C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_700k_dxa_confirm\20260625-102200`

## Validation

- `py_compile` for `scripts/run_stageE_700k_dxa_confirm.py`: passed.
- GPU-grid plan-only: passed; estimated `710338` atoms and `8.82 GiB` GPU memory.
- GPU-grid check-env: passed; LAMMPS GPU binary, MEAM, MEAM/KK, KOKKOS, KOKKOS CUDA, Python imports, GPU, and disk gates passed.
- `.venv\Scripts\python.exe -m compileall analysis scripts tests`: passed.
- `.venv\Scripts\python.exe -m unittest discover tests`: passed, `85` tests.
- Live process scan before launch: no active LAMMPS/Stage E runner.
- Smoke gate: passed with `smoke_returncode=0`.

## Launch Result

Production is running:

- worker PID: `18876`
- production runner PID: `1620`
- run_stage_sweep child PID: `19788`
- LAMMPS PID at initial check: `19852`
- first production chunk: `0 -> 10000`
- initial production thermo: step `0`, temp `287.98125 K`, max temp `287.98125 K`
- C: free disk at initial runtime check: `25.596 GiB`
- blockers: none

The required KOKKOS CUDA neighbor workaround is active:

```text
neigh_modify    delay 0 every 10 check no
```

This is recorded as a run-local workaround, not an upstream LAMMPS/KOKKOS fix.

## Artifacts

- `runs\stageE_700k_dxa_confirm\20260625-102200\stageE_700k_launch_record.json`
- `runs\stageE_700k_dxa_confirm\20260625-102200\stageE_700k_launch_record.md`
- `runs\stageE_700k_dxa_confirm\20260625-102200\stageE_700k_runtime_initial_check.md`
- `runs\stageE_700k_dxa_confirm\20260625-102200\stageE_700k_dxa_confirm_status.json`
- `agent_report_stageE_700k_dxa_confirm_launch.md`
- `C:\Users\dille\Documents\ilua-system\state\reports\physics_md_al_fe\stageE_700k_dxa_confirm_launch.json`

## Next Step

Monitor until production reaches `80000/80000`, then read `stageE_700k_final_summary.json` and compare DXA/CNA/PTM/plastic-zone metrics against 510k v2 and 250k longrun.
