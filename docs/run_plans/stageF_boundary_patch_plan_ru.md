# Stage F boundary-patch plan

Дата: 2026-06-29

## Цель

Перейти от blind DXA hunting к локальной модели границы Fe4Al13 / Al и физически читаемому профилю `sigma(r)`, где `r=0` на interface, а `r` направлен в Al matrix. Основной критерий: толщина слоя, где stress proxy выше или сравнима с `sigma_y = 120 MPa`.

## Почему не full inclusion

Полное включение `5-7 um` и область `20-30 um` не моделируются атомистически в текущем проекте: даже `700k-1M` atoms дают nanoscopic domain. Stage F должен уточнять локальную physics на boundary patch, а не имитировать полный микронный объект.

## F0: planar boundary patch

- `geometry_id`: `F0_planar_100A`
- interface: Fe4Al13 / Al
- geometry: planar, plane approximately XY
- `r=0`: nominal interface plane
- `r direction`: `+Z` into Al matrix
- eigenstrain / magnetic induction direction: `Z`
- box: `120 x 120 A`
- Al matrix depth: `100 A`
- Fe4Al13 depth: `50 A`
- total z: about `150-180 A`
- preferred boundary: `p p f`
- bottom Fe/support: fixed or weakly constrained layer if needed
- thermostat: NVT 300 K on mobile atoms only
- first role: clean `sigma(r)` without curved-interface noise

F0_300A:

- `geometry_id`: `F0_planar_300A`
- box: `100-120 x 100-120 A`
- Al depth: `300 A`
- Fe4Al13 depth: `50 A`
- total z: `350-380 A`
- role: check whether `sigma(r)` falls below `120 MPa` before the far boundary

F0_500A:

- plan only
- do not run automatically
- use only if F0_300A still truncates stress decay

## F1: curved cap / truncated ellipsoid boundary

- `geometry_id`: `F1_curved_cap_100A`
- geometry: truncated ellipsoid / curved cap
- not full inclusion
- cap surface is local interface `r=0`
- `r direction`: local outward normal into Al matrix
- `Z`: field/eigenstrain direction
- cap radius x/y: `80 A`
- cap height z: `40 A`
- Al depth above cap: `120 A`
- Fe4Al13 support below cap: `50 A`
- lateral box: `180-220 A`
- total z: `180-230 A`
- preferred boundary: `p p f`
- role: match the visual notebook sketch after F0 interpretation exists

## Eigenstrain scenarios

| eps_z | label | role |
|---:|---|---|
| `0` | baseline | no magnetostriction control |
| `0.00194` | physical | main physically relevant estimate, about `147 MPa / 75.7 GPa` |
| `0.005` | moderate_overload | diagnostic threshold case only |
| `0.010` | high_overload | diagnostic high-stress case only, no direct physical claim |

Do not overclaim overload cases.

## Run protocol

Preparation:

- build data file
- minimize
- sanity contact check: no hard overlaps `< 1.8 A`
- write geometry metadata JSON compatible with `analysis/python/stageF_boundary_stress_decay.py`

Smoke:

- `2000` steps
- NVT 300 K
- dump every `100` or `200` steps
- restart at end
- validate: no `ERROR`, no `nan`, no lost atoms, no temperature spike, no CUDA illegal address, restart exists, final data exists

Production:

- never start automatically before smoke passes
- first production: `50000` steps
- extend to `100000` steps only if 50k is stable
- dump every `1000-2000` steps
- restart every `5000-10000` steps
- chunked/resumable from restart
- if failure: stop and write failure report

## Initial safe queue

1. `F0_planar_100A_eps0000` smoke
2. `F0_planar_100A_eps00194` smoke
3. `F0_planar_100A_eps005` smoke
4. `F0_planar_100A_eps00194` production 50k only if smoke passed
5. `F0_planar_100A_eps005` production 50k only if smoke passed
6. `F0_planar_300A_eps00194` smoke only
7. `F1_curved_cap_100A_eps00194` smoke only
8. `F1_curved_cap_100A_eps005` smoke only

No full sweep. No F0_500A automatic run. No F1 production until F0 interpretation is written.

## Metadata-only prep result

`scripts/prepare_stageF_boundary_patch_geometry.py --all-metadata` completed without launching MD and wrote 7 metadata files under `structures/stageF_boundary_patch/`.

| case | atoms | Al matrix atoms | Fe4Al13-side atoms |
|---|---:|---:|---:|
| `F0_planar_100A_eps0000` | `149405` | `139460` | `9945` |
| `F0_planar_100A_eps00194` | `149359` | `139414` | `9945` |
| `F0_planar_100A_eps005` | `149175` | `139230` | `9945` |
| `F0_planar_300A_eps00194` | `327559` | `317614` | `9945` |
| `F0_planar_300A_eps005` | `327375` | `317430` | `9945` |
| `F1_curved_cap_100A_eps00194` | `473137` | `458779` | `14358` |
| `F1_curved_cap_100A_eps005` | `472938` | `458613` | `14325` |

## Analysis hooks

Every run must produce metadata with:

`case_id`, `geometry_id`, `geometry_type`, `box_x_A`, `box_y_A`, `box_z_A`, `al_depth_A`, `fe_depth_A`, `cap_radius_x_A`, `cap_radius_y_A`, `cap_height_A`, `interface_definition`, `r_zero_definition`, `r_direction`, `eigenstrain_axis`, `eps_z`, `temperature_K`, `yield_threshold_mpa`, `data_file`, `dump_files`, `restart_files`, `lammps_input`, `log_file`.

Required analysis outputs:

- `sigma_xx(r)`, `sigma_yy(r)`, `sigma_zz(r)`
- `sigma_vm(r)`
- `above_yield_fraction(r)`
- `plastic_layer_thickness_A`
- `HCP/OTHER(r)`
- DXA as secondary diagnostic
- event timeline

## Exact next command

Prepare the first data file for the safe baseline smoke:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_stageF_boundary_patch_geometry.py --geometry F0_planar_100A --eps-z 0 --write-data
```
