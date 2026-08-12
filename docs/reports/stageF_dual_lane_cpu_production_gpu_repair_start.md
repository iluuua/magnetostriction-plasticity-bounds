# Stage F dual-lane CPU production / GPU repair start

- Timestamp: 2026-07-01T00:19:18+03:00
- Run ID: `20260701-001918`
- CPU fallback approval: explicitly approved by prompt.txt on 2026-06-30
- Target run root: `runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748`

## Pair rule

Valid pairs are `CPU_eps00194 - CPU_eps0000` or `GPU_eps00194 - GPU_eps0000`.
Mixed CPU/GPU deltas, mixed zhi values, or mixed protocols are invalid.

## CPU lane

1. Prepare eps0000 and eps00194 zhi=200 data under a fresh comparable CPU root.
2. Run eps0000 CPU 10k smoke.
3. Run eps00194 CPU 10k smoke.
4. Only if both smokes are clean, run eps0000 50k CPU production.
5. Only if eps0000 production is clean, run eps00194 50k CPU production.

## GPU lane

GPU backend repair remains separate. GPU production is still gated behind a valid comparable GPU smoke pair and no GPU result will be mixed into the CPU fallback delta.
