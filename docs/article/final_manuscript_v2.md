# Final manuscript v2 — pointer and changelog

Date: 2026-06-04.

## Status

`final_manuscript_v1.md` (the existing English draft) was **used as the base** and extended to the full
international IMRaD structure. The v2 manuscript is split into two canonical, parallel documents:

- **English (canonical):** `docs/article/article_en.md`
- **Russian (canonical):** `docs/article/article_ru.md`

This file is a changelog only — it does not duplicate the manuscript. `final_manuscript_v1.md` is left
**unmodified** as the historical base.

## What changed from v1 → v2

1. **Structure.** v1 had Abstract + Intro + Methods + sections 3–9. v2 expands to the full international
   layout: Title, Abstract, Keywords, Introduction, Objective & Tasks, Materials & Methods, Computational
   Model, Initial Structure Preparation, Interface Orientation/Mismatch, Interface Construction, MD Setup,
   Eigenstrain Surrogate, Local Loading Protocol, Numerical Stability Checks, Results, Discussion,
   Limitations, Conclusions, Future Work, Data & Code Availability, Reproducibility Notes, References,
   Supplementary Materials.
2. **Sourcing.** Every significant number now carries a source path in parentheses, cross-checked against
   `docs/audit/claims_register.csv` / `.md`.
3. **Results vs Discussion split.** v2 keeps Results strictly factual; all interpretation (why 0 MPa
   matters, why warning pair 232-260 is not interface failure, why the virial profile is comparative, why
   the support maximum is a boundary artifact, why no final validation) moved to Discussion.
4. **References discipline.** Verifiable references (LAMMPS docs, OpenKIM/NIST Jelinek 2012, COD 1571554)
   are listed normally; Feng 2023, Que 2024, and SpringerMaterials are moved to "References to verify".
   No new references were invented.
5. **Honest flags carried in.** OVITO screenshots absent from repo; ellipsoid "axes vs semi-axes"
   terminology to verify; non-uniform loading-step protocols — all stated explicitly.

## Numerical content (unchanged from the data)

Both branches and all values are identical to the local results: flat interface 0/60/120/147/200 MPa
(15000-step protocol for 120/147/200); ellipsoid eigenstrain eps_z = 0.0010/0.0025/0.0050/0.0100. No new
physics was produced; nothing was re-run.

## Recommended next step

When the open decisions in `docs/article/teacher_brief_ru.md` are resolved, fold the answers into
`article_en.md` / `article_ru.md` and, if a single combined manuscript file is required for submission,
generate it from those two canonical sources.
