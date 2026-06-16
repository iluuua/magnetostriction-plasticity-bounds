# Stage B Post-Run Branching Pipeline

Date: 2026-06-14

Scope:

- added post-run decision logic for the running Stage B realism 100k run;
- prepared a single-case 500k confirmation gate;
- prepared no-dislocation branch proposals;
- kept all launch paths gated and dry-run/validate safe.

Runtime truth:

- `runs/stageB_realism_100k/20260613-222836` was still running when this was prepared;
- `lmp_kokkos_cuda.exe` was active and was not interrupted;
- no 500k, 250k, 700k, A2, full factorial, or second MD job was launched.

New operator entry points:

- `scripts/analyze_stageB_realism_100k_postrun.py`
- `scripts/launch_stageB_500k_confirmation.py`
- `scripts/launch_stageB_no_dislocation_branch.py`
- `scripts/extract_stageB_failed_case.py`

Exact next action:

After the current Stage B production finishes, run:

```powershell
.venv\Scripts\python.exe scripts\analyze_stageB_realism_100k_postrun.py --run-root runs\stageB_realism_100k\20260613-222836
```

Then follow the branch in `postrun_decision.json`.

