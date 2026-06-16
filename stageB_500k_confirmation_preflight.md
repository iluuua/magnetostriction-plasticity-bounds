# Stage B 500k Confirmation Preflight

Static preparation report.

Required gates:

- current Stage B 100k complete;
- `postrun_decision.json` exists;
- branch is `A_500k_confirmation`;
- winner has confirmed DXA line signal;
- production logs are clean;
- disk free is at least 60 GB;
- no active `lmp_kokkos_cuda.exe`;
- exact manual approval is present for `--launch`.

Dry-run and validate-only modes never launch MD.

