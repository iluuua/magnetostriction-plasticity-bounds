# Stage F CPU results: report for Pshonkin criteria

Дата: 2026-07-02T07:38:17+03:00

## Answer

Завершенная CPU fallback pair пригодна как физический ответ на текущий запрос: построен `sigma(r)` от плоской границы Fe4Al13/Al в Al matrix, выполнено сравнение `eps00194` против `eps0000`, и результат проверен относительно `sigma_y = 120.0 MPa`.

При этом остаточная пластичность не подтверждена: verdict residual-check = `not_confirmed`. Корректная формулировка: есть передача/перераспределение local virial stress proxy около interface; устойчивую дислокационную пластическую зону по этим данным заявлять нельзя.

## Last 20% stress summary

| case | mean VM layer A | p95 VM layer A | near 0-10A VM MPa | far 50A+ VM MPa |
| --- | --- | --- | --- | --- |
| eps0000 | 121.068 | 121.068 | 1042.5 | 803.219 |
| eps00194 | 121.068 | 121.068 | 1117.9 | 739.733 |

## Defect/plasticity status

| case | step | HCP | OTHER | DXA segments | DXA line A |
| --- | --- | --- | --- | --- | --- |
| eps0000 | 0 | 0 | 2910.0 | 0 | 0 |
| eps0000 | 50000.0 | 1 | 3028.0 | 0 | 0 |
| eps00194 | 0 | 0 | 2535.0 | 0 | 0 |
| eps00194 | 50000.0 | 0 | 3126.0 | 0 | 0 |

`Dmin2` не использовался, потому что это поле не сохранено в CPU dump, а отдельный reference-strain pipeline в этом анализе не вводился.

## Figures

- `docs\reports\figures\stageF_cpu_results_sigma_vm_last20.png`
- `docs\reports\figures\stageF_cpu_results_sigma_zz_last20.png`
- `docs\reports\figures\stageF_cpu_results_sigma_vm_p95_last20.png`
- `docs\reports\figures\stageF_cpu_results_delta_sigma_vm_last20.png`
- `docs\reports\figures\stageF_cpu_results_defect_other_final.png`
- `docs\reports\figures\stageF_cpu_results_defect_hcp_final.png`
- `docs\reports\figures\stageF_cpu_results_defect_nonfcc_final.png`
- `docs\reports\figures\stageF_cpu_results_delta_defect_nonfcc_final.png`

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
