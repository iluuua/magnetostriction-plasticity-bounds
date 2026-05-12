# Unloaded local stress/strain diagnostics для interface trial_001

Дата: 2026-05-09

## 1. Цель

Проверить локальные stress/strain indicators для уже стабильного `trial_001` после короткого unloaded NVT 300 K.

Запрещённые действия не выполнялись:

- 120 MPa не применялось;
- `fix addforce` не использовался;
- stress scenario не создавался;
- NPT не использовался.

## 2. LAMMPS stress dump

- Input: `lammps/02_interface_relax/trial_001/in.interface_unloaded_diagnostics`
- Initial state: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k`
- Log: `lammps/02_interface_relax/trial_001/log.interface_unloaded_diagnostics.lammps`
- Summary: `lammps/02_interface_relax/trial_001/log_summary_interface_unloaded_diagnostics.json`
- Dump: `lammps/02_interface_relax/trial_001/dump.interface_unloaded_stress_run0.lammpstrj`
- Dump summary: `lammps/02_interface_relax/trial_001/dump_summary_interface_unloaded_diagnostics.json`

LAMMPS-команда фактически делает `run 0`: атомы не двигаются, интегратор не используется. Выгружены:

- `c_pe_atom`;
- `c_stress_atom[1..6]` через `compute stress/atom NULL virial`;
- global virial-only stress estimates.

Проверка лога:

- `ERROR`: false
- `nan`: false
- `lost atoms`: false
- `Dangerous builds`: 0
- Loop: 0 steps, 618 atoms
- `Total wall time`: 0:00:00
- diagnostic dump: 1 frame, 618 atoms/frame

Как и в предыдущих LAMMPS-запусках, процесс не вернулся в shell после печати `Total wall time`; файлы были записаны, после чего процесс был остановлен.

## 3. Python diagnostics

- Analyzer: `analysis/python/analyze_interface_unloaded_diagnostics.py`
- Plotter: `analysis/python/plot_interface_unloaded_diagnostics.py`
- JSON summary: `lammps/02_interface_relax/trial_001/interface_unloaded_diagnostics_summary.json`
- Stress profile: `results/tables/interface_trial_001_unloaded_stress_profile.csv`
- Strain profile: `results/tables/interface_trial_001_unloaded_strain_profile.csv`
- Per-atom diagnostics: `results/tables/interface_trial_001_unloaded_atom_diagnostics.csv`
- Stress plot: `results/figures/interface_trial_001_unloaded_stress_profile.png`
- Strain plot: `results/figures/interface_trial_001_unloaded_strain_profile.png`

Method:

- z-bin width: 5 A
- in-plane area: 102.15691288528764 A^2
- interface z estimate: 39.69490511641068 A
- Al slab z max: 39.012668401450206 A
- Fe4Al13 slab z min: 40.377141831371155 A
- stress conversion: `sigma = -sum(stress_atom) / bin_volume`
- units: bar converted to GPa with `1 bar = 1e-4 GPa`
- strain proxy: local affine least-squares fit from `data.interface_minimized` to `data.interface_nvt_300k`, neighbor cutoff 4.0 A

Important limitation: this is not OVITO Atomic Strain and not a time-averaged stress. It is a single-frame diagnostic proxy after NVT.

## 4. Phase-level summary

| Phase | Atoms | z range, A | Hydrostatic proxy, GPa | Mean displacement, A | Mean VM strain proxy | Mean D2min, A^2 |
|---|---:|---|---:|---:|---:|---:|
| Al slab | 210 | 5.575-39.013 | -1.5396 | 0.4639 | 0.0363 | 0.0432 |
| Fe4Al13 slab | 408 | 40.377-103.713 | -0.7109 | 0.3760 | 0.0839 | 0.3633 |

The phase-level hydrostatic numbers are approximate because slab volumes are estimated from z extents and full in-plane area.

## 5. Interface-near bins

Interface-adjacent bins:

| z center, A | Phase | Atoms | Hydrostatic proxy, GPa | Mean VM strain proxy | Mean displacement, A |
|---:|---|---:|---:|---:|---:|
| 37.5 | Al slab | 28 | -1.9779 | 0.0497 | 0.3855 |
| 42.5 | Fe4Al13 slab | 29 | -1.2475 | 0.0413 | 0.3467 |

The interface-adjacent bins do not show an immediate overlap-like blow-up. The strongest hydrostatic bin is at z=7.5 A in the free Al-side region, not at the interface.

## 6. Extremes

Highest absolute hydrostatic bin:

- z center: 7.5 A
- phase: Al slab
- atom count: 28
- hydrostatic proxy: -3.5899 GPa
- sigma_xx/sigma_yy/sigma_zz: -4.9666 / -5.3221 / -0.4809 GPa

Highest mean strain proxy bin:

- z center: 87.5 A
- phase: Fe4Al13 slab
- atom count: 31
- mean VM strain proxy: 0.1293
- max VM strain proxy: 0.6269
- mean D2min: 0.7442 A^2

These extremes should be treated as diagnostic flags. The high-stress Al bin is near the free slab side, and the high-strain Fe4Al13 bin is not the interface bin.

## 7. Verdict

The unloaded local diagnostics are acceptable as a first baseline:

- LAMMPS `run 0` diagnostics completed without `ERROR`, `nan`, or lost atoms;
- no external stress was applied;
- stress/strain outputs were generated;
- interface-adjacent bins are finite and do not indicate catastrophic geometry failure.

This still does not physically validate the interface. The next defensible step is a longer unloaded NVT and/or time-averaged local stress profile before preparing any 120 MPa scenario.
