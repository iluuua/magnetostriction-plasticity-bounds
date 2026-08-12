# Stage F CPU results: production verification

Дата: 2026-07-02T07:38:17+03:00

Status: `completed_clean_cpu_pair`

Проверка относится только к CPU fallback pair. GPU результаты не смешивались с CPU delta pair.

| case | status | return | max step | final data | final restart |
| --- | --- | --- | --- | --- | --- |
| F0_planar_100A_comm_eps0000_cpu_zhi200 | completed_clean | 0 | 50000.0 | 1 | 1 |
| F0_planar_100A_comm_eps00194_cpu_zhi200 | completed_clean | 0 | 50000.0 | 1 | 1 |

## Protocol gates

| gate | value |
| --- | --- |
| boundary | p p f |
| zhi_A | 200 |
| dump_every | 1000.0 |
| thermo_modify_lost_ignore | 0 |
| box_relax | 0 |
| wall | 0 |
