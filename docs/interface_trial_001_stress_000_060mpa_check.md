# Проверка stress_000mpa и stress_060mpa для interface trial_001

Дата: 2026-05-10

## 1. Цель

Провести первые реальные controlled loading sanity tests:

- `0 MPa` control run с той же support/boundary setup;
- `60 MPa` compression-ramp run в сторону Al, то есть по `-z`.

Ограничения:

- `120 MPa` не запускалось;
- unloaded baseline не перезаписывался;
- NPT не использовался;
- физическая валидация интерфейса не заявляется.

## 2. Inputs

Control:

- folder: `lammps/03_interface_stress/stress_000mpa/run_001_control/`
- input: `in.interface_stress_000mpa_control`
- log: `log.interface_stress_000mpa_control.lammps`
- output data: `data.interface_stress_000mpa_control`
- dump: `dump.interface_stress_000mpa_control.lammpstrj`

60 MPa compression ramp:

- folder: `lammps/03_interface_stress/stress_060mpa/run_001_compression_ramp/`
- input: `in.interface_stress_060mpa_compression_ramp`
- log: `log.interface_stress_060mpa_compression_ramp.lammps`
- output data: `data.interface_stress_060mpa_compression_ramp`
- dump: `dump.interface_stress_060mpa_compression_ramp.lammpstrj`

Common setup:

- reference data: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k_long`
- `boundary p p f`
- fixed bottom support: lowest 4 A of `Al_slab`, z <= 9.709919949401659 A
- fixed_bottom atoms: 28
- mobile atoms: 590
- thermostat: `fix nvt` only on `mobile`
- fixed_bottom velocity set to zero and force zeroed with `fix setforce 0.0 0.0 0.0`
- MEAM Jelinek 2012 potential

60 MPa loading:

- target group: `Fe4Al13_slab` in z = 40.16445..48.16445 A
- target atoms: 52
- final force per target atom: `-0.0007357076524527927 eV/A`
- ramp: 0 to final force over 2000 steps
- hold: final force for 8000 steps
- total run: 10000 steps

Note: the thermo column `v_fz_ramp` resets its displayed `ramp()` function during the second `run`; the active second-stage load is the constant `fix load_fe_hold ... -0.000735707652452793`.

## 3. Mandatory log checks

Commands used after each run:

```bash
grep -E "ERROR|nan|lost atoms|Dangerous builds|Loop time|Total wall time" log.*.lammps || true
tail -120 log.*.lammps
```

Results:

| Run | ERROR/nan/lost atoms | Dangerous builds | Loop / wall time |
|---|---|---:|---|
| 0 MPa control | no | 0 | 5000 steps, wall 0:01:15 |
| 60 MPa compression ramp | no | 0 / 0 | 2000 + 8000 steps, wall 0:02:31 |

LAMMPS again wrote `Total wall time` but did not return cleanly to shell; outputs existed, so only the completed process was stopped.

## 4. Thermo summary

| Metric | 0 MPa control | 60 MPa compression ramp |
|---|---:|---:|
| Final Temp, K | 289.96437 | 288.38011 |
| Final mobile Temp, K | 303.74875 | 302.08918 |
| Last-20 mean Temp, K | 289.153834 | 284.2763455 |
| Last-20 mean mobile Temp, K | 302.899688 | 297.7903305 |
| PotEng drift, eV | +2.31990 | +0.39340 |
| TotEng drift, eV | +2.60530 | +2.27970 |
| Last-20 mean Press, bar | -4321.03137 | -4850.928525 |
| Overall Press range, bar | -5833.7909 to -2929.4678 | -6367.0776 to -2406.4047 |

The fixed-box pressure remains negative in both runs. This is a continuing geometry/support risk, not a validation success.

## 5. Geometry and distances

| Metric | 0 MPa control | 60 MPa compression ramp |
|---|---:|---:|
| Min Al-Al, A | 2.3833805557094343 | 2.456602159762194 |
| Min Fe-Fe, A | 2.658076130572971 | 2.6837108845186077 |
| Min Al-Fe, A | 2.129863446519644 | 2.030136901643954 |
| Min cross-slab, A | 2.4387914441647434 | 2.456602159762194 |
| Min cross-slab Al-Fe, A | 2.4387914441647434 | 2.511969031454882 |
| Pairs < 1.8 A | 0 | 0 |
| Al-Fe pairs < 2.1 A | 0 | 1 |
| Cross-slab Al-Fe pairs < 2.1 A | 0 | 0 |

The 60 MPa run is not a hard-overlap failure, but the one Al-Fe warning pair below 2.1 A must be inspected before any higher-load scenario.

Follow-up warning-pair inspection for 60 MPa:

- JSON: `lammps/03_interface_stress/stress_060mpa/run_001_compression_ramp/warning_pairs_interface_stress_060mpa_compression_ramp.json`
- Distance table: `results/tables/interface_trial_001_stress_060mpa_warning_pair_distance_over_time.csv`
- Distance figure: `results/figures/interface_trial_001_stress_060mpa_warning_pair_distance_over_time.png`
- Neighborhood table: `results/tables/interface_trial_001_stress_060mpa_warning_pair_neighborhood.csv`

Result:

- pair: atoms 232-260, Al-Fe;
- classification: internal Fe4Al13 pair;
- final distance: 2.030136901643954 A;
- trajectory min/max/mean: 1.9596358488504906 / 2.2493083063244073 / 2.0861105731794494 A;
- frames below 2.1 A: 57 / 101;
- frames below 1.8 A: 0 / 101;
- monotonic collapse: false;
- contact type: intermittent short contact.

This is the same internal Fe4Al13 warning pair seen in the unloaded long-NVT check, not a cross-slab interface warning.

## 6. Stress profile proxy

Stress/atom dumps were generated and parsed:

- 0 MPa frames: 51
- 60 MPa frames: 101
- CSV comparison: `results/tables/interface_trial_001_stress_000_060mpa_comparison.csv`
- 0 MPa stress profile: `results/tables/interface_trial_001_stress_000mpa_control_stress_profile.csv`
- 60 MPa stress profile: `results/tables/interface_trial_001_stress_060mpa_compression_ramp_stress_profile.csv`

Interface-near bins:

| Metric | 0 MPa control | 60 MPa compression ramp |
|---|---:|---:|
| Interface z estimate, A | 40.3602 | 40.34395 |
| Al-side hydrostatic mean, GPa | -0.8877706406860397 | -0.9441686302425827 |
| Al-side sigma_zz mean, GPa | -0.49222499649846696 | -0.4519310979047885 |
| Fe-side hydrostatic mean, GPa | -0.8327401722225356 | -0.8128431502509667 |
| Fe-side sigma_zz mean, GPa | -0.47257588233257947 | -0.3518168636081032 |

These values are virial stress proxies from `compute stress/atom NULL virial`, not experimentally validated absolute stresses.

## 7. Verdict

0 MPa control: passed sanity check.

60 MPa compression ramp: passed basic sanity check with warning.

Warnings/blockers:

- one Al-Fe pair below 2.1 A after 60 MPa;
- that pair is internal Fe4Al13 pair 232-260, not cross-slab;
- no hard overlaps below 1.8 A;
- no cross-slab Al-Fe warning pairs below 2.1 A;
- pressure remains strongly negative;
- triclinic skew remains;
- interface is still not physically validated.

Next step: inspect the 60 MPa dump and the warning-pair neighborhood in OVITO Basic before considering any 120 MPa setup.
