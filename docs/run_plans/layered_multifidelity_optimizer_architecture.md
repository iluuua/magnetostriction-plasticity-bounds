# Layered multi-fidelity optimizer architecture

Date: 2026-06-12

Status: implemented as a planner-only layer (v1, rule-based). No MD execution.

Code: `analysis/python/science_optimizer/` + `scripts/run_layered_optimizer.py`
Config: `configs/layered_optimizer_policy.yaml`
Outputs: `runs/science_optimizer/dry_run_{timestamp}/`

This layer sits ABOVE the existing GPU stage runner
(`analysis/python/stage_runner/gpu_grid.py`). It does not replace it and does
not modify it. It decides *what to propose next, at which size, at which
fidelity, and when to stop/promote/pivot a branch*, and exports that plan as
data (YAML/JSONL/Markdown) for a human or the runner to act on.

## Why not a full grid search

The naive search space is already combinatorial:

```text
eps (5) x atom targets (8) x inclusion size (3) x shape (3) x position (2)
x predefects (4) x count (3) x composition (3) = ~26 000 cases
```

One A1_medium production (100k steps, 250k atoms) costs roughly 30 GPU-hours
on the RTX 3060 at the observed ~9.4 steps/s @ 24k atoms (linear-in-atoms
scaling). Even the eps x size sub-grid alone at production fidelity is weeks
of compute; the full grid is years. A grid also spends most of its budget on
regions we already expect to be null (tiny eps at tiny sizes) and cannot
react to instability (hangs, CUDA errors) other than by burning more time.

## Why not gradient descent

- Most axes are **discrete or categorical** (shape, position, composition,
  predefect variant, inclusion count). There is no gradient.
- The main observable (dislocation nucleation) is a **threshold/rare event**:
  zero over a wide region, then abrupt onset. Finite-difference gradients are
  zero or noise almost everywhere.
- Single MD trajectories are **stochastic** (thermal noise, restart seams),
  so a numerical gradient would need many repeats per point - more expensive
  than the grid it was supposed to avoid.
- Part of the outcome space is **infrastructure failure** (hang, cudaError),
  which is not differentiable and must be handled by retry/stop logic, not by
  a step direction.

## Why a layered adaptive decision system

The actual structure of the problem is a small number of *nested gates*:
cheap checks decide whether expensive checks are worth it (fidelity), small
systems decide whether large systems are worth it (size), ideal crystals
decide whether realism branches are needed (physics), and every branch can
die early on stability or cost. That is exactly a layered multi-fidelity
racing scheme, not a black-box optimization run. v1 encodes the gates as
explicit rules; a sampler (Bayesian/Hyperband) can later replace *candidate
selection inside a layer* without changing the gate skeleton.

## Layer model (L0..L7)

| Layer | Name | Maps to physics / computation |
|---|---|---|
| L0 | infrastructure | existing GPU runner: chunked production, watchdog, restart/resume, state.json. The planner only emits queue items + config patches against it. |
| L1 | fidelity | how long we integrate: smoke 2k / short 20k / production 100k steps / large_confirmation. |
| L2 | size_scale | how many atoms: 24k -> 80k/120k -> 200k/250k/300k -> 500k/700k. Controls finite-size artifacts vs cost. |
| L3 | physics_surrogate | eigenstrain eps_z in the Fe-Al inclusion = magnetostriction surrogate; values 0 / 0.0010 / 0.0025 (physical) / 0.0050 / 0.0100 (overload). |
| L4 | inclusion_design | Stage B axes: size_nm, shape, position, predefects, count, composition. |
| L5 | realism | monocrystal -> grain boundary -> vacancies -> seeded dislocation -> polycrystal -> multi-inclusion. |
| L6 | objective | what "good" means: defect signal, stability, cost, interpretability (objectives.py). |
| L7 | decision_policy | promote / stop / retry / pivot / confirm-on-larger-scale / manual review (decision_policy.py). |

Each layer exposes `allowed_values`, `prerequisites`, `cost_level`,
`risk_level`, `scientific_value`, `promotion_rules`, `stop_rules`
(`layers.py`), so the gate logic is data, not folklore.

## Fidelity ladder (L1)

| Rung | Steps | Purpose | Gate |
|---|---:|---|---|
| smoke | 2 000 | stability + early signal | entry point of every case |
| short | 20 000 | medium confirmation | requires smoke pass |
| production | 100 000 | final metrics | requires smoke AND short pass |
| large_confirmation | 100 000 @ 250k/500k/700k atoms | size-effect confirmation only | requires production signal or an explicit unresolved size-effect gate |

Hard rule: failed / hung / nan / lost-atoms / cuda-error trials are rejected.
A single hang with successful restart recovery earns exactly one retry at the
same fidelity; a second hang stops the branch (matches the chunked
watchdog runner semantics: retry_hung_chunk_once).

## Size-scale decisions (L2)

- `A0_24k` validates the pipeline and provides baselines (currently covered
  by the active sweep `runs/stage_sweep_gpu_grid/20260611-175339`).
- `A1_small` (80k/120k) asks whether any size effect appears at all.
- `A1_medium` (200k/250k/300k) is the **main scientific gate**: it decides
  the whole downstream strategy.
- `A2_large` (500k/700k) is confirmation-only and the most expensive rung
  (~60h/85h estimated per production at the observed rate, i.e. multi-session
  chunked runs).

### When to go 500k/700k

Only when BOTH hold:

1. A1_medium production is stable, and
2. there is a defect signal to confirm (science_utility >= 1.0), or a
   documented, still-open size-effect question that a human explicitly
   gates through.

700k additionally requires that 500k was stable AND remained informative.
A null A1_medium result never escalates the ideal monocrystal to 700k.

### When to pivot to grain boundary / predefects / polycrystal

If A1_medium production is stable but shows **no signal** (no dislocations,
HCP/OTHER at baseline, no plastic zone), the bottleneck is most likely the
unrealistically perfect crystal, not the system size. The policy then emits
`pivot_to_realism`: near_grain_boundary position, vacancies_medium,
seed_dislocation_if_available (polycrystal stays future work until a builder
exists), each at smoke fidelity first, one axis at a time.

## Stage B inclusion-design search (L4)

Stage B (see `docs/run_plans/stage_B_inclusion_design_grid_plan.md` and
`configs/stage_sweep_inclusion_design.template.yaml`) plugs in as the L4
layer, gated by the A1_medium outcome:

- signal exists -> B1_size (2/4/6 nm), then B2_shape (sphere/platelet vs the
  ellipsoid baseline), at the cheap informative size (120k atoms);
- no signal -> B3_position (near_grain_boundary) and B4_predefects become
  the priority branch (this *is* the realism pivot);
- B5 multi-inclusion only after a single-inclusion signal exists;
- B6 composition (FeAl, Fe3Al) only after validated structures, potentials,
  and an interface-orientation search.

No full factorial: every wave changes one high-value design axis at a time,
and every Stage B substage requires manual enabling of a copied template.

## Objectives (L6)

`objectives.py` implements:

```text
defect_signal_score = 3.0*I(dislocations>0) + 1.5*log1p(line_length)
                    + 1.0*max(0, hcp - hcp_baseline)
                    + 0.8*max(0, other - other_baseline)
                    + 1.0*I(plastic_zone) + 0.5*I(stacking_fault)
penalty = 4.0*I(!stable) + 3.0*(failed + hung + cuda_error)
        + 2.0*(lost_atoms + nan_found) + 0.1*runtime_hours
science_utility = defect_signal_score - penalty
```

plus stability_score, cost_efficiency (utility per hour),
interpretability_score, and a promotion label (reject / retry /
promote_to_short / promote_to_production / confirm_large / pivot_to_realism /
manual_review). Signal thresholds (HCP +0.05 %, OTHER +0.5 %) mirror the
science_gates of `configs/stage_sweep_gpu_grid.yaml`.

## Decision policy (L7)

`rule_based_policy_v1`, first match wins: hang handling -> hard failures ->
branch failure rate -> runtime/disk budget guard -> smoke/short promotion ->
production outcome (confirm_large / pivot_to_realism / manual review) ->
large_confirmation review. Every `Decision` reports what to run next, why,
required fidelity, expected cost (hours + runtime class + budget check),
stop conditions, and whether human approval is required. Four canonical mock
scenarios (no-signal pivot, signal confirmation, hang retry/stop, expensive
low-value stop) are exported into every dry-run decision report.

## Direct magnetic field stays future work

The eigenstrain eps_z is a mechanical surrogate for magnetostrictive loading.
A direct magnetic simulation (LAMMPS SPIN or similar) is documented as
future work because it requires, none of which currently exist for this
system: magnetic moments, exchange constants, spin-lattice coupling, a
magnetostriction tensor, anisotropy constants, field orientation, domain
structure, and a validated spin-lattice Al-Fe potential. Until then the
surrogate ladder grows instead: eigenstrain direction sweep -> tensor-like
anisotropic eigenstrain -> cyclic eigenstrain.

## Integration path for Bayesian optimization / Hyperband (v2)

v1 is deliberately rule-based: with ~0 completed production trials there is
nothing for a surrogate model to learn from, and gate/stability constraints
dominate every decision. The upgrade path is already shaped:

- `decision_policy.get_policy()` is the single entry point; v2 policies
  (`bayesian_optimizer_v2`, `hyperband_v2`) exist as documented placeholders
  behind the same `Decision` interface.
- Bayesian/TPE (after roughly 15-20 completed production trials with
  science_utility values): model science_utility over (eps_z, atom_target,
  design axes), propose by expected improvement, but only *within* the layer
  gates - the fidelity ladder and stop rules stay authoritative.
- Hyperband maps naturally onto the existing budget ladder (2k/20k/100k
  steps as rungs, defect_signal_score as the racing metric) once smoke-level
  early metrics are shown to correlate with production outcomes.
- No Optuna/BoTorch/Ax dependency is added until that data exists; the
  current implementation is stdlib + PyYAML only.
