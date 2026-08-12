# Stage F CPU Results: talk track для устного доклада

## Слайд 1. Что моделировали

- Локальная плоская граница Fe4Al13/Al: F0 planar, `r=0` на interface `z=50.0 A`.
- CPU-only comparable pair: `eps0000` baseline и `eps00194` physical eigenstrain.
- Анализируем `sigma(r)`, CNA/DXA и residual verdict без новых production запусков.

## Слайд 2. Почему CPU, а не GPU

- GPU backend имеет KOKKOS/MEAM blocker и не дает валидную comparable GPU pair.
- CPU pair завершена clean: обе cases 50k, одинаковый protocol, без CPU/GPU mixing.

## Слайд 3. Напряжения

- Peak Delta sigma_vm = `578.422 MPa` at `r=1 A`.
- Peak Delta sigma_zz = `-327.157 MPa` at `r=92.5 A`.
- Total eps00194 sigma_vm >120 MPa to `121.068 A`; Delta meaningful layer to `4 A`.
- Delta sigma_vm at 50/100 A = `-20.441` / `30.16 MPa`.

## Слайд 4. Пластика/дефекты

- Final DXA line length: `0 A` for eps0000 and eps00194.
- Max final Delta OTHER/non-FCC fraction: `0.036` near `r=3 A`.
- HCP final signal is essentially absent; eps00194 HCP max fraction = `0`.
- Residual plasticity verdict: `not_confirmed`.

## Слайд 5. Вывод

- Stress transfer: confirmed in local F0 CPU model.
- Plasticity: not confirmed by final CNA/DXA/residual check.
- Next step: stop and discuss with supervisor; if new MD is requested, F1 curved cap is the cleanest secondary option.

## Как отвечать на вопросы

1. Почему не 5 micrometer inclusion?
   Потому что atomistic MD cannot cover that scale here; F0 answers local interface physics.
2. Почему planar boundary?
   Это минимальная модель для вопроса Пшонкина: `sigma(r)` от границы в Al.
3. Почему local virial stress proxy?
   Dump contains stress/atom virial; it is valid for relative profiles and CPU-only delta, but not a calibrated continuum stress.
4. Почему нет дислокаций, если stress >120 MPa?
   120 MPa is a continuum reference; local virial stress can exceed it without a persistent atomistic defect network.
5. Что значит 578 MPa?
   Это peak CPU-only baseline-subtracted local VM proxy in the first interface bin, not a bulk yield stress.
6. Можно ли считать это пластической деформацией?
   Нет, residual verdict is not confirmed: final DXA is 0 A and no persistent defect evidence is present.
7. Что даст eps005?
   Diagnostic overload sensitivity, but it may overdrive the model and is not the next clean physics step.
8. Что даст F1 curved cap?
   Checks whether curvature changes stress localization compared with flat F0.
9. Что даст F0_300A?
   More distance for decay/cutoff, but current Delta already falls below noise near 100 A; use only if supervisor asks for longer far field.
10. Почему GPU не использовали?
   GPU path is not a valid comparable pair; CPU pair is clean and comparable.
