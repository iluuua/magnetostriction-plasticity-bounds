# Stage F Codex recovery preflight

- Timestamp: 2026-06-30T05:00:48+03:00
- Repo: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe`
- Branch: `ilua/auto/stageD-local-interface-100k-mechanics`
- Current run root: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748`
- Python: `Python 3.12.5`
- `prepare_stageF_boundary_patch_geometry.py` py_compile: `0`
- `stageF_boundary_stress_decay.py` py_compile: `0`

## Git status
```text
M .codex/state/current_context.md
 M analysis/python/stage_runner/analysis_runner.py
 M analysis/python/stage_runner/gpu_grid.py
 M docs/00_index/DOC_INDEX.md
?? analysis/python/stageF_boundary_stress_decay.py
?? configs/stageD_local_interface_100k_mechanics.template.yaml
?? configs/stageE_250k_single_physical_longrun.template.yaml
?? configs/stageE_700k_dxa_confirm.template.yaml
?? configs/stageE_homogeneous_inclusion_scaleup.template.yaml
?? diagnostics/
?? docs/60_milestones/2026-06-18_stageD_local_interface_100k_prepare.md
?? docs/60_milestones/2026-06-22_stageE_homogeneous_inclusion_scaleup.md
?? docs/60_milestones/2026-06-23_stageE_250k_single_physical_longrun.md
?? docs/60_milestones/2026-06-25_stageE_700k_dxa_confirm_launch.md
?? docs/reports/figures/
?? docs/reports/physicist_last_meeting_action_plan.md
?? docs/reports/renders/
?? docs/reports/stageE_700k_full_analysis_report_ru.md
?? docs/reports/stageE_700k_full_analysis_with_temporal_evolution_ru.md
?? docs/reports/stageE_700k_temporal_defect_atoms.png
?? docs/reports/stageE_700k_temporal_dislocation_length.png
?? docs/reports/stageE_700k_temporal_evolution_report_ru.md
?? docs/reports/stageE_700k_temporal_evolution_summary.json
?? docs/reports/stageE_700k_temporal_evolution_table.csv
?? docs/reports/stageE_700k_temporal_hcp_atoms.png
?? docs/reports/stageE_dxa_confirmation_candidate_runs.disabled.json
?? docs/reports/stageE_dxa_confirmation_hypotheses_and_run_plan_ru.md
?? docs/reports/stageE_physics_report_for_pshonkin_ru.md
?? docs/reports/stageE_physics_report_for_pshonkin_ru.pdf
?? docs/reports/stageE_physics_report_for_pshonkin_ru.tex
?? docs/reports/stageF_F0_commensurate_ppf_atom_count_consistency.md
?? docs/reports/stageF_F0_commensurate_ppf_common_cell_audit.json
?? docs/reports/stageF_F0_commensurate_ppf_common_cell_audit.md
?? docs/reports/stageF_F0_commensurate_ppf_common_cell_fix_plan.md
?? docs/reports/stageF_F0_commensurate_ppf_file_inventory.json
?? docs/reports/stageF_F0_commensurate_ppf_file_inventory.md
?? docs/reports/stageF_F0_commensurate_ppf_input_path_validation.json
?? docs/reports/stageF_F0_commensurate_ppf_input_path_validation.md
?? docs/reports/stageF_F0_commensurate_ppf_log_parse_report.md
?? docs/reports/stageF_F0_commensurate_ppf_log_parse_summary.json
?? docs/reports/stageF_F0_commensurate_ppf_production_report.md
?? docs/reports/stageF_F0_commensurate_ppf_production_summary.json
?? docs/reports/stageF_F0_commensurate_ppf_smoke10k_report.md
?? docs/reports/stageF_F0_commensurate_ppf_smoke10k_summary.json
?? docs/reports/stageF_F0_planar_100A_commensurate_ppf_design.md
?? docs/reports/stageF_F0_planar_100A_completion_failure_report.md
?? docs/reports/stageF_F0_planar_100A_file_inventory.json
?? docs/reports/stageF_F0_planar_100A_file_inventory.md
?? docs/reports/stageF_F0_planar_100A_forensic_decision_report.md
?? docs/reports/stageF_F0_planar_100A_geometry_check.md
?? docs/reports/stageF_F0_planar_100A_geometry_failure_report.md
?? docs/reports/stageF_F0_planar_100A_geometry_mmf_fix_report.md
?? docs/reports/stageF_F0_planar_100A_geometry_summary.json
?? docs/reports/stageF_F0_planar_100A_gpu_zero_forensic_precheck.md
?? docs/reports/stageF_F0_planar_100A_launch_preflight.md
?? docs/reports/stageF_F0_planar_100A_log_parse_report.md
?? docs/reports/stageF_F0_planar_100A_log_parse_summary.json
?? docs/reports/stageF_F0_planar_100A_production_launch_status.md
?? docs/reports/stageF_F0_planar_100A_production_launch_summary.json
?? docs/reports/stageF_F0_planar_100A_smoke_report.md
?? docs/reports/stageF_F0_planar_100A_smoke_summary.json
?? docs/reports/stageF_boundary_stress_decay_report_ru.md
?? docs/reports/stageF_boundary_stress_decay_stderr.log
?? docs/reports/stageF_boundary_stress_decay_stdout.log
?? docs/reports/stageF_boundary_stress_decay_summary.json
?? docs/reports/stageF_boundary_stress_decay_table.csv
?? docs/reports/stageF_codex_recovered_state.json
?? docs/reports/stageF_codex_recovered_state.md
?? docs/reports/stageF_codex_recovery_preflight.json
?? docs/reports/stageF_codex_recovery_preflight.md
?? docs/reports/stageF_event_timeline.csv
?? docs/reports/stageF_event_timeline_report_ru.md
?? docs/reports/stageF_physics_meeting_alignment_ru.md
?? docs/run_plans/stageF_boundary_patch_plan_ru.md
?? lammps/stageF_boundary_patch/
?? pr_body.md
?? scripts/analyze_stageD_postrun.py
?? scripts/analyze_stageE_700k_temporal_evolution.py
?? scripts/analyze_stageE_v2_final.py
?? scripts/make_common_cell_eps00194.py
?? scripts/prepare_stageD_local_interface_100k.py
?? scripts/prepare_stageE_homogeneous_inclusion_scaleup.py
?? scripts/prepare_stageF_boundary_patch_geometry.py
?? scripts/run_stageE_250k_single_physical_longrun.py
?? scripts/run_stageE_700k_dxa_confirm.py
?? scripts/run_stageE_smoke_then_full.py
?? scripts/run_stageE_v2_stabilized.py
?? scripts/stageF_codex_recovery_reporter.py
?? scripts/validate_stageF_input_paths.py
?? scripts/watch_stageC_safe_prep.ps1
?? structures/stageF_boundary_patch/
```

## Active LAMMPS / Stage F processes
```text
[
    {
        "ProcessId":  8004,
        "Name":  "python.exe",
        "CommandLine":  "\"C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\.venv\\Scripts\\python.exe\" scripts\\stageF_codex_recovery_reporter.py"
    },
    {
        "ProcessId":  4792,
        "Name":  "python.exe",
        "CommandLine":  "\"C:\\Users\\dille\\AppData\\Local\\Programs\\Python\\Python312\\python.exe\" scripts\\stageF_codex_recovery_reporter.py"
    }
]
```

## GPU
```text
2026/06/30 05:00:47.286, NVIDIA GeForce RTX 3060, 6 %, 1388 MiB, 12288 MiB
```

## Disk C
```text
{
    "Name":  "C",
    "Used":  220760379392,
    "Free":  28606914560,
    "Root":  "C:\\"
}
```

## Immediate conclusion
No active LAMMPS/Stage F process remains. GPU is not occupied by LAMMPS compute. The sequence is blocked after `eps00194` smoke failed with `cudaErrorIllegalAddress` at step 0; production and delta-analysis were not launched.
