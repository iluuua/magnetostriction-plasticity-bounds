# Local repository forensic audit — initial snapshot

Audit date: 2026-06-04 (Thu Jun 4 13:37 MSK 2026)
Auditor role: forensic Git / MD audit (read-only). No destructive commands, no simulations, no commits were run.
Scope: full local working tree of `physics_md_al_fe`, including uncommitted artifacts.

> **Headline finding.** The committed `main` branch stops at the **147 MPa** flat-interface
> loading stage. A large body of completed work — the **200 MPa** loading run, the entire
> **ellipsoidal inclusion + eigenstrain** branch, and a full **`docs/article/`** draft pack
> including `final_manuscript_v1.md` — exists **only in the uncommitted working tree** and
> has been there since ~2026-05-12 to 05-14. The project's true state is materially ahead of
> its last commit. See `repo_consistency_report.md` and `uncommitted_inventory.md`.

---

## 1. Identity and remote

```
pwd            : /Users/ilua/Documents/ilua-system/projects/physics_md_al_fe
date           : Thu Jun  4 13:37:57 MSK 2026
toplevel       : /Users/ilua/Documents/ilua-system/projects/physics_md_al_fe
branch         : main
remote origin  : https://github.com/iluuua/physics_md_al_fe.git (fetch/push)
```

## 2. Commit history (`git log --oneline --decorate -n 20`)

```
37d26bf (HEAD -> main, origin/main, origin/HEAD) Merge pull request #1 from iluuua/work/alfe-md-baseline-fe-phase
f7674b6 (origin/work/alfe-md-baseline-fe-phase, work/alfe-md-baseline-fe-phase) new push
4fd13af A lot was done
336b273 readme
432905d Initial commit
```

Local `main` is level with `origin/main` (HEAD `37d26bf`). No unpushed commits; all divergence
from `origin` is in the **working tree** (uncommitted), not in local commits.

## 3. Working-tree status (`git status --short`)

```
 M .codex/state/current_context.md
 M README.md
 M docs/00_index/DOC_INDEX.md
 M results/reports/run_report.md
?? analysis/python/ (11 new *.py ellipsoid/eigenstrain scripts)
?? docs/60_milestones/2026-05-12_interface_trial_001_stress_200mpa_upper_bound.md
?? docs/60_milestones/2026-05-14_article_ready_checkpoint.md
?? docs/article/                      (7 files incl. final_manuscript_v1.md)
?? docs/ellipsoid_inclusion/          (3 check docs)
?? docs/interface_trial_001_stress_200mpa_check.md
?? lammps/03_interface_stress/stress_200mpa/run_001_compression_ramp/ (5 JSON summaries)
?? lammps/04_ellipsoid_inclusion/     (minimize + NVT + 4 eigenstrain runs, raw dumps)
?? results/figures/article_selected/  (5 PNG)
?? results/figures/ellipsoid_inclusion/ (4 PNG)
?? results/figures/interface_trial_001_stress_200mpa_*.png (2 PNG)
?? results/tables/article/            (2 CSV)
?? results/tables/ellipsoid_inclusion/ (6 JSON/CSV)
?? results/tables/interface_trial_001_stress_000_060_120_147_200mpa_comparison.csv
?? results/tables/interface_trial_001_stress_200mpa_*.csv (3 CSV)
?? structures/interface/ellipsoid_inclusion/ (data + eigenstrain structures + reports)
```

Counts: `git ls-files --others --exclude-standard | wc -l` = **127** untracked.
`git ls-files --modified` = **4**. `git ls-files --deleted` = **0**.
`git ls-files --others --ignored --exclude-standard` = **0** (no repo `.gitignore` exists).

## 4. Diff stat of tracked modifications (`git diff --stat`)

```
 .codex/state/current_context.md | 37 +++--   (rewritten: 147 MPa handoff -> ellipsoid baseline handoff)
 README.md                       | 14 +++     (added "Final loading-series checkpoint": 0/60/120/147/200 MPa)
 docs/00_index/DOC_INDEX.md      | 45 +++     (added 200 MPa, ellipsoid, eigenstrain, article sections)
 results/reports/run_report.md   | 57 +++     (added final loading-series + eigenstrain + article-ready sections)
 4 files changed, 142 insertions(+), 11 deletions(-)
```

The tracked-file edits **already describe** the 200 MPa + ellipsoid + article work. This corroborates
that the uncommitted work is real and was mid-documentation when the session stopped.

## 5. Disk usage (`du -sh ./*`, sorted)

```
  0B  ./analytics      0B  ./literature     4.0K ./LICENSE   36K ./README.md
 220K ./docs          572K ./analysis       1.0M ./potentials
 2.6M ./results        16M ./structures      179M ./lammps
Total working tree: 232 MB   (.git = 32 MB)
```

`lammps/` (179 MB) dominates, almost entirely raw `.lammpstrj` dumps and `data.*` structures.

## 6. Uncommitted-file weight by commit decision (see `uncommitted_inventory.csv`)

| should_commit | files | size | content |
|---|---:|---:|---|
| yes   | 74 | **1.1 MB** | docs, scripts, CSV tables, PNG figures, LAMMPS inputs/logs, JSON summaries |
| maybe | 11 | 30.7 MB | `data.*` minimized/relaxed LAMMPS structures |
| no    | 46 | 105.2 MB | 11 raw `.lammpstrj` dumps (99.4 MB) + 35 `.xyz` visual-debug slices (5.8 MB) |

**The entire scientifically valuable, human-readable record is ~1.1 MB.** The 136 MB of raw
trajectories/structures is the only thing forcing a Git-LFS / keep-local decision.

## 7. Tracked "garbage" already in history (cleanliness defect)

`git ls-files | grep -E 'DS_Store|__pycache__|\.pyc$'` returned **20 tracked files**:

```
.DS_Store, lammps/.DS_Store, potentials/.DS_Store, structures/.DS_Store, structures/converted/.DS_Store
analysis/python/__pycache__/*.pyc   (15 compiled-bytecode files)
```

These were committed in earlier history. They are not "uncommitted" but are a real hygiene
problem: see `git_commit_plan.md` for the `git rm --cached` + `.gitignore` remediation (no
deletion of source, history rewrite optional).

## 8. Commands that errored

None. All read-only forensic commands (`git log/status/diff/ls-files`, `find`, `du`, `stat`)
completed successfully.

## 9. Safety attestation

No file was deleted, moved, or overwritten. No `git clean`, `git reset`, `git checkout -- .`,
or `git commit` was run. No LAMMPS simulation was launched. No raw data, dump, log, table, or
figure was modified. New files were written only under `docs/audit/` and `docs/article/`.
