# Stage F: stress-decay от interface в Al matrix

Дата: 2026-06-29

Run root: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageE_700k_dxa_confirm\20260625-102200`

## Краткий вывод

Stress layer в существующем 700k run вычислен как local virial stress proxy по Al matrix bins от аналитической поверхности Fe4Al13 / Al. Реальный режим расстояния: `surface-distance`.

По заданному p95-критерию слой выше `120 MPa` идет до `157.85 A` в кадре `0`. Это граница доступного расстояния в текущем 700k box, а не доказанный физический cutoff.

Mean `sigma_vm(r)` показывает сильную near-interface компоненту, но p95/per-atom virial proxy остается шумным и часто выше порога далеко от interface. Поэтому текущий 700k ellipsoid-run полезен как post-processing sanity check, но не дает аккуратного cutoff `sigma(r)` до уровня ниже `120 MPa`; для этого нужен Stage F boundary-patch с controlled geometry.

## Ответы на вопросы

1. Есть ли stress layer? Да, по local virial proxy слой выше `120 MPa` есть около interface; p95-критерий не дает чистого затухания ниже порога в доступном 700k box.
2. Толщина слоя выше `120 MPa`: `157.85 A` continuous по p95-критерию в кадре `0`; максимум above-yield distance `157.855 A`.
3. Затухание: mean VM обычно падает от near-interface к дальним bin, но p95 atom-level virial остается noisy; надежно сказать "затухает за N A" нельзя.
4. Передается ли напряжение в Al matrix? В существующей модели stress proxy передается в matrix, но интерпретация ограничена ellipsoid geometry и virial noise.
5. Физически значимые дислокации: нет подтверждения. Есть short transient DXA на `60000`, `2` segments, `17.45 A`, затем `70000/80000` возвращаются к DXA `0`.
6. Почему transient DXA at 60000 недостаточен: линия короче `50 A`, событие исчезает на следующем sampled frame и не является persistent dislocation.
7. Можно показать Пшонкину: да, как reality-alignment и motivation для boundary-patch, но не как окончательный `sigma(r)` cutoff.

## Frame timeline

| step | layer A | max dist A | max mean VM | max p95 VM | HCP | OTHER | DXA | line A | class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 157.855 | 157.855 | 794.211 | 28611.4 | 0 | 6160 | 0 | 0.000 | no_event |
| 10000 | 157.636 | 157.636 | 1523.845 | 22750.8 | 4 | 7490 | 0 | 0.000 | weak_hcp |
| 20000 | 157.751 | 157.751 | 1475.922 | 23198 | 3 | 7512 | 0 | 0.000 | weak_hcp |
| 30000 | 157.802 | 157.802 | 1555.222 | 23376.4 | 0 | 7714 | 0 | 0.000 | weak_hcp |
| 40000 | 157.668 | 157.668 | 1923.344 | 22352.1 | 1 | 7745 | 0 | 0.000 | weak_hcp |
| 50000 | 157.839 | 157.839 | 1418.523 | 22158.5 | 5 | 7781 | 0 | 0.000 | weak_hcp |
| 60000 | 157.656 | 157.656 | 1846.199 | 24500.2 | 6 | 7844 | 2 | 17.451 | confirmed_DXA |
| 70000 | 157.749 | 157.749 | 1575.298 | 22817.8 | 1 | 7935 | 0 | 0.000 | weak_hcp |
| 80000 | 157.690 | 157.690 | 1527.119 | 22258.5 | 3 | 7889 | 0 | 0.000 | weak_hcp |

## Notes on stress conversion

- Dump columns: `c_st[1..6]`.
- Conversion follows existing Stage D/E convention: `pressure_bar = -sum(c_st)/estimated_bin_volume`; `1 bar = 0.1 MPa`.
- Full tensor VM is used because shear components are present.
- Bin volume uses mean atomic volume; absolute MPa values are approximate and should not be overclaimed.
- `atomic_strain_p95/p99` and `Dmin2_p95/p99` are empty because these properties were not stored in the Stage E dump and no same-pipeline reference deformation field is available across chunked files.

## Source Map

```json
{
  "prompt": "C:\\Users\\dille\\Documents\\ilua-system\\prompt.txt",
  "physicist_transcript": "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\Phonkin_discussion_m4a.txt",
  "visual_photos": [
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (1).jpg",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (2).jpg",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (3).jpg",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (4).jpg",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (5).jpg",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\pshonkin_materials_ishodniki\\visual (6).jpg"
  ],
  "stageE_reports": [
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\stageE_700k_full_analysis_with_temporal_evolution_ru.md",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\stageE_700k_temporal_evolution_report_ru.md",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\stageE_700k_temporal_evolution_table.csv",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\stageE_700k_temporal_evolution_summary.json",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\agent_report_stageE_700k_temporal_evolution_analysis.md"
  ],
  "run_root": "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200",
  "dumps_used": [
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\dump.chunk0000000_0010000.lammpstrj",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\dump.chunk0000000_0010000.lammpstrj",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\dump.chunk0010000_0020000.lammpstrj",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\dump.chunk0020000_0030000.lammpstrj",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\dump.chunk0030000_0040000.lammpstrj",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\dump.chunk0040000_0050000.lammpstrj",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\dump.chunk0050000_0060000.lammpstrj",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\dump.chunk0060000_0070000.lammpstrj",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\dump.final.lammpstrj"
  ],
  "restart_files_used_as_metadata": [
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\restart.10000",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\restart.20000",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\restart.30000",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\restart.40000",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\restart.50000",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\restart.60000",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\restart.70000",
    "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\runs\\stageE_700k_dxa_confirm\\20260625-102200\\cases\\E4_700k_dxa_confirm\\E4_phys001942_700k_80k\\production\\restart.80000"
  ],
  "limitations": [
    "surface distance is analytic ellipsoid radial approximation for the existing Stage E geometry",
    "virial stress is a local proxy using mean atomic volume, not a calibrated continuum stress",
    "atomic strain and Dmin2 are unavailable in existing dump columns",
    "dump cadence is 10000 steps",
    "existing 700k ellipsoid domain cannot answer full micron-scale stress decay"
  ],
  "safe_claims": [
    "short transient DXA at timestep 60000",
    "no persistent dislocation evidence in sampled 700k frames",
    "Stage F should use boundary-patch sigma(r)"
  ],
  "unsafe_claims": [
    "claims that a stable dislocation was confirmed",
    "claims of a mature dislocation line",
    "claims that a physical dislocation was proven",
    "claims that a 20-micron atomistic domain was run",
    "claims that a full 5 micron inclusion was modeled"
  ],
  "render_status": {
    "status": "completed",
    "files": [
      "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\renders\\stageF_before_event_type.png",
      "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\renders\\stageF_at_event_60000_type.png",
      "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\renders\\stageF_after_event_70000_type.png",
      "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\renders\\stageF_final_80000_type.png",
      "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\renders\\stageF_geometry_interface_view.png",
      "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\renders\\stageF_cna_at_event_60000.png",
      "C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe\\docs\\reports\\renders\\stageF_stress_layer_view.png"
    ],
    "blockers": []
  }
}
```
