# Stage E 250k Single Physical Longrun Launch

Date: 2026-06-23

Status: `production_running`

## Scope

Run exactly one Stage E single-inclusion homogeneous Al matrix case:

- target atoms: `250000`
- case id: `E3_phys001942_250k_120k`
- run stage: `E3_250k_longrun`
- physical eigenstrain: `eps_z=0.001942`
- production length: `120000` steps
- thermal sanity stop: `1000 K`
- no control, no 700k, no eps0025/eps0050/eps0100, no grain boundary, vacancies, polycrystal, or mechanical load

The current prompt superseded the earlier artificial `25 GiB` disk gate. The active gate for this launch was `C: free >= 18 GiB`.

## Files Added

- `configs/stageE_250k_single_physical_longrun.template.yaml`
- `scripts/run_stageE_250k_single_physical_longrun.py`

The wrapper writes preflight/status JSON, launches smoke first, launches production only after `smoke_returncode=0`, monitors `max_temp_K > 1000`, and writes final reports after `analysis.json` exists.

## Run Root

```text
C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_250k_single_physical_longrun\20260623-205439
```

Status file:

```text
C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_250k_single_physical_longrun\20260623-205439\stageE_250k_longrun_status.json
```

## Preflight

- live LAMMPS / run_stageE processes before launch: none
- LAMMPS binary: `B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe`
- Kokkos CUDA / MEAM capability check: passed
- GPU: NVIDIA GeForce RTX 3060, 12288 MiB total
- free C: before launch: `24.689 GiB`
- required free C: `18 GiB`
- cleanup performed in this launch: none; disk was already above the required threshold

## Runtime Checkpoint

At `2026-06-23T22:03:12+03:00`:

- smoke return code: `0`
- production return code: pending
- current production chunk: `0 -> 60000`
- current production step: `1000/120000`
- actual atoms from thermo: `254055`
- box dimensions from thermo: `141.75 x 141.75 x 210.6 A` = `14.175 x 14.175 x 21.06 nm`
- current temperature: `170.22707 K`
- max temperature so far: `287.73568 K`
- free C: `19.548 GiB`
- active LAMMPS PID at checkpoint: `23284`

Production is still running; analysis and final physics verdict are pending.

## Validation

- `.venv\Scripts\python.exe -m py_compile scripts\run_stageE_250k_single_physical_longrun.py scripts\run_stage_sweep.py analysis\python\stage_runner\gpu_grid.py analysis\python\stage_runner\builder.py`: passed
- `.venv\Scripts\python.exe scripts\run_stage_sweep.py --config configs\stageE_250k_single_physical_longrun.template.yaml --plan-only`: passed
- `.venv\Scripts\python.exe scripts\run_stageE_250k_single_physical_longrun.py --config configs\stageE_250k_single_physical_longrun.template.yaml --preflight-only`: passed, no blockers
- live launch preflight: passed
- smoke gate: passed with `smoke_returncode=0`

## Remaining Risks

- The 120000-step production is a long background calculation; completion and OVITO analysis are not done at this checkpoint.
- Disk is above the launch gate but not spacious (`19.548 GiB` at the checkpoint). The output policy is intentionally sparse: production dump every `120000`, final dump/data enabled, restarts at `60000` and `120000`.
- If temperature exceeds `1000 K`, the wrapper will kill the active process tree and write the exact blocker in `stageE_250k_longrun_status.json`.

## Exact Next Action

Monitor the live status:

```powershell
Get-Content -Raw C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_250k_single_physical_longrun\20260623-205439\stageE_250k_longrun_status.json
```

After production finishes, read:

```powershell
Get-Content -Raw C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_250k_single_physical_longrun\20260623-205439\stageE_250k_final_summary.json
```
