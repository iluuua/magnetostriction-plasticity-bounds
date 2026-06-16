# Focused Production Failure Diagnosis

Generated: 2026-06-16T02:30:32+03:00

Run root: `runs/stageB_nearGB_vacancies_focus_100k/20260615-215533`

## Summary

- Failed case: `B3_nearGB_vacancies_medium_eps0025_production`
- Failed chunk: `chunk0000000_0010000`
- Exit code: `1`
- Last timestep: `0`
- Production started: no; LAMMPS failed before opening the production log and before executing the input.
- Category: `config_bug_fix_required`
- Root cause: generated chunked production file names were too long for the current deep Windows run directory. The full production log path was 279 characters, and the input/dump/final restart paths also crossed or approached the legacy Windows path limit. LAMMPS aborted immediately while trying to open the relative `-log` target.

## Evidence

Failed command:

```text
B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe -k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off -in in.B3_nearGB_vacancies_medium_eps0025_production.chunk0000000_0010000 -log log.B3_nearGB_vacancies_medium_eps0025_production.chunk0000000_0010000.lammps
```

Error from `stdout.chunk0000000_0010000.txt`:

```text
ERROR on proc 0: Cannot open universe log file log.B3_nearGB_vacancies_medium_eps0025_production.chunk0000000_0010000.lammps: No such file or directory (C:\Users\dille\Documents\builds\lammps-kokkos-cuda\lammps\src\lammps.cpp:538)
```

Recorded runner failure reasons:

- nonzero exit code: `1`
- LAMMPS log missing
- forbidden error marker: `ERROR`
- no `Total wall time` line
- expected output missing: `restart.B3_nearGB_vacancies_medium_eps0025_production.10000`

Path length check in the failed production directory:

| file | full path length |
| --- | ---: |
| production work dir | 201 |
| failed input | 271 |
| failed log | 279 |
| failed dump | 283 |
| failed final restart | 261 |
| failed final dump | 268 |

The successful prep and smoke phases for both focused cases show that the config, potential files, structures, GPU executable, and MEAM input are otherwise valid. This is not classified as physics instability: there were no lost atoms, NaN, exploding thermo values, or production timesteps.

## Safety Check

- Active process scan before repair found no active focused/old Python runner and no active `lmp_kokkos_cuda`; the only match was the self-referential PowerShell scan command.
- GPU: NVIDIA GeForce RTX 3060, 12288 MiB total, 433 MiB used, driver 591.86.
- Disk: C free 29.67 GB, B free 267.36 GB.

## Repair Plan

Applied code repair in `analysis/python/stage_runner/gpu_grid.py`:

- chunked production input: `in.<chunk_tag>`
- chunked production log: `log.<chunk_tag>.lammps`
- chunked production dump: `dump.<chunk_tag>.lammpstrj`
- chunked production restart: `restart.<step>`
- chunked final data/dump: `data.final`, `dump.final.lammpstrj`
- restart resume scans both new short names and old long names for compatibility.
- production analysis accepts `dump.final.lammpstrj` as the chunked final dump.

Failed state backup:

`runs/stageB_nearGB_vacancies_focus_100k/20260615-215533/failed_state_backup_20260616T023032`

## Classification

`config_bug_fix_required`: local runner filename/path issue. Safe resume is allowed after backup because no production restart was written, no production timestep was completed, prep/smoke outputs remain valid, and the fix does not change physics, case IDs, eps values, or run scope.
