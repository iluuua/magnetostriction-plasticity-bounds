# Stage F dual-lane CPU worker launch

- Timestamp: 2026-07-01T00:19:22+03:00
- Status: **running_smoke_gate**
- Worker PID: `10784`
- Comparable root: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_comparable_20260701-001918`
- Production root: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_production_20260701-001918`
- Status JSON: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_comparable_20260701-001918/cpu_fallback_worker_status.json`
- Worker stdout: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_comparable_20260701-001918/worker_stdout.log`
- Worker stderr: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748/cpu_fallback_comparable_20260701-001918/worker_stderr.log`

The worker is currently in the smoke gate. It will launch production only after both CPU zhi=200 smokes complete clean.

Monitor:

```powershell
Get-Content -Raw runs\stageF_F0_planar_100A_ppf_commensurate\20260630-010748\cpu_fallback_comparable_20260701-001918\cpu_fallback_worker_status.json
```
