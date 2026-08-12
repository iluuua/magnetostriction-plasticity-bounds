# Stage F CPU Results: Key Stress Numbers

Дата: 2026-07-02T08:03:43+03:00

Primary window: `last20_mean`. Stress is a local virial proxy; absolute MPa values should be interpreted with the documented conversion caveat.

## Executive Metrics

| Metric | Value | r / layer | Interpretation |
| --- | --- | --- | --- |
| Peak Delta sigma_vm mean | 578.422 | 0.0-2.0 A; last20_mean | Largest CPU-only baseline-subtracted VM change; signed value, selected by absolute magnitude. |
| Peak Delta sigma_vm p95 | 1745.8 | 85.0-90.0 A; final | Atom-level virial proxy p95 is noisy; use as secondary support only. |
| Peak Delta sigma_zz mean | -327.157 | 90.0-95.0 A; final | Z component is not the dominant peak component. |
| Peak total sigma_vm eps00194 | 2860.3 | 0.0-2.0 A | Total local virial VM proxy in physical CPU case. |
| Peak total sigma_vm eps0000 | 2281.9 | 0.0-2.0 A | Baseline also has high local virial stress near interface. |
| Thickness total sigma_vm > 120 MPa | 121.068 | contiguous from interface | Total VM proxy remains above 120 MPa to available slab edge; not a clean physical cutoff. |
| Thickness Delta sigma_vm meaningful above noise | 4 | noise floor 133.527 MPa | Baseline-subtracted near-interface effect is localized to the first two bins. |
| Delta sigma_vm at 10 A | -1.149 | 8-10 | Nearest-bin last-20%-mean CPU-only delta. |
| Delta sigma_vm at 20 A | -12.454 | 18-20 | Nearest-bin last-20%-mean CPU-only delta. |
| Delta sigma_vm at 50 A | -20.441 | 48-50 | Nearest-bin last-20%-mean CPU-only delta. |
| Delta sigma_vm at 100 A | 30.16 | 95-100 | Nearest-bin last-20%-mean CPU-only delta. |
| Decay within 100 A | yes | Delta sigma_vm at 100 A = 30.16 MPa | Delta sigma_vm falls below robust far-field noise by the 4-6 A bin and is below noise near 100 A; total sigma_vm remains above 120 MPa across the available slab, so total-stress cutoff is not a clean physical cutoff. |

## Checkpoints

| r checkpoint | r center A | eps0000 VM | eps00194 VM | Delta VM | eps0000 zz | eps00194 zz | Delta zz | f>120 eps0000 | f>120 eps00194 | Delta f |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0-5 A | 2.5 | 1402.8 | 1564.1 | 161.264 | -115.245 | -157.423 | -42.178 | 1 | 1 | 0 |
| 10 A | 9 | 681.646 | 680.497 | -1.149 | -256.214 | -247.94 | 8.274 | 1 | 1 | 0 |
| 20 A | 19 | 674.552 | 662.098 | -12.454 | -313.453 | -306.487 | 6.966 | 1 | 1 | 0 |
| 50 A | 49 | 733.232 | 712.791 | -20.441 | -163.135 | -232.206 | -69.071 | 1 | 1 | 0 |
| 100 A | 97.5 | 786.722 | 816.881 | 30.16 | -290.208 | -266.138 | 24.07 | 1 | 1 | 0 |

## Directional Component Check

At the peak Delta sigma_vm bin, components are:

| Component | MPa |
| --- | --- |
| delta_sigma_xx_mean_mpa | -160.13 |
| delta_sigma_yy_mean_mpa | -607.587 |
| delta_sigma_zz_mean_mpa | 52.308 |
| delta_sigma_vm_mean_mpa | 578.422 |

Dominant component: `delta_sigma_yy_mean_mpa`. Z dominance: `False`.

## Noise Floor

Method: far-field r_center>=70 A, threshold = median(abs(delta_vm)) + 2*1.4826*MAD. Noise floor = `133.527 MPa`. Far-field boundary-edge outliers are listed in JSON and should not be overinterpreted as a smooth physical decay signal.
