# Stage F GPU production recovery current state

- Timestamp: 2026-07-01T16:28:56+03:00
- Target repo: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe`
- Branch: `ilua/auto/stageD-local-interface-100k-mechanics`
- Active LAMMPS/MPI/StageF worker processes: `0`
- CPU smoke pair: `[{'case': 'F0_planar_100A_comm_eps0000_cpu_zhi200', 'status': 'completed_clean', 'max_step': 10000, 'returncode': 0}, {'case': 'F0_planar_100A_comm_eps00194_cpu_zhi200', 'status': 'completed_clean', 'max_step': 10000, 'returncode': 0}]`
- CPU production pair: `[{'case': 'F0_planar_100A_comm_eps0000_cpu_zhi200', 'status': 'completed_clean', 'max_step': 50000, 'returncode': 0}, {'case': 'F0_planar_100A_comm_eps00194_cpu_zhi200', 'status': 'completed_clean', 'max_step': 50000, 'returncode': 0}]`
- GPU free for short diagnostics: `True`
- GPU production safe to launch now: `False`
- Disk query: return code `0`

## Safe action

Short GPU source-level diagnostics are safe. GPU production is not safe because no comparable GPU smoke pair is clean.
CPU fallback production outputs are complete and must remain intact.
