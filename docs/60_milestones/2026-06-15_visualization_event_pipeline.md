# Visualization Event Pipeline Milestone

Date: 2026-06-15

Scope:

- added a post-processing event pipeline for existing Stage B run artifacts;
- added event timeline schema and classification helpers;
- added event-window dry-run planning with restart selection;
- added OVITO render manifests for geometry, deformation, DXA, event frames,
  and static figures;
- added a reproducible 30 FPS ffmpeg command path;
- added tests and operator documentation.

Runtime truth:

- no MD production run was launched;
- no 500k run was launched;
- no event-window rerun was launched;
- OVITO rendering was not executed;
- ffmpeg encoding was not executed.

Dry-run result for `runs/stageB_realism_100k/20260613-222836`:

- available completed analysis frames: 1;
- current event class: `weak_hcp`;
- confirmed DXA: not found in the available frame;
- fallback event window: `90000..110000`;
- restart source:
  `restart.B3_nearGB_perfect_eps0025_production.90000`.

Validation:

```powershell
.venv\Scripts\python.exe -m compileall analysis\python\event_pipeline scripts\build_event_timeline.py scripts\plan_event_window.py scripts\render_event_frames.py scripts\render_dxa_frames.py scripts\render_deformation_frames.py scripts\render_geometry_panels.py scripts\export_event_figures.py scripts\encode_animation_30fps.py scripts\run_event_pipeline_dry_run.py tests\test_event_pipeline.py
.venv\Scripts\python.exe -m unittest discover tests -p 'test_event_pipeline.py'
.venv\Scripts\python.exe -m compileall analysis scripts tests
.venv\Scripts\python.exe -m unittest discover tests
.venv\Scripts\python.exe scripts\run_event_pipeline_dry_run.py --run-root runs\stageB_realism_100k\20260613-222836
```

Exact next action:

After the Stage B 100k run completes, rerun:

```powershell
.venv\Scripts\python.exe scripts\run_event_pipeline_dry_run.py --run-root runs\stageB_realism_100k\20260613-222836
```

Then review `event_pipeline/event_timeline.json` and
`event_pipeline/event_window_plan.md` before any approved high-frequency rerun,
OVITO render execution, or ffmpeg encoding.
