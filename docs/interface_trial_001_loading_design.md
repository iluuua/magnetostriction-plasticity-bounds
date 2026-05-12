# Loading design для Al / Fe4Al13 interface trial_001

Дата: 2026-05-10

## 1. Цель

Подготовить контролируемый дизайн будущей локальной нагрузки для `trial_001` без запуска нагруженного расчёта.

Ограничения соблюдены:

- 120 MPa не запускалось;
- активный `fix addforce` не использовался;
- stress scenario не запускался;
- NPT не использовался;
- unloaded baseline не перезаписывался;
- физическая валидация интерфейса не заявляется.

## 2. Reference state

- Data: `lammps/02_interface_relax/trial_001/data.interface_nvt_300k_long`
- Metadata: `structures/interface/flat_interface/trial_001/interface_metadata.json`
- Interface z: 40.16445 A
- In-plane area: 102.15691288528764 A^2 = 1.0215691288528763 nm^2
- Phase assignment: atom ids `1:210` = `Al_slab`, atom ids `211:618` = `Fe4Al13_slab`

## 3. Proposed regions

Target loading region:

- Phase: `Fe4Al13_slab`
- z-range: 40.16445 to 48.16445 A
- Width: 8 A on Fe4Al13 side near the interface
- Target atoms: 52 total
- Composition inside target group: 40 Al-type atoms, 12 Fe-type atoms

Al-side monitor region:

- Phase: `Al_slab`
- z-range: 32.16445 to 40.16445 A
- Width: 8 A on Al side near the interface
- Monitor atoms: 42

The target group is intentionally a near-interface Fe4Al13 slice, not the full slab. Future production inputs should still decide whether the force direction represents compression toward Al (`-z`) or tension away from Al (`+z`).

## 4. Force calculation

Formula:

```text
F_total = sigma * A
F_atom = F_total / N_target
1 eV/A = 1.602176634e-9 N
```

Source table: `results/tables/interface_trial_001_loading_force_table.csv`

| Scenario | sigma, MPa | F_total, N | F_atom, N | F_atom, eV/A |
|---|---:|---:|---:|---:|
| stress_000mpa | 0 | 0 | 0 | 0 |
| stress_060mpa | 60 | 6.129414773117258e-11 | 1.1787336102148572e-12 | 0.0007357076524527927 |
| stress_120mpa | 120 | 1.2258829546234515e-10 | 2.3574672204297145e-12 | 0.0014714153049055854 |
| stress_147mpa | 147 | 1.5017066194137282e-10 | 2.8878973450264004e-12 | 0.001802483748509342 |
| stress_200mpa | 200 | 2.0431382577057524e-10 | 3.929112034049524e-12 | 0.002452358841509309 |

For compression toward the Al slab, the future `addforce` z-component would be negative. For tension away from Al, it would be positive. The templates keep both as comments only.

## 5. Templates created

- `lammps/03_interface_stress/stress_000mpa/in.interface_stress_template`
- `lammps/03_interface_stress/stress_060mpa/in.interface_stress_template`
- `lammps/03_interface_stress/stress_120mpa/in.interface_stress_template`
- `lammps/03_interface_stress/stress_147mpa/in.interface_stress_template`
- `lammps/03_interface_stress/stress_200mpa/in.interface_stress_template`

Template contents:

- read `data.interface_nvt_300k_long`;
- use the same MEAM Jelinek 2012 potential;
- define `Al_slab`, `Fe4Al13_slab`, `fe_load`, and `al_monitor` groups;
- define `compute pe/atom` and `compute stress/atom NULL virial`;
- store scenario-specific force values as LAMMPS variables;
- keep `fix addforce` as commented placeholders only;
- include no active dynamics `run`.

## 6. Why loading is not launched yet

Loading is still blocked because:

- the interface is not physically validated;
- fixed-box long-NVT pressure remains negative;
- triclinic skew remains;
- Al-side density near interface drops relative to bulk-like Al;
- warning pair 232-260 is internal Fe4Al13 and monitor-only, but still needs visual follow-up;
- direction and duration of loading need explicit approval after final OVITO review.

Verdict: force calculation and input skeletons are prepared. No loaded scenario has been run.

## 7. Follow-up status

After this design document was created, only the first low-load sanity tests were run:

- `0 MPa` control;
- `60 MPa` compression ramp toward Al side.

`120 MPa` has still not been run. See `docs/interface_trial_001_stress_000_060mpa_check.md` for the run analysis.
