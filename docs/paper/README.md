# Рукопись: сборка и состав

Статья в двух версиях: английская (`main.tex`, elsarticle, Computational
Materials Science) и русская (`main_ru.tex`, формат ФТТ). Обе собираются
локально через pdflatex.

## Как собрать

```
cd docs/paper
python splice_drafts.py                 # _drafts/*.tex -> main_v2.tex, main_ru_v2.tex
pdflatex main_v2 && bibtex main_v2 && pdflatex main_v2 && pdflatex main_v2
pdflatex main_ru_v2 && pdflatex main_ru_v2
```

Готовые PDF копируются в `manuscript_en.pdf` и `manuscript_ru.pdf` (они
лежат в репозитории). `python make_docx.py` делает из них Word-версии для
правки соавтором, `highlights.tex` собирается отдельно.

MiKTeX в этой системе не может перестроить `pdftex.map` (`initexmf` падает
на записи PATH), поэтому оба преамбула сами подгружают шрифты cm-super:
`\pdfmapfile{+cm-super-t1.map}`, для русской версии дополнительно
`+cm-super-t2a.map`. Без этих строк pdflatex подставляет растровые шрифты
Type 3, и в PDF пропадает поиск по тексту. В Overleaf строки безвредны.

## Overleaf

Загрузить `main.tex` (или `main_ru.tex` под именем `main.tex`),
`references.bib`, `main.bbl`, `highlights.tex` и все файлы `fig_*`.
Подробности в `README_overleaf.txt`.

## Состав

| Файл | Что это |
| --- | --- |
| `main.tex`, `main_ru.tex` | итоговые версии, собираются из черновиков |
| `_drafts/Section_*.tex` | исходные разделы, по языку на файл |
| `_drafts/*_notes.md` | какие термины и как объяснены, что удалено и почему |
| `_drafts/patch_*.py` | раунды правок: анкеры и замены каждого прохода |
| `_drafts/numbers_round*.json` | числа, подставляемые в текст из записей `docs/reports/` |
| `splice_drafts.py` | сборка `main_v2.tex` / `main_ru_v2.tex` из черновиков |
| `audit_v4.py` | сверка чисел в тексте с JSON-записями расчётов |
| `make_docx.py` | экспорт в Word через pypandoc |
| `fig_cell_*` | рендеры ячеек (OVITO), `analysis/python/stageG14_render_cells.py` |
| `fig_sigma_profile_*`, `fig_rss_vs_thresholds_*`, `fig_trajectories_*` | `analysis/python/stageG11_figures.py` |
| `fig_loading_programme_*` | `analysis/python/stageG14_loading_programme.py` |

Каждое число в тексте восходит к записи в `docs/reports/`. Раунды правок
(три содержательных плюс две многоагентные проверки) описаны в истории
коммитов, а не в отдельном файле.
