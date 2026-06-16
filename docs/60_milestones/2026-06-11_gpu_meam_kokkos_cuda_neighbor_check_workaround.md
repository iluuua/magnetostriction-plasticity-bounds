# Milestone: GPU MEAM/KOKKOS CUDA neighbor-check workaround

Date: 2026-06-11.

## Scope

Resume and complete the GPU debug/fix pipeline for the A0/A1 Al + Fe4Al13 ellipsoid inclusion production lane.

## Result

GPU MEAM/KOKKOS CUDA is approved for A0 production when run-local inputs use:

```text
neigh_modify    delay 0 every 10 check no
```

The release GPU binary is:

```text
B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe
```

## Root Cause

The crash was isolated to the Kokkos CUDA neighbor distance-check reduction, not the MEAM force kernel:

```text
LAMMPS_NS::NeighborKokkos::check_distance_kokkos<Kokkos::Cuda>
src/KOKKOS/neighbor_kokkos.cpp:203
Invalid __global__ write of size 4 bytes to address 0x0
```

## Validation

- A0 eps_0000 static `run 0`: pass, matched CPU/static baseline values.
- A0 eps_0000 baseline dynamics: failed after printed step 9 with `cudaErrorIllegalAddress`.
- A0 eps_0000 with `check no every 10`, `run 200`: pass.
- A0 eps_0000 with `check no every 10`, `run 2000`: pass.
- A0 eps_0025 with `check no every 10`, `run 2000`: pass.
- A0 eps_0000 with `check no every 10`, `run 20000`: pass, exit 0, no `ERROR`, no `nan`, no `lost atoms`.

Primary report:

```text
runs\gpu_debug\20260611-151634\debug_report.md
```

Success report:

```text
runs\gpu_debug\20260611-151634\gpu_fix_success_report.md
```

Machine-readable decision:

```text
runs\gpu_debug\20260611-151634\gpu_debug_decision.json
```

## Remaining Risk

`Dangerous builds` are not checked with `check no`. The mitigation is regular neighbor rebuilding every 10 steps and explicit reporting of this condition in GPU production outputs.

This is a run-local workaround. It does not repair the upstream LAMMPS/Kokkos source bug.

## Next Action

Prepare a run-local A0 production input with:

```text
neigh_modify    delay 0 every 10 check no
run             100000
```

Run GPU A0 production from its output directory:

```text
set CUDA_LAUNCH_BLOCKING=1
B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe -k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off -in in.nvt_eps_0000.gpu -log log.nvt_eps_0000.gpu.lammps
```
