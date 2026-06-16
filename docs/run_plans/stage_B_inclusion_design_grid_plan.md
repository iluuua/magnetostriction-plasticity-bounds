# Stage B inclusion design grid plan

Date: 2026-06-11

Status: future-work design spec. Do not run this stage until the active A0/A1/A2 size sweep has a reviewed result.

## Goal

Stage A asks whether the eigenstrain surrogate can produce a measurable defect response at increasing size:

```text
inclusion eigenstrain -> local stress -> Al defects / dislocations
```

Stage B starts only after that baseline size sweep. Its goal is to move from:

```text
is there any effect at all?
```

to:

```text
which inclusion and material-realism parameters make the effect controllable or dangerous?
```

The magnetic field is still not simulated directly. LAMMPS SPIN could in principle model spin-lattice dynamics, Zeeman terms, exchange, and anisotropy, but the Fe4Al13 / FeAl problem currently lacks the required magnetic moments, exchange constants, spin-lattice coupling, magnetostriction tensor, anisotropy, field orientation, domain structure, and validated spin-lattice Al-Fe potential. Stage B remains a mechanical surrogate through inclusion eigenstrain.

## Parameter Priorities

| Parameter | Criticality | Why it matters |
|---|---:|---|
| Position relative to grain boundary | 10/10 | Grain boundaries can dominate defect nucleation and can turn a null single-crystal result into a visible plasticity result. |
| Polycrystal | 10/10 | A realistic microstructure may need grain-boundary and grain-orientation effects before scaling to very large ideal crystals. |
| Inclusion size | 9/10 | Elastic/plastic zone size and nucleation thresholds are strongly size-dependent. |
| Predefects / vacancies / initial dislocations | 9/10 | Real Al is not defect-free; pre-existing defects may control the threshold. |
| Shape | 8/10 | Spheres, elongated ellipsoids, and platelets concentrate stress differently. |
| Concentration / multi-inclusion | 8/10 | Multiple inclusions can create interacting stress fields and collective effects. |
| Composition Fe4Al13 / FeAl / Fe3Al | 8/10 | Phase choice changes modulus, lattice mismatch, interface chemistry, and potential validity. |
| Crystallographic orientation | 8/10 | Inclusion/matrix orientation controls mismatch and slip-system activation. |
| Cyclic exposure | 7/10 | A magnetic-memory surrogate may need repeated eigenstrain cycles after static loading is understood. |
| Temperature | 6/10 | Temperature changes activation, but it is secondary until geometry and defects are calibrated. |

## Why Not A Full Factorial Grid

A naive full grid would explode immediately. For example, a 3x3x3x3x3x5xN sweep over size, shape, position, composition, predefects, temperature, and eps values would already create hundreds or thousands of production cases before adding atom-count choices and repeats.

That is not a practical or scientific plan. Stage B must use progressive gated design-of-experiments:

- change only one high-value axis at a time;
- keep A-stage baselines as references;
- run smoke and short checks before production;
- stop branches that show no signal or poor stability;
- escalate expensive geometry only when it answers a clear question.

## Minimal Stage B Grid

### B1_size

Purpose: determine whether inclusion size controls signal strength once the A-stage size baseline is known.

```yaml
atom_targets: [120000, 250000]
inclusion_sizes_nm: [2, 4, 6]
eps_z: [0.0025, 0.0100]
shape: ellipsoid_1_1_2
position: grain_interior
```

Run B1 first if A1_medium or A2 shows a stable signal in the ideal single-crystal geometry.

### B2_shape

Purpose: compare stress concentration caused by shape after a useful size is known.

```yaml
atom_targets: [120000, 250000]
inclusion_sizes_nm: [from_B1_best_or_signal]
shapes: [sphere, ellipsoid_1_1_2, platelet]
eps_z: [0.0025, 0.0100]
```

Use the best or most interesting B1 size. Do not run all shapes for all sizes unless B1 shows a strong reason.

### B3_position

Purpose: test whether the same inclusion becomes more active near grain boundaries.

```yaml
positions: [grain_interior, near_grain_boundary]
eps_z: [0.0025, 0.0100]
```

Use the best or most interesting size+shape from B1/B2.

### B4_predefects

Purpose: test whether realistic defects lower the threshold.

```yaml
variants: [perfect, vacancies_low, vacancies_medium, seed_dislocation_if_available]
eps_z: [0.0025, 0.0100]
```

Run this branch especially if the ideal single crystal remains elastic.

### B5_multi_inclusion

Purpose: test collective stress-field interactions.

```yaml
inclusion_counts: [1, 2, 4]
eps_z: [0.0025, 0.0100]
```

Run only after B1-B4 produce a stable signal. Multi-inclusion cases are expensive and can be hard to interpret without single-inclusion baselines.

### B6_composition

Purpose: compare Fe4Al13, FeAl, and Fe3Al only after structure and potential validation.

```yaml
compositions: [Fe4Al13, FeAl, Fe3Al]
```

This branch requires validated structures, validated potentials, and an interface/orientation search. Do not use composition as a free parameter before the Al-Fe potential track is scientifically defensible for each phase.

## Gate Logic

- If A1_medium at 200k-300k shows no signal, Stage B should prioritize grain boundaries and predefects over 500k/700k ideal monocrystal scaling.
- If A1_medium shows signal, Stage B should first tune inclusion size and shape.
- If 500k/700k is needed, use it only for size-effect confirmation, not as a blind default.
- If A2_large is blocked by disk, time, or stability, Stage B should prefer smaller targeted design cases over larger brute-force cases.
- Each Stage B substage must be manually enabled after reviewing the previous stage report.

## Metrics

Required metrics:

- dislocation count;
- total dislocation line length;
- dislocation density;
- FCC/HCP/OTHER fractions;
- stacking-fault indicators;
- plastic-zone radius or extent;
- stress and thermo summaries;
- runtime and cost metrics.

The same analysis definitions should be reused across Stage A and Stage B so size, geometry, and material-realism effects can be compared.

## Production Strategy

- Use the same GPU profile only if the current Stage A pipeline validates it.
- Chunked production is mandatory.
- Restart/resume is mandatory.
- Do not use `CUDA_LAUNCH_BLOCKING` in production.
- Do not use `compute-sanitizer` in production.
- Generate run-local inputs only.
- Do not edit tracked LAMMPS templates in place.
- Do not modify potentials or baseline structures in place.
- Do not run multiple GPU LAMMPS cases concurrently on one GPU.

## Recommended Execution Order

1. Review A1_medium and A2 gate reports.
2. Choose the branch:
   - signal present: B1_size -> B2_shape;
   - no signal: B3_position -> B4_predefects;
   - realistic phase question: B6_composition after validation.
3. Enable exactly one Stage B substage in a copied runtime config.
4. Run smoke -> short -> production with chunked restart/resume.
5. Stop and write a gate report before expanding the grid.

## Stop Conditions

Stop a branch when:

- repeated CUDA errors occur;
- free disk falls below the configured threshold;
- physics instability appears;
- output metrics are indistinguishable from baseline after the intended question is answered;
- a cheaper branch can answer the next question more directly.
