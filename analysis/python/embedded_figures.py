#!/usr/bin/env python3
"""Figures for the embedded-inclusion calculation (sphere in an Al box).

    python analysis/python/embedded_figures.py --only scheme
    python analysis/python/embedded_figures.py --language ru

Figures, written to docs/paper as PDF and PNG (Russian copies end in _ru):
  fig_cell     section of the cell with the inclusion, and the given strain
  fig_scheme   the given strain of the inclusion: a round inclusion in the
               matrix, lengthened along the field x and shortened across it;
               the arrows are the forces the matrix feels from the inclusion
  fig_map      stress added by the strain in the xz plane through the
               inclusion centre: MD next to the continuum solution
  fig_decay    the same stresses against the distance from the inclusion
               surface along x, z and the 45-degree direction
  fig_creep    the shear stress needed for a 25 % creep-rate increase against
               the activation volume, with the stress computed here

Stresses are in MPa, tension positive. Inputs: the JSON records written by
embedded_inclusion_field.py (MD) and embedded_inclusion_continuum.py.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Rectangle

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "docs" / "paper"
REPORTS = ROOT / "docs" / "reports"
TEAL = "#007F82"
ORANGE = "#BC5D22"
BLUE = "#246CA5"
INK = "#262B30"
MATRIX = "#E3E7EA"
INCLUSION = "#E5B090"


class Text:
    def __init__(self, language: str):
        self.ru = language == "ru"

    def __call__(self, en: str, ru: str) -> str:
        return ru if self.ru else en

    def num(self, s: str) -> str:
        return s.replace(".", ",") if self.ru else s

    def name(self, stem: str) -> str:
        return stem + ("_ru" if self.ru else "")


def setup_style() -> None:
    matplotlib.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.linewidth": 0.8,
        "axes.edgecolor": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
        "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 300,
    })


def save(fig: plt.Figure, stem: str) -> None:
    for ext in ("pdf", "png"):
        fig.savefig(PAPER / f"{stem}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print("written", stem)


def arrow(ax, xy, dxy, color=ORANGE, lw=1.6):
    ax.add_patch(FancyArrowPatch(xy, (xy[0] + dxy[0], xy[1] + dxy[1]), arrowstyle="-|>",
                                 mutation_scale=11, lw=lw, color=color, zorder=5))


def figure_scheme(t: Text) -> None:
    """Round inclusion in the matrix and the shape it is given (strain exaggerated)."""
    fig, ax = plt.subplots(figsize=(3.6, 3.0))
    draw_scheme(ax, t)
    save(fig, t.name("fig_scheme"))


def draw_scheme(ax, t: Text) -> None:
    ax.add_patch(Rectangle((-2.0, -1.6), 4.0, 3.2, fc=MATRIX, ec=INK, lw=0.8))
    ax.add_patch(Circle((0, 0), 0.75, fc="white", ec=INK, lw=0.9, ls=(0, (3, 2)), zorder=2))
    # lengthened along x by e, shortened along z by e/2 (here e = 0.30 for visibility)
    e = 0.30
    ax.add_patch(Ellipse((0, 0), 2 * 0.75 * (1 + e), 2 * 0.75 * (1 - e / 2),
                         fc=INCLUSION, ec=INK, lw=1.0, zorder=3))
    ax.text(0, 0, "Al$_{13}$Fe$_4$", ha="center", va="center", fontsize=9, zorder=6)
    for s in (1, -1):
        arrow(ax, (0, s * 1.25), (0, -s * 0.38))               # squeezed from top and bottom
        arrow(ax, (s * 1.02, 0), (s * 0.42, 0))                 # pushed out along x
    ax.text(1.40, 1.30, t("Al matrix", "матрица Al"), ha="center", va="center", fontsize=8)
    ax.text(0, -1.45, t("dashed: before; filled: given strain (exaggerated)",
                        "штрих: до деформации; заливка: заданная (увеличено)"),
            ha="center", va="center", fontsize=6.5, color=INK)
    # axes and field direction
    arrow(ax, (-1.85, -1.05), (0.45, 0), color=INK, lw=1.0)
    arrow(ax, (-1.85, -1.05), (0, 0.45), color=INK, lw=1.0)
    ax.text(-1.33, -1.05, "x", va="center", fontsize=8)
    ax.text(-1.85, -0.53, "z", ha="center", fontsize=8)
    arrow(ax, (-1.85, 1.30), (0.6, 0), color=BLUE, lw=1.4)
    ax.text(-1.2, 1.30, "H", color=BLUE, va="center", fontsize=9, fontweight="bold")
    ax.set_xlim(-2.05, 2.05)
    ax.set_ylim(-1.65, 1.65)
    ax.set_aspect("equal")
    ax.axis("off")


IRON = "#A43B26"
MATRIX_ATOM = "#CDD2D6"


def render_section(data_path: Path, meta: dict, half_slab: float = 5.0):
    """Ray-trace the atoms of a central slab |y - y_c| < half_slab, viewed along +y."""
    from matplotlib import colors as mcolors
    from ovito.io import import_file
    from ovito.vis import TachyonRenderer, Viewport
    from PySide6.QtGui import QImage

    pipe = import_file(str(data_path), atom_style="atomic")
    pipe.source.data.cell_.pbc = (True, True, True)
    box = np.asarray(pipe.compute().cell)[:3, :3].diagonal()
    n_al = meta["N_AL"]
    yc = box[1] / 2

    def appearance(frame, data):
        pos = np.asarray(data.particles.positions)
        ids = np.asarray(data.particles["Particle Identifier"])
        types = np.asarray(data.particles["Particle Type"])
        col = np.tile(mcolors.to_rgb(MATRIX_ATOM), (len(pos), 1))
        col[ids > n_al] = mcolors.to_rgb(INCLUSION)
        col[types == 2] = mcolors.to_rgb(IRON)
        data.particles_.create_property("Color", data=col)
        data.particles_.create_property("Radius", data=np.where(types == 2, 0.9, 0.72))
        data.cell.vis.enabled = False
        data.particles_.delete_elements(np.abs(pos[:, 1] - yc) > half_slab)

    pipe.modifiers.append(appearance)
    pipe.add_to_scene()
    try:
        vp = Viewport(type=Viewport.Type.Ortho)
        vp.camera_dir = (0, 1, 0)
        vp.camera_up = (0, 0, 1)
        side = float(max(box[0], box[2]))
        vp.camera_pos = (box[0] / 2, -400.0, box[2] / 2)
        vp.fov = side / 2
        img = vp.render_image(size=(1800, 1800), background=(1, 1, 1),
                              renderer=TachyonRenderer(antialiasing=True, ambient_occlusion=False))
        img = img.convertToFormat(QImage.Format.Format_RGBA8888)
        rgba = np.asarray(img.bits()).reshape(img.height(), img.bytesPerLine())
        rgb = rgba[:, : img.width() * 4].reshape(img.height(), img.width(), 4).copy()
    finally:
        pipe.remove_from_scene()
    extent = [box[0] / 2 - side / 2, box[0] / 2 + side / 2, box[2] / 2 - side / 2, box[2] / 2 + side / 2]
    return rgb, np.asarray(extent) / 10.0, box


def figure_model(t: Text, data_path: Path, meta_path: Path) -> None:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    rgb, ext, box = render_section(data_path, meta)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.3), gridspec_kw={"width_ratios": [1.05, 1]})
    a1.imshow(rgb, extent=ext, interpolation="lanczos")
    a1.set_xlabel(t("x (field direction), nm", "x (направление поля), нм"))
    a1.set_ylabel("z, nm")
    a1.set_title(t("(a) section of the cell through the inclusion",
                   "(а) сечение ячейки через включение"), fontsize=9)
    a1.text(0.02, 0.98, t("Al matrix", "матрица Al"), transform=a1.transAxes, va="top", fontsize=7.5)
    a1.text(0.5, 0.5, "Al$_{13}$Fe$_4$", transform=a1.transAxes, ha="center", va="center", fontsize=8)
    lab = t("cell %.1f × %.1f × %.1f nm, %d atoms", "ячейка %.1f × %.1f × %.1f нм, %d атомов")
    a1.text(0.5, -0.30, t.num(lab % (box[0] / 10, box[1] / 10, box[2] / 10, meta["n_atoms"])).replace(",", " ", 0),
            transform=a1.transAxes, ha="center", fontsize=7)
    plt.sca(a2)
    draw_scheme(a2, t)
    a2.set_title(t("(b) the given strain of the inclusion", "(б) заданная деформация включения"), fontsize=9)
    fig.tight_layout()
    save(fig, t.name("fig_cell"))


def load(path: Path | None):
    return json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else None


def figure_decay(t: Text, cont: dict, md: dict | None, radius: float) -> None:
    """Normal and equivalent stresses against the distance from the surface."""
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.6), sharey=False)
    panels = [("pole", t("(a) along the field, x", "(а) вдоль поля, x")),
              ("equator", t("(b) across the field", "(б) поперёк поля")),
              ("diagonal", t("(c) at 45° to the field", "(в) под 45° к полю"))]
    for ax, (key, title) in zip(axs, panels):
        L = cont["lines"][key]
        d = np.array(L["d_A"])
        far = L["isolated_far"]
        rr = np.array(far["r_over_R"])
        dd = (rr - 1) * radius
        qty = [("srr", t("normal, along radius", "нормальное, по радиусу"), ORANGE),
               ("von_mises", t("equivalent (von Mises)", "эквивалентное (Мизес)"), INK)]
        if key == "diagonal":
            qty = [("s_axial_shear", t(r"glide stress $\sigma_{xz}$", r"касательное $\sigma_{xz}$"), TEAL),
                   ("von_mises", t("equivalent (von Mises)", "эквивалентное (Мизес)"), INK)]
        for k, lab, col in qty:
            ax.plot(dd, far[k], color=col, lw=1.1, label=lab + t(", continuum", ", континуум"))
            ax.plot(d, L["periodic"][k], color=col, lw=0.8, ls=":")
            if md:
                P = md["profiles"][key]
                ax.errorbar([q["d_A"] for q in P], [q[k] for q in P],
                            yerr=[q[k + "_sem"] for q in P], fmt="o", ms=2.6, color=col,
                            elinewidth=0.6, capsize=0, label=lab + t(", MD", ", МД"))
        ax.axhline(0, color=INK, lw=0.5)
        ax.set_xlim(0, 75)
        ax.set_title(title, fontsize=9)
        ax.set_xlabel(t("distance from the inclusion surface, Å", "расстояние от поверхности включения, Å"))
    axs[0].set_ylabel(t("added stress, MPa", "дополнительное напряжение, МПа"))
    axs[0].legend(fontsize=6.3, frameon=False, loc="lower right")
    axs[2].legend(fontsize=6.3, frameon=False, loc="upper right")
    fig.tight_layout()
    save(fig, t.name("fig_decay"))


def figure_creep(t: Text, creep: dict) -> None:
    """Shear stress needed for +25 % creep rate against the activation volume."""
    v = np.array(creep["vstar_b3"])
    fig, ax = plt.subplots(figsize=(3.6, 2.8))
    ax.plot(v, creep["required_amplitude_MPa"], color=INK, lw=1.4,
            label=t("needed for +25 %", "нужно для +25 %"))
    eff = [np.nan if e is None else e for e in creep["effective_amplitude_MPa"]["grains"]]
    ax.plot(v, eff, color=ORANGE, lw=1.4, ls="--",
            label=t("given by the strained inclusion", "даёт деформированное включение"))
    vt = creep["vstar_for_target_b3"]["grains"]
    ax.axvline(70, color=BLUE, lw=0.8, ls=":")
    ax.text(72, 75, t("70 $b^3$\n(Al–Mg–Si)", "70 $b^3$\n(Al–Mg–Si)"), color=BLUE, fontsize=7)
    ax.plot([vt], [np.interp(vt, v, creep["required_amplitude_MPa"])], "o", color=ORANGE, ms=4)
    ax.set_xlabel(t("activation volume $V^*$, $b^3$", "активационный объём $V^*$, $b^3$"))
    ax.set_ylabel(t("shear stress amplitude, MPa", "амплитуда касательного напряжения, МПа"))
    ax.set_xlim(10, 145)
    ax.set_ylim(0, 100)
    ax.legend(fontsize=7, frameon=False, loc="upper right")
    fig.tight_layout()
    save(fig, t.name("fig_creep"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--language", choices=("en", "ru"), default="en")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--continuum", type=Path, default=REPORTS / "embedded_continuum.json")
    ap.add_argument("--md", type=Path, default=REPORTS / "embedded_field.json")
    ap.add_argument("--creep", type=Path, default=REPORTS / "embedded_creep.json")
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--cell", type=Path, default=ROOT / "structures/embedded_inclusion/sphere_R25/data.sphere_R25")
    ap.add_argument("--meta", type=Path, default=ROOT / "structures/embedded_inclusion/sphere_R25/sphere_R25_metadata.json")
    a = ap.parse_args()
    setup_style()
    t = Text(a.language)
    cont, md, creep = load(a.continuum), load(a.md), load(a.creep)
    todo = {"scheme": lambda: figure_scheme(t),
            "model": lambda: figure_model(t, a.cell, a.meta),
            "decay": lambda: figure_decay(t, cont, md, a.radius),
            "creep": lambda: figure_creep(t, creep)}
    for key, fn in todo.items():
        if a.only is None or key in a.only:
            fn()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
