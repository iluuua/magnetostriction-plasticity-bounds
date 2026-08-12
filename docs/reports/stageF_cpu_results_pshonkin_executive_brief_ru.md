# Stage F CPU Results: executive brief для Пшонкина

## Короткий вывод

Мы разобрали уже завершенную CPU fallback pair `eps0000`/`eps00194` для F0 planar boundary, без новых MD запусков и без GPU. Напряжение от eigenstrain видно как near-interface baseline-subtracted signal: peak Delta sigma_vm = `578.422 MPa` в первом bin около interface. При этом total local virial sigma_vm остается выше `120 MPa` по всей доступной Al-области, поэтому total-stress cutoff сам по себе не дает чистую физическую толщину. Пластичность не подтверждена: финальный DXA = `0 A`, residual verdict = `not_confirmed`.

## 5 главных чисел

| № | Показатель | Значение | Зачем важно |
| --- | --- | --- | --- |
| 1 | Peak Delta sigma_vm | 578.422 MPa | главный baseline-subtracted stress-transfer signal |
| 2 | r peak Delta sigma_vm | 1 A | показывает near-interface localization |
| 3 | Total sigma_vm >120 MPa layer | 121.068 A | total virial proxy above yield reference across available slab |
| 4 | Delta sigma_vm at 50/100 A | -20.441 / 30.16 MPa | Delta signal is below noise by far field |
| 5 | DXA / residual verdict | 0 A / not_confirmed | no final dislocation line evidence |

## Интерпретация

Подтверждено:

- stress transfer в локальной F0 planar модели;
- сильный near-interface Delta sigma_vm layer в 0-4 A по robust noise threshold;
- Delta sigma_vm near 100 A ниже noise floor.

Не подтверждено:

- residual plasticity;
- DXA/dislocation line in final CPU frames;
- dominance of sigma_zz at the VM peak.

Ограничение:

- stress is a local virial proxy, not calibrated continuum stress;
- F0 planar is a flat-boundary local model, not a 5 micrometer inclusion model;
- total sigma_vm >120 MPa reaches the available slab edge, so total-stress cutoff is not a clean thickness.

## Формулировка для Пшонкина

Мы посчитали локальную плоскую границу Fe4Al13/Al в CPU-only pair, с `eps00194` против baseline `eps0000`. На профиле `sigma(r)` видно, что magnetostrictive eigenstrain дает дополнительное локальное напряжение у interface: peak Delta sigma_vm около `578.422 MPa` в первом bin. Этот baseline-subtracted эффект быстро падает: уже к 50 A Delta sigma_vm около `-20.441 MPa`, а около 100 A около `30.16 MPa`, то есть ниже нашего far-field noise floor. Total sigma_vm в local virial proxy выше 120 MPa практически во всей доступной Al области, но это не стоит трактовать как точный continuum cutoff. По дефектам финальный DXA дает 0 A, HCP практически нет, OTHER/non-FCC меняется только как слабый interface-shell/background сигнал. Поэтому честный вывод: напряжение передается, а пластичность и дислокации этими данными не подтверждены.

## Следующий шаг

Primary next step: `stop/no new MD until supervisor feedback`. Эти числа уже отвечают на meeting question без запуска eps005/F1/F0_300A.

Secondary option: `F1 curved cap`, если Пшонкин попросит проверить curvature/geometry realism after seeing the planar-boundary numbers.
