# Git commit plan (PLAN ONLY — nothing is committed)

Date: 2026-06-04. This is a proposal. **No `git add`, `git commit`, `git rm`, or `.gitignore`
write has been performed.** Execute only after explicit user approval, and never with `git add -A`.

Context: 232 MB working tree, 179 MB in `lammps/`. The committable scientific record is only
~1.1 MB (74 files). The rest is 136 MB of raw dumps/structures that need an explicit storage
decision. See `uncommitted_inventory.csv`.

---

## Commit candidate 1 — documentation / article (NEW, this audit)
~Tiny. Safe to commit.
```
docs/audit/local_repo_audit_initial.md
docs/audit/uncommitted_inventory.md
docs/audit/uncommitted_inventory.csv
docs/audit/source_map.md
docs/audit/claims_register.md
docs/audit/claims_register.csv
docs/audit/repo_consistency_report.md
docs/audit/git_commit_plan.md
docs/article/current_project_picture_ru.md
docs/article/article_ru.md
docs/article/article_en.md
docs/article/figures_tables_plan.md
docs/article/teacher_brief_ru.md
docs/article/final_manuscript_v2.md            # if produced
```
Suggested message: `docs: add forensic audit, claims register, and full-reality RU/EN article pack`

## Commit candidate 2 — scientific source docs (untracked, important)
```
docs/interface_trial_001_stress_200mpa_check.md
docs/60_milestones/2026-05-12_interface_trial_001_stress_200mpa_upper_bound.md
docs/60_milestones/2026-05-14_article_ready_checkpoint.md
docs/ellipsoid_inclusion/ellipsoid_trial_001_nvt_300k_baseline.md
docs/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_series_check.md
docs/ellipsoid_inclusion/ellipsoid_trial_001_eigenstrain_epsz_p0p00250_check.md
docs/article/{final_manuscript_v1,article_results_draft,eigenstrain_model,figure_plan,references,article_checklist,selected_figures_checklist}.md
```
Plus the 4 modified tracked docs (README, DOC_INDEX, run_report, current_context).
Message: `docs: record 200 MPa upper-bound, ellipsoid eigenstrain branch, and article checkpoint`

## Commit candidate 3 — source analysis scripts (11 untracked .py)
```
analysis/python/{apply_ellipsoid_eigenstrain,build_ellipsoid_inclusion_trial,
check_eigenstrain_minimized_sanity,check_ellipsoid_nvt_sanity,collect_eigenstrain_series_summary,
make_eigenstrain_visual_debug,make_ellipsoid_nvt_visual_debug,make_ellipsoid_visual_debug,
make_one_eigenstrain_input,plot_ellipsoid_eigenstrain_series,run_eigenstrain_series}.py
```
Message: `analysis: add ellipsoid inclusion + eigenstrain build/check/plot scripts`

## Commit candidate 4 — result tables (CSV + small JSON, ~tiny)
```
results/tables/article/{article_key_results_summary,simulation_parameters_summary}.csv
results/tables/ellipsoid_inclusion/*.csv + *.json     (series summary + 5 distance reports)
results/tables/interface_trial_001_stress_000_060_120_147_200mpa_comparison.csv
results/tables/interface_trial_001_stress_200mpa_*.csv (3)
```

## Commit candidate 5 — figures (PNG, ~0.8 MB)
```
results/figures/article_selected/figure_2..6_*.png
results/figures/ellipsoid_inclusion/*.png  (4)
results/figures/interface_trial_001_stress_200mpa_*.png (2)
```

## Commit candidate 6 — LAMMPS inputs + log summaries (small, reproducibility)
```
lammps/03_interface_stress/stress_200mpa/run_001_compression_ramp/*.json  (5 summaries)
lammps/04_ellipsoid_inclusion/**/in.*      (LAMMPS input decks)
lammps/04_ellipsoid_inclusion/**/log.*     (run logs)
structures/interface/ellipsoid_inclusion/trial_001/**/*.json  (build/metadata reports)
```
Keep inputs/logs/summaries (text, small); they make runs reproducible. Excludes `data.*`/`*.lammpstrj`.

---

## DO NOT COMMIT (plain git)
- `*.lammpstrj` raw dumps — 11 files, **99.4 MB** (one is 79 MB).
- `*.xyz` visual-debug slices — 35 files, 5.8 MB (regenerable from `data.*` + scripts).
- `.DS_Store` (×5) and `analysis/python/__pycache__/*.pyc` (×15) — already tracked; remove from tracking.

## Tracked-garbage remediation (separate housekeeping commit)
```
git rm --cached .DS_Store lammps/.DS_Store potentials/.DS_Store structures/.DS_Store structures/converted/.DS_Store
git rm --cached analysis/python/__pycache__/*.pyc
# then commit the .gitignore below
```
This untracks them without deleting the working-tree copies and without rewriting history.
(Optional history purge with `git filter-repo` is a separate, higher-risk decision — not recommended now.)

## Proposed `.gitignore` (review before applying — it must not hide important data)
```gitignore
# OS / editor
.DS_Store
# Python
__pycache__/
*.pyc
# Large raw MD artifacts (tracked via LFS or kept local — see decision below)
*.lammpstrj
# Visualization scratch (regenerable)
**/visual_debug/*.xyz
```
**Caution:** ignoring `*.lammpstrj` and `data.*` means they live only locally unless LFS is set
up. Do not add these patterns until the storage decision (below) is made, or you risk silently
excluding the only copy of raw data.

---

## NEED USER DECISION — large raw artifacts (136 MB)

| Option | What | Pros | Cons |
|---|---|---|---|
| **A. Git LFS** | track `*.lammpstrj` + `data.*` via LFS | full provenance, reproducible, in-repo | needs LFS setup; GitHub LFS quota; clone size |
| **B. Keep local + .gitignore** | commit only inputs/logs/summaries; raw stays on disk | small clean repo; raw never lost locally | raw not shared; reviewer can't re-derive figures without rerun |
| **C. External artifact store** | push raw to Zenodo/Drive/S3, link a DOI/URL in docs | citeable archive, small repo | manual upload; external dependency |
| **D. Selective** | LFS only the reusable `data.*` baselines; ignore `.lammpstrj`/`.xyz` | balance of size and reuse | partial reproducibility |

Recommendation to discuss: **D** (LFS the key `data.*` baselines that others might reuse; keep
`.lammpstrj`/`.xyz` local or in an external archive) — but this is the user's call. **Until a
decision is made, do not run any `git add` that would sweep in the 99 MB dumps.**

## Safety
This file is a plan. Commit only on explicit approval. Never `git add -A` here — it would stage
136 MB of raw data and the tracked-garbage files in one shot.
