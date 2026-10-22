# Stresses around a magnetostrictive Al13Fe4 inclusion in aluminium

Research data and analysis for the English and Russian manuscripts in
[docs/paper](docs/paper). The study computes the stress that an Al13Fe4
inclusion, lengthened along a magnetic field, produces in the surrounding
aluminium, and asks whether that stress is large enough to move dislocations.

The inclusion is a sphere of radius 2.5 nm placed in the middle of a periodic
aluminium cell of 12.6 x 12.4 x 12.6 nm (118,861 atoms) and surrounded by
aluminium on all sides. It is given a magnetostrictive strain of 0.194 % along
the field and -0.097 % across it, and held in that shape while the aluminium
relaxes at 0 K. The strain is an input of the model: the magnetostriction of
Al13Fe4 has not been measured, and the interatomic potential (MEAM, Jelinek et
al. 2012, run in LAMMPS) does not describe magnetism. Every stress scales
linearly with the strain.

## Main results

| Quantity | Result |
|---|---|
| Normal stress next to the inclusion, 5-10 A from the surface | about -126 MPa along the field, +75 MPa across it |
| Shear stress on the slip planes, same distance | up to 28 MPa |
| Response of the matrix | elastic and linear: +eps and -eps give mirror responses to within 0.8 MPa; no dislocations (DXA) in any state, also at 4 and 10 times the strain |
| Straight edge dislocation 12 A above the particle | moves 0.78 A away when the strain is applied (about half the 1.43 A valley spacing) and returns to within 0.06 A when it is removed |
| Atomistic field against the elastic solution for the same cell | about 0.80 of it beyond 10 A from the interface (median deviation 2.5 %); the loss builds up in a compliant layer of distorted aluminium a few angstroms thick |
| Strain at which a real particle would start local yield (elastic, single sphere) | 0.028-0.043 % for slip on {111}<110> (CRSS 13-20 MPa), 0.045-0.067 % for von Mises (40-60 MPa) |
| Line-averaged shear stress on an edge dislocation 10 A above the particle | up to 5.8 MPa |
| Stress at which a straight edge dislocation glides with this potential (0 K) | about 9 MPa, in jumps of b/2 |
| Activation volume at which the field gives the observed +25 % creep rate | about 23 b^3 |

These are results for one potential, one inclusion radius and one way of
building the interface, at 0 K. Whether the 0.80 factor carries over to
micron-size particles is an assumption that the calculation does not test.

## Repository map

| Location | Contents |
|---|---|
| `docs/paper/` | LaTeX sources, reading PDFs, figures in both languages, bibliography; drafts and the fill script in `docs/paper/_drafts/` |
| `docs/reports/` | Numerical records used by the paper (`embedded_*.json`, `meam_elastic_constants.json`) |
| `data/publication/embedded/` | Compressed, checksummed configurations and logs of the embedded-inclusion runs |
| `analysis/python/` | Stress, strain, defect, continuum, yield and creep analysis; figure generation |
| `lammps/embedded_inclusion/` | LAMMPS inputs: reference relaxation, static pair, dislocation slab relaxation and sweep |
| `scripts/` | Cell builders, strained-cell builder, run queues, data packaging, document build |
| `structures/` | Crystallographic source and the built cells with their metadata |
| `potentials/` | MEAM parameter files and their attribution |
| `tests/` | Focused checks of the published analysis |

The earlier version of the study (an Al13Fe4 ridge on a substrate, harmonic
restraints, dislocation ramps) is kept for the record: its data are in
`data/stageG4_clean/` and `data/publication/` outside `embedded/`, its scripts
are the `stage*` and `publication_*` modules, and its manuscript is in the git
history (commit `bb179ba`).

## Reproduce the analysis

Python 3.12 and the packages in `requirements.txt` are used. OVITO is needed for
the defect analysis and the cell render. LAMMPS is only needed to rerun the
simulations.

```sh
python -m pip install -r requirements.txt
python scripts/package_embedded_data.py --verify
python scripts/build_embedded_inclusion.py --shape sphere --radius 25 --out structures/embedded_inclusion/sphere_R25
python analysis/python/embedded_inclusion_continuum.py --box 125.9382 123.9383 126.1981 --out docs/reports/embedded_continuum.json
python analysis/python/embedded_yield.py --out docs/reports/embedded_yield.json
python analysis/python/embedded_figures.py
python analysis/python/embedded_figures.py --language ru
python docs/paper/_drafts/fill_embedded.py
python -m pytest tests
```

The built cells are not tracked; the builder line above recreates the one the
cell figure needs (the dislocation slabs come from
`scripts/build_embedded_dislocation.py`). The field, gate, defect and interface
records are computed from the static dumps (`ref`, `plus`, `minus`) by
`embedded_inclusion_field.py`, `embedded_gates.py`, `embedded_dxa.py` and
`embedded_interface.py`, and the dislocation and margin records by
`embedded_disl_states.py` and `embedded_records.py`; each script states its
inputs in its docstring. Stresses are per-atom virials divided by
16.6075 A^3, tension positive, in MPa.

## Run the simulations

The cell is built by `scripts/build_embedded_inclusion.py`. The reference cell
is relaxed by `lammps/embedded_inclusion/in.relax_control`, and
`scripts/queue_embedded_static.sh` then builds and relaxes the +eps and -eps
cells and runs the field analyses. `scripts/queue_embedded_plasticity.sh` runs
the dislocation slab next to the particle and the cells with 4 and 10 times the
strain. The original runs used LAMMPS 22 July 2025 with Kokkos on one GPU.

## Build the documents

Install a TeX distribution with pdfLaTeX, BibTeX, the article class, AMS
mathematics, graphicx, placeins, natbib and Russian Babel support, then run:

```sh
python scripts/build_manuscript.py
python scripts/validate_publication.py
```

## Attribution and reuse

Original project code is under the [MIT licence](LICENSE). The MEAM parameters
and crystallographic data keep their upstream attribution; see
[potentials/README.md](potentials/README.md). Cite the sources in
`docs/paper/references.bib` and the repository revision when reusing a
calculation.

The manuscripts are research drafts by I. Mikhailovskiy and D. Pshonkin.
