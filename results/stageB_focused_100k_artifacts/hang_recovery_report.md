# Hang recovery report

Generated: 2026-06-16T23:10:56
Run root: `C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe\runs\stageB_nearGB_vacancies_focus_100k\20260615-215533`

Watchdog policy: a production chunk is declared hung when the LAMMPS process is alive but
CPU time and log/dump/restart files all stop changing for 25 minutes.
A hung chunk is killed, the case resumes from the latest valid restart, and the chunk is retried once.
If the same chunk hangs twice the case is marked failed and escalation stops.
Production runs in chunks of 10000 steps with write_restart + state.json
update + log verification (ERROR/nan/lost atoms/cudaError) after every chunk.

## B3_nearGB_vacancies_medium_eps0025_production

- status: `success` (success=True)
- current_step: 100000/100000
- resumed_from_restart_step: None
- previous attempt: status=`failed` chunked=True exit_code=1 steps_completed=0 failure_reasons=["chunk chunk0000000_0010000 failed: ['nonzero exit code: 1', 'LAMMPS log missing', 'forbidden error markers: ERROR', 'no Total wall time line', 'expected output missing: restart.B3_nearGB_vacancies_medium_eps0025_production.10000']"]

| chunk | attempt | status | exit | steps | wall_s | t/s | restart_written |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chunk0000000_0010000 | 1 | success | 0 | 10000 | 3727.958 | 2.684 | True |
| chunk0010000_0020000 | 1 | success | 0 | 20000 | 3702.461 | 2.702 | True |
| chunk0020000_0030000 | 1 | success | 0 | 30000 | 3707.488 | 2.698 | True |
| chunk0030000_0040000 | 1 | success | 0 | 40000 | 3706.077 | 2.699 | True |
| chunk0040000_0050000 | 1 | success | 0 | 50000 | 3710.571 | 2.696 | True |
| chunk0050000_0060000 | 1 | success | 0 | 60000 | 3706.735 | 2.699 | True |
| chunk0060000_0070000 | 1 | success | 0 | 70000 | 3706.217 | 2.699 | True |
| chunk0070000_0080000 | 1 | success | 0 | 80000 | 3710.771 | 2.696 | True |
| chunk0080000_0090000 | 1 | success | 0 | 90000 | 3710.739 | 2.696 | True |
| chunk0090000_0100000 | 1 | success | 0 | 100000 | 3711.032 | 2.696 | True |

### Watchdog / recovery events

- none

## B3_nearGB_vacancies_medium_eps0100_production

- status: `success` (success=True)
- current_step: 100000/100000
- resumed_from_restart_step: None

| chunk | attempt | status | exit | steps | wall_s | t/s | restart_written |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chunk0000000_0010000 | 1 | success | 0 | 10000 | 3709.543 | 2.697 | True |
| chunk0010000_0020000 | 1 | success | 0 | 20000 | 3706.962 | 2.698 | True |
| chunk0020000_0030000 | 1 | success | 0 | 30000 | 3708.526 | 2.697 | True |
| chunk0030000_0040000 | 1 | success | 0 | 40000 | 3710.926 | 2.696 | True |
| chunk0040000_0050000 | 1 | success | 0 | 50000 | 3765.969 | 2.656 | True |
| chunk0050000_0060000 | 1 | success | 0 | 60000 | 3710.395 | 2.696 | True |
| chunk0060000_0070000 | 1 | success | 0 | 70000 | 3710.322 | 2.697 | True |
| chunk0070000_0080000 | 1 | success | 0 | 80000 | 3723.397 | 2.687 | True |
| chunk0080000_0090000 | 1 | success | 0 | 90000 | 3715.724 | 2.692 | True |
| chunk0090000_0100000 | 1 | success | 0 | 100000 | 3706.343 | 2.699 | True |

### Watchdog / recovery events

- none

