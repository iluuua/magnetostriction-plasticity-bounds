# Interface trial_001 — 200 MPa upper-bound compression-ramp check

## Status

200 MPa compression-ramp completed and was accepted as a controlled upper-bound / failure-probe after manual OVITO review.

This is not final physical validation. The goal of this scenario was to test the numerical and geometrical stability limit of the simplified flat-interface `trial_001` model.

## Model

- Interface: Al(111) / Fe4Al13(100)
- Structure: `trial_001`
- Data source: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k_long`
- Boundary: `p p f`
- Support: fixed-bottom Al layer
- Thermostat: NVT on mobile atoms only
- Loading direction: `-z`, toward Al side
- Loaded region: Fe4Al13-side near-interface region
- Target stress: 200 MPa
- Final force per loaded atom: `-0.002452358841509309 eV/A`
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
- Minimum Al-Al distance: 2.4587 A
- Minimum Fe-Fe distance: 2.6223 A
- Minimum Al-Fe distance: 2.0232 A
- Minimum cross-slab distance: 2.4587 A
- Minimum cross-slab Al-Fe distance: 2.4999 A
- Pairs below 1.8 A: 0
- Cross-slab Al-Fe pairs below 2.1 A: 0
- `safe_basic`: True

## Warning pair 232-260

- Pair: 232-260
- Type: Al-Fe
- Classification: internal Fe4Al13 pair
- Contact type: intermittent short contact
- Minimum distance over trajectory: 1.9126 A
- Maximum distance over trajectory: 2.2537 A
- Mean distance over trajectory: 2.0797 A
- Frames below 2.1 A: 99
- Frames below 1.8 A: 0
- Monotonic collapse: False

Verdict: monitor-warning, not a loading blocker.

## Stress profile

Stress profile is interpreted as a comparative virial proxy, not as an absolute experimentally validated stress field.

- Interface z: 40.2844 A

Al-side interface bin, z=35..40 A:

- Hydrostatic proxy mean: -0.7892 GPa
- Sigma_zz mean: -0.2664 GPa

Fe-side interface bin, z=40..45 A:

- Hydrostatic proxy mean: -0.7687 GPa
- Sigma_zz mean: -0.1956 GPa

Highest absolute hydrostatic proxy:

- Bin: z=5..10 A
- Hydrostatic proxy mean: -4.1797 GPa
- Interpretation: fixed-bottom support artifact, not direct interface maximum.

## OVITO visual review

Manual OVITO review was completed for frames:

- 0
- 50
- 100
- 150

Selections used:

- `ParticleIdentifier == 232 || ParticleIdentifier == 260`
- `Position.Z > 32 && Position.Z < 48`

Visual findings:

- Pair 232-260 remains inside the Fe4Al13 slab.
- No visible monotonic collapse of pair 232-260.
- No visible interface detachment.
- No visible empty gap at the interface.
- No visible whole-block drift of Fe4Al13 relative to Al.
- No visible atom ejection.
- Red atoms are selection/coloring markers, not a stress-map and not automatically defects.

## Verdict

200 MPa compression-ramp is accepted as a controlled upper-bound / failure-probe after manual OVITO review.

Do not treat this as final physical validation. Stress/atom is treated as a comparative virial proxy, and the highest hydrostatic proxy remains near fixed-bottom support.
