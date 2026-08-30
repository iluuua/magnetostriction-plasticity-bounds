# Stage B 500k Confirmation Plan

Prepared for the case where Stage B realism 100k produces confirmed DXA line
signal.

The 500k path is single-case only:

- source: completed Stage B 100k `postrun_decision.json`;
- branch: `A_500k_confirmation`;
- case: `winner_case` only;
- atom target: 500k class;
- production steps: 100000;
- chunk size: 10000;
- restart every chunk;
- no full factorial;
- no additional seeds by default.

The generated effective config is written by
`scripts/launch_stageB_500k_confirmation.py` only after preflight passes.

