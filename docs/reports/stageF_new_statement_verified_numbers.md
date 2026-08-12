# Stage F — новая постановка: перепроверенные числа

Дата: 2026-07-06

Все значения перепроверены по JSON-сводкам и напрямую по CSV-профилям (pandas). Основное окно усреднения: `last20_mean` (последние 20% производственной траектории). Interface: `z = 50.0 Å`, координата `r = z − 50 Å`. Порог сравнения: `σ_y,Al ≈ 120 MPa`. Робастный far-field шумовой уровень Δσ_vm: `133.527 MPa`.

## Напряжения

| Показатель | Значение | Где измерено | Источник | Интерпретация |
| ---------- | -------: | ------------ | -------- | ------------- |
| Peak Δσ_vm mean | +578.422 MPa | r≈1 Å, bin 0–2 Å, last20_mean | `stageF_cpu_results_key_stress_numbers.json` | максимум добавочного von Mises proxy у interface |
| Total σ_vm eps00194 (peak) | 2860.344 MPa | r≈1 Å, last20_mean | `stageF_cpu_results_sigma_summary.json` | абсолютный уровень поля у границы (physical case) |
| Total σ_vm eps0000 (peak) | 2281.921 MPa | r≈1 Å, last20_mean | `stageF_cpu_results_sigma_summary.json` | интерфейсный фон baseline |
| Meaningful Δσ_vm above noise | 4 Å | first below-noise bin 4–6 Å (Δ=1.673 MPa) | `stageF_cpu_results_key_stress_numbers.json` | добавочный сигнал выше шума только в первых ~4 Å |
| Layer total σ_vm > 120 MPa | 121.068 Å | last20_mean, до края Al slab | `stageF_cpu_results_sigma_summary.json` | это local virial proxy до края доступного слэба, НЕ толщина пластической зоны |
| Δσ_vm @ 0–5 Å | +161.264 MPa | r≈2.5 Å | `..._key_stress_numbers.json` | сильный near-interface Δ |
| Δσ_vm @ 10 Å | −1.149 MPa | r≈9 Å | `..._key_stress_numbers.json` | уже около нуля |
| Δσ_vm @ 20 Å | −12.454 MPa | r≈19 Å | `..._key_stress_numbers.json` | ниже шума |
| Δσ_vm @ 50 Å | −20.441 MPa | r≈49 Å | `..._key_stress_numbers.json` | ниже шума |
| Δσ_vm @ 100 Å | +30.160 MPa | r≈97.5 Å | `..._key_stress_numbers.json` | мал относительно interface peak и шума |
| Δσzz @ 0–5 Å | −42.178 MPa | r≈2.5 Å | `..._key_stress_numbers.json` | компонента zz |
| Δσzz @ 10 Å | +8.274 MPa | r≈9 Å | `..._key_stress_numbers.json` | компонента zz |
| Δσzz @ 20 Å | +6.966 MPa | r≈19 Å | `..._key_stress_numbers.json` | компонента zz |
| Δσzz @ 50 Å | −69.071 MPa | r≈49 Å | `..._key_stress_numbers.json` | компонента zz |
| Δσzz @ 100 Å | +24.070 MPa | r≈97.5 Å | `..._key_stress_numbers.json` | компонента zz |
| Δσ-компоненты в пике VM (r≈1 Å) | Δσxx=−160.130; Δσyy=−607.587; Δσzz=+52.308 | last20_mean | `..._key_stress_numbers.json` | пик доминируется Δσyy, не σzz |
| σzz dominance | not_confirmed | пик bin 0–2 Å | `..._key_stress_numbers.json` | z-направление не доминирует в пике |

## Пластичность и дефекты

| Показатель | Значение | Где измерено | Источник | Интерпретация |
| ---------- | -------: | ------------ | -------- | ------------- |
| DXA final line length eps0000 | 0 Å | step 50000 | `stageF_cpu_results_defect_summary.json` | развитых дислокационных линий нет |
| DXA final line length eps00194 | 0 Å | step 50000 | `stageF_cpu_results_defect_summary.json` | развитых дислокационных линий нет |
| HCP eps0000 max (final) | 0.000862 (1 атом) | r≈1 Å | `stageF_cpu_results_key_plasticity_numbers.json` | HCP практически отсутствует |
| HCP eps00194 max (final) | 0.0 | r≈1 Å | `stageF_cpu_results_key_plasticity_numbers.json` | HCP отсутствует |
| max \|ΔOTHER/non-FCC\| (final) | 0.035964 | r≈3 Å, bin 2–4 Å | `..._key_plasticity_numbers.json` (verified via CSV) | слабый локальный интерфейсный structural отклик |
| Residual plasticity verdict | not_confirmed | итоговая проверка | `stageF_cpu_results_residual_plasticity_check.json` | остаточная пластичность не подтверждена |

## Протокол и геометрия (обе cases идентичны)

| Параметр | Значение | Источник |
| --- | --- | --- |
| boundary | `p p f` | `stageF_cpu_results_production_verification.json` |
| zhi | 200 Å | production_verification.json |
| Lx × Ly × Lz | 94.4529 × 122.0488 × 200 Å | production_verification.json |
| Атомов | 113 295 | production_verification.json |
| Al matrix atoms (proxy) | ~82 000 | sigma_summary.json |
| timestep | 0.001 ps | production_verification.json |
| термостат | mobile NVT 300 K, damping 0.1 | production_verification.json |
| velocity seed | 88004 | production_verification.json |
| production steps | 50 000 | production_verification.json |
| returncode / статус | 0 / completed_clean | production_verification.json |
| MPI ranks / OMP threads | 6 / 2 | production_verification.json |
| box/relax, wall | false, false | production_verification.json |
| OVITO (CNA/DXA) | 3.15.4 | defect_summary.json |

Формула перевода virial → напряжение: `σ_mpa = −Σ(c_st)/(Lx·Ly·bin_width)·0.1`.
