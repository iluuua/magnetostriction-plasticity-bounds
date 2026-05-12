# Milestone: interface trial_001 unloaded diagnostics

Дата: 2026-05-09

## Итог

Выполнены unloaded local stress/strain diagnostics для `trial_001` после 5000-step NVT.

## Проверено

- LAMMPS `run 0` на `data.interface_nvt_300k`.
- `compute stress/atom NULL virial` и `pe/atom` выгружены в dump.
- `ERROR/nan/lost atoms`: нет.
- `Dangerous builds = 0`.
- Diagnostic dump: 1 frame, 618 atoms/frame.
- 120 MPa, `fix addforce`, NPT и stress scenario не использовались.
- Python-профили stress/strain построены по z-bin 5 A.

## Основные числа

- Interface z estimate: 39.695 A.
- Interface-near hydrostatic proxy: Al-side bin z=37.5 A: -1.978 GPa; Fe4Al13-side bin z=42.5 A: -1.248 GPa.
- Mean VM strain proxy: Al slab 0.0363; Fe4Al13 slab 0.0839.
- Highest mean strain proxy bin: z=87.5 A, Fe4Al13, 0.1293.

## Риски

- Stress profile is single-frame, not time-averaged.
- Strain is a custom affine proxy, not OVITO Atomic Strain.
- Large triclinic skew and negative pressure remain.
- OVITO GUI/Python remains unavailable.

## Следующий шаг

Run longer unloaded NVT with periodic stress dumps for time-averaged profiles. Do not prepare or apply 120 MPa yet.
