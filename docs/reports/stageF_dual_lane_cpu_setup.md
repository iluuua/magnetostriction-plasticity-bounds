# Stage F dual-lane CPU setup

- Timestamp: 2026-07-01T00:19:22+03:00
- Comparable root: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_comparable_20260701-001918`
- Production root: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_production_20260701-001918`
- CPU binary: `C:\Users\dille\AppData\Local\LAMMPS 64-bit 22Jul2025-MSMPI\bin\lmp.exe`
- MPI policy: `6` ranks x `2` OpenMP threads
- Boundary: `p p f`
- zhi: `200.0 A` for both cases
- No wall, no box/relax, no lost-ignore policy.

## Data comparability

| case | atoms | type counts | Lx | Ly | Lz | min z | max z |
|---|---:|---|---:|---:|---:|---:|---:|
| eps0000 CPU zhi200 | 113295 | `{'1': 105960, '2': 7335}` | 94.45292756533274 | 122.04881286963183 | 200.0 | 0.0 | 169.48318145395854 |
| eps00194 CPU zhi200 | 113295 | `{'1': 105960, '2': 7335}` | 94.45292756533274 | 122.04881286963183 | 200.0 | 0.0 | 169.36761963461598 |
