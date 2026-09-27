"""Check localized figure labels and equality of the English/Russian plot data.

The graph tests use archived records and capture Matplotlib objects without
writing output files. Atomistic rendering is verified separately with OVITO.
"""

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis" / "python"))

import publication_figures as figures  # noqa: E402


def test_labels_preserve_english_filenames_and_localize_russian_numbers():
    english = figures.FigureLabels("en")
    russian = figures.FigureLabels("ru")
    assert english("Time", "Время") == "Time"
    assert russian("Time", "Время") == "Время"
    assert english.number(-15.451, ".2f") == "-15.45"
    assert russian.number(-15.451, ".2f") == "-15,45"
    assert english.stem("fig_field") == "fig_field"
    assert russian.stem("fig_field") == "fig_field_ru"
    with pytest.raises(ValueError):
        figures.FigureLabels("unknown")


@pytest.mark.parametrize("name", ["field", "dynamics", "bridge"])
def test_localization_preserves_every_plotted_value(name, monkeypatch):
    captured = []

    def capture(figure, output, stem):
        captured.append((figure, stem))

    monkeypatch.setattr(figures, "save_plot", capture)
    figures.setup_style()
    args = SimpleNamespace(
        reports=ROOT / "docs/reports",
        interface_metadata=figures.STRUCTURES
        / figures.INTERFACE
        / f"{figures.INTERFACE}_metadata.json",
        loaded_metadata=figures.STRUCTURES / figures.LOADED / f"{figures.LOADED}_metadata.json",
        output=ROOT / "build/unused",
    )
    try:
        for language in ("en", "ru"):
            args.language = language
            getattr(figures, f"figure_{name}")(args)
        (english, en_stem), (russian, ru_stem) = captured
        assert en_stem == f"fig_{name}"
        assert ru_stem == f"fig_{name}_ru"
        assert len(english.axes) == len(russian.axes)
        for en_ax, ru_ax in zip(english.axes, russian.axes, strict=True):
            assert en_ax.get_xlim() == ru_ax.get_xlim()
            assert en_ax.get_ylim() == ru_ax.get_ylim()
            assert en_ax.get_xscale() == ru_ax.get_xscale()
            assert en_ax.get_yscale() == ru_ax.get_yscale()
            for en_line, ru_line in zip(en_ax.lines, ru_ax.lines, strict=True):
                np.testing.assert_array_equal(en_line.get_xydata(), ru_line.get_xydata())
            for en_patch, ru_patch in zip(en_ax.patches, ru_ax.patches, strict=True):
                np.testing.assert_array_equal(
                    en_patch.get_path().vertices, ru_patch.get_path().vertices
                )
                np.testing.assert_array_equal(
                    en_patch.get_patch_transform().get_matrix(),
                    ru_patch.get_patch_transform().get_matrix(),
                )
            assert re.search("[А-Яа-я]", ru_ax.get_xlabel() + ru_ax.get_ylabel())
            title = ru_ax.get_title(loc="left")
            if en_ax.get_title(loc="left"):
                assert re.search("[А-Яа-я]", title)
            else:
                assert any(re.search("[А-Яа-я]", item.get_text()) for item in ru_ax.texts)
    finally:
        for figure, _ in captured:
            figures.plt.close(figure)


def test_manuscripts_select_their_own_figure_language():
    pattern = r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}"
    base = ["fig_model.png", "fig_field.pdf", "fig_dynamics.pdf", "fig_bridge.pdf"]
    for filename, suffix in (("main.tex", ""), ("main_ru.tex", "_ru")):
        source = (ROOT / "docs/paper" / filename).read_text(encoding="utf-8")
        expected = [f"{Path(name).stem}{suffix}{Path(name).suffix}" for name in base]
        assert re.findall(pattern, source) == expected
