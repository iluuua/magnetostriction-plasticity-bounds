# Stage F dual-lane resource policy

- Timestamp: 2026-07-01T00:19:22+03:00
- CPU lane policy: `6` MPI ranks x `2` OpenMP threads.
- Reason: local preflight reports 6 cores / 12 logical processors; this avoids the earlier 8 x 6 oversubscription while keeping eps0000 and eps00194 identical.
- Execution order: smoke eps0000, smoke eps00194, production eps0000, production eps00194.
- GPU lane: no GPU production launch while CPU fallback pair is running; GPU repair evidence remains separate.
- Output policy: dump every 1000, restart every 5000, final data and final restart.
- Forbidden policy: no `thermo_modify lost ignore`, no wall, no `fix box/relax`, no eps005/F1/F0_300A launch.

CPU comparable root: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_comparable_20260701-001918`
CPU production root: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_production_20260701-001918`
