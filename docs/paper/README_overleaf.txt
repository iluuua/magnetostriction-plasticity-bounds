Overleaf build instructions
===========================

English version (overleaf_en.zip)
  New Project -> Upload Project -> select the zip.
  Main document: main.tex          Compiler: pdfLaTeX
  Contents: main.tex, references.bib, main.bbl, highlights.tex,
            fig_sigma_profile_en.pdf, fig_trajectories_en.pdf,
            fig_rss_vs_thresholds_en.pdf
  main.bbl is included so the bibliography appears on the first pass;
  Overleaf will regenerate it with BibTeX anyway.

Russian version (overleaf_ru.zip)
  Main document: main_ru.tex       Compiler: pdfLaTeX
  Contents: main_ru.tex, fig_sigma_profile_ru.pdf,
            fig_trajectories_ru.pdf, fig_rss_vs_thresholds_ru.pdf
  The reference list is typed manually (numbered in citation order,
  FTT style), so no .bib file is needed.

Verified locally with MiKTeX 24.1 / pdfTeX 4.18:
  main.tex     21 pages, 0 errors, 0 undefined references, 0 overfull boxes (file names in Data availability use \path so they break)
  main_ru.tex  18 pages, 0 errors, 0 undefined references, 0 overfull boxes (file names in Data availability use \path so they break)

The figures are language-specific: the _en files carry English axis labels,
the _ru files Russian ones. Do not mix them between the two projects.
