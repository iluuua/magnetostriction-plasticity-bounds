# Индекс документов

| Файл | Назначение |
|---|---|
| `docs/al_relaxation_check.md` | Проверка baseline чистого Al. |
| `docs/al13fe4_relaxation_check.md` | Проверка standalone Fe4Al13 / Al13Fe4. |
| `docs/interface_plan.md` | План безопасной сборки плоской границы. |
| `docs/interface_mismatch_candidates.md` | Ранжирование low-index Al/Fe4Al13 in-plane supercell mismatch. |
| `docs/interface_trial_001_check.md` | Проверка первого unloaded flat interface trial_001 после minimization. |
| `docs/interface_trial_001_nvt_check.md` | Проверка короткого unloaded NVT 300 K для interface trial_001. |
| `docs/interface_trial_001_unloaded_diagnostics.md` | Unloaded local stress/strain diagnostics для trial_001 после NVT. |
| `docs/interface_trial_001_time_averaged_stress.md` | Longer unloaded NVT и time-averaged local stress profile для trial_001. |
| `docs/interface_trial_001_warning_pairs_check.md` | Инспекция Al-Fe warning pair после long NVT для trial_001. |
| `docs/interface_trial_001_contact_density_check.md` | Проверка contact density apparent OVITO gaps для trial_001. |
| `docs/interface_trial_001_loading_design.md` | Дизайн будущего controlled loading без запуска stress-сценария. |
| `docs/interface_trial_001_stress_000_060mpa_check.md` | Проверка первых реальных 0 MPa control и 60 MPa compression-ramp runs. |
| `docs/interface_trial_001_stress_120mpa_check.md` | Проверка 120 MPa compression-ramp controlled sanity-run. |
| `docs/interface_trial_001_stress_147mpa_check.md` | Проверка 147 MPa compression-ramp controlled sanity-run после OVITO review. |
| `docs/60_milestones/2026-05-09_interface_trial_001_minimized.md` | Milestone-артефакт по сборке и minimization интерфейса trial_001. |
| `docs/60_milestones/2026-05-09_interface_trial_001_nvt_300k.md` | Milestone-артефакт по unloaded NVT 300 K для trial_001. |
| `docs/60_milestones/2026-05-09_interface_trial_001_unloaded_diagnostics.md` | Milestone-артефакт по unloaded diagnostics для trial_001. |
| `docs/60_milestones/2026-05-10_interface_trial_001_time_averaged_unloaded_stress.md` | Milestone-артефакт по time-averaged unloaded stress для trial_001. |
| `docs/60_milestones/2026-05-10_interface_trial_001_warning_pair_inspection.md` | Milestone-артефакт по инспекции warning pair после long NVT. |
| `docs/60_milestones/2026-05-10_interface_trial_001_contact_density_check.md` | Milestone-артефакт по contact-density проверке apparent gaps. |
| `docs/60_milestones/2026-05-10_interface_trial_001_loading_design.md` | Milestone-артефакт по подготовке loading design/templates. |
| `docs/60_milestones/2026-05-10_interface_trial_001_stress_000_060mpa_sanity.md` | Milestone-артефакт по 0/60 MPa sanity runs. |
| `docs/60_milestones/2026-05-11_interface_trial_001_stress_120mpa_sanity.md` | Milestone-артефакт по 120 MPa sanity run. |
| `docs/60_milestones/2026-05-11_interface_trial_001_stress_147mpa_sanity.md` | Milestone-артефакт по 147 MPa sanity run. |
| `docs/60_milestones/2026-06-11_gpu_meam_kokkos_cuda_neighbor_check_workaround.md` | GPU MEAM/KOKKOS CUDA debug milestone: sanitizer root cause and approved neighbor-check workaround. |
| `docs/60_milestones/2026-06-11_gpu_grid_runner_started.md` | GPU grid runner milestone: config-driven production sweep runner started under `runs/stage_sweep_gpu_grid/20260611-175339`. |
| `docs/60_milestones/2026-06-14_stageB_postrun_branching_pipeline.md` | Stage B post-run decision, 500k confirmation, and no-dislocation branch milestone. |
| `docs/60_milestones/2026-06-15_visualization_event_pipeline.md` | Stage B event timeline, event-window, OVITO render manifest, static figure, and 30 FPS video pipeline milestone. |
| `docs/60_milestones/2026-06-15_focus_5_6_transition.md` | Safe transition milestone for preserving completed Stage B cases and preparing the focused nearGB vacancies 5-6 run. |
| `docs/60_milestones/2026-06-15_focus_5_6_operator_stop_and_launch.md` | Operator stop-and-launch milestone for stopping the old Stage B queue and starting the focused nearGB vacancies 5-6 run. |
| `docs/60_milestones/2026-06-16_stageC_1M_queue_plan.md` | Stage C 1M-class nearGB vacancies eps0100 queue plan, preflight, launch-after-focus command, and validation. |
| `docs/60_milestones/2026-06-17_stageC_1M_safe_prep_retry.md` | Stage C 1M safe-prep retry pagefile setup, preflight, prep-only launch, and monitoring handoff. |
| `docs/run_plans/stageB_postrun_decision_tree.md` | Operator decision tree for Stage B realism 100k post-run branching and dry-run commands. |
| `docs/paper/visualization_event_pipeline.md` | Operator and paper-traceability documentation for event detection, window selection, OVITO rendering, figures, video, and manifests. |
| `configs/stageB_nearGB_vacancies_focus_100k.template.yaml` | Focused Stage B config template for only `B3_nearGB_vacancies_medium_eps0025` and `B3_nearGB_vacancies_medium_eps0100`. |
| `configs/stageC_1M_nearGB_vacancies_eps0100_100k.template.yaml` | Stage C 1M-class config template for exactly one nearGB vacancies eps0100 case with 100k checkpoint. |
| `scripts/prepare_focus_5_6_transition.py` | Safe transition helper that writes completed-case manifests, safe-stop plan, focused run setup, and preflight artifacts without launching MD. |
| `scripts/prepare_stageC_1M_queue_plan.py` | Stage C 1M queue-preparation helper that writes effective config, preflight, volume estimate, command files, README, and report without launching MD. |
| `scripts/launch_stageC_1M_after_focus.py` | Stage C launch-after-focus guard that rechecks no active LAMMPS/focused runner before launching the prepared 1M command. |
| `scripts/launch_stageC_1M_safe_prep_retry.py` | Stage C safe-prep retry helper that records pagefile/resource/geometry preflight and launches only prep in a fresh root. |
| `agent_report_focus_5_6_operator_stop_and_launch.md` | Operator handoff report for the old queue stop, focused launch, initial runtime check, focused event dry-run, and validation. |
| `agent_report_stageC_1M_queue_plan.md` | Operator handoff report for the Stage C 1M queue root, blockers, launch command, continuation plan, event dry-run, and tests. |
| `results/tables/interface_mismatch_candidates.csv` | CSV-таблица mismatch-кандидатов. |
| `results/tables/interface_trial_001_unloaded_stress_profile.csv` | z-профиль unloaded virial stress для trial_001. |
| `results/tables/interface_trial_001_unloaded_strain_profile.csv` | z-профиль unloaded strain/displacement proxy для trial_001. |
| `results/tables/interface_trial_001_unloaded_atom_diagnostics.csv` | per-atom unloaded stress/strain proxy diagnostics для trial_001. |
| `results/tables/interface_trial_001_time_averaged_stress_profile.csv` | Time-averaged z-профиль unloaded virial stress для trial_001. |
| `results/tables/interface_trial_001_warning_pair_distance_over_time.csv` | Дистанция warning Al-Fe pair по long-NVT frames. |
| `results/tables/interface_trial_001_warning_pair_neighborhood.csv` | 4 A neighborhood around warning pair in final long-NVT data. |
| `results/tables/interface_trial_001_contact_density_z_profile.csv` | 1 A z-bin contact-density profile для apparent gap проверки. |
| `results/tables/interface_trial_001_loading_force_table.csv` | Расчёт force per atom для 0/60/120/147/200 MPa templates. |
| `results/tables/interface_trial_001_stress_000_060mpa_comparison.csv` | Сравнение 0 MPa control и 60 MPa compression-ramp sanity runs. |
| `results/tables/interface_trial_001_stress_000_060_120mpa_comparison.csv` | Сравнение 0 / 60 / 120 MPa controlled sanity runs. |
| `results/tables/interface_trial_001_stress_000_060_120_147mpa_comparison.csv` | Сравнение 0 / 60 / 120 / 147 MPa controlled sanity runs. |
| `results/tables/interface_trial_001_stress_000mpa_control_stress_profile.csv` | Time-averaged stress/atom z-profile для 0 MPa control. |
| `results/tables/interface_trial_001_stress_060mpa_compression_ramp_stress_profile.csv` | Time-averaged stress/atom z-profile для 60 MPa compression ramp. |
| `results/tables/interface_trial_001_stress_060mpa_warning_pair_distance_over_time.csv` | Дистанция warning pair 232-260 during 60 MPa run. |
| `results/tables/interface_trial_001_stress_060mpa_warning_pair_neighborhood.csv` | Neighborhood warning pair 232-260 after 60 MPa run. |
| `results/tables/interface_trial_001_stress_120mpa_compression_ramp_stress_profile.csv` | Time-averaged stress/atom z-profile для 120 MPa compression ramp. |
| `results/tables/interface_trial_001_stress_120mpa_warning_pair_distance_over_time.csv` | Дистанция warning pair 232-260 during 120 MPa run. |
| `results/tables/interface_trial_001_stress_147mpa_compression_ramp_stress_profile.csv` | Time-averaged stress/atom z-profile для 147 MPa compression ramp. |
| `results/tables/interface_trial_001_stress_147mpa_warning_pair_distance_over_time.csv` | Дистанция warning pair 232-260 during 147 MPa run. |
| `results/figures/interface_trial_001_unloaded_stress_profile.png` | PNG-график z-профиля unloaded virial stress. |
| `results/figures/interface_trial_001_unloaded_strain_profile.png` | PNG-график unloaded strain/displacement proxy. |
| `results/figures/interface_trial_001_time_averaged_stress_profile.png` | PNG-график time-averaged unloaded stress profile. |
| `results/figures/interface_trial_001_warning_pair_distance_over_time.png` | PNG-график warning-pair distance over time. |
| `results/figures/interface_trial_001_contact_density_z_profile.png` | PNG-график 1 A z-density profile для apparent gap проверки. |
| `results/figures/interface_trial_001_stress_000mpa_control_stress_profile.png` | PNG-график stress profile для 0 MPa control. |
| `results/figures/interface_trial_001_stress_060mpa_compression_ramp_stress_profile.png` | PNG-график stress profile для 60 MPa compression ramp. |
| `results/figures/interface_trial_001_stress_060mpa_warning_pair_distance_over_time.png` | PNG-график warning pair 232-260 during 60 MPa run. |
| `results/figures/interface_trial_001_stress_120mpa_compression_ramp_stress_profile.png` | PNG-график stress profile для 120 MPa compression ramp. |
| `results/figures/interface_trial_001_stress_120mpa_warning_pair_distance_over_time.png` | PNG-график warning pair 232-260 during 120 MPa run. |
| `results/figures/interface_trial_001_stress_147mpa_compression_ramp_stress_profile.png` | PNG-график stress profile для 147 MPa compression ramp. |
| `results/figures/interface_trial_001_stress_147mpa_warning_pair_distance_over_time.png` | PNG-график warning pair 232-260 during 147 MPa run. |
| `potentials/README.md` | Таблица потенциалов и проверенный MEAM `pair_coeff`. |
| `results/reports/run_report.md` | Главный отчёт по запуску 2026-05-09. |
| `.codex/state/current_context.md` | Короткий handoff текущего состояния. |

## 120 MPa loading

- `docs/interface_trial_001_stress_120mpa_check.md`
- `docs/60_milestones/2026-05-11_interface_trial_001_stress_120mpa_sanity.md`
- `results/tables/interface_trial_001_stress_000_060_120mpa_comparison.csv`
- `results/tables/interface_trial_001_stress_120mpa_compression_ramp_stress_profile.csv`
- `results/tables/interface_trial_001_stress_120mpa_warning_pair_distance_over_time.csv`
- `results/figures/interface_trial_001_stress_120mpa_compression_ramp_stress_profile.png`
- `results/figures/interface_trial_001_stress_120mpa_warning_pair_distance_over_time.png`
- `results/figures/ovito_review_120mpa/`

## 147 MPa loading

- `docs/interface_trial_001_stress_147mpa_check.md`
- `docs/60_milestones/2026-05-11_interface_trial_001_stress_147mpa_sanity.md`
- `results/tables/interface_trial_001_stress_000_060_120_147mpa_comparison.csv`
- `results/tables/interface_trial_001_stress_147mpa_compression_ramp_stress_profile.csv`
- `results/tables/interface_trial_001_stress_147mpa_warning_pair_distance_over_time.csv`
- `results/figures/interface_trial_001_stress_147mpa_compression_ramp_stress_profile.png`
- `results/figures/interface_trial_001_stress_147mpa_warning_pair_distance_over_time.png`
- `results/figures/ovito_review_147mpa/`

## 200 MPa loading

- `docs/interface_trial_001_stress_200mpa_check.md`
- `docs/60_milestones/2026-05-12_interface_trial_001_stress_200mpa_upper_bound.md`
- `results/tables/interface_trial_001_stress_000_060_120_147_200mpa_comparison.csv`
- `results/tables/interface_trial_001_stress_200mpa_compression_ramp_stress_profile.csv`
- `results/tables/interface_trial_001_stress_200mpa_warning_pair_distance_over_time.csv`
- `results/tables/interface_trial_001_stress_200mpa_warning_pair_neighborhood.csv`
- `results/figures/interface_trial_001_stress_200mpa_compression_ramp_stress_profile.png`
- `results/figures/interface_trial_001_stress_200mpa_warning_pair_distance_over_time.png`
- `results/figures/ovito_review_200mpa/`

## Ellipsoid inclusion baseline

- `structures/interface/ellipsoid_inclusion/trial_001/data.ellipsoid_trial_001`
- `lammps/04_ellipsoid_inclusion/trial_001/00_minimize/data.ellipsoid_minimized`
- `lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/data.ellipsoid_nvt_300k`
- `lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/dump.ellipsoid_nvt_300k.lammpstrj`
- `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_nvt_300k_distance_report.json`
- `docs/ellipsoid_inclusion/ellipsoid_trial_001_nvt_300k_baseline.md`

## Ellipsoid inclusion eigenstrain series

- `docs/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_check.md`
- `results/tables/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_summary.csv`
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_energy_final.png`
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_min_pair_distance.png`
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_alfe_warning_pairs.png`
- `results/figures/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_force_two_norm_final.png`

## GPU MEAM/KOKKOS CUDA runtime

- `docs/60_milestones/2026-06-11_gpu_meam_kokkos_cuda_neighbor_check_workaround.md`
- `docs/60_milestones/2026-06-11_gpu_grid_runner_started.md`
- `docs/60_milestones/2026-06-14_stageB_postrun_branching_pipeline.md`
- `docs/60_milestones/2026-06-15_visualization_event_pipeline.md`
- `docs/60_milestones/2026-06-15_focus_5_6_transition.md`
- `docs/60_milestones/2026-06-15_focus_5_6_operator_stop_and_launch.md`
- `docs/60_milestones/2026-06-16_stageC_1M_queue_plan.md`
- `docs/60_milestones/2026-06-17_stageC_1M_safe_prep_retry.md`
- `docs/run_plans/stageB_postrun_decision_tree.md`
- `docs/paper/visualization_event_pipeline.md`
- `configs/stageB_nearGB_vacancies_focus_100k.template.yaml`
- `configs/stageC_1M_nearGB_vacancies_eps0100_100k.template.yaml`
- `scripts/prepare_focus_5_6_transition.py`
- `scripts/prepare_stageC_1M_queue_plan.py`
- `scripts/launch_stageC_1M_after_focus.py`
- `scripts/launch_stageC_1M_safe_prep_retry.py`
- `agent_report_focus_5_6_transition.md`
- `agent_report_focus_5_6_operator_stop_and_launch.md`
- `agent_report_stageC_1M_queue_plan.md`
- `runs/gpu_debug/20260611-151634/debug_report.md`
- `runs/gpu_debug/20260611-151634/gpu_fix_success_report.md`
- `runs/gpu_debug/20260611-151634/gpu_debug_decision.json`
- `runs/stage_sweep_gpu_grid/20260611-175339/final_report.md`
- `runs/stage_sweep_gpu_grid/20260611-175339/state.json`

## Article-ready checkpoint

- `docs/article/article_results_draft.md`
- `docs/article/figure_plan.md`
- `docs/article/article_checklist.md`
- `results/tables/article/article_key_results_summary.csv`
- `docs/60_milestones/2026-05-14_article_ready_checkpoint.md`

## Final article draft pack

- `docs/article/final_manuscript_v1.md`
- `docs/article/references.md`
- `docs/article/eigenstrain_model.md`
- `results/tables/article/simulation_parameters_summary.csv`
