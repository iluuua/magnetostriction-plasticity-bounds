# Deposited simulation data

`manifest.json` describes the source and output of each transformation, with
SHA-256 checksums and byte sizes. `scripts/package_publication_data.py --verify`
checks the published package without access to the original machine.

## Datasets

| Directory | State or calculation |
|---|---|
| `interface/` | Common relaxed reference, preparation log and exact initial control/strained states for the static minimisations |
| `g15_free_control/` | Unrestrained, unstrained interface cell, 101,000 steps, final applied stress 400 MPa |
| `g15_held_control/` | Restrained, unstrained interface cell, 45,000 steps, final stress 145.45 MPa |
| `g15_held_strained/` | Restrained, strained interface cell, the same 45,000-step loading programme |
| `alloy/` | Al-Mg-Si comparator without an inclusion, 45/55/65/75 MPa staircase |

The complete static virial dumps remain in `../stageG4_clean/`. They contain
the particle-level data needed to independently reconstruct the field profile.
The G15 cells contain 91,428 atoms; the alloy cell contains 92,800 atoms.

## File formats and units

`initial.data.gz` and `final.data.gz` are losslessly compressed LAMMPS data
files. `final.lammpstrj.gz` preserves every column of the final LAMMPS dump.
`log.lammps.gz` preserves the integration/minimisation log and thermostat and
loading diagnostics. These machine-readable formats are kept unchanged;
explanations are provided here rather than inserted into numeric records.

`trajectory.NNN.lammpstrj.gz` contains up to 20 consecutive saved G15 frames.
Read the numerically ordered files as a single sequence. Every original saved
timestep and every original decimal coordinate string is retained. The columns
are `id type x y z`. Periodic box headers are unchanged. Energy and virial
columns are omitted from this position-only projection. It supports DXA and
position tracking, not a reconstruction of the complete dynamic stress field.

The alloy trajectory uses the same numbered-shard convention but preserves
every original column, including energy and virial stress. All 131 frames from
step 0 through 130,000 are deposited at a 1 ps interval. The full original was
recovered from a verified local backup; its checksum is recorded in the manifest.

The alloy `initial.data.gz` is a candidate replay input. Its saved date is later
than the original run. Atom IDs, types and fixed-bottom positions agree with
the run, but no launch-time hash certifies the initial mobile coordinates.
The preparation log also records an energy-tolerance stop with force two-norm
10.118429 eV/angstrom, not force convergence. The completed 130 ps trajectory
remains available for direct reanalysis with these preparation limitations.

Lengths are in angstrom, time in ps and energy in eV. One integration step is
0.001 ps. LAMMPS `stress/atom` values are in bar angstrom cubed; the analysis
converts to MPa after spatial averaging. The MD conversion `-S / volume` makes
normal compression positive, opposite to the tensile-positive Cauchy tensor.
Shear components retain their sign. Maximum absolute resolved shear and von
Mises values are unchanged by reversing the tensor sign.

The regular G15 sampling interval is 2,000 steps (2 ps). The free trajectory
ends at step 100,000 and the held trajectories at step 44,000. Their separate
final states are at steps 101,000 and 45,000. A final state is not silently
inserted into the sampled onset analysis.

## Analysis records

`docs/reports/stageG10_field_profile.*` contains the static stress profile.
The coordinate `r_A` is height above the flat substrate plane; height above
the nominal ridge crest is `r_A - 20`. This is not the nearest-surface distance
for every atom in a width-averaged slice. Axial-window entries use
`abs(x - ridge_centre) < 10` angstrom. The `above_apex` flag distinguishes
matrix-only slices from the excluded flank slices. The cutoff is the maximum
height of all inclusion atoms (IDs above 72,532) in both snapshots, 39.718591
angstrom. It retains 23 slices starting at z = 40-44 angstrom.

`stageG12_eigenstrain_retention.json` describes an affine fit on the Fe
sublattice. Its reported standard error is the formal fit error, not a
between-run uncertainty. Records with `free` in the name are diagnostic
unconverged relaxations and are not the primary maintained-strain result.

`stageG2_depinning_*G15*.csv` contains per-frame DXA positions, segment
statistics and nominal load. Associated JSON files describe the onset rule.
The original lower line disappears early in both restrained cells. Later
same-family fragments at the periodic seam do not establish renewed motion
of that original line. A short DXA segment is not accepted as a new dislocation.

`stageG6_vstar_relA_frames.csv` and its summary describe the alloy staircase.
The velocity fit did not identify a positive activation volume. Initial/final
states, logs, the complete trajectory and derived frame tables are provided.
The historical stress mask excludes Mg (type 2). The separate
`stageG6_stress_selection_relA.json` compares it with Al-only and all-alloy
selections on the same complete trajectory; the motion conclusion is unchanged.

Reconstruct the alloy analysis from the deposited shards with:

```sh
python analysis/python/stageG6_vstar_analysis.py --dump "data/publication/alloy/trajectory.*.lammpstrj.gz" --tag relA --stress-selection legacy --compare-stress-selections --out-dir build/verification
```

For an interface trajectory, use the recorded ramp endpoint rather than the
last saved frame as `--total-steps`. For example:

```sh
python analysis/python/stageG2_depinning.py --dump "data/publication/g15_held_control/trajectory.*.lammpstrj.gz" --case G15_ctl --total-steps 45000 --tau-max-mpa 145.45 --log data/publication/g15_held_control/log.lammps.gz --out-dir build/verification
```

The held strained case has the same parameters. The free control uses
`--total-steps 101000 --tau-max-mpa 400`. These commands run post-processing,
not molecular dynamics. The outputs are placed outside the authoritative records.

`stageG8_eshelby3d.json` and
`stageG5_two_scale_bridge.json` are analytical calculations. They carry their
parameters and units. Their idealised geometry and boundary conditions differ
from the tethered MD cell; numerical agreement is not an independent validation.
