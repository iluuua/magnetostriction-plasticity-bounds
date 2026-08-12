# Stage F GPU candidate validation ladder

- Timestamp: 2026-07-01T16:46:40+03:00
- Candidate binary: `B:\builds\lammps-kokkos-cuda-stageF-rebuild-20260630-201808\build\lmp.exe`
- Candidate flags: `-k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off`
- GPU recovered: `False`
- Stopped at: `V1`
- Max clean step: `0`
- eps0000 comparable validation: `not_run`

| Gate | Status | Max step | Folder | First failure |
|---|---|---:|---|---|
| V0 | completed_clean | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/candidate_V0` |  |
| V1 | failed | `0` | `runs/stageF_gpu_production_recovery_20260701-162855/source_diagnostics/candidate_V1` | (cuda_instance->cuda_event_record_wrapper( CudaInternal::constantMemReusablePerDevice[cuda_device])) error( cudaErrorIllegalAddress): an illegal memory access w |
