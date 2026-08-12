# Stage F dual-lane CPU smoke gate

- Timestamp: 2026-07-01T12:12:40+03:00
- Gate status: **completed_clean_smoke_pair**
- Current case: `None`
- Worker PID: `22556`
- Comparable root: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_comparable_20260701-001918`

| case | status | max step | return code | folder |
|---|---|---:|---:|---|
| F0_planar_100A_comm_eps0000_cpu_zhi200 | completed_clean | 10000 | 0 | `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_comparable_20260701-001918/F0_planar_100A_comm_eps0000_cpu_zhi200/smoke10k` |
| F0_planar_100A_comm_eps00194_cpu_zhi200 | completed_clean | 10000 | 0 | `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_comparable_20260701-001918/F0_planar_100A_comm_eps00194_cpu_zhi200/smoke10k` |

Production starts only if both CPU smokes complete clean under the same CPU binary, rank/thread policy, zhi=200, and protocol.
