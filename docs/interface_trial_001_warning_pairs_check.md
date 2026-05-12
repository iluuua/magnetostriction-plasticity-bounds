# Проверка warning Al-Fe pairs после long NVT для trial_001

Дата: 2026-05-10

## 1. OVITO status

Проверки:

```bash
ls /Applications | grep -i ovito || true
python -c "import ovito; print(ovito.version)" || true
which ovito || true
ovito --help | head -20 || true
```

Результат:

- `/Applications` не содержит OVITO app.
- Python module `ovito` не импортируется: `ModuleNotFoundError: No module named 'ovito'`.
- В conda env есть `/opt/anaconda3/envs/alfe-md/bin/ovito`, но GUI/CLI падает с `dyld: Symbol not found ... Gui.so`.

Вывод: OVITO всё ещё недоступен. Не пытались собирать OVITO из исходников. Для визуальной проверки нужно отдельно установить официальный OVITO Basic for macOS с `ovito.org`.

## 2. Input data

- Final long-NVT data: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k_long`
- Long-NVT trajectory: `lammps/02_interface_relax/trial_001/dump.interface_nvt_300k_long.lammpstrj`
- Metadata: `structures/interface/flat_interface/trial_001/interface_metadata.json`
- Prior distance report: `lammps/02_interface_relax/trial_001/interface_nvt_300k_long_distance_report.json`

Script-based inspection:

- Script: `analysis/python/inspect_warning_pairs.py`
- JSON: `lammps/02_interface_relax/trial_001/warning_pairs_long_nvt.json`
- Distance table: `results/tables/interface_trial_001_warning_pair_distance_over_time.csv`
- Distance plot: `results/figures/interface_trial_001_warning_pair_distance_over_time.png`
- Neighborhood table: `results/tables/interface_trial_001_warning_pair_neighborhood.csv`

## 3. Warning pair found

One Al-Fe pair is below the 2.1 A warning threshold in the final long-NVT data.

| Field | Value |
|---|---|
| Atom ids | 232 - 260 |
| Species | Al - Fe |
| Types | 1 - 2 |
| Phase i | Fe4Al13_slab |
| Phase j | Fe4Al13_slab |
| Classification | internal Fe4Al13 pair |
| Final data distance | 2.026948650230154 A |
| Cross-slab pair | no |
| Below hard 1.8 A | no |

Coordinates in `data.interface_nvt_300k_long`:

| Atom | Species | x, A | y, A | z, A |
|---:|---|---:|---:|---:|
| 232 | Al | 11.751900335303445 | 5.239434491053698 | 103.44147214545163 |
| 260 | Fe | 10.853973594239598 | 3.7715575033962807 | 102.37021795178045 |

This pair is internal to the Fe4Al13 slab and is close to the high-z side of that slab, not at the Al/Fe4Al13 cross-slab interface.

## 4. Time tracking

Distance over 21 long-NVT frames:

| Metric | Value |
|---|---:|
| Minimum distance, A | 2.0267974114104237 |
| Maximum distance, A | 2.353091312805352 |
| Mean distance, A | 2.1169774530489107 |
| Std distance, A | 0.08710725352502317 |
| Frames below 2.1 A | 11 / 21 |
| Frames below 1.8 A | 0 / 21 |
| Monotonically decreases | false |
| Contact type | intermittent short contact |

The shortest value occurs at the final saved frame, but the trajectory is not monotonic: the distance goes above and below 2.1 A during the run. This is not a clear monotonic collapse.

## 5. Neighborhood

The neighborhood table contains atoms within 4 A of the warning-pair center in the final long-NVT data:

- file: `results/tables/interface_trial_001_warning_pair_neighborhood.csv`
- atoms in table including the pair atoms: 11
- all listed atoms are in `Fe4Al13_slab`

## 6. Verdict

The warning pair is internal to the Fe4Al13 slab and does not cross the Al/Fe4Al13 interface. It never drops below the hard 1.8 A threshold and does not monotonically collapse over the sampled trajectory.

Verdict: warning to monitor, not a hard blocker for the unloaded baseline. It is still a blocker for rushing into loading, because the geometry has not been visually inspected and OVITO remains unavailable.

Next step: install working OVITO or add a further unloaded geometry refinement/visual sanity check before any 120 MPa scenario.
