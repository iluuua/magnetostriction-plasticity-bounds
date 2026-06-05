# Uncommitted file inventory

Companion to `uncommitted_inventory.csv` (131 rows: 127 untracked + 4 modified tracked).
Classification was produced by a one-off git-metadata aggregator (no physics, no simulation).
Date: 2026-06-04.

## Summary by commit decision

| should_commit | files | total size | what it is |
|---|---:|---:|---|
| **yes**   | 74 | **1.1 MB** | all docs, analysis scripts, CSV tables, PNG figures, LAMMPS inputs/logs, JSON summaries |
| **maybe** | 11 | 30.7 MB | `data.*` LAMMPS structure files (minimized / relaxed / eigenstrain) |
| **no**    | 46 | 105.2 MB | 11 raw `.lammpstrj` dumps (99.4 MB) + 35 `.xyz` visual-debug slices (5.8 MB) |

## Summary by type

| files | size | type | default action |
|---:|---:|---|---|
| 11 | 99.4 MB | LAMMPS dump trajectory (raw `.lammpstrj`) | **do not** plain-commit; Git LFS or keep local |
| 11 | 30.7 MB | LAMMPS data structure (raw `data.*`) | decide: LFS or keep local |
| 35 |  5.8 MB | XYZ visual-debug slices | keep local / regenerable |
| 11 |  0.8 MB | PNG figure | commit |
|  4 |  0.1 MB | tracked doc/report (modified) | commit (documentation update) |
| 11 |  ~0 MB  | Python analysis/build scripts | commit |
|  7 |  ~0 MB  | CSV results table | commit |
| 11 |  ~0 MB  | markdown docs (article 7 / ellipsoid 3 / milestone 2 / check 1, minus overlap) | commit |
| 16 |  ~0 MB  | JSON summaries + LAMMPS inputs + logs | commit |

## High-relevance untracked files (commit candidates — scientific record)

**Article pack** (`docs/article/`, all untracked):
`final_manuscript_v1.md`, `article_results_draft.md`, `eigenstrain_model.md`, `figure_plan.md`,
`references.md`, `article_checklist.md`, `selected_figures_checklist.md`.

**200 MPa flat-interface branch:**
`docs/interface_trial_001_stress_200mpa_check.md`,
`docs/60_milestones/2026-05-12_interface_trial_001_stress_200mpa_upper_bound.md`,
`results/tables/interface_trial_001_stress_000_060_120_147_200mpa_comparison.csv`,
`results/tables/interface_trial_001_stress_200mpa_*.csv` (3),
the 5 `lammps/03_interface_stress/stress_200mpa/.../*.json` summaries,
2 × `results/figures/interface_trial_001_stress_200mpa_*.png`.

**Ellipsoid inclusion branch:**
`docs/ellipsoid_inclusion/*.md` (3), `docs/60_milestones/2026-05-14_article_ready_checkpoint.md`,
11 × `analysis/python/*ellipsoid*/*eigenstrain*.py`, the eigenstrain series summary + 5 distance
report JSON, 4 × `results/figures/ellipsoid_inclusion/*.png`, structure build-report JSON.

**Article-selected figures** (`results/figures/article_selected/`): figures 2–6 present.
**NB:** the selected-figures checklist also lists `figure_1b/1c/1d_*.png`, which are **absent**
from disk (only figures 2–6 exist). Flagged in `repo_consistency_report.md`.

## Large raw artifacts (NOT commit candidates without an explicit decision)

| file | size |
|---|---:|
| `lammps/04_ellipsoid_inclusion/trial_001/01_nvt_300k/dump.ellipsoid_nvt_300k.lammpstrj` | 79 MB |
| `lammps/04_ellipsoid_inclusion/trial_001/00_minimize/dump.ellipsoid_minimize.lammpstrj` | 7.6 MB |
| `.../02_eigenstrain_relax/epsz_p0p00500_minimize/dump.*.lammpstrj` | 4.6 MB |
| 4 × `structures/.../eigenstrain/.../data.ellipsoid_eigenstrain_*` | 4 × 3.0 MB |
| `lammps/.../01_nvt_300k/data.ellipsoid_nvt_300k` + 4 × eigenstrain minimized `data.*` | ~3.1 MB each |
| 35 × `*.xyz` visual-debug slices | 5.8 MB total |

These are reproducible from the committed inputs + scripts. Recommended handling in
`git_commit_plan.md`: Git LFS for the `data.*` structures one may want to redistribute, keep
`.lammpstrj` and `.xyz` local or LFS, and add a `.gitignore`. **Do not delete them.**

## Modified tracked files (4)

| file | change | commit? |
|---|---|---|
| `README.md` | +14 lines: "Final loading-series checkpoint" (0/60/120/147/200 MPa, OVITO, caveat) | yes (doc update) |
| `docs/00_index/DOC_INDEX.md` | +45 lines: 200 MPa, ellipsoid baseline, eigenstrain, article sections | yes (doc update) |
| `results/reports/run_report.md` | +57 lines: final loading-series + eigenstrain + article-ready | yes (doc update) |
| `.codex/state/current_context.md` | rewritten: 147 MPa handoff → ellipsoid baseline handoff | yes (handoff state) |

## Tracked garbage (separate from the uncommitted set)

`.DS_Store` (×5) and `analysis/python/__pycache__/*.pyc` (×15) are **already committed**. They
are not in the uncommitted set but should be removed from tracking — see `git_commit_plan.md`.
