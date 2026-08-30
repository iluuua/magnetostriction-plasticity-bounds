# Stage B Positive Control Plan

Purpose: prove that the DXA/CNA analysis path detects dislocations when the
loading protocol should generate them.

Target design:

- small 30k-class system;
- pure Al or GB Al;
- controlled shear/tension using `fix deform` or an existing equivalent;
- smoke first;
- no inclusion required unless the builder supports it.

Current blocker: no pure-Al/GB shear runner exists in `stage_runner.gpu_grid.py`.

