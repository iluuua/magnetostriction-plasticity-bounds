# Interface trial_001 — 147 MPa compression-ramp check

## Status

147 MPa compression-ramp completed and was accepted as a controlled sanity-run after manual OVITO review.

This is not final physical validation. The goal was to check numerical stability, dangerous short contacts, cross-slab interface contacts, warning-pair behavior, and local stress-profile proxy after the accepted 120 MPa sanity-run.

## Model

- Interface: Al(111) / Fe4Al13(100)
- Structure: `trial_001`
- Data source: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k_long`
- Boundary: `p p f`
- Support: fixed-bottom Al layer
- Thermostat: NVT on mobile atoms only
- Loading direction: `-z`, toward Al side
- Loaded region: Fe4Al13-side near-interface region, z=40.16445..48.16445 A
- Target stress: 147 MPa
- Final force per loaded atom: `-0.001802483748509342 eV/A`
- Protocol: 5000-step ramp + 10000-step hold
- NPT: not used
- 200 MPa: not run

## LAMMPS basic result

- Final step: 15000
- Frames: 151
- Atoms per frame: 618
- ERROR: no
- nan: no
- lost atoms: no
- Dangerous builds: 0 / 0
- Final mobile temperature: 294.4813 K
- Last-20 mean mobile temperature: 302.1072 K
- Mean pressure over thermo rows: -4278.0545 bar

## Distance checks

- Total atoms: 618
- Al atoms: 522
- Fe atoms: 96
- Minimum Al-Al distance: 2.4039 A
- Minimum Fe-Fe distance: 2.6238 A
- Minimum Al-Fe distance: 2.0242 A
- Minimum cross-slab distance: 2.5018 A
- Minimum cross-slab Al-Fe distance: 2.5930 A
- Pairs below 1.8 A: 0
- Al-Fe pairs below 2.1 A: 1
- Cross-slab Al-Fe pairs below 2.1 A: 0
- `safe_basic`: True

## Warning pair 232-260

- Pair: 232-260
- Type: Al-Fe
- Classification: internal Fe4Al13 pair
- Contact type: intermittent short contact
- Minimum distance over trajectory: 1.9562 A
- Maximum distance over trajectory: 2.2168 A
- Mean distance over trajectory: 2.0732 A
- Frames below 2.1 A: 104
- Frames below 1.8 A: 0
- Monotonic collapse: False

Verdict: monitor-warning, not a script-level loading blocker.

## Stress profile

Stress profile is interpreted as a comparative virial proxy, not as an absolute experimentally validated stress field.

- Interface z: 40.2794 A

Al-side interface bin, z=35..40 A:

- Hydrostatic proxy mean: -0.7885 GPa
- Sigma_zz mean: -0.3664 GPa

Fe-side interface bin, z=40..45 A:

- Hydrostatic proxy mean: -0.8201 GPa
- Sigma_zz mean: -0.1898 GPa

Highest absolute hydrostatic proxy:

- Bin: z=5..10 A
- Hydrostatic proxy mean: -4.1946 GPa
- Interpretation: fixed-bottom support artifact, not direct interface maximum.

## Comparison vs 120 MPa

| Metric | 120 MPa | 147 MPa | Comment |
|---|---:|---:|---|
| Final step | 15000 | 15000 | same protocol |
| Dangerous builds | 0 / 0 | 0 / 0 | passed |
| Pairs below 1.8 A | 0 | 0 | no hard overlap |
| Cross-slab Al-Fe below 2.1 A | 0 | 0 | no interface warning contact |
| Minimum cross-slab distance, A | 2.5259 | 2.5018 | slightly lower at 147 MPa |
| Minimum cross-slab Al-Fe distance, A | 2.5569 | 2.5930 | still above warning threshold |
| Warning pair min distance, A | 1.9757 | 1.9562 | internal Fe4Al13 pair remains monitor-only |
| Warning pair frames below 2.1 A | 106 | 104 | comparable |
| Warning pair frames below 1.8 A | 0 | 0 | no hard-overlap frame |
| Warning pair monotonic collapse | false | false | no monotonic collapse |
| Al-side hydrostatic proxy, GPa | -0.8366 | -0.7885 | diagnostic only |
| Fe-side hydrostatic proxy, GPa | -0.8353 | -0.8201 | diagnostic only |
| Highest abs hydrostatic proxy, GPa | -4.1900 | -4.1946 | support artifact in both cases |

## Stop-condition result

Script/log checks:

- ERROR / nan / lost atoms: no
- Dangerous builds not equal to 0: no
- Any pair below 1.8 A: no
- Cross-slab Al-Fe pair below 2.1 A: no
- Warning pair 232-260 monotonic collapse: no

Manual OVITO review:

- Fe4Al13 block detachment or whole-block drift: not observed.
- Atom ejection: not observed.
- Interface empty gap: not observed.

## OVITO screenshots to attach manually

Manual OVITO review was completed for frames 0, 50, 100, and 150.

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
- Red atoms are selection/coloring markers, not a stress-map and not automatically defects.

Screenshots were reviewed manually during the session and should be attached manually if required for submission.

Suggested screenshot paths:

- `results/figures/ovito_review_147mpa/frame000_pair_232_260.png`
- `results/figures/ovito_review_147mpa/frame050_pair_232_260.png`
- `results/figures/ovito_review_147mpa/frame100_pair_232_260.png`
- `results/figures/ovito_review_147mpa/frame150_pair_232_260.png`
- `results/figures/ovito_review_147mpa/frame000_interface_zone.png`
- `results/figures/ovito_review_147mpa/frame050_interface_zone.png`
- `results/figures/ovito_review_147mpa/frame100_interface_zone.png`
- `results/figures/ovito_review_147mpa/frame150_interface_zone.png`

## Verdict

147 MPa compression-ramp is accepted as a controlled sanity-run after manual OVITO review.

Do not treat this as final physical validation. Stress/atom is treated as a comparative virial proxy, and the highest hydrostatic proxy remains near fixed-bottom support.
