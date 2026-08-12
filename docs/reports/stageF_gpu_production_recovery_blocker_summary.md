# Stage F GPU production recovery blocker summary

- Timestamp: 2026-07-01T16:28:56+03:00
- Exact GPU failure pattern: valid KOKKOS CUDA MEAM/KK dynamics prints thermo at Step 0, then fails before advancing with cudaStreamSynchronize(stream) cudaErrorIllegalAddress; run0-only can complete, but run10 dynamics fails at max_step 0.
- GPU backend matrix status: `not recovered`
- Binaries already tested:
  - `B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe`
  - `B:\builds\lammps-kokkos-cuda-debug\build\lmp_kokkos_cuda_debug.exe`
  - `B:\builds\lammps-kokkos-cuda-stageF-rebuild-20260630-201808\build\lmp.exe`

## Flags already tested

- -k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off
- newton off (invalid: MEAM/KK requires newton pair on)
- neigh full (invalid with KOKKOS/newton combination)
- gpu/aware omitted
- gpu/aware on
- atom sort off
- no per-atom computes/dumps
- coordinates-only dump
- smaller timestep 0.0005
- thermal ramp 10 to 300 K
- comm/sort/atom-map/binsize runtime variants

## Do not repeat blindly

- Do not rerun GPU production before both comparable GPU smokes are clean.
- Do not mix CPU and GPU cases in one delta pair.
- Do not repeat newton off for meam/kk; it is an invalid configuration.
- Do not rerun the old m m f open_lateral branch as production evidence.

## Open hypotheses

- MEAM/KK pair or neighbor-device kernel illegal address on this Windows CUDA/Kokkos build.
- Runtime DLL/toolchain incompatibility still possible, but direct no-MPI failures argue against pure MSMPI cause.
- NVT is not the first suspect if NVE run10 fails the same way.
