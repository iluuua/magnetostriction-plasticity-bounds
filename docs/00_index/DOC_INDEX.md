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
