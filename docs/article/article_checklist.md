# Article completion checklist

## Already available

- Flat-interface loading series: 0 / 60 / 120 / 147 / 200 MPa.
- Ellipsoid inclusion baseline: minimized + NVT 300 K.
- Ellipsoid eigenstrain series: eps_z = 0.0010 / 0.0025 / 0.0050 / 0.0100.
- Summary CSV for eigenstrain series.
- Four eigenstrain figures:
  - final energy;
  - minimum pair distance;
  - Al-Fe warning contacts;
  - final force two-norm.
- Article result draft.
- Figure plan.
- Key result summary table.

## Still needed for final article

- Select final OVITO screenshots:
  - flat interface geometry;
  - ellipsoid cutaway;
  - Fe-only ellipsoid view;
  - optional 200 MPa flat-interface review screenshot.
- Write final introduction with literature references.
- Add material/potential justification.
- Add equation / explanation of eigenstrain surrogate.
- Add final methods section with exact simulation parameters.
- Add final limitations paragraph.
- Add final conclusion.
- Add references.

## Strong claims allowed

- The simulations passed controlled numerical sanity checks.
- No hard overlaps below 1.8 A were detected in accepted cases.
- No visible catastrophic interface/inclusion failure was observed in reviewed OVITO views.
- The workflow is reproducible from the included scripts and outputs.

## Claims not allowed

- Final physical validation.
- Quantitative experimental stress prediction.
- Direct proof of real defect formation.
- Direct proof of magnetostriction mechanism at experimental scale.

## Added after article-ready checkpoint

- `docs/article/references.md`
- `docs/article/eigenstrain_model.md`
- `docs/article/final_manuscript_v1.md`
- `results/tables/article/simulation_parameters_summary.csv`

## Next manual task

Select final OVITO screenshots for figures:
- ellipsoid cutaway;
- Fe-only ellipsoid view;
- flat-interface 200 MPa review if available;
- optional flat-interface stress-profile screenshot.
