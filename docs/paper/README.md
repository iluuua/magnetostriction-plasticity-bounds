# Manuscripts and figures

`main.tex` (English) and `main_ru.tex` (Russian) are the manuscripts;
`supplementary.tex` and `supplementary_ru.tex` hold the cell preparation, the
convergence and linearity checks, the elastic solutions, the creep model and
the lattice resistance of a straight dislocation. `highlights.tex` lists the
highlights.

These five files are generated. Edit the drafts in `_drafts/`
(`main_*_embedded.tex`, `supp_*_embedded.tex`, `highlights_embedded.tex` and the
text blocks `s2_*.tex`, `s6_*.tex`, `disl_*.tex`) and run

```sh
python docs/paper/_drafts/fill_embedded.py
```

which puts the numbers from `docs/reports/embedded_*.json` into the «KEY»
places and writes the five files here. `--dry-run` prints every value and its
source without writing.

| Figure | Content |
|---|---|
| `fig_cell` | Section of the cell through the inclusion (OVITO) and a sketch of the given strain with the forces on the aluminium |
| `fig_map` | Added von Mises stress and slip-plane shear stress in the xz plane: atomistic and elastic, same cell |
| `fig_decay` | Added stresses against distance from the surface along the field, across it and in the shear lobes; far field of a single sphere |
| `fig_glide` | Shear stress averaged along a straight edge dislocation above the inclusion |
| `fig_creep` | Shear amplitude needed for a 25 % creep-rate increase against the activation volume |

English figures keep the base name; Russian ones end in `_ru` and use a
decimal comma. Both sets come from `analysis/python/embedded_figures.py`
(`--language ru` for the Russian set).

`python scripts/build_manuscript.py` from the repository root compiles the
manuscripts and supplements; intermediate files stay in `build/paper`.
