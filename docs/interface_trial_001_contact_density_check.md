# Проверка contact density для interface trial_001

Дата: 2026-05-10

## 1. Цель

Проверить, являются ли видимые в OVITO gap/void-like области около Al / Fe4Al13 реальными пустотами интерфейса или артефактами визуализации, triclinic skew и открытой структуры фазы Fe4Al13.

Ограничения соблюдены:

- 120 MPa не применялось;
- `fix addforce` не использовался;
- stress scenario не создавался;
- NPT не использовался;
- физическая валидация интерфейса не заявляется.

## 2. Входные данные

- Data: `/Users/ilua/Documents/ilua-system/projects/physics_md_al_fe/lammps/02_interface_relax/trial_001/data.interface_nvt_300k_long`
- Metadata: `/Users/ilua/Documents/ilua-system/projects/physics_md_al_fe/structures/interface/flat_interface/trial_001/interface_metadata.json`
- Phase assignment: `atom_id<=Al_slab_atoms (210)`
- interface_z: 40.164450 A
- interface window: +/- 8.000 A
- OVITO app paths detected: `['/Applications/Ovito.app']`
- OVITO Python module available: `False`

## 3. Cross-slab contact

| Quantity | Value |
|---|---:|
| Al_slab atoms near interface | 42 |
| Fe4Al13_slab atoms near interface | 52 |
| Cross-slab pairs tested | 2184 |
| Minimum cross-slab distance, A | 2.592466 |
| Mean of 10 smallest cross-slab distances, A | 2.662031 |

Pair counts:

| Cutoff, A | Cross-slab pair count |
|---:|---:|
| 2.3 | 0 |
| 2.5 | 0 |
| 2.8 | 20 |
| 3.0 | 33 |
| 3.5 | 48 |

## 4. z-density profile

- CSV: `results/tables/interface_trial_001_contact_density_z_profile.csv`
- Figure: `results/figures/interface_trial_001_contact_density_z_profile.png`
- Bin width: 1.000 A
- In-plane area: 102.156913 A^2
- Largest empty z-gap between occupied bins: 1.0 A, z=7.0..8.0 A
- Empty 1 A bins inside interface window: 2
- Empty interface-bin ranges: `[[32.0, 33.0], [37.0, 38.0]]`

Density comparison:

| Region | Interface density, atoms/A^3 | Bulk-like density, atoms/A^3 | Drop, % |
|---|---:|---:|---:|
| Al_slab | 0.066891 | 0.109635 | 38.99 |
| Fe4Al13_slab | 0.061180 | 0.063107 | 3.05 |

## 5. Verdict

Status: `contact_present_visible_gaps_likely_visualization_or_structure_artifact`

Recommendation: Keep trial_001 as unloaded baseline candidate, but still inspect visually before any loading.

Notes:

- minimum cross-slab distance is 2.592 A
- cross-slab pairs within 3.0/3.5 A: 33/48
- empty 1 A bins in interface window: 2

Interpretation: visible gaps are not automatically evidence of an interface void in this triclinic/open-structure slab. The largest empty z-gap is only 1 A and is not located at the interface; the empty 1 A interface bins should be interpreted together with Al(111) layer spacing, triclinic projection, and Fe4Al13 open structure. The contact-density numbers should be used together with OVITO visual inspection before any loaded scenario.
