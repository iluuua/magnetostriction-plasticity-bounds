# Stage C 1M Preflight

Generated: 2026-06-16T17:31:25
Stage C root: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123`
Selected case: `C1_1M_nearGB_vacancies_medium_eps0100`

- allowed_to_launch_now: `False`
- queue_ready: `True`
- blocked_by: `['active_focused_100k_lammps']`
- can_launch_after_current_focus_finishes: `True`

## Runtime And Storage

- estimated_atoms: `944812`
- estimated_memory_gb: `11.64`
- expected_runtime: `optimistic ~4 days; expected ~5 days; pessimistic ~6.5 days`
- estimated_dump_gb: `1.2`
- estimated_restart_gb: `0.77`
- estimated_total_storage_gb: `3.98`
- disk_free_gb: `{'C': 28.132, 'B': 267.363}`

## Launch Command

```powershell
.venv\Scripts\python.exe scripts\run_stage_sweep.py --config runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123\effective_config.yaml --run-dir runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123 --run-stage C1_1M_scaleup_100k --gpu
```

Do not run the launch command while `blocked_by` is non-empty.

## Launch-After-Focus Command

```powershell
.venv\Scripts\python.exe scripts\launch_stageC_1M_after_focus.py --focus-run-root runs\stageB_nearGB_vacancies_focus_100k\20260615-215533 --stageC-run-root runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123
```
