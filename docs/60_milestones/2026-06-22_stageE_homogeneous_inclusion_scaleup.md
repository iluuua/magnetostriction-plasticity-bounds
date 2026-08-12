# Stage E homogeneous inclusion scale-up

Updated: 2026-06-23T13:40:38+03:00

## v1 failed checkpoint

- Run root: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_homogeneous_inclusion_scaleup\20260622-100215`
- Status: `full_failed`
- Failed case: `E1_homogeneous_control_eps0000_production`
- Failed step: `0/10000`
- Error: `cudaErrorIllegalAddress` / illegal memory access
- Missing production outputs: `restart.10000`, `data.final`, `dump.final.lammpstrj`
- Prep instability: control max `21117.964 K`; physical max `1103133 K`

Verdict: v1 is physically invalid and must not be used as a physics result.

## v2 final checkpoint

- Run root: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_homogeneous_inclusion_scaleup_v2\20260622-224433`
- Target atoms: requested `500000`, actual `510375`
- Model: homogeneous Al matrix plus one Fe4Al13 inclusion; no grain boundary, no polycrystal, no vacancies, no eps0100
- Physical eigenstrain: `eps_z=0.001942`
- Status: `analysis_completed`
- Smoke: `stable`
- Production: `completed`; control and physical both reached `10000/10000`, exit code `0`
- Analysis: `completed`
- Max temperature: `291.98355 K`, below `1000 K` sanity stop
- Outputs complete: `data.final`, `dump.final.lammpstrj`, `restart.10000`, and `analysis.json` present for both production cases
- Valid physics result: `true`

## Physics result

DXA finds no dislocation in control and one short dislocation segment in physical eps001942:

| case | DXA segments | line length A | Burgers family |
| --- | ---: | ---: | --- |
| control eps0000 | 0 | 0.0 | none |
| physical eps001942 | 1 | 8.47 | `1/6<112>` |

Boundary defects remain localized around the inclusion-matrix interface. In the physical case the Al matrix has `12` CNA HCP atoms and `6079` CNA OTHER atoms; the 0-5 A interface shell contains `11` HCP and `4261` OTHER atoms, while the far >30 A matrix contains `0` HCP and `0` OTHER atoms.

Stress-transfer proxy for physical eps001942:

| zone | Pzz MPa | von Mises MPa |
| --- | ---: | ---: |
| interface 0-5 A | -705.2805 | 220.807 |
| near 5-15 A | 815.0283 | 122.9994 |
| mid 15-30 A | 902.9596 | 80.6728 |
| far >30 A | 907.3028 | 16.1694 |

Verdict: `confirmed_dislocations`, specifically an incipient/local dislocation signal at the inclusion-boundary scale. This is not a developed plastic zone through the Al matrix; the far matrix remains near-elastic by defect counts and stress proxy.

## Reports

- `runs/stageE_homogeneous_inclusion_scaleup_v2/20260622-224433/stageE_v2_analysis_summary.json`
- `runs/stageE_homogeneous_inclusion_scaleup_v2/20260622-224433/stageE_v2_boundary_dislocation_report.md`
- `runs/stageE_homogeneous_inclusion_scaleup_v2/20260622-224433/stageE_v2_stress_transfer_report.md`
- `runs/stageE_homogeneous_inclusion_scaleup_v2/20260622-224433/stageE_v2_physics_verdict.md`
- `runs/stageE_homogeneous_inclusion_scaleup_v2/20260622-224433/stageE_v2_failure_or_success_report.md`

Next command:

```powershell
Get-Content -Raw C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_homogeneous_inclusion_scaleup_v2\20260622-224433\stageE_v2_analysis_summary.json
```
