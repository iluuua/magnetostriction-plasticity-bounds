# Interface trial_001 — 120 MPa compression-ramp check

## Status

120 MPa compression-ramp completed as a controlled sanity-run.

This is not final physical validation. The goal was to check numerical stability, interface integrity, dangerous short contacts, warning-pair behavior, local stress-profile proxy, and visual geometry in OVITO.

## Model

- Interface: Al(111) / Fe4Al13(100)
- Structure: `trial_001`
- Data source: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k_long`
- Boundary: `p p f`
- Support: fixed-bottom Al layer
- Thermostat: NVT on mobile atoms only
- Loading direction: `-z`, toward Al side
- Loaded region: Fe4Al13-side near-interface region
- Target stress: 120 MPa
- Final force per loaded atom: `-0.0014714153049055854 eV/A`
- Protocol: 5000-step ramp + 10000-step hold

## LAMMPS basic result

- Final step: 15000
- Frames: 151
- Atoms per frame: 618
- ERROR: no
- nan: no
- lost atoms: no
- Dangerous builds: 0 / 0

## Distance checks

- Total atoms: 618
- Al atoms: 522
- Fe atoms: 96
- Minimum Al-Al distance: 2.4546 A
- Minimum Fe-Fe distance: 2.5689 A
- Minimum Al-Fe distance: 2.0233 A
- Minimum cross-slab distance: 2.5259 A
- Minimum cross-slab Al-Fe distance: 2.5569 A
- Pairs below 1.8 A: 0
- Al-Fe pairs below 2.1 A: 1
- Cross-slab Al-Fe pairs below 2.1 A: 0
- `safe_basic`: True

## Warning pair 232-260

- Pair: 232-260
- Type: Al-Fe
- Classification: internal Fe4Al13 pair
- Contact type: intermittent short contact
- Minimum distance over trajectory: 1.9757 A
- Maximum distance over trajectory: 2.2053 A
- Mean distance over trajectory: 2.0788 A
- Frames below 2.1 A: 106
- Frames below 1.8 A: 0
- Monotonic collapse: False

Verdict: monitor-warning, not blocker.

## Stress profile

Stress profile is interpreted as a comparative virial proxy, not as an absolute experimentally validated stress field.

- Interface z: 40.2615 A

Al-side interface bin, z=35..40 A:

- Hydrostatic proxy mean: -0.8366 GPa
- Sigma_zz mean: -0.3445 GPa

Fe-side interface bin, z=40..45 A:

- Hydrostatic proxy mean: -0.8353 GPa
- Sigma_zz mean: -0.2636 GPa

Highest absolute hydrostatic proxy:

- Bin: z=5..10 A
- Hydrostatic proxy mean: -4.1900 GPa
- Interpretation: fixed-bottom support artifact, not direct interface maximum.

## OVITO visual review

Checked frames:

- 0
- 50
- 100
- 150

Selections used:

```text
ParticleIdentifier == 232 || ParticleIdentifier == 260
Position.Z > 32 && Position.Z < 48
```

Visual findings:

- Pair 232-260 remains inside the Fe4Al13 slab.
- No visible monotonic collapse of pair 232-260.
- No visible interface detachment.
- No visible empty gap at the interface.
- No visible whole-block drift of Fe4Al13 relative to Al.
- No visible atom ejection.
- Bright red atoms in screenshots are selection/coloring markers, not stress-map and not automatically defects.

Screenshots to attach manually if needed:

- `results/figures/ovito_review_120mpa/frame000_pair_232_260.png`
- `results/figures/ovito_review_120mpa/frame050_pair_232_260.png`
- `results/figures/ovito_review_120mpa/frame100_pair_232_260.png`
- `results/figures/ovito_review_120mpa/frame150_pair_232_260.png`
- `results/figures/ovito_review_120mpa/frame000_interface_zone.png`
- `results/figures/ovito_review_120mpa/frame050_interface_zone.png`
- `results/figures/ovito_review_120mpa/frame100_interface_zone.png`
- `results/figures/ovito_review_120mpa/frame150_interface_zone.png`

## Verdict

120 MPa compression-ramp is accepted as a controlled sanity-run.

Do not treat this as final physical validation. Before higher loads, compare 0 / 60 / 120 MPa consistently and document boundary-condition artifacts.

