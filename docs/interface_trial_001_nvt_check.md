# Проверка unloaded NVT 300 K для interface trial_001

Дата: 2026-05-09

## 1. Сценарий

- Candidate: Al(111) / Fe4Al13(100)
- Initial data: `lammps/02_interface_relax/trial_001/data.interface_minimized`
- Input: `lammps/02_interface_relax/trial_001/in.interface_nvt_300k`
- Ensemble: NVT only
- Boundary: `p p f`
- Temperature: 300 K
- Run length: 5000 steps
- Timestep: LAMMPS default for `units metal`, 0.001 ps
- Dump period: 100 steps
- Thermo period: 100 steps
- 120 MPa: not applied
- `fix addforce`: not used
- NPT: not used

MEAM potential:

```lammps
pair_style meam
pair_coeff * * ../../../potentials/meam/Jelinek_2012/Jelinek_2012_meamf AlS SiS MgS CuS FeS ../../../potentials/meam/Jelinek_2012/Jelinek_2012_meam.alsimgcufe AlS FeS
```

Before NVT, the minimization log was preserved:

- `lammps/02_interface_relax/trial_001/log.interface_minimize.lammps`

NVT log:

- `lammps/02_interface_relax/trial_001/log.interface_nvt_300k.lammps`

## 2. System

| Quantity | Value |
|---|---:|
| Total atoms | 618 |
| Al type 1 | 522 |
| Fe type 2 | 96 |
| Al slab atoms | 210 |
| Fe4Al13 slab atoms | 408 |
| Lx, A | 15.315254 |
| Ly, A | 6.6702724 |
| Lz, A | 109.21148 |
| xy, A | 4.0025167 |

## 3. Log summary

- JSON: `lammps/02_interface_relax/trial_001/log_summary_interface_nvt_300k.json`
- Loop time: 68.878 s
- Steps: 5000
- Atoms: 618
- `ERROR`: false
- `nan`: false
- `lost atoms`: false
- `Dangerous builds`: 0
- `Total wall time`: 0:01:08

LAMMPS again wrote `Total wall time` but did not return to shell by itself. The output files existed, so the finished process was stopped after confirming the files were present.

## 4. Thermo summary

| Quantity | Initial | Final | Last 20 mean |
|---|---:|---:|---:|
| Temp, K | 300.000 | 300.86157 | 299.9958705 |
| PotEng, eV | -2143.9047 | -2120.7239 | -2120.550855 |
| TotEng, eV | -2119.9786 | -2096.7291 | -2096.625120 |
| Press, bar | -4981.1784 | -6539.3182 | -5110.9447259 |
| Volume, A^3 | 11156.707 | 11156.707 | 11156.707 |

Potential energy rises relative to the 0 K minimized state because velocities are created at 300 K. In the last 20 thermo points, PE stays in the range -2122.8582 to -2119.1201 eV.

Pressure remains strongly fluctuating and negative on average because this is a fixed-box slab sanity-run with free z boundary. This is a risk to monitor, not a standalone validation failure.

## 5. Dump summary

- Dump: `lammps/02_interface_relax/trial_001/dump.interface_nvt_300k.lammpstrj`
- Final dump: `lammps/02_interface_relax/trial_001/dump.interface_nvt_300k_final.lammpstrj`
- JSON: `lammps/02_interface_relax/trial_001/dump_summary_interface_nvt_300k.json`
- Reader: fallback LAMMPS header parser
- Frames: 51
- Atoms per frame: 618
- OVITO Python: unavailable

## 6. Distance check after NVT

- Script: `analysis/python/check_interface_distances.py`
- Data checked: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k`
- JSON: `lammps/02_interface_relax/trial_001/interface_nvt_300k_distance_report.json`
- Phase assignment: `atom_id <= 210` is Al slab, remaining atoms are Fe4Al13 slab.

| Check | Value |
|---|---:|
| Minimum Al-Al distance, A | 2.4954410534290377 |
| Minimum Fe-Fe distance, A | 2.6499727731895004 |
| Minimum Al-Fe distance, A | 2.2834059099057114 |
| Minimum cross-slab distance, A | 2.534898445930031 |
| Minimum cross-slab Al-Fe distance, A | 2.6466769427073733 |
| Pairs below 1.8 A | 0 |
| Al-Fe pairs below 2.1 A | 0 |
| Cross-slab pairs below 1.8 A | 0 |
| Cross-slab Al-Fe pairs below 2.1 A | 0 |

## 7. Verdict

The 5000-step unloaded NVT sanity-check is stable by the basic criteria:

- no `ERROR`;
- no `nan`;
- no lost atoms;
- `Dangerous builds = 0`;
- dump has the expected 51 frames and 618 atoms per frame;
- post-NVT distance check shows no hard overlaps and no Al-Fe warning pairs.

Verdict: acceptable for a longer unloaded NVT run or additional unloaded interface analysis. It is not enough to claim physical interface validation, and it is not yet a basis for applying 120 MPa.

Next action: run a longer unloaded relaxation/analysis step or compute unloaded local stress/strain diagnostics before preparing any stress scenario.
