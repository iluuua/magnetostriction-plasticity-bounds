# Stage F Codex recovered state

- Timestamp: 2026-06-30T05:00:48+03:00
- Target repo: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe`
- Branch: `ilua/auto/stageD-local-interface-100k-mechanics`
- Current commensurate run root: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748`

## Invalid branch: open_lateral_mmf
- Run root: `runs/stageF_F0_planar_100A_open_lateral/20260629-184320`
- Status: physically invalid diagnostic branch only.
- Production: failed with CUDA illegal-address markers; no 50k valid production.
- Decision: ignored for physics, not resumed, not used for delta-analysis.

## Intended branch: commensurate_ppf
- Run root exists: `True`
- Cases on disk: `F0_planar_100A_comm_eps0000, F0_planar_100A_comm_eps00194`
- `eps0000`: CPU box/relax data exists; latest smoke log reached step 10000 and wrote final data/restart.
- `eps00194`: independent relaxed data exists but is rejected; common-cell seed and fixed-box minimized data now exist.
- `eps00194` smoke: launched after common-cell fix and failed at step 0 with `cudaErrorIllegalAddress`.
- Production: not started for either commensurate case.
- Delta-analysis: not run.

## Running now
No LAMMPS/Stage F process was found after the failed `eps00194` smoke.

## What must not be trusted from chat memory
- Do not assume production was started.
- Do not assume delta-analysis was done.
- Do not compare independently box-relaxed `eps0000` and `eps00194`.
- Do not treat old `m m f` as valid production.
