# Stage F GPU source-level diagnostics

- Timestamp: 2026-07-01T16:29:35+03:00
- Diagnostics root: `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics`
- Decision: run0 passes but NVE dynamics fails, so failure is in dynamics pair/neighbor/MEAM-KOKKOS path before NVT-specific isolation.
- Root cause class: `pair MEAM/KK`

| Test | Status | Return code | Max step | Folder | First fatal |
|---|---|---:|---:|---|---|
| D0_debug_run0_direct | completed_clean | `0` | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/D0_debug_run0_direct` |  |
| D1_debug_cuda_launch_blocking_run10_nvt | failed | `3221226505` | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/D1_debug_cuda_launch_blocking_run10_nvt` | (cuda_instance->cuda_event_record_wrapper( CudaInternal::constantMemReusablePerDevice[cuda_device])) error( cudaErrorIllegalAddress): an illegal memory access was encount |
| D2_debug_kokkos_debug_run10_nvt | failed | `3221226505` | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/D2_debug_kokkos_debug_run10_nvt` | cudaStreamSynchronize(stream) error( cudaErrorIllegalAddress): an illegal memory access was encountered C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps\lib\kokk |
| D3_debug_no_memory_pool_run10_nvt | failed | `3221226505` | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/D3_debug_no_memory_pool_run10_nvt` | cudaStreamSynchronize(stream) error( cudaErrorIllegalAddress): an illegal memory access was encountered C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps\lib\kokk |
| D4_debug_run10_nve | failed | `3221226505` | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/D4_debug_run10_nve` | cudaStreamSynchronize(stream) error( cudaErrorIllegalAddress): an illegal memory access was encountered C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps\lib\kokk |
| D5_debug_no_gpu_aware_run10_nvt | failed | `3221226505` | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/D5_debug_no_gpu_aware_run10_nvt` | cudaStreamSynchronize(stream) error( cudaErrorIllegalAddress): an illegal memory access was encountered C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps\lib\kokk |
| D6_debug_mpiexec_np1_run10_nvt | failed | `3221226505` | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/D6_debug_mpiexec_np1_run10_nvt` | cudaStreamSynchronize(stream) error( cudaErrorIllegalAddress): an illegal memory access was encountered C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps\lib\kokk |
| D7_rebuild_cuda_launch_blocking_run10_nvt | failed | `3221226505` | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/D7_rebuild_cuda_launch_blocking_run10_nvt` | (cuda_instance->cuda_event_record_wrapper( CudaInternal::constantMemReusablePerDevice[cuda_device])) error( cudaErrorIllegalAddress): an illegal memory access was encount |
| D8_rebuild_run10_nve | failed | `3221226505` | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/D8_rebuild_run10_nve` | cudaStreamSynchronize(stream) error( cudaErrorIllegalAddress): an illegal memory access was encountered C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps\lib\kokk |
