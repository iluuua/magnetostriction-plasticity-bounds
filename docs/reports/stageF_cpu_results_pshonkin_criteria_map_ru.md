# Stage F CPU results: Pshonkin criteria map

Дата: 2026-07-02T07:38:17+03:00

| criterion | status | evidence |
| --- | --- | --- |
| CPU pair completed clean | yes | Both eps0000/eps00194 production50k returncode 0, max step 50000. |
| No CPU/GPU mixing | yes | Delta uses CPU fallback pair only. |
| r=0 on Fe4Al13/Al interface | yes | F0 planar interface `z=50.0 A`, +Z into Al matrix. |
| Al matrix only | yes | `type=1` and `z>=interface_z`. |
| sigma(r) vs 120 MPa | yes | Mean VM, p95 VM, |sigma_zz| metrics exported. |
| Baseline-subtracted delta | yes | `eps00194 - eps0000` CSV exported. |
| Final + last 20% window | yes | `step 50000` and `40000..50000` time-averaged stress profiles. |
| CNA/DXA defect check | partial | OVITO CNA/DXA on step 0 and final; Dmin2 unavailable. |
| Persistent plasticity claim | no | Residual verdict: `not_confirmed`. |
| Physical report to Pshonkin | yes | Russian reports and meeting brief generated. |

## Guardrails

- Не утверждать, что стабильная дислокация доказана.
- Не превращать atom-level virial p95 в точный continuum cutoff без оговорки.
- Не смешивать CPU и GPU lanes в одном delta pair.
- Не считать GPU blocker физическим blocker для уже завершенной CPU пары.

## Source Map

```json
{
  "prompt": "C:\\Users\\dille\\Documents\\ilua-system\\prompt.txt",
  "physicist_transcript": "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\Phonkin_discussion_m4a.txt",
  "visual_sketches": [
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (1).jpg",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (2).jpg",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (3).jpg",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (4).jpg",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (5).jpg",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (6).jpg"
  ],
  "cpu_setup": "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\stageF_dual_lane_cpu_setup.json",
  "cpu_worker_status": "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageF_F0_planar_100A_ppf_commensurate\\20260630-010748\\cpu_fallback_comparable_20260701-001918\\cpu_fallback_worker_status.json",
  "production_status": "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\stageF_dual_lane_cpu_production_status.json",
  "production_root": "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageF_F0_planar_100A_ppf_commensurate\\20260630-010748\\cpu_fallback_production_20260701-001918",
  "previous_alignment": "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\stageF_physics_meeting_alignment_ru.md",
  "previous_boundary_stress_decay": "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\stageF_boundary_stress_decay_report_ru.md"
}
```
