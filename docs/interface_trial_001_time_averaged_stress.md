# Time-averaged unloaded stress profile для interface trial_001

Дата: 2026-05-10

## 1. Цель

Получить time-averaged local stress profile для уже стабильного unloaded интерфейса `trial_001` после короткого NVT и single-frame diagnostics.

Жёсткие ограничения соблюдены:

- 120 MPa не применялось;
- `fix addforce` не использовался;
- stress scenario не создавался;
- NPT не использовался;
- физическая валидация интерфейса не заявляется.

## 2. Long unloaded NVT

- Input: `lammps/02_interface_relax/trial_001/in.interface_nvt_300k_long_unloaded`
- Initial state: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k`
- Log: `lammps/02_interface_relax/trial_001/log.interface_nvt_300k_long.lammps`
- Summary: `lammps/02_interface_relax/trial_001/log_summary_interface_nvt_300k_long.json`
- Final data: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k_long`
- Trajectory dump: `lammps/02_interface_relax/trial_001/dump.interface_nvt_300k_long.lammpstrj`
- Stress dump: `lammps/02_interface_relax/trial_001/dump.interface_nvt_300k_long_stress.lammpstrj`
- Final dump: `lammps/02_interface_relax/trial_001/dump.interface_nvt_300k_long_final.lammpstrj`

Run length was set to 20000 steps instead of 50000 because the prior 5000-step NVT took about 69 s on this Mac; 50000 steps would have taken roughly 11-12 minutes. This is documented in the LAMMPS input.

NVT settings:

- `boundary p p f`
- `fix nvt_all all nvt temp 300.0 300.0 0.1`
- trajectory dump every 1000 steps
- stress dump every 1000 steps
- thermo every 500 steps

Log checks:

- `ERROR`: false
- `nan`: false
- `lost atoms`: false
- `Dangerous builds`: 0
- Loop: 20000 steps, 618 atoms, 297.247 s
- `Total wall time`: 0:04:57

LAMMPS again wrote `Total wall time` but did not return to shell by itself. All output files existed, so only the completed process was stopped.

## 3. Long NVT thermo summary

| Quantity | Final | Last-20 mean | Overall mean | Overall range |
|---|---:|---:|---:|---:|
| Temp, K | 294.64769 | 302.510973 | 302.422329 | 280.18403 to 329.76334 |
| PotEng, eV | -2123.0231 | -2121.67248 | -2121.35098 | -2123.0231 to -2119.591 |
| TotEng, eV | -2099.5239 | -2097.54617 | -2097.23174 | -2099.6079 to -2095.0986 |
| Press, bar | -4816.1437 | -4403.595752 | -4308.360256 | -8975.9428 to 124.43745 |

Potential energy drift from first to last thermo row: -2.2992 eV.

## 4. Dump and distance checks

- Trajectory summary: `lammps/02_interface_relax/trial_001/dump_summary_interface_nvt_300k_long.json`
- Stress dump summary: `lammps/02_interface_relax/trial_001/dump_summary_interface_nvt_300k_long_stress.json`
- Distance report: `lammps/02_interface_relax/trial_001/interface_nvt_300k_long_distance_report.json`

Dump checks:

- trajectory frames: 21
- trajectory atoms/frame: 618
- stress frames: 21
- stress atoms/frame: 618
- OVITO Python: unavailable, fallback header parser used

Post-long-NVT distances:

| Check | Value |
|---|---:|
| Minimum Al-Al distance, A | 2.510464644949592 |
| Minimum Fe-Fe distance, A | 2.6087804889456216 |
| Minimum Al-Fe distance, A | 2.026948650230154 |
| Minimum cross-slab distance, A | 2.5924655274192756 |
| Minimum cross-slab Al-Fe distance, A | 2.5924655274192756 |
| Pairs below 1.8 A | 0 |
| Al-Fe pairs below 2.1 A | 1 |
| Cross-slab Al-Fe pairs below 2.1 A | 0 |

The single Al-Fe pair below the 2.1 A warning threshold is internal to the Fe4Al13 slab, not cross-slab. This is a warning to monitor, but not a hard-overlap failure because no pair is below 1.8 A.

Follow-up inspection:

- Script: `analysis/python/inspect_warning_pairs.py`
- Report: `docs/interface_trial_001_warning_pairs_check.md`
- Warning pair: atoms 232-260, Al-Fe, internal `Fe4Al13_slab`
- Final data distance: 2.026948650230154 A
- Trajectory min/max/mean: 2.026797 / 2.353091 / 2.116977 A
- Frames below 2.1 A: 11 / 21
- Frames below 1.8 A: 0 / 21
- Monotonic collapse: false
- Contact type: intermittent short contact

The warning pair is not at the Al/Fe4Al13 cross-slab interface. It remains a warning to monitor and a reason to avoid rushing into loading before visual or additional unloaded geometry checks.

Additional contact-density inspection for visible OVITO gaps:

- Script: `analysis/python/check_interface_contact_density.py`
- Report: `docs/interface_trial_001_contact_density_check.md`
- Minimum cross-slab distance: 2.5924655274192756 A
- Cross-slab pairs within 2.8 / 3.0 / 3.5 A: 20 / 33 / 48
- Largest empty z-gap between occupied bins: 1 A and not intersecting the interface window

This check does not confirm a large physical interface void. The apparent gaps remain a visual/geometric inspection item, not a loading clearance.

## 5. Time-averaged stress analysis

- Script: `analysis/python/analyze_interface_time_averaged_stress.py`
- Input stress dump: `lammps/02_interface_relax/trial_001/dump.interface_nvt_300k_long_stress.lammpstrj`
- Output CSV: `results/tables/interface_trial_001_time_averaged_stress_profile.csv`
- Output JSON: `lammps/02_interface_relax/trial_001/interface_time_averaged_stress_summary.json`
- Output figure: `results/figures/interface_trial_001_time_averaged_stress_profile.png`

Method:

- all 21 stress frames were read;
- phase assignment from metadata: `atom_id <= 210` is `Al_slab`;
- z-bin width: 5 A;
- stress proxy: `compute stress/atom NULL virial`;
- bin stress conversion: `sigma = -sum(stress_atom) / bin_volume`;
- bin volume: in-plane cell area times 5 A bin width;
- values are time means and standard deviations over frames.

This is an unloaded virial stress proxy, not an experimentally validated absolute stress.

## 6. Interface-near time averages

Estimated interface z from the long trajectory: 40.16445 A.

| Bin | z center, A | Hydrostatic mean, GPa | Hydrostatic std, GPa | sigma_zz mean, GPa | sigma_zz std, GPa | Single-frame hydrostatic, GPa |
|---|---:|---:|---:|---:|---:|---:|
| Al-side | 37.5 | -1.282659 | 0.727198 | -0.876969 | 0.921933 | -1.977868 |
| Fe4Al13-side | 42.5 | -0.879494 | 0.519491 | -0.012122 | 1.117203 | -1.247509 |

Compared with the previous single-frame diagnostics, time averaging reduces the magnitude of the interface-near hydrostatic proxy:

- Al-side delta: +0.695209 GPa;
- Fe4Al13-side delta: +0.368015 GPa.

Highest absolute time-averaged hydrostatic bin:

- z center: 7.5 A;
- phase: Al free-surface side;
- hydrostatic mean: -3.466478 GPa;
- hydrostatic std: 0.485368 GPa.

## 7. Verdict

The 20000-step unloaded NVT and time-averaged stress analysis completed successfully as a baseline diagnostic.

Acceptable findings:

- no `ERROR`, `nan`, or lost atoms;
- `Dangerous builds = 0`;
- 21 stress frames were generated and parsed;
- no hard overlaps below 1.8 A;
- no cross-slab Al-Fe warning pairs below 2.1 A.

Remaining concerns:

- one internal Fe4Al13 Al-Fe pair is below the 2.1 A warning threshold;
- warning-pair tracking shows intermittent internal contact, not cross-slab collapse;
- pressure remains negative on average in fixed-box slab NVT;
- large triclinic skew remains;
- stress normalization near free surfaces is approximate;
- this is not physical validation of the interface.

Next defensible step: inspect geometry visually when OVITO is available and/or run another unloaded geometry refinement before designing any 120 MPa scenario.
