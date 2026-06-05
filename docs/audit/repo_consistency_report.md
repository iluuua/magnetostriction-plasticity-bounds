# Repository consistency report

Date: 2026-06-04. Compares README, `DOC_INDEX.md`, milestone/check docs, `current_context.md`
and the actual working tree. No files were changed. Answers the 10 consistency questions.

## 1. Does the README match current data?
Partly. The **working-tree** README (uncommitted +14 lines) added a "Final loading-series
checkpoint" covering 0/60/120/147/200 MPa with the correct caveat — so it now matches the flat
branch. **Gaps:** (a) the README's main framing still names "120 MPa" as the base scenario
(§4 table, §5 hypothesis) although reality spans 0–200 MPa; (b) the README does **not** document
the ellipsoid eigenstrain **series** at all (the added section is loading-only). The **committed**
README lacks the 200 MPa checkpoint entirely.

## 2. Does `DOC_INDEX.md` list all important documents?
Working-tree DOC_INDEX (uncommitted +45 lines) now lists 200 MPa, ellipsoid baseline, eigenstrain
series, article-ready checkpoint and the final article pack. **Missing from the index:**
`docs/article/selected_figures_checklist.md`; the milestones
`docs/60_milestones/2026-05-09_al_fe_phase_baseline.md` and `..._interface_mismatch_scan.md`;
and (once created) the `docs/audit/*` files.

## 3. Important local files not referenced in the index
`selected_figures_checklist.md`, the two 2026-05-09 milestones above, and the new `docs/audit/`
deliverables. Also several Branch-1 diagnostic tables (unloaded strain/atom diagnostics) are
indexed, but the **ellipsoid distance-report JSONs** are only partially indexed.

## 4. Docs that say "not run" while results already exist  ⚠️
**Yes — multiple historical statements are now stale** (they were correct when written, but a
naive reader sees a contradiction):
- `docs/interface_trial_001_loading_design.md`: "120 MPa has still not been run" (it later ran).
- `docs/interface_trial_001_check.md`: "Stress-сценарии … пока не запускать" (later run).
- `docs/interface_trial_001_stress_147mpa_check.md`: "200 MPa: not run" (later run — see 200 check).
- `docs/interface_mismatch_candidates.md`: "120 MPa пока не применять" (later applied).

**Resolution:** these are time-ordered progress notes, not errors. The article must take state
from the **latest** sources (200 MPa check, 2026-05-14 article-ready checkpoint), not from these
earlier "not run" lines. Do not edit the historical docs; treat newest-wins.

## 5. Contradiction on 120 / 147 / 200 MPa?
No true contradiction, but two coexisting comparison tables:
`...000_060_120_147mpa_comparison.csv` (committed, no 200) and
`...000_060_120_147_200mpa_comparison.csv` (uncommitted, with 200). The article should cite the
**000–200** table as current and treat the 147-only table as superseded.

## 6. Divergence between `current_context.md`, README, milestones?
Each is internally correct but topic-scoped: `current_context.md` (working tree) describes the
**ellipsoid NVT baseline** (most recent single-topic handoff); README's checkpoint describes the
**flat loading series**; the **2026-05-14 article-ready checkpoint** is the unifying document
covering both branches. **Single source of truth for current state = the 2026-05-14 checkpoint.**

## 7. Files that should be added to the index
`docs/audit/*` (8 new), `docs/article/{current_project_picture_ru,article_ru,article_en,figures_tables_plan,teacher_brief_ru}.md`
(5 new), `docs/article/selected_figures_checklist.md`, the two 2026-05-09 milestones.

## 8. Files that must NOT be touched
All raw scientific artifacts: `*.lammpstrj` dumps, `data.*` structures, `log.*` logs,
`results/tables/*`, `results/figures/*`, `structures/*`, and the existing `docs/article/final_manuscript_v1.md`
(it is the article base — extend via a new v2, never overwrite v1).

## 9. What should be committed later (separate commit) — see `git_commit_plan.md`
The ~1.1 MB of committable docs/scripts/tables/figures/inputs/summaries, grouped by category.

## 10. What should go into `.gitignore`
`.DS_Store`, `__pycache__/`, `*.pyc`, and a decided policy for `*.lammpstrj` and large `data.*`.
See `git_commit_plan.md`.

---

## Additional defects found (flag, do not auto-fix)

- **⚠️ Missing OVITO screenshots.** `DOC_INDEX.md` and the 120/147/200 check docs reference
  `results/figures/ovito_review_{120,147,200}mpa/` folders that **do not exist on disk**. The
  manual OVITO review happened, but the screenshots were never saved. The article must say "manual
  review only; screenshots to be attached" — never cite these as present files (claim U07).
- **⚠️ Missing selected figures.** `selected_figures_checklist.md` marks Figures 1B/1C/1D as done
  and lists `results/figures/article_selected/figure_1b/1c/1d_*.png`, but only Figures **2–6**
  exist in `article_selected/`. Figure 1 (geometry) is **not** rendered yet.
- **⚠️ Terminology conflict.** Ellipsoid metadata key `ellipsoid_axes_A` = 12×12×24 Å, but
  `final_manuscript_v1.md` and `simulation_parameters_summary.csv` call these "semi-axes". Resolve
  before submission (full axis lengths vs semi-axes differ by 2×). Logged as a `to_verify` item.
- **⚠️ Tracked garbage.** `.DS_Store` (×5) and `__pycache__/*.pyc` (×15) are committed in history.
- **⚠️ No `.gitignore`** in a 232 MB repo with 136 MB of uncommitted raw artifacts: real
  data-loss / accidental-`git add -A` risk.
