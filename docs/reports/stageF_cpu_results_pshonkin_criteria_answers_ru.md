# Stage F CPU Results: ответы по критериям Пшонкина

Дата: 2026-07-02T08:03:43+03:00

| Критерий Пшонкина | Что проверили | Численный результат | Вывод | Статус |
| --- | --- | --- | --- | --- |
| Есть ли передача напряжения от границы в Al? | CPU-only Delta sigma(r), eps00194 - eps0000 | Peak Delta sigma_vm = 578.422 MPa at 1 A | Передача local virial stress proxy подтверждена около interface. | confirmed |
| Есть ли локальный напряженный слой у interface? | total sigma_vm and Delta sigma_vm | Total VM >120 MPa to 121.068 A; Delta above noise to 4 A | Есть сильный near-interface Delta layer; total VM cutoff не чистый из-за baseline/local virial noise. | confirmed |
| Превышает ли напряжение 120 MPa? | eps00194 total sigma_vm_mean/p95 | Peak eps00194 VM = 2860.3 MPa | Да по local virial proxy; абсолютные MPa не являются continuum-calibrated stress. | confirmed |
| Какова толщина слоя? | contiguous bins from r=0 | Total VM mean layer 121.068 A; Delta meaningful layer 4 A | Для разговора важнее Delta layer 0-4 A; total layer reaches available slab edge. | confirmed |
| Затухает ли эффект внутри 100 A? | Delta sigma_vm at checkpoints and noise floor | Delta VM at 100 A = 30.16 MPa; noise floor 133.527 MPa | Baseline-subtracted near-interface effect decays below noise well before 100 A. | confirmed |
| Доминирует ли sigma_zz из-за eigenstrain Z? | Delta xx/yy/zz at peak VM bin | Dominant = delta_sigma_yy_mean_mpa | Peak is mixed/interface VM stress; sigma_zz does not dominate. | not_confirmed |
| Есть ли признаки пластической деформации? | CNA/DXA final and residual verdict | Residual verdict = not_confirmed | Пластичность не подтверждена. | not_confirmed |
| Есть ли HCP/OTHER рост сверх baseline? | final delta defect profile | Max Delta OTHER/non-FCC = 0.036 | Есть слабая local interface-shell разница, не самостоятельное доказательство пластичности. | inconclusive |
| Есть ли DXA/dislocations? | OVITO DXA final | DXA line length = 0 A for eps0000 and eps00194 final | DXA-сигнала в CPU final нет. | not_confirmed |
| Есть ли остаточная/необратимая пластичность? | residual plasticity check | not_confirmed | Не подтверждена; нет unload/quench/Dmin2 proof. | not_confirmed |
| Достаточен ли F0_planar для вывода? | geometry scope | F0 planar answers local flat-boundary stress transfer only | Достаточен для локального planar stress answer; не заменяет curved/micron inclusion. | technical_limitation |
| Что логично запускать дальше? | decision logic | primary: stop/no new MD until supervisor feedback; secondary: F1 curved cap if requested | Сначала показать числа Пшонкину; следующий MD должен быть motivated by feedback. | next_step_required |
