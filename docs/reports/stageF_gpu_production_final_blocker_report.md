# Stage F GPU production final blocker report

- Timestamp: 2026-07-01T16:46:40+03:00
- GPU recovered: `False`
- Root cause class: `pair MEAM/KK`
- Minimal repro package: `runs/stageF_gpu_production_recovery_20260701-162855`
- Source-level evidence: run0 passes but NVE dynamics fails, so failure is in dynamics pair/neighbor/MEAM-KOKKOS path before NVT-specific isolation.
- Current best failing command: `B:\builds\lammps-kokkos-cuda-stageF-rebuild-20260630-201808\build\lmp.exe -k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off -in in.run10_nve -log log.lammps`

## Why production cannot start

No eps00194 GPU V6 10000 clean smoke and no eps0000 comparable GPU 10000 clean smoke exist.

## Binaries tested

- `B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe`
- `B:\builds\lammps-kokkos-cuda-debug\build\lmp_kokkos_cuda_debug.exe`
- `B:\builds\lammps-kokkos-cuda-stageF-rebuild-20260630-201808\build\lmp.exe`
- `B:\builds\lammps-kokkos-cuda-stageF-rebuild-20260630-201808\build\lmp.exe`

## Build variants

- Build 1 - KOKKOS CUDA RelWithDebInfo Ampere86 debug symbols: `build_succeeded_probe_failed`
- Build 2 - Serial/no-MPI KOKKOS CUDA: `covered_by_build1`
- Build 3 - Older/newer local source: `not_attempted`
- Build 4 - CPU pair + GPU neighbor: `not_production_candidate`

## Recommendation

1. Continue CPU fallback production/post-processing for the physics result, keeping CPU-only delta separate.
2. Move GPU execution to Linux/server for an independent KOKKOS CUDA MEAM check.
3. Debug LAMMPS KOKKOS/MEAM source with the minimal repro package.
4. Try different potential/model only after scientific approval.
