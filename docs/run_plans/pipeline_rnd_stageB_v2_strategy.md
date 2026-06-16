# Stage B-Aware Optimization Pipeline v2 Strategy

Date: 2026-06-12

Status: R&D planner design and prototype. Planner only: no MD execution, no
LAMMPS launch, no active run-root access.

## Executive Summary

Stage B v2 turns the next month of calculations into a staged adaptive design
instead of a full factorial grid. The current execution lane remains
`A1_custom_100k`; this planner waits for that gate, then proposes the smallest
informative Stage B wave:

- physical eps signal at 0.0025: confirm at 250k after manual approval, then
  run B1_size;
- only overload eps signal at 0.0100: run B5 threshold eps [0.0050, 0.0075],
  then pivot to B3 realism if the threshold remains high;
- no A1_100k signal: run B3 position/predefects before spending on blind
  500k/700k ideal-monocrystal scaling.

The implemented prototype is:

- `analysis/python/science_optimizer/pipeline_rnd_stageB_v2.py`
- `scripts/run_pipeline_rnd_stageB_v2.py`
- policy input: `configs/pipeline_rnd_stageB_v2_policy.template.yaml`
- dry-run output root: `runs/pipeline_rnd_stageB/dry_run_<timestamp>/`

## What Changed Versus The Old Pipeline

The earlier planner layer was Stage A-centric: it reasoned over size, eps,
fidelity, cost, and realism pivots. Stage B v2 makes the inclusion design axes
first-class policy axes:

- inclusion size: [2, 4, 6] nm;
- inclusion shape: sphere, ellipsoid_1_1_2, platelet;
- inclusion position: grain_interior, near_grain_boundary;
- predefects: perfect, vacancies_low, vacancies_medium,
  seed_dislocation_if_available;
- concentration: inclusion_count [1, 2, 4].

It also removes the old default short run as a separate fidelity. The
`early_production_gate` is the first two 10k production chunks and can continue
resumably to full 100k production for winners.

## Why Full Factorial Is Rejected

The naive Stage B grid is already:

```text
3 inclusion sizes
x 3 shapes
x 2 positions
x 4 predefect variants
x 3 inclusion counts
x 2 eps values
= 432 configs
```

At 100k atoms, smoke plus production for that grid is estimated at about
6400 GPU-hours before atom-count repeats, 250k/500k/700k confirmation, analysis
cost, or replicate seeds. The staged B1-B4 plan, counting smoke plus selected
production winners, is about 110 GPU-hours. The rejected grid is therefore
roughly 58x more expensive for a less informative design.

## Why Gradient Descent Is Not Appropriate

Most Stage B variables are categorical or discrete: shape, position,
predefect variant, inclusion count, and composition. There is no meaningful
continuous gradient over those axes.

The main observable is threshold-like defect nucleation. It can remain exactly
zero over broad regions and then appear abruptly, so finite-difference
gradients would mostly measure noise. MD trajectories also include thermal
variance and infrastructure failure modes such as hangs or CUDA errors, which
must be handled by gate/retry/stop policy rather than a step direction.

## Why Stage B Parameters Matter

| Axis | Criticality | Reason |
| --- | ---: | --- |
| position | 10/10 | Grain boundaries/interfaces can dominate nucleation. |
| inclusion_size_nm | 9/10 | Size controls local stress field and plastic-zone scale. |
| predefects | 9/10 | Real Al is not a perfect monocrystal; defects lower barriers. |
| shape | 8/10 | Sharp or elongated shapes concentrate stress differently. |
| inclusion_count | 8/10 | Multiple inclusions can overlap stress fields and damage zones. |

Composition remains gated. `Fe4Al13` is enabled; `FeAl` and `Fe3Al` require
validated structure, potential compatibility, and interface orientation before
they become calculation axes.

## Stage B Staged Waves

### B0_baseline_lock

Freeze the design before changing any axis:

- atom target: 100k by default;
- eps: [0.0025, 0.0100];
- inclusion size: assume 4 nm, but mark `VERIFY_BUILDER`;
- shape: ellipsoid_1_1_2;
- position: grain_interior;
- predefect: perfect;
- count: 1;
- composition: Fe4Al13.

### B1_size

Vary only `inclusion_size_nm` [2, 4, 6]. Keep shape, position, predefect, count,
and composition fixed. Smoke all 6 size/eps candidates, then promote the top 2
to early production and full production only if the gate remains useful.

### B2_shape

Use the best or most informative B1 size. Vary shape across sphere,
ellipsoid_1_1_2, and platelet for eps [0.0025, 0.0100]. Smoke all 6 candidates,
then promote the top 2.

### B3_position_predefects

Use the best size/shape from B1/B2, or run this first if A1_100k has no ideal
monocrystal signal. Vary:

- positions: grain_interior, near_grain_boundary;
- predefects: perfect, vacancies_medium, seed_dislocation_if_available.

Smoke all 12 candidates, then promote the top 2. This branch is the preferred
realism pivot before blind 700k ideal-monocrystal scaling.

### B4_concentration

Only after a single-inclusion signal or manual approval. Vary inclusion count
[1, 2, 4] for the best single-inclusion design. Reject the branch if the
builder cannot place inclusions with safe clearance and non-overlap. Smoke all
6 candidates, then promote only the top 1.

### B5_eps_threshold

Only if eps=0.0100 has signal and eps=0.0025 does not. Test eps [0.0050,
0.0075] to locate the threshold. If the threshold remains high, prioritize B3
realism rather than larger ideal monocrystals.

## Cost Model

Anchor:

```text
ref_atoms = 24259
ref_steps_per_s = 9.46
estimated_steps_per_s = ref_steps_per_s * ref_atoms / atom_count
estimated_hours = steps / estimated_steps_per_s / 3600 * overhead_factor
```

Overheads:

- 100k: 1.15;
- 250k: 1.3;
- 500k/700k: 1.5;
- Stage B small variant: 1.2.

Key estimates:

| Item | Estimated GPU-hours |
| --- | ---: |
| 100k production, 1 eps | 13.92 |
| 100k production, 2 eps | 27.84 |
| 250k production, 1 eps | 39.34 |
| 500k production, 1 eps | 90.78 |
| 700k production, 1 eps | 127.09 |
| B1_size smoke only | 1.74 |
| B1_size smoke + top-2 production | 30.79 |
| B2_shape smoke + top-2 production | 30.79 |
| B3_position_predefects smoke + top-2 production | 32.54 |
| B4_concentration smoke + top-1 production | 16.27 |
| rejected full factorial smoke + production | 6400.28 |

## Objective And Promotion Criteria

The prototype implements `science_utility`:

```text
defect_signal_score =
3.0 * I(dislocation_count > 0)
+ 1.5 * log1p(total_line_length)
+ 1.0 * max(0, hcp_fraction - baseline_hcp_fraction)
+ 0.8 * max(0, other_fraction - baseline_other_fraction)
+ 1.0 * I(plastic_zone_detected)
+ 0.5 * I(stacking_fault_indicator)

penalty =
4.0 * I(not stable)
+ 3.0 * I(failed)
+ 3.0 * I(hung)
+ 3.0 * I(cuda_error)
+ 2.0 * I(lost_atoms)
+ 2.0 * I(nan_found)
+ 0.1 * runtime_hours

science_utility = defect_signal_score - penalty
```

Promote when any of these are present and the case is stable:

- dislocation_count > 0;
- total_line_length grows;
- HCP/OTHER increases versus baseline;
- plastic_zone detected;
- physical eps=0.0025 shows signal;
- overload eps=0.0100 reveals a threshold worth refining.

## Kill Criteria

Stop or reject a branch on:

- failed run;
- repeated hang;
- CUDA error;
- lost atoms;
- NaN;
- unstable thermo;
- invalid builder placement;
- inconsistent atom IDs or inclusion IDs;
- no signal plus high runtime cost;
- multi-inclusion chaos that prevents interpretation.

## When To Stay In Ideal Monocrystal

Stay in the ideal monocrystal when A1_100k or a Stage B wave shows a clean,
interpretable signal and the next question is size or shape confirmation. In
that case, B1_size and B2_shape are higher-value than immediately adding
predefects or concentration.

## When To Pivot To Realism

Pivot to B3 position/predefects when:

- A1_100k is stable but has no dislocations, no HCP/OTHER growth, and no plastic
  zone;
- only eps=0.0100 has a signal and B5 threshold remains too high;
- larger ideal monocrystal scaling would mainly spend cost without changing the
  physical question.

The first realism checks should be near_grain_boundary and vacancies_medium;
seed_dislocation_if_available remains conditional on builder support.

## When To Go 250k/500k/700k

Use 250k as a manual confirmation scale when 100k shows interpretable signal,
especially at eps=0.0025 or in a near-boundary B3 case.

Use 500k only after a stable production signal leaves a real size-effect
question unresolved. Use 700k only after 500k remains stable and informative.
Never use 700k as the first answer to a null ideal-monocrystal result.

## Direct Magnetic Field

Direct magnetic field remains a disabled future track. Do not implement SPIN or
field coupling until magnetic moments, exchange constants, spin-lattice
coupling, magnetostriction tensor, anisotropy, field orientation, domain
structure, and a validated spin-lattice Al-Fe potential exist.

## Risk Table

| Risk | Mitigation |
| --- | --- |
| Full factorial explosion | Use B1-B5 staged waves and smoke ranking. |
| Smoke signal does not predict production | Treat smoke as stability and early signal only; use early production gate before full production. |
| Builder cannot place multi-inclusions safely | Reject B4 until clearance/non-overlap is validated. |
| Ideal monocrystal stays null | Pivot to B3 realism before 700k. |
| Overload-only signal misleads strategy | Run B5 threshold and then B3 if threshold remains high. |
| Composition invalidity | Keep FeAl/Fe3Al disabled until validation exists. |
| Infrastructure failures hide physics | Hard reject CUDA/lost_atoms/NaN; retry only a single recovered hang. |

## Implementation Roadmap

1. Keep A1_custom_100k execution isolated and wait for its gate report.
2. Use `run_pipeline_rnd_stageB_v2.py --cost-model` to review current budget.
3. Use `--mock-decisions` to sanity-check gate actions against A1 outcomes.
4. Use `--generate-stageB-queue` to export proposal data.
5. After manual review, copy the Stage B template into a runtime config for one
   selected wave only.
6. Keep direct magnetic field, full composition sweep, and heavy optimizers
   disabled until data and validation justify them.

## Exact Next Recommended Queue After A1_100k Results

If A1_100k eps=0.0025 has signal:

1. Write A1_100k gate report.
2. Confirm the signal at 250k only after manual approval.
3. Start B1_size smoke queue at 100k for size [2, 4, 6] and eps [0.0025,
   0.0100].
4. Promote the top 2 B1 candidates through early production gate.

If only A1_100k eps=0.0100 has signal:

1. Run B5_eps_threshold proposals for eps [0.0050, 0.0075].
2. If threshold remains high, start B3_position_predefects.
3. Do not prioritize blind 700k ideal monocrystal.

If A1_100k has no signal:

1. Start B3_position_predefects smoke proposals.
2. Prioritize near_grain_boundary and vacancies_medium.
3. Keep B4 concentration gated until a single-inclusion signal exists.
4. Keep 500k/700k manual-only and deprioritized.
