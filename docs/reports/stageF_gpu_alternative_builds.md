# Stage F GPU alternative builds

- Timestamp: 2026-07-01T16:29:35+03:00
- Build root: `B:\builds\lammps-stageF-gpu-production-recovery-20260701-162855`
- Source: `C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps\cmake`
- VsDevCmd: `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat`
- Overall status: `build_succeeded_probe_failed`

| Build | Status | Note | Binary |
|---|---|---|---|
| Build 1 - KOKKOS CUDA RelWithDebInfo Ampere86 debug symbols | `build_succeeded_probe_failed` |  | `B:\builds\lammps-stageF-gpu-production-recovery-20260701-162855\build1_relwithdebinfo_ampere86\build\lmp.exe` |
| Build 2 - Serial/no-MPI KOKKOS CUDA | `covered_by_build1` | Build 1 was configured with BUILD_MPI=no and direct single-rank executable; this removes MSMPI from the failing probe. | `None` |
| Build 3 - Older/newer local source | `not_attempted` | No alternate local source was selected for this timeboxed pass; no internet fetch was performed. | `None` |
| Build 4 - CPU pair + GPU neighbor | `not_production_candidate` | Not acceptable as production replacement in this task; recorded only as experimental option. | `None` |
