# Strained inclusions and dislocation motion in aluminium

Research data and analysis for the English and Russian manuscripts in
[docs/paper](docs/paper). The study asks how a prescribed deformation of an
Al13Fe4 inclusion transfers shear stress to an aluminium matrix, and how that
stress compares with the motion of existing dislocations.

The inclusion strain is a modelling input, 0.00194 (0.194%). It is motivated by
an earlier stress estimate and is not a measurement of Al13Fe4 magnetostriction.
LAMMPS describes the mechanical response with the Jelinek et al. MEAM potential.
The model contains no magnetic-field dynamics.

## Research approach

The static calculation compares two states prepared from the same relaxed
configuration. One ridge is displaced along an axis 45 degrees from the surface
normal. Harmonic springs hold the inclusion near its reference coordinates
while the matrix relaxes. The difference of the spatially averaged stress
tensors isolates the response of this constrained model. A coordinate restraint
is distinct from changing the material's stress-free lattice.

Three shear ramps follow an existing dislocation pair in the same 91,428-atom
interface geometry. One unstrained, unrestrained control reaches 400 MPa. Two
restrained runs, unstrained and strained, reach 145.45 MPa at the same loading
rate. The saved regular frames end at 395.45 and 140.91 MPa, respectively;
separate final states contain the run endpoints. A 92,800-atom Al-Mg-Si
calculation without an inclusion is a separate comparator, not an identical
cell.

An isotropic inclusion solution and an activated-glide integral examine the
sensitivity of an assumed creep response to stress and activation volume.
They do not validate the assigned strain or explain a persistent response
after magnetic-field removal.

## Main observations

| Observable | Result and scope |
|---|---|
| Axial-window shear increment | Maximum magnitude 15.45 MPa, about 2.2 nm above the ridge crest |
| Width-averaged maximum resolved shear | Maximum 5.65 MPa across the twelve FCC slip systems; the xz component alone peaks at 5.04 MPa |
| Retained imposed ridge strain | Projection 0.973; formal fit standard error 0.0038 |
| Upper-line departure in the restrained pair | 105-115 MPa in the control and 115-125 MPa in the strained run |
| Interpretability of the ramp comparison | One-frame difference; early motion and periodic-seam fragments limit inference |
| Spherical analytical comparison | 41.45 MPa interior resolved shear for the same assumed strain and isotropic constants |

These are results for one potential, one geometry and a limited set of loading
conditions. There is no cell-size, rate or independent-seed convergence study.
Short DXA fragments are not evidence of a newly nucleated dislocation. Spatial
scatter between stress bins is not an estimate of numerical uncertainty.

The maintained static pair reaches its requested force tolerance. The separate
alloy preparation stops on energy tolerance with a force two-norm of
10.12 eV/angstrom, so its limited-motion trajectory is not an equilibrated
pinning-threshold measurement. The archived alloy starting file also lacks a
launch-time checksum; exact replay of that initial mobile configuration is
unverified. These limitations do not prevent reanalysis of the deposited
trajectory.

## Repository map

| Location | Contents |
|---|---|
| `docs/paper/` | Authoritative LaTeX sources, current PDFs, four figures in both languages and bibliography |
| `docs/reports/` | Numerical records and per-frame tables used by the paper |
| `data/stageG4_clean/` | Complete control/strained virial dumps for the static stress calculation |
| `data/publication/` | Initial/final states, loading logs, G15 positions, complete alloy trajectory and checksums |
| `analysis/python/` | Stress, strain, dislocation, continuum and creep analysis; figure generation |
| `lammps/` | The three input protocols needed to replay the published calculations |
| `scripts/` | Data packaging, portable calculation launcher, document build and validation |
| `structures/` | Crystallographic source and retained geometry metadata |
| `potentials/` | Original MEAM files and their attribution |
| `tests/` | Focused checks of the published analysis |

The source of truth is `main.tex` / `main_ru.tex`, with technical details in the
two supplementary sources. No section-splicing or text-replacement pipeline is
required. Repository documentation is in English; the Russian manuscript is
maintained as an explicit language counterpart.

## Reproduce the analysis

Python 3.12 and the packages in `requirements.txt` are used. OVITO is required
for dislocation analysis and the atomistic render. LAMMPS is only required to
rerun molecular dynamics.

```sh
python -m pip install -r requirements.txt
python scripts/package_publication_data.py --verify
python analysis/python/stageG10_field_profile.py --r-max 110
python analysis/python/stageG12_eigenstrain_retention.py
python analysis/python/stageG8_eshelby3d.py
python analysis/python/stageG5_two_scale_bridge.py
python analysis/python/publication_figures.py
python analysis/python/publication_figures.py --language ru
python -m pytest tests
```

The default static inputs are the compressed dumps in `data/stageG4_clean`.
The stress profile is restricted to the published range; comparisons must use
the same atom selection, bin width and tensor convention. JSON and CSV outputs
share one basename.

Signed MD tensors use positive normal compression, from `-S / volume` where
`S` is LAMMPS `stress/atom`. Tensile-positive Cauchy tensors have the opposite
sign. Maximum absolute resolved shear and von Mises values are unchanged.
The retained matrix layers are selected using the actual inclusion envelope
in both snapshots, including Al and Fe, rather than a fixed crest cutoff.

The data guide in [data/publication/README.md](data/publication/README.md)
identifies transformations, sampling intervals, units and analysis limitations.
Source checksums distinguish deposited simulation output from derived tables.
No DOI or external data deposit is claimed.

## Build the documents

Install a TeX distribution providing pdfLaTeX, BibTeX, the article class,
AMS mathematics, graphicx, natbib and Russian Babel support. Then run:

```sh
python scripts/build_manuscript.py
python scripts/validate_publication.py
```

Intermediate files go to `build/paper`. Current reading PDFs are written to
`docs/paper`; local Overleaf ZIPs contain the relevant source, figures and
bibliography. Bibliography and figure changes require rebuilding both languages.

## Replay a calculation

The launcher starts from a deposited initial configuration. The alloy input
has the provenance limitation described above. It prints an
explicit command unless `--execute` is supplied:

```sh
python scripts/run_calculation.py interface_control
python scripts/run_calculation.py g15_held_strained --executable /path/to/lmp --kokkos --execute
```

Available cases are `interface_control`, `interface_strained`,
`g15_free_control`, `g15_held_control`, `g15_held_strained` and `alloy`.
The original runs used LAMMPS 22 July 2025, MEAM, a 1 fs timestep and CUDA
Kokkos where applicable. Set `LAMMPS_EXECUTABLE` or pass `--executable`.
GPU support is optional and must be compiled into the chosen binary.
The launcher never overwrites an existing result directory.

## Attribution and reuse

Original project code retains the [MIT licence](LICENSE). The MEAM parameters
and crystallographic data retain their upstream attribution; the repository
licence does not replace third-party terms. See [potentials/README.md](potentials/README.md)
for the parameter source. Cite the scientific sources in `references.bib`
and identify the repository revision when reusing a calculation.

The manuscripts are research drafts by I. Mikhailovskiy and D. Pshonkin.
