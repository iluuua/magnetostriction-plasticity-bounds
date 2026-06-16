# Stage B Post-Run Decision Tree

Status: prepared while `runs/stageB_realism_100k/20260613-222836` production is still running.

The current Stage B realism 100k run is the source of truth. No 500k, 250k,
700k, A2, full factorial, or second LAMMPS process is allowed before that run
finishes and `scripts/analyze_stageB_realism_100k_postrun.py` produces a
post-run verdict.

## Decision Categories

`confirmed_dislocation_signal` opens only `A_500k_confirmation`. A case is
confirmed when any production `analysis.json` has:

- `dislocation_segments > 0`
- `dislocation_length_A > 0`
- `dislocation_density_per_m2 > 0`

`weak_plasticity_candidate` means CNA/plastic-zone or atomic-strain support
exists, but DXA line signal is still zero. This does not automatically open
500k; it requires manual repeat or intermediate review.

`deformation_only_no_dxa` means displacement/localization exists without DXA,
CNA, atomic-strain, or plastic-zone support. This routes to the no-dislocation
validation branch.

`no_dislocation_no_plasticity` routes to the no-dislocation validation branch.

`unstable` routes to geometry/protocol debug. It blocks both 500k and
no-dislocation physics experiments.

`incomplete` means wait.

## 500k Allowed

500k is allowed only when all gates pass:

- Stage B 100k is complete.
- `postrun_decision.json` exists.
- `branch == "A_500k_confirmation"`.
- `winner_case` is set.
- the winner has confirmed DXA line signal.
- all 100k production logs are clean.
- disk free is at least the configured threshold.
- no `lmp_kokkos_cuda.exe` process is active.
- manual approval is present through `--approve-500k-confirmation` or
  `APPROVE_500K_CONFIRMATION.txt` with exact text `APPROVE_500K_CONFIRMATION`.

500k remains one winner case only. No full factorial or additional seeds are
enabled by default.

## 500k Forbidden

500k is forbidden for:

- incomplete Stage B 100k;
- unstable Stage B 100k;
- no DXA line signal;
- deformation-only displacement;
- no-dislocation branch outcomes;
- active LAMMPS;
- missing manual approval.

## No-Dislocation Branch

The no-dislocation branch exists to avoid wasting a 500k run when the 100k
realism step does not confirm dislocations. Proposal order:

1. `B6_positive_control_shear_30k`
2. `B6_seed_dislocation_nearGB_100k`
3. `B6_cyclic_eigenstrain_100k`
4. `B6_platelet_or_faceted_inclusion_nearGB_100k`
5. `B6_high_temperature_assist_100k`

Current runner support is intentionally conservative: seed dislocation,
cyclic eigenstrain, platelet/faceted inclusion, and pure-Al positive-control
launches are blocked until real builder/runtime support exists.

## Commands

Post-run analysis:

```powershell
.venv\Scripts\python.exe scripts\analyze_stageB_realism_100k_postrun.py --run-root runs\stageB_realism_100k\20260613-222836
```

Post-run dry-run while production is incomplete:

```powershell
.venv\Scripts\python.exe scripts\analyze_stageB_realism_100k_postrun.py --run-root runs\stageB_realism_100k\20260613-222836 --dry-run
```

500k dry-run:

```powershell
.venv\Scripts\python.exe scripts\launch_stageB_500k_confirmation.py --run-root runs\stageB_realism_100k\20260613-222836 --dry-run
```

500k validate:

```powershell
.venv\Scripts\python.exe scripts\launch_stageB_500k_confirmation.py --run-root runs\stageB_realism_100k\20260613-222836 --validate-only
```

500k launch after manual approval:

```powershell
.venv\Scripts\python.exe scripts\launch_stageB_500k_confirmation.py --run-root runs\stageB_realism_100k\20260613-222836 --launch --approve-500k-confirmation
```

No-dislocation branch dry-run:

```powershell
.venv\Scripts\python.exe scripts\launch_stageB_no_dislocation_branch.py --run-root runs\stageB_realism_100k\20260613-222836 --dry-run
```

## Monitoring

Check the active Stage B process without interrupting it:

```powershell
Get-CimInstance Win32_Process |
Where-Object {
  ($_.Name -match 'python|powershell|lmp') -and
  ($_.CommandLine -like '*stageB_realism_100k*' -or $_.Name -like 'lmp_kokkos_cuda*')
} |
Select-Object ProcessId, ParentProcessId, Name, CommandLine |
Format-List
```

Safe stop is manual owner action only. Do not kill the current production from
the post-run or branch scripts.

