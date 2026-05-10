# Milestone: trial_001 time-averaged unloaded stress

Дата: 2026-05-10

## Итог

Проведён longer unloaded NVT для `trial_001` и рассчитан time-averaged local virial stress profile.

## Проверено

- Run length: 20000 steps, not 50000, due local Mac runtime.
- NVT 300 K, `boundary p p f`.
- No 120 MPa, no `fix addforce`, no NPT, no stress scenario.
- No `ERROR/nan/lost atoms`.
- `Dangerous builds = 0`.
- Trajectory dump: 21 frames, 618 atoms/frame.
- Stress dump: 21 frames, 618 atoms/frame.
- Post-long-NVT: no pairs below 1.8 A; one internal Al-Fe pair below 2.1 A.

## Основные числа

- Final T: 294.648 K.
- Last-20 mean T: 302.511 K.
- Overall mean pressure: -4308.360 bar.
- Interface z estimate: 40.164 A.
- Time-averaged hydrostatic proxy:
  - Al-side bin z=37.5 A: -1.283 +/- 0.727 GPa.
  - Fe4Al13-side bin z=42.5 A: -0.879 +/- 0.519 GPa.

## Риски

- One internal Fe4Al13 Al-Fe pair is below warning threshold 2.1 A.
- Fixed-box slab pressure remains negative.
- Large triclinic skew remains.
- OVITO unavailable.
- This remains unloaded diagnostic baseline, not physical validation.

## Следующий шаг

Fix/enable OVITO visual inspection or refine unloaded geometry before preparing any 120 MPa scenario.
