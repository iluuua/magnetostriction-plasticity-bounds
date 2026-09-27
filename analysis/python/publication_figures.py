#!/usr/bin/env python3
"""Render four manuscript figures from the archived calculations.

Run with the repository's Python environment::

    python analysis/python/publication_figures.py
    python analysis/python/publication_figures.py --only field dynamics bridge
    python analysis/python/publication_figures.py --language ru

Inputs are two archived LAMMPS atomic-style files, their geometry metadata, and
the G10, G15, G5 and G8 records in docs/reports. Paths can be overridden for
curated copies. --list-inputs prints paths and SHA-256 hashes without plotting.

LAMMPS coordinates and CSV displacements are in angstrom; figures use nm.
The G15 time conversion is 0.001 ps per step. Stresses are in MPa. The G5
integral uses SI units internally and returns a fractional rate increase.

Outputs are fig_model.png (600 dpi) and fig_field, fig_dynamics, fig_bridge
as PDF and PNG (300 dpi). PDF text uses embedded TrueType fonts. No MD,
record editing, downloads or intermediate image files are required. Russian
figures use the same numerical inputs and geometry, with a _ru filename suffix.

The model panels show real atoms in 1 nm central sections of the relaxed
interface reference and the as-built loaded cell, each containing 91,428
atoms. DXA runs on the full loaded cell with p p f boundaries.
Field curves retain the sign of the xz stress difference. Their abscissa
is height above the nominal crest (40 A), not shortest distance to the
interface. Slice selection uses the actual envelope of all inclusion atoms
in both snapshots. Signed MD shear uses the compression-positive convention.
G15 centroids that intersect a 1.5 nm periodic-seam margin are omitted:
the CSV does not resolve the original partner from seam fragments there.
Departure brackets reproduce the recorded per-line criterion; they are
sampling intervals, not confidence intervals or nucleation thresholds.
The bridge applies the same assumed r^-3 stress distribution to two scalar
stress scales. Neither the activation volume nor the imposed strain is
validated as a material property by that comparison.

Dependencies: numpy, scipy, matplotlib, Pillow; OVITO and PySide6 for model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors as mcolors
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Rectangle
from scipy.integrate import quad
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[2]
PUBLICATION_DATA = ROOT / "data" / "publication"
STRUCTURES = ROOT / "structures" / "stageG4_tilted_solute"
INTERFACE = "G4_tilted_eps0000_u100k"
LOADED = "G4_tilted_eps0000_dipu100k"
TEAL = "#007F82"
ORANGE = "#BC5D22"
BLUE = "#246CA5"
INK = "#262B30"
MATRIX = "#CDD2D6"
INCLUSION_AL = "#E5B090"
IRON = "#A43B26"
FAULT = "#459E75"
STEP_PS = 0.001
PRELOAD_PS = 5.0
SEAM_MARGIN_A = 15.0


@dataclass(frozen=True)
class FigureLabels:
    """Choose figure text and filenames without modifying numerical data."""

    language: str

    def __post_init__(self):
        if self.language not in ("en", "ru"):
            raise ValueError(f"Unsupported figure language: {self.language}")

    def __call__(self, english: str, russian: str) -> str:
        return russian if self.language == "ru" else english

    def number(self, value: float, precision: str) -> str:
        """Apply the decimal separator only to a displayed number."""
        text = format(value, precision)
        return text.replace(".", ",") if self.language == "ru" else text

    def stem(self, name: str) -> str:
        return name + ("_ru" if self.language == "ru" else "")


def read_json(path: Path) -> dict:
    """Read a UTF-8 record without changing its contents."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def setup_style() -> None:
    """Set final-size typography and deterministic vector-PDF settings."""
    matplotlib.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 10,
            "axes.titleweight": "medium",
            "axes.labelcolor": INK,
            "text.color": INK,
            "axes.edgecolor": "#697178",
            "axes.linewidth": 0.7,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "legend.frameon": False,
            "lines.linewidth": 1.5,
            "lines.markersize": 3.5,
            "mathtext.fontset": "dejavusans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def save_plot(fig: plt.Figure, output: Path, stem: str) -> None:
    """Save matching PDF/PNG figures without timestamp-dependent metadata."""
    fig.savefig(
        output / f"{stem}.pdf",
        bbox_inches="tight",
        pad_inches=0.06,
        metadata={"Creator": "publication_figures.py", "CreationDate": None, "ModDate": None},
    )
    fig.savefig(output / f"{stem}.png", dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


def note(ax: plt.Axes, text: str, xy, xytext, color=INK, **kwargs) -> None:
    """Add a compact label with a plain leader in the axes' data coordinates."""
    ax.annotate(
        text,
        xy=xy,
        xytext=xytext,
        fontsize=8,
        color=color,
        arrowprops={"arrowstyle": "-", "color": color, "lw": 0.65},
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.1},
        **kwargs,
    )


def render_atoms(path: Path, meta: dict, loaded: bool) -> tuple:
    """Ray trace actual atoms and return RGB pixels, view extent and DXA centres.

    The orthographic view is along +y, with +x right and +z up. OVITO's fov is half the visible
    vertical extent, so the pixel-to-coordinate mapping is fixed explicitly.
    This makes the overlaid 2 nm scale bar a physical, reproducible length.
    """
    from ovito.io import import_file
    from ovito.modifiers import DislocationAnalysisModifier
    from ovito.vis import TachyonRenderer, Viewport
    from PySide6.QtGui import QImage

    pipe = import_file(str(path), atom_style="atomic")
    # LAMMPS data files do not store boundary flags; OVITO defaults to p p p.
    pipe.source.data.cell_.pbc = (True, True, False)
    initial = pipe.compute()
    if initial.particles.count != meta["counts"]["total"]:
        raise ValueError(f"Atom count disagrees with metadata: {path}")
    if initial.particles.count != 91428:
        raise ValueError("These panels require the matched 91,428-atom cells.")
    measured_box = np.asarray(initial.cell)
    if not np.allclose(
        np.diag(measured_box[:, :3])[:2], [meta["box_A"]["lx"], meta["box_A"]["ly"]], atol=1e-6
    ):
        raise ValueError(f"In-plane box dimensions disagree with metadata: {path}")
    centres, projected_lines = [], []
    if loaded:
        pipe.modifiers.append(
            DislocationAnalysisModifier(
                input_crystal_structure=DislocationAnalysisModifier.Lattice.FCC
            )
        )
        dxa = pipe.compute()
        for seg in dxa.dislocations.segments:
            if seg.length >= 0.8 * meta["box_A"]["ly"]:
                centres.append(np.asarray(seg.points).mean(axis=0))
                projected_lines.append(np.asarray(seg.points)[:, [0, 2]].copy() / 10)
        if len(centres) != 4:
            raise ValueError("Expected four extended partial lines in the loaded start cell.")
        print("Model DXA partial-line centres (A):", np.round(centres, 3).tolist())

    n_matrix = meta["counts"]["al_matrix"]
    middle_y = 0.5 * meta["box_A"]["ly"]

    def appearance(frame, data):
        """Colour phase membership by atom ID and show a central 10 A section."""
        pos = np.asarray(data.particles.positions)
        ids = np.asarray(data.particles["Particle Identifier"])
        types = np.asarray(data.particles["Particle Type"])
        inclusion = ids > n_matrix
        colours = np.tile(mcolors.to_rgb(MATRIX), (len(pos), 1))
        colours[inclusion] = mcolors.to_rgb(INCLUSION_AL)
        colours[types == 2] = mcolors.to_rgb(IRON)
        if loaded:
            hcp = np.asarray(data.particles["Structure Type"]) == 2
            colours[hcp & ~inclusion] = mcolors.to_rgb(FAULT)
            for surf in data.surfaces.values():
                surf.vis.enabled = False
            # Project the full-cell DXA lines onto the final coordinate axes.
            data.dislocations.vis.enabled = False
        data.particles_.create_property("Color", data=colours)
        data.particles_.create_property("Radius", data=np.where(types == 2, 0.9, 0.72))
        data.cell.vis.enabled = False
        data.particles_.delete_elements(np.abs(pos[:, 1] - middle_y) > 5.0)

    pipe.modifiers.append(appearance)
    lx = meta["box_A"]["lx"]
    height = 174.0
    extent_a = [lx / 2 - height / 2, lx / 2 + height / 2, -10.0, 164.0]
    pipe.add_to_scene()
    try:
        vp = Viewport(type=Viewport.Type.Ortho)
        vp.camera_dir = (0, 1, 0)
        vp.camera_up = (0, 0, 1)
        vp.camera_pos = (lx / 2, -400.0, 77.0)
        vp.fov = height / 2
        qimage = vp.render_image(
            size=(2160, 2160),
            background=(1, 1, 1),
            renderer=TachyonRenderer(antialiasing=True, ambient_occlusion=False),
        )
        qimage = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
        rgba = np.asarray(qimage.bits()).reshape(qimage.height(), qimage.bytesPerLine())
        rgb = rgba[:, : qimage.width() * 4].reshape(qimage.height(), qimage.width(), 4).copy()
    finally:
        pipe.remove_from_scene()
    return rgb, np.asarray(extent_a) / 10.0, np.asarray(centres) / 10.0, projected_lines


def figure_model(args) -> None:
    """Two real-coordinate views with boundaries, crystallographic axes and scale."""
    text = FigureLabels(args.language)
    metas = [read_json(args.interface_metadata), read_json(args.loaded_metadata)]
    russian = args.language == "ru"
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 5.0 if russian else 4.7))
    fig.subplots_adjust(
        left=0.005, right=0.995, bottom=0.26 if russian else 0.19, top=0.9, wspace=0.02
    )
    for index, (ax, path, meta) in enumerate(
        zip(axes, [args.interface, args.loaded], metas, strict=True)
    ):
        rgb, extent, centres, projected_lines = render_atoms(path, meta, bool(index))
        ax.imshow(rgb, extent=extent, interpolation="none")
        ax.set_xlim(extent[:2])
        ax.set_ylim(extent[2:])
        ax.axis("off")
        ax.set_title(
            (
                text("(a) Relaxed interface reference", "(а) Релаксированная граница")
                if index == 0
                else text("(b) As-built loaded cell", "(б) Исходная ячейка с дислокациями")
            )
            + text("\n91,428 atoms", "\n91 428 атомов"),
            fontsize=10,
            pad=7,
        )
        lx = meta["box_A"]["lx"] / 10
        cx = meta["ridge"]["center_x_A"] / 10
        for x in (0, lx):
            ax.plot([x, x], [0, 15.0], ls=(0, (3, 3)), lw=0.65, color="#858B90")
        ax.add_patch(
            Rectangle((0, 0), lx, 0.6, facecolor="none", edgecolor=INK, hatch="////", linewidth=0.6)
        )
        ax.text(
            lx / 2,
            0.95,
            text("Fixed base", "Закреплённое основание"),
            ha="center",
            fontsize=7.5,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1},
        )
        ax.text(
            cx,
            10.1,
            text("Al matrix", "Матрица Al"),
            ha="center",
            fontsize=9,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5},
        )
        note(ax, text(r"Al$_{13}$Fe$_4$ ridge", r"Выступ Al$_{13}$Fe$_4$"), (cx, 3.1), (1.0, 5.2))
        ax.text(
            0.1,
            15.5,
            text("Free surface / vacuum", "Свободная поверхность / вакуум")
            if index == 0
            else text(r"Surface shear $+x$", r"Сдвиг $+x$"),
            fontsize=8,
        )
        if index:
            for line in projected_lines:
                ax.plot(line[:, 0], line[:, 1], color=BLUE, lw=1.15)
            ax.annotate(
                "",
                xy=(14, 15.6),
                xytext=(9.3, 15.6),
                arrowprops={"arrowstyle": "->", "lw": 1.2, "color": ORANGE},
            )
            split = float(np.median(centres[:, 2]))
            lower = centres[centres[:, 2] < split].mean(axis=0)
            upper = centres[centres[:, 2] > split].mean(axis=0)
            note(
                ax,
                text("Upper partner", "Верхняя линия"),
                (upper[0], upper[2]),
                (7.8, 8.6),
                color=BLUE,
            )
            note(
                ax,
                text("Lower partner", "Нижняя линия"),
                (lower[0], lower[2]),
                (10.4, 5.9),
                color=BLUE,
            )
        else:
            ax.annotate(
                "",
                xy=(cx + 1.1, 4.1),
                xytext=(cx - 0.5, 2.5),
                arrowprops={"arrowstyle": "->", "lw": 1.3, "color": TEAL},
            )
            note(
                ax,
                text(r"Strain axis, $45^\circ$", r"Ось деформации $45^\circ$"),
                (cx + 1.1, 4.1),
                (8.9, 6.1),
                color=TEAL,
            )
        ax.plot([1, 3], [-0.65, -0.65], color=INK, lw=2.5, solid_capstyle="butt")
        ax.text(3.35, -0.65, text("2 nm", "2 нм"), fontsize=8, ha="left", va="center")
        ax.text(10, -0.7, text(r"Periodic $x,y$", r"Периодичность $x,y$"), fontsize=8, ha="center")
    handles = [
        Line2D([], [], marker="o", ls="", color=c, label=t, ms=5)
        for c, t in (
            (MATRIX, text("Matrix Al", "Al матрицы")),
            (INCLUSION_AL, text("Inclusion Al", "Al включения")),
            (IRON, "Fe"),
            (FAULT, text("Stacking fault", "Дефект упаковки")),
        )
    ]
    handles.append(
        Line2D(
            [],
            [],
            color=BLUE,
            label=text("DXA partial lines", "Частичные дислокации (DXA)"),
            lw=1.2,
        )
    )
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.1 if russian else 0.055),
        ncol=3 if russian else 5,
        columnspacing=0.9,
        handletextpad=0.3,
    )
    fig.text(
        0.5,
        0.08 if russian else 0.045,
        text(
            r"$x\parallel[1\bar{1}0]$ (right)     $y\parallel[11\bar{2}]$ (view direction)"
            r"     $z\parallel[111]$ (up)",
            r"$x\parallel[1\bar{1}0]$ (вправо)     $y\parallel[11\bar{2}]$ (направление взгляда)"
            r"     $z\parallel[111]$ (вверх)",
        ),
        ha="center",
        fontsize=8,
    )
    fig.text(
        0.5,
        0.005,
        text(
            "Central 1 nm atomic section; full periodic thickness 6.45 nm."
            "  DXA lines from the full loaded cell.",
            "Центральный срез толщиной 1 нм. Полная периодическая толщина 6,45 нм.\n"
            "Линии дислокаций определены методом DXA по всей ячейке.",
        ),
        ha="center",
        fontsize=7.5,
    )
    fig.savefig(
        args.output / f"{text.stem('fig_model')}.png", dpi=600, bbox_inches="tight", pad_inches=0.07
    )
    plt.close(fig)


def coordinate_diagram(ax, record: dict, meta: dict, text: FigureLabels) -> None:
    """Draw an explicitly labelled coordinate diagram, not an atomistic image."""
    height = (meta["ridge"]["apex_z_A"] - record["z_interface_A"]) / 10
    radius = meta["ridge"]["rx_A"] / 10
    theta = np.linspace(0, np.pi, 101)
    points = np.c_[radius * np.cos(theta), height * np.sin(theta)]
    ax.add_patch(Rectangle((-5, -2), 10, 2, color=INCLUSION_AL, alpha=0.65))
    ax.add_patch(
        Polygon(points, closed=True, facecolor=INCLUSION_AL, edgecolor=ORANGE, linewidth=1)
    )
    ax.add_patch(Rectangle((-1, height), 2, 5.6, facecolor=TEAL, alpha=0.07))
    ax.add_patch(Rectangle((-4.8, 6), 9.6, record["bin_A"] / 10, facecolor=BLUE, alpha=0.16))
    ax.axhline(height, color=ORANGE, ls="--", lw=0.8)
    ax.plot([-1, -1, 1, 1], [7.6, height, height, 7.6], color=TEAL, ls=":", lw=1)
    ax.annotate(
        "",
        xy=(0, 6.2),
        xytext=(0, height),
        arrowprops={"arrowstyle": "<->", "color": TEAL, "lw": 1},
    )
    ax.text(0.3, 4.0, r"$d$", color=TEAL, fontsize=10)
    ax.annotate(
        "",
        xy=(4.2, 6.2),
        xytext=(4.2, 0),
        arrowprops={"arrowstyle": "<->", "color": INK, "lw": 0.8},
    )
    ax.text(4.4, 3.2, r"$r$", fontsize=10)
    ax.text(0, -1.2, text("Support layer", "Подложка"), ha="center", fontsize=8)
    ax.text(0, 0.65, text("Ridge", "Выступ"), ha="center", fontsize=8)
    ax.text(-4.5, 4.7, "Al", fontsize=9)
    ax.text(
        0, 8.1, text("2 nm axial window", "Осевое окно 2 нм"), ha="center", fontsize=8, color=TEAL
    )
    ax.text(-4.6, 6.55, text("0.4 nm slice", "Слой 0,4 нм"), fontsize=7.5, color=BLUE)
    ax.set_xlim(-5, 5.4)
    ax.set_ylim(-2, 9)
    ax.set_xticks([-4, 0, 4])
    ax.set_yticks([0, 2, 4, 6, 8])
    ax.set_xlabel(text(r"$x-x_c$ (nm)", r"$x-x_c$ (нм)"))
    ax.set_ylabel(text(r"$r=z-z_0$ (nm)", r"$r=z-z_0$ (нм)"))
    ax.set_title(text("(a) Coordinate diagram", "(а) Координаты"), loc="left")


def figure_field(args) -> None:
    """Use nominal-crest distances with the record's actual-apex slice filter."""
    text = FigureLabels(args.language)
    record = read_json(args.reports / "stageG10_field_profile.json")
    meta = read_json(args.interface_metadata)
    rows = [row for row in record["profile"] if row["above_apex"]]
    nominal_crest = meta["ridge"]["apex_z_A"]
    crest_r = nominal_crest - record["z_interface_A"]
    distance = (np.array([row["r_A"] for row in rows]) - crest_r) / 10
    axial = np.array([row["d_sigma_xz_axis_MPa"] for row in rows])
    width = np.array([row["d_sigma_xz_MPa"] for row in rows])
    fig, (left, ax) = plt.subplots(
        1, 2, figsize=(7.2, 3.65), gridspec_kw={"width_ratios": [1, 2.2]}
    )
    fig.subplots_adjust(left=0.08, right=0.99, bottom=0.2, top=0.82, wspace=0.35)
    coordinate_diagram(left, record, meta, text)
    ax.axhline(0, color="#7E878D", lw=0.75)
    ax.axvline(0, color=ORANGE, ls="--", lw=0.8)
    ax.plot(
        distance,
        axial,
        "o-",
        color=TEAL,
        label=text(r"Axial $|x-x_c|<1$ nm", r"На оси $|x-x_c|<1$ нм"),
    )
    ax.plot(
        distance,
        width,
        "s-",
        color=BLUE,
        label=text("Full layer average", "Среднее по ширине слоя"),
    )
    ax.set_xlim(-0.2, max(distance) + 0.35)
    ax.set_ylim(-18, 8)
    ax.set_yticks([-15, -10, -5, 0, 5])
    ax.set_xlabel(text(r"Height above nominal crest, $d$ (nm)", r"Высота над вершиной $d$ (нм)"))
    ax.set_ylabel(text(r"Signed $\Delta\sigma_{xz}$ (MPa)", r"$\Delta\sigma_{xz}$ со знаком (МПа)"))
    ax.set_title(
        text("(b) Maintained ridge deformation", "(б) Удерживаемая деформация выступа"), loc="left"
    )
    ax.grid(axis="y", color="#DDE2E5", lw=0.5)
    ax.legend(loc="lower right")
    peak = int(np.argmax(np.abs(axial)))
    note(
        ax,
        f"{text.number(axial[peak], '.2f')} " + text("MPa", "МПа"),
        (distance[peak], axial[peak]),
        (distance[peak] + (0.85 if args.language == "en" else -1.1), axial[peak] - 1.5),
        color=TEAL,
    )
    fig.text(
        0.5,
        0.96,
        text("Prescribed strain", "Заданная деформация")
        + rf" $\varepsilon={text.number(100 * record['eigenstrain_used'], '.3f')}\%$;"
        + text(
            r" $\Delta\sigma=\sigma_{\mathrm{strained}}-\sigma_{\mathrm{control}}$",
            r" $\Delta\sigma=\sigma_{\varepsilon}-\sigma_0$",
        ),
        ha="center",
        fontsize=9,
    )
    fig.text(
        0.5,
        0.02,
        text(
            rf"Nominal crest {nominal_crest / 10:.3f} nm; "
            rf"$d=r-{crest_r / 10:g}\,\mathrm{{nm}}$. "
            rf"Inclusion envelope {record['ridge_apex_A'] / 10:.3f} nm; "
            "compression-positive convention.",
            f"Номинальная вершина {text.number(nominal_crest / 10, '.3f')} нм. "
            rf"$d=r-{text.number(crest_r / 10, 'g')}$ нм. "
            f"Граница включения {text.number(record['ridge_apex_A'] / 10, '.3f')} нм.\n"
            "Сжатие принято положительным.",
        ),
        ha="center",
        fontsize=8,
    )
    save_plot(fig, args.output, text.stem("fig_field"))


def trajectory(path: Path, lx_a: float) -> dict:
    """Read upper-partner centroids and mask seam-intersecting DXA aggregates."""
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    keys = ("step", "tau_nominal_MPa", "xu_minus", "xmin_minus", "xmax_minus")
    columns = {
        key: np.array([float(row[key]) if row[key] else np.nan for row in rows]) for key in keys
    }
    finite = np.isfinite(columns["xu_minus"])
    trusted = (
        finite
        & (columns["xmin_minus"] >= SEAM_MARGIN_A)
        & (columns["xmax_minus"] <= lx_a - SEAM_MARGIN_A)
    )
    if not trusted[0]:
        raise ValueError(f"No unambiguous reference centroid in {path}")
    displacement = (columns["xu_minus"] - columns["xu_minus"][0]) / 10
    displacement[~trusted] = np.nan
    return {
        "time_ps": columns["step"] * STEP_PS,
        "step": columns["step"],
        "tau_mpa": columns["tau_nominal_MPa"],
        "displacement_nm": displacement,
        "omitted_ps": (columns["step"][finite & ~trusted] * STEP_PS).tolist(),
    }


def figure_dynamics(args) -> None:
    """Compare held G15 trajectories, recorded departure brackets and loading."""
    text = FigureLabels(args.language)
    summary = read_json(args.reports / "stageG2_depinning_summary_G15held.json")
    lx_a = read_json(args.loaded_metadata)["box_A"]["lx"]
    fig, (ax, stress) = plt.subplots(
        2, 1, figsize=(7.2, 4.8), sharex=True, gridspec_kw={"height_ratios": [2.25, 1]}
    )
    fig.subplots_adjust(left=0.12, right=0.98, bottom=0.17, top=0.86, hspace=0.15)
    colours = [BLUE, ORANGE]
    for case, colour, marker, label in zip(
        ("G15_ctl", "G15_fld"),
        colours,
        ("o", "s"),
        (
            text("Held control", "Удерживаемый контроль"),
            text("Held strained ridge", "Удерживаемый деформированный выступ"),
        ),
        strict=True,
    ):
        data = trajectory(args.reports / f"stageG2_depinning_{case}_G15held.csv", lx_a)
        ax.plot(
            data["time_ps"],
            data["displacement_nm"],
            marker=marker,
            color=colour,
            label=label,
            ms=3.5,
        )
        onset = summary["cases"][case]["per_line"]["minus"]["onset"]
        index = int(np.flatnonzero(data["step"] == onset["step"])[0])
        lo, hi = data["time_ps"][index - 1 : index + 1]
        tau_lo, tau_hi = data["tau_mpa"][index - 1 : index + 1]
        for panel in (ax, stress):
            panel.axvspan(lo, hi, color=colour, alpha=0.12, lw=0)
        # Horizontal brackets follow the 2 ps output cadence, not an error model.
        y = -0.65 if case == "G15_ctl" else -1.8
        ax.annotate(
            "",
            xy=(lo, y),
            xytext=(hi, y),
            arrowprops={"arrowstyle": "|-|", "lw": 1, "color": colour},
        )
        ax.text(
            lo - 0.8,
            y,
            f"{lo:.0f}-{hi:.0f} " + text("ps", "пс"),
            color=colour,
            ha="right",
            va="center",
            fontsize=8,
        )
        print(
            f"{case}: departure {lo:g}-{hi:g} ps, {tau_lo:.3f}-{tau_hi:.3f} MPa;"
            f" omitted seam centroids at {data['omitted_ps']} ps"
        )
        if case == "G15_ctl":
            stress.plot(data["time_ps"], data["tau_mpa"], color=INK, lw=1.3, marker=".", ms=2.5)
    for panel in (ax, stress):
        panel.axvspan(0, PRELOAD_PS, color="#DEE3E6", alpha=0.65, lw=0)
        panel.axvline(PRELOAD_PS, color="#7E878D", ls=":", lw=0.8)
        panel.grid(axis="y", color="#DEE3E6", lw=0.5)
        panel.set_xlim(0, 44)
    ax.set_ylim(-10.4, 1.3)
    ax.set_ylabel(text(r"Upper-partner $x(t)-x(0)$ (nm)", "Верхняя линия\n" + r"$x(t)-x(0)$ (нм)"))
    ax.set_title(
        text("(a) Displacement and departure brackets", "(а) Смещение и интервалы ухода линии"),
        loc="left",
    )
    ax.legend(loc="lower left")
    ax.text(2.5, 0.6, text("Preload", "Выдержка"), fontsize=7.5, ha="center")
    ax.text(18, 0.6, text("Shear ramp", "Рост сдвиговой нагрузки"), fontsize=8, ha="center")
    stress.set_ylim(-5, 160)
    stress.set_yticks([0, 75, 150])
    stress.set_ylabel(text(r"$\tau_{\mathrm{applied}}$ (MPa)", r"$\tau$ (МПа)"))
    stress.set_xlabel(text("Time (ps)", "Время (пс)"))
    stress.text(
        0.02,
        0.8,
        text("(b) Shared loading programme", "(б) Общая программа нагружения"),
        transform=stress.transAxes,
        fontsize=9,
    )
    fig.text(
        0.5,
        0.96,
        text(
            "91,428 atoms; inclusion held in both runs; 300 K",
            "91 428 атомов; включение удерживается в обоих расчётах; 300 К",
        ),
        ha="center",
        fontsize=10,
    )
    fig.text(
        0.5,
        0.055,
        text(
            "DXA centroids intersecting a 1.5 nm periodic-seam margin are omitted.",
            "Положения линий DXA, заходящих в зону 1,5 нм у периодического шва, исключены.",
        ),
        ha="center",
        fontsize=8,
    )
    fig.text(
        0.5,
        0.01,
        text(
            "Shading marks the 2 ps sampling brackets of the recorded departure criterion.",
            "Заливка отмечает интервалы регистрации ухода линии с шагом записи 2 пс.",
        ),
        ha="center",
        fontsize=8,
    )
    save_plot(fig, args.output, text.stem("fig_dynamics"))


def creep_enhancement(stress_mpa: float, volume_b3: float, constants: dict) -> float:
    """Evaluate the G5 integral and return a fractional creep-rate increase.

    x = V* tau / kT is dimensionless; V* is supplied in units of b^3.
    The sinh form avoids cancellation in cosh(u)-1 near u=0 and includes
    the analytic endpoint value 1/2, using the same integral as stage G5.
    """
    x = volume_b3 * constants["b_m"] ** 3 * stress_mpa * 1e6 / constants["kT_300K_J"]
    if x < 0:
        raise ValueError("Activation volume and stress amplitude must be nonnegative.")
    if x == 0:
        return 0.0

    def integrand(u):
        return 0.5 if u == 0 else 2 * (math.sinh(u / 2) / u) ** 2

    integral, _ = quad(integrand, 0, x, epsabs=1e-12, epsrel=1e-10)
    return constants["volume_fraction"] * x * integral


def figure_bridge(args) -> None:
    """Plot the conditional G5 response using recorded MD and sphere stress scales."""
    text = FigureLabels(args.language)
    bridge = read_json(args.reports / "stageG5_two_scale_bridge.json")
    constants = bridge["constants"]
    field = read_json(args.reports / "stageG10_field_profile.json")
    sphere = read_json(args.reports / "stageG8_eshelby3d.json")
    md = max(abs(row["d_sigma_xz_axis_MPa"]) for row in field["profile"] if row["above_apex"])
    eshelby = sphere["interior_stress_MPa"]["sphere_3D"]["max_RSS_MPa"]
    target = constants["target_enhancement"]
    volumes = np.linspace(10, 142, 529)
    fig, ax = plt.subplots(figsize=(7.2, 4.15))
    fig.subplots_adjust(left=0.12, right=0.99, top=0.85, bottom=0.22)
    for stress, colour, style, label in (
        (
            md,
            TEAL,
            "-",
            text(
                f"MD axial peak, {md:.3f} MPa", f"Осевой максимум МД, {text.number(md, '.3f')} МПа"
            ),
        ),
        (
            eshelby,
            ORANGE,
            "--",
            text(
                f"Sphere interior, {eshelby:.2f} MPa",
                f"Внутри сферы, {text.number(eshelby, '.2f')} МПа",
            ),
        ),
    ):
        rates = [100 * creep_enhancement(stress, v, constants) for v in volumes]
        ax.semilogy(volumes, rates, color=colour, ls=style, label=label, lw=1.8)
        crossing = brentq(
            lambda v, amplitude=stress: creep_enhancement(amplitude, v, constants) - target, 1, 200
        )
        ax.plot([crossing], [100 * target], "o", color=colour, ms=5)
        ax.vlines(crossing, 1e-3, 100 * target, color=colour, ls=":", lw=0.9)
        ax.annotate(
            f"{text.number(crossing, '.1f')} $b^3$",
            xy=(crossing, 100 * target),
            xytext=(crossing + 5, 250),
            color=colour,
            fontsize=8,
            arrowprops={"arrowstyle": "-", "color": colour, "lw": 0.7},
        )
        print(f"Bridge stress {stress:.3f} MPa: 25% at V*={crossing:.6f} b^3")
    ax.axhline(100 * target, color=INK, ls=(0, (5, 3)), lw=1)
    ax.text(139, 100 * target * 1.6, text("25% target", "Уровень 25%"), ha="right", fontsize=8)
    ax.set_xlim(10, 142)
    ax.set_ylim(1e-3, 1e13)
    ax.set_xticks([20, 40, 60, 80, 100, 120, 140])
    ax.set_yticks([1e-2, 1, 1e2, 1e4, 1e6, 1e8, 1e10, 1e12])
    ax.set_xlabel(
        text(r"Assumed activation volume, $V^*/b^3$", r"Принятый активационный объём $V^*/b^3$")
    )
    ax.set_ylabel(text("Relative creep-rate increase (%)", "Прирост скорости ползучести (%)"))
    ax.set_title(
        text("Conditional two-scale response", "Условный двухмасштабный отклик"), loc="left", pad=10
    )
    ax.grid(axis="y", color="#DEE3E6", lw=0.5)
    ax.legend(loc="upper left")
    temperature = constants["kT_300K_J"] / 1.380649e-23
    fig.text(
        0.99,
        0.91,
        rf"$T={temperature:.0f}$ "
        + text("K", "К")
        + rf"; $f={text.number(constants['volume_fraction'], '.5f')}$; "
        + text("prescribed strain", "заданная деформация")
        + rf" ${text.number(100 * field['eigenstrain_used'], '.3f')}\%$",
        ha="right",
        fontsize=8,
    )
    fig.text(
        0.5,
        0.06,
        text(
            r"Both stress scales enter the same assumed $r^{-3}$ distribution "
            "and two-scale integral.",
            r"Для обеих оценок принято распределение $r^{-3}$ и один двухмасштабный интеграл.",
        ),
        ha="center",
        fontsize=8,
    )
    fig.text(
        0.5,
        0.013,
        text(
            "Activation volume and inclusion strain are conditional inputs to this comparison.",
            "Активационный объём и деформация включения заданы условно.",
        ),
        ha="center",
        fontsize=8,
    )
    save_plot(fig, args.output, text.stem("fig_bridge"))


def input_files(args) -> list[Path]:
    """List the exact file dependencies of the selected figures."""
    files = []
    if "model" in args.only:
        files.extend([args.interface, args.interface_metadata, args.loaded, args.loaded_metadata])
    if "field" in args.only:
        files.extend([args.interface_metadata, args.reports / "stageG10_field_profile.json"])
    if "dynamics" in args.only:
        files.extend(
            [args.loaded_metadata, args.reports / "stageG2_depinning_summary_G15held.json"]
        )
        files.extend(
            args.reports / f"stageG2_depinning_G15_{case}_G15held.csv" for case in ("ctl", "fld")
        )
    if "bridge" in args.only:
        files.extend(
            args.reports / name
            for name in (
                "stageG5_two_scale_bridge.json",
                "stageG8_eshelby3d.json",
                "stageG10_field_profile.json",
            )
        )
    return list(dict.fromkeys(files))


def main() -> int:
    """Resolve portable input paths and generate only the requested figure files."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=("model", "field", "dynamics", "bridge"),
        default=["model", "field", "dynamics", "bridge"],
    )
    parser.add_argument(
        "--interface", type=Path, default=PUBLICATION_DATA / "interface" / "initial_ctl.data.gz"
    )
    parser.add_argument(
        "--interface-metadata",
        type=Path,
        default=STRUCTURES / INTERFACE / f"{INTERFACE}_metadata.json",
    )
    parser.add_argument(
        "--loaded", type=Path, default=PUBLICATION_DATA / "g15_held_control" / "initial.data.gz"
    )
    parser.add_argument(
        "--loaded-metadata", type=Path, default=STRUCTURES / LOADED / f"{LOADED}_metadata.json"
    )
    parser.add_argument("--reports", type=Path, default=ROOT / "docs" / "reports")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "paper")
    parser.add_argument("--language", choices=("en", "ru"), default="en")
    parser.add_argument("--list-inputs", action="store_true")
    args = parser.parse_args()
    for path in input_files(args):
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        display_path = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        print(f"INPUT {display_path}  sha256={digest}")
    if args.list_inputs:
        return 0
    args.output.mkdir(parents=True, exist_ok=True)
    setup_style()
    builders = {
        "model": figure_model,
        "field": figure_field,
        "dynamics": figure_dynamics,
        "bridge": figure_bridge,
    }
    for name in args.only:
        builders[name](args)
        print(f"Wrote {FigureLabels(args.language).stem(f'fig_{name}')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
