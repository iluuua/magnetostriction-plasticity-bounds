# Stage F CPU Results: Key Plasticity Numbers

Дата: 2026-07-02T08:03:43+03:00

Classification: `absent/not_confirmed`.

| Metric | eps0000 | eps00194 | Delta | r | Interpretation |
| --- | --- | --- | --- | --- | --- |
| DXA line length final | 0 | 0 | 0 | all Al matrix | DXA line length is zero in final CPU frames. |
| DXA max timeline available | 0 | 0 | 0 | step 0/final | not_observed_in_available_step0_and_step50000_frames |
| HCP max fraction | 0.001 | 0 | -0.001 | 1 | HCP is essentially absent; no positive growth signal in eps00194 final. |
| OTHER max fraction | 0.936 | 0.966 | 0.036 | 3 | OTHER is concentrated in interface shell/background. |
| Delta HCP max |  |  | -0.001 | 1 | Negative/small; not a plasticity signature. |
| Delta OTHER max |  |  | 0.036 | 3 | Small final interface-shell delta. |
| FCC drop max |  |  | 0.036 | 3 | Equivalent to max positive non-FCC delta; weak local shell signal. |
| Residual plasticity verdict |  |  | not_confirmed |  | No DXA, no persistent defect cluster, no Dmin2/unload proof. |

## Reason

- Stress transfer is present as a virial proxy, but stress alone is not residual plasticity.
- CNA/DXA final comparison does not establish a persistent dislocation network.
- Dmin2 was not available from stored dump fields and is not claimed.
