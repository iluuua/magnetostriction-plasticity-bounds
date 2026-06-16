# GPU grid runner started

Date: 2026-06-11

Scope:
- Turned the validated KOKKOS/CUDA MEAM neighbor-check workaround into a config-driven production GPU grid runner.
- Started the gated sweep from A0_24k toward A1_small, A1_medium, and A2_large.

Files changed:
- `configs/stage_sweep_gpu_grid.yaml`
- `analysis/python/stage_runner/gpu_grid.py`
- `scripts/run_stage_sweep.py`
- `.codex/state/current_context.md`
- `docs/00_index/DOC_INDEX.md`
- `agent_report_gpu_grid_runner.md`

Validation:
- `.venv\Scripts\python.exe -m compileall analysis scripts`
- `.venv\Scripts\python.exe scripts\run_stage_sweep.py --config configs\stage_sweep_gpu_grid.yaml --plan-only`
- `.venv\Scripts\python.exe scripts\run_stage_sweep.py --config configs\stage_sweep_gpu_grid.yaml --check-env`

Active run:
- Run root: `runs/stage_sweep_gpu_grid/20260611-175339`
- First completed case: `A0_24k_24259_eps_0000_smoke`
- Result: exit 0, 2000/2000 steps, no `ERROR`, no `nan`, no `lost atoms`, no `cudaError`
- Rate: 9.164 timesteps/s
- Neighbor builds: 200
- Dangerous builds status: not checked because the production workaround uses `check no`

Production GPU profile:
```text
B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe -k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off -in <input> -log <log>
```

Production input rewrite:
```text
neigh_modify    delay 0 every 10 check no
```

Notes:
- `CUDA_LAUNCH_BLOCKING` is not used in production; the runner removes forbidden environment keys from child LAMMPS processes.
- Generated inputs, structures, logs, tables, and reports are under `runs/`.
- Original templates, potentials, and CPU baseline data were not modified.
- Active process started before the final trajectory-dump field fix; intermediate trajectory dumps in that active run may omit atom `id`, but final dumps include `id type x y z`. The checked-in runner code is fixed for future starts/resume.

Exact next action:
Monitor `runs/stage_sweep_gpu_grid/20260611-175339/state.json`. If interrupted, resume with:
```powershell
.venv\Scripts\python.exe scripts\run_stage_sweep.py --config configs\stage_sweep_gpu_grid.yaml --run-dir runs\stage_sweep_gpu_grid\20260611-175339 --resume
```
