# GPU grid sweep final report

Generated: 2026-06-16T23:10:57
Run root: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageB_nearGB_vacancies_focus_100k\20260615-215533`

## Git Status

```text
M .codex/state/current_context.md
 M docs/00_index/DOC_INDEX.md
?? analysis/python/event_pipeline/
?? analysis/python/science_optimizer/
?? analysis/python/stage_runner/
?? configs/
?? docs/60_milestones/2026-06-11_gpu_grid_runner_started.md
?? docs/60_milestones/2026-06-11_gpu_meam_kokkos_cuda_neighbor_check_workaround.md
?? docs/60_milestones/2026-06-14_stageB_postrun_branching_pipeline.md
?? docs/60_milestones/2026-06-15_focus_5_6_operator_stop_and_launch.md
?? docs/60_milestones/2026-06-15_focus_5_6_transition.md
?? docs/60_milestones/2026-06-15_visualization_event_pipeline.md
?? docs/60_milestones/2026-06-16_stageC_1M_queue_plan.md
?? docs/paper/
?? docs/run_plans/layered_multifidelity_optimizer_architecture.md
?? docs/run_plans/pipeline_rnd_stageB_v2_strategy.md
?? docs/run_plans/production_pipeline_master_plan.md
?? docs/run_plans/stageB_postrun_decision_tree.md
?? docs/run_plans/stage_B_inclusion_design_grid_plan.md
?? monitor_snapshots/
?? scripts/
?? stageB_500k_confirmation_plan.md
?? stageB_500k_confirmation_preflight.md
?? stageB_cyclic_eigenstrain_plan.md
?? stageB_no_dislocation_branch_plan.md
?? stageB_platelet_inclusion_plan.md
?? stageB_positive_control_plan.md
?? stageB_seeded_defect_plan.md
?? status_dump_20260616_020108.txt
?? tests/
```

## Changed Files

- ` M .codex/state/current_context.md`
- ` M docs/00_index/DOC_INDEX.md`
- `?? analysis/python/event_pipeline/`
- `?? analysis/python/science_optimizer/`
- `?? analysis/python/stage_runner/`
- `?? configs/`
- `?? docs/60_milestones/2026-06-11_gpu_grid_runner_started.md`
- `?? docs/60_milestones/2026-06-11_gpu_meam_kokkos_cuda_neighbor_check_workaround.md`
- `?? docs/60_milestones/2026-06-14_stageB_postrun_branching_pipeline.md`
- `?? docs/60_milestones/2026-06-15_focus_5_6_operator_stop_and_launch.md`
- `?? docs/60_milestones/2026-06-15_focus_5_6_transition.md`
- `?? docs/60_milestones/2026-06-15_visualization_event_pipeline.md`
- `?? docs/60_milestones/2026-06-16_stageC_1M_queue_plan.md`
- `?? docs/paper/`
- `?? docs/run_plans/layered_multifidelity_optimizer_architecture.md`
- `?? docs/run_plans/pipeline_rnd_stageB_v2_strategy.md`
- `?? docs/run_plans/production_pipeline_master_plan.md`
- `?? docs/run_plans/stageB_postrun_decision_tree.md`
- `?? docs/run_plans/stage_B_inclusion_design_grid_plan.md`
- `?? monitor_snapshots/`
- `?? scripts/`
- `?? stageB_500k_confirmation_plan.md`
- `?? stageB_500k_confirmation_preflight.md`
- `?? stageB_cyclic_eigenstrain_plan.md`
- `?? stageB_no_dislocation_branch_plan.md`
- `?? stageB_platelet_inclusion_plan.md`
- `?? stageB_positive_control_plan.md`
- `?? stageB_seeded_defect_plan.md`
- `?? status_dump_20260616_020108.txt`
- `?? tests/`

## Config-Driven Proof

- Sweep stages, atom targets, eps values, steps, GPU args, rewrites, gates, resource thresholds, and analysis settings come from `effective_config.yaml`.
- Python iterates `stages` from YAML and does not carry hardcoded eps or atom-target sweep lists.

## Effective GPU Profile

- executable: `B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe`
- args: `-k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off`
- forbidden env removed from child process: `CUDA_LAUNCH_BLOCKING`
- production confirmation: `CUDA_LAUNCH_BLOCKING` is not placed in command lines and is removed from the LAMMPS child environment.
- neighbor workaround: `neigh_modify    delay 0 every 10 check no`
- risk: Dangerous builds are not checked with `check no`; this is a validated run-local workaround, not an upstream source fix.

## Stage Status

| stage | status | selected_target | science_signal |
| --- | --- | --- | --- |
| B3_nearGB_vacancies_focus_100k | success | stageB_100k | True |

## Runtime Summary

- recorded cases: 6
- successful cases: 6
- stopped reason: `None`

## Escalation Decision

All enabled configured stages completed.

## Next Recommended Scientific Action

- Continue the gated run until A1_medium production and analysis determine whether A2 is justified.
- Report the KOKKOS neighbor-check CUDA bug upstream with the sanitizer root cause and validated workaround.
