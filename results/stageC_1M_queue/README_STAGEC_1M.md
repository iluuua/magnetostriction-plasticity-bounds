# Stage C 1M Queue Root

Selected case: `C1_1M_nearGB_vacancies_medium_eps0100`.
This root is prepared for a single 100k-step Stage C checkpoint.

## Launch Policy

- Do not launch while any LAMMPS process is active.
- Do not launch while the focused Stage B run is active.
- Use `launch_after_focus_command.txt` after the focused run completes or stops.
- Continuation to 200k/250k is manual-only after the 100k decision report.

## Expected Runtime

- optimistic: about 4 days
- expected: about 5 days
- pessimistic: about 6.5 days

## Event Pipeline

After the 100k checkpoint completes, run:

```powershell
.venv\Scripts\python.exe scripts\run_event_pipeline_dry_run.py --run-root runs\stageC_1M_nearGB_vacancies_eps0100_100k\20260616-173123 --allow-incomplete
```
