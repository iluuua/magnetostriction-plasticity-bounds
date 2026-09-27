# Manuscripts and figures

`main.tex` and `main_ru.tex` are the authoritative English and Russian
manuscripts. `supplementary.tex` and `supplementary_ru.tex` contain the numerical
protocols, additional controls and reproducibility limitations. Both language
versions use the same numerical figure data and bibliography. English figures
keep their base filenames; Russian figures have a `_ru` suffix and translated
axes, legends, units and annotations.

| Figure | Input and interpretation |
|---|---|
| `fig_model.png` | OVITO rendering of deposited atomic coordinates; interface and loaded cells |
| `fig_field.pdf` | Signed shear increment from the common held-state pair, with coordinate definitions |
| `fig_dynamics.pdf` | Restrained G15 upper-line motion and the applied loading programme |
| `fig_bridge.pdf` | Shear amplitude needed for a 25% modelled rate increase, with ridge and sphere reference stresses |

The figure generator is `analysis/python/publication_figures.py`.
Run it with `--language ru` to regenerate the Russian set; English is the default.
Its `--list-inputs` option reports the exact files and checksums.
The comparison is mechanical: no measured magnetic strain or field-off memory
process is simulated.

Run `python scripts/build_manuscript.py` from the repository root after
regenerating figures. It writes the two manuscript PDFs, two supplement PDFs
and local Overleaf archives. Intermediate TeX files stay in `build/paper`.

The compact draft has an abstract below 150 English words, five keywords and
four figures. It is prepared as a regular research article with explicit model
limitations. No journal acceptance or current quartile is implied by this
format. [Physical Review Materials author guidance](https://journals.aps.org/prmaterials/authors)
allows regular articles without a fixed length limit and requires clear data
availability. Its Letter format has a
4,500-word limit and a separate editorial standard.
