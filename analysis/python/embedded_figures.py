#!/usr/bin/env python3
"""Figures for the embedded-inclusion calculation (sphere in an Al box).

    python analysis/python/embedded_figures.py                 # English set
    python analysis/python/embedded_figures.py --language ru   # Russian set
    python analysis/python/embedded_figures.py --only cell map

Figures, written to docs/paper as PDF and PNG (Russian copies end in _ru):
  fig_cell    (a) section of the cell through the inclusion (OVITO); (b) the
              given strain: round inclusion, lengthened along the field x and
              shortened across; arrows are the forces with which the inclusion
              acts on the aluminium, from the radial stress at the interface
  fig_map     added stress in the xz plane through the centre: von Mises and the
              slip-plane shear sigma_xz, MD (averaged about the field axis) next
              to the elastic solution for the same periodic cell
  fig_decay   added stress against distance from the surface along the field,
              across it and in the two shear lobes; MD, the same-cell elastic
              solution and the single sphere; and the far field of the single
              sphere in r/R
  fig_glide   sigma_xz averaged along a straight edge dislocation (line along y)
              on planes at height h above the inclusion, against x
  fig_creep   shear amplitude needed for a 25 % creep-rate increase against the
              activation volume, and the amplitude equivalent to the computed field

Inputs: docs/reports/embedded_field.json (MD), embedded_continuum.json,
embedded_creep.json, and the cell structure for fig_cell. Stresses in MPa,
tension positive.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Rectangle

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
PAPER = ROOT / "docs" / "paper"
REPORTS = ROOT / "docs" / "reports"
TEAL = "#007F82"
ORANGE = "#BC5D22"
BLUE = "#246CA5"
INK = "#262B30"
GREY = "#8A939B"
MATRIX = "#E3E7EA"
INCLUSION = "#E5B090"
IRON = "#A43B26"
MATRIX_ATOM = "#CDD2D6"
R_MICRON = 2.5          # radius of a 5 um particle, for the upper distance scale
YIELD = (40.0, 60.0)    # sigma_0.2 of the alloy, Friha et al. 2024


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
        "font.family": "DejaVu Sans", "font.size": 8.5, "axes.linewidth": 0.8,
        "axes.edgecolor": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
        "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 300,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def save(fig: plt.Figure, stem: str) -> None:
    if stem.endswith("_ru"):                      # decimal comma on linear axes
        from matplotlib.ticker import FuncFormatter, ScalarFormatter
        comma = FuncFormatter(lambda v, _: ("%g" % v).replace(".", ",").replace("-", "−"))
        for ax in fig.axes + [c for a_ in fig.axes for c in a_.child_axes]:
            for axis in (ax.xaxis, ax.yaxis):
                if isinstance(axis.get_major_formatter(), ScalarFormatter):
                    axis.set_major_formatter(comma)
    for ext in ("pdf", "png"):
        fig.savefig(PAPER / f"{stem}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print("written", stem)


def load(path: Path | None):
    return json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else None


def arrow(ax, xy, dxy, color=ORANGE, lw=1.5, scale=10):
    ax.add_patch(FancyArrowPatch(xy, (xy[0] + dxy[0], xy[1] + dxy[1]), arrowstyle="-|>",
                                 mutation_scale=scale, lw=lw, color=color, zorder=5))


# ------------------------------------------------------------------ fig_cell
def interface_traction(theta: np.ndarray) -> np.ndarray:
    """Radial force per area with which the inclusion acts on the matrix (MPa,
    outward positive) = -sigma_rr of the matrix at the interface, single sphere."""
    import embedded_inclusion_continuum as C
    e_s = C.transformation_strain(C.strain_given())
    n = np.stack([np.cos(theta), np.zeros_like(theta), np.sin(theta)], -1)
    sig = C.stress_from_strain(C.exterior_strain(1.0005 * n, np.zeros(3), 1.0, e_s)) / 1e6
    return -np.einsum("pi,pij,pj->p", n, sig, n)


def draw_scheme(ax, t: Text) -> None:
    ax.add_patch(Rectangle((-2.0, -1.6), 4.0, 3.2, fc=MATRIX, ec=INK, lw=0.8))
    r0, e = 0.72, 0.30                            # strain exaggerated for visibility
    ax.add_patch(Circle((0, 0), r0, fc="white", ec=INK, lw=0.9, ls=(0, (3, 2)), zorder=2))
    ax.add_patch(Ellipse((0, 0), 2 * r0 * (1 + e), 2 * r0 * (1 - e / 2), fc=INCLUSION, ec=INK,
                         lw=1.0, zorder=3))
    ax.text(0, 0, "Al$_{13}$Fe$_4$", ha="center", va="center", fontsize=9, zorder=6)
    th = np.radians(np.arange(0, 360, 30))
    f = interface_traction(th)
    k = 0.42 / np.abs(f).max()
    for a_, fv in zip(th, f):
        u = np.array([math.cos(a_), math.sin(a_)])
        base = u * np.array([r0 * (1 + e), r0 * (1 - e / 2)]) * 1.06
        if fv > 0:
            arrow(ax, tuple(base), tuple(u * fv * k))
        else:
            arrow(ax, tuple(base - u * fv * k), tuple(u * fv * k))
    fx, fz = interface_traction(np.array([0.0]))[0], interface_traction(np.array([math.pi / 2]))[0]
    ax.text(1.62, 0.18, t.num("%.0f" % fx) + t(" MPa", " МПа"), ha="center", fontsize=7, color=ORANGE)
    ax.text(0.10, 0.84, t.num("%.0f" % abs(fz)) + t(" MPa", " МПа"), ha="left", fontsize=7, color=ORANGE)
    ax.text(1.40, -1.18, t("Al matrix", "матрица Al"), ha="center", va="center", fontsize=8)
    ax.text(0, -1.45, t("dashed: before; filled: given strain (exaggerated)",
                        "штрих: до деформации; заливка: заданная (увеличено)"),
            ha="center", va="center", fontsize=6.3, color=INK)
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


def figure_cell(t: Text, data_path: Path, meta_path: Path) -> None:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    rgb, ext, box = render_section(data_path, meta)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.3), gridspec_kw={"width_ratios": [1.05, 1]})
    a1.imshow(rgb, extent=ext, interpolation="lanczos")
    for s in ("top", "right"):
        a1.spines[s].set_visible(True)
    a1.set_xlabel(t("x (field direction), nm", "x (направление поля), нм"))
    a1.set_ylabel(t("z, nm", "z, нм"))
    a1.set_title(t("(a) section of the cell through the inclusion",
                   "(а) сечение ячейки через включение"), fontsize=9)
    a1.text(0.03, 0.97, t("Al matrix", "матрица Al"), transform=a1.transAxes, va="top", fontsize=7.5,
            bbox=dict(fc="white", ec="none", pad=1.0))
    a1.text(0.5, 0.5, "Al$_{13}$Fe$_4$", transform=a1.transAxes, ha="center", va="center", fontsize=8,
            bbox=dict(fc="white", ec="none", alpha=0.8, pad=1.0))
    lab = t("cell %.1f × %.1f × %.1f nm, %s atoms", "ячейка %.1f × %.1f × %.1f нм, %s атомов")
    count = "{:,}".format(meta["n_atoms"]).replace(",", " ")
    a1.text(0.5, -0.27, t.num(lab % (box[0] / 10, box[1] / 10, box[2] / 10, "§")).replace("§", count),
            transform=a1.transAxes, ha="center", fontsize=7)
    draw_scheme(a2, t)
    a2.set_title(t("(b) the given strain of the inclusion", "(б) заданная деформация включения"), fontsize=9)
    fig.tight_layout()
    save(fig, t.name("fig_cell"))


# ------------------------------------------------------------------- fig_map
def md_xz_maps(md: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Reconstruct the xz-plane maps from the axisymmetric (|s|, rho) average."""
    A = md["axisym"]
    s = np.array(A["s_centres_A"])
    rho = np.array(A["rho_centres_A"])
    vm = np.array([[np.nan if v is None else v for v in row] for row in A["von_mises"]])
    sh = np.array([[np.nan if v is None else v for v in row] for row in A["s_axial_shear"]])
    # the bins next to the field axis (rho < 2 A) hold few atoms; an empty one takes
    # the value of the next ring outward (cells inside the inclusion stay empty)
    for arr in (vm, sh):
        gap = np.isnan(arr[:, 0]) & ~np.isnan(arr[:, 1])
        arr[gap, 0] = arr[gap, 1]
    x = np.concatenate([-s[::-1], s])
    z = np.concatenate([-rho[::-1], rho])
    VM = np.block([[vm[::-1, ::-1], vm[::-1, :]], [vm[:, ::-1], vm]])
    SH = np.block([[sh[::-1, ::-1], -sh[::-1, :]], [-sh[:, ::-1], sh]])
    return x, z, VM, SH


def figure_map(t: Text, md: dict, cont: dict, radius: float) -> None:
    sec = cont["section_xz"]
    cx, cz = np.array(sec["x_A"]), np.array(sec["z_A"])
    order_x, order_z = np.argsort(cx), np.argsort(cz)
    cvm = np.array(sec["von_mises"])[np.ix_(order_x, order_z)]
    csh = np.array(sec["sxz"])[np.ix_(order_x, order_z)]
    cx, cz = cx[order_x], cz[order_z]
    X2, Z2 = np.meshgrid(cx, cz, indexing="ij")
    inside = X2 ** 2 + Z2 ** 2 < (radius + 2.5) ** 2      # voxel-smoothed interface
    cvm[inside] = np.nan
    csh[inside] = np.nan
    fig, axs = plt.subplots(2, 2, figsize=(6.4, 6.0), sharex=True, sharey=True)
    vmax, smax = 150.0, 40.0
    panels = []
    if md:
        mx, mz, mvm, msh = md_xz_maps(md)
        panels = [(axs[0, 0], mx, mz, mvm, "magma_r", 0, vmax),
                  (axs[1, 0], mx, mz, msh, "RdBu_r", -smax, smax)]
    panels += [(axs[0, 1], cx, cz, cvm, "magma_r", 0, vmax), (axs[1, 1], cx, cz, csh, "RdBu_r", -smax, smax)]
    ims = {}
    for ax, xx, zz, data, cmap, lo, hi in panels:
        im = ax.pcolormesh(xx / 10, zz / 10, np.ma.masked_invalid(data).T, cmap=cmap, vmin=lo, vmax=hi,
                           shading="nearest", rasterized=True)
        # pixels within 2.5 A of the surface are masked (voxel-smoothed interface);
        # a smooth disc hides the pixel edge of the mask, the outline marks r = R
        ax.add_patch(Circle((0, 0), (radius + 3.2) / 10, fc="white", ec="none", zorder=3))
        ax.add_patch(Circle((0, 0), radius / 10, fc="white", ec=INK, lw=0.6, zorder=4))
        ax.set_aspect("equal")
        lim = min(np.abs(xx).max(), np.abs(zz).max()) / 10
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ims[cmap] = im
    for ax in axs[1, :]:
        ax.set_xlabel(t("x (field direction), nm", "x (направление поля), нм"))
    for ax in axs[:, 0]:
        ax.set_ylabel(t("z, nm", "z, нм"))
    axs[0, 0].set_title(t("atomistic", "атомистический расчёт"), fontsize=9)
    axs[0, 1].set_title(t("elastic, same cell", "теория упругости, та же ячейка"), fontsize=9)
    for ax, lab in zip(axs.ravel(), ("(a)", "(b)", "(c)", "(d)") if not t.ru else ("(а)", "(б)", "(в)", "(г)")):
        ax.text(0.03, 0.97, lab, transform=ax.transAxes, va="top", fontsize=8.5,
                bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.8))
    for ang in (25, 67):
        for sx in (1, -1):
            for sz in (1, -1):
                a_ = math.radians(ang)
                axs[1, 0].plot([sx * radius / 10 * math.cos(a_), sx * 6 * math.cos(a_)],
                               [sz * radius / 10 * math.sin(a_), sz * 6 * math.sin(a_)],
                               color=INK, lw=0.4, ls=":")
    fig.tight_layout(rect=(0, 0, 0.88, 1))
    c1 = fig.add_axes([0.89, 0.55, 0.018, 0.37])
    fig.colorbar(ims["magma_r"], cax=c1).set_label(t("von Mises, MPa", "по Мизесу, МПа"))
    c2 = fig.add_axes([0.89, 0.09, 0.018, 0.37])
    fig.colorbar(ims["RdBu_r"], cax=c2).set_label(r"$\tau=\sigma_{xz}$, " + t("MPa", "МПа"))
    save(fig, t.name("fig_map"))


# ----------------------------------------------------------------- fig_decay
def md_rows(md: dict, name: str) -> list[dict]:
    if md is None:
        return []
    src = md.get("linear") or md["profiles"]
    return src.get(name, [])


def figure_decay(t: Text, md: dict | None, cont: dict, radius: float) -> None:
    fig, axs = plt.subplots(1, 4, figsize=(9.6, 2.9), gridspec_kw={"width_ratios": [1, 1, 1, 1.05]})
    panels = [
        ("pole", t("(a) along the field", "(а) вдоль поля"),
         [("srr", t("normal along radius", "нормальное по радиусу"), ORANGE),
          ("von_mises", t("von Mises", "по Мизесу"), INK)]),
        ("equator", t("(b) across the field", "(б) поперёк поля"),
         [("srr", t("normal along radius", "нормальное по радиусу"), ORANGE),
          ("stt", t("normal along x", "нормальное вдоль x"), BLUE),
          ("von_mises", t("von Mises", "по Мизесу"), INK)]),
        ("lobes", t("(c) shear on the slip plane", "(в) касательное в плоскости скольжения"),
         [("lobe25", "25°", TEAL), ("lobe67", "67°", ORANGE)]),
    ]
    dmax = 38.0
    if md:
        from embedded_gates import agreement
        layer = agreement(md, cont)["interface_layer_A"]
    else:
        layer = 0.0
    for ax, (name, title, qty) in zip(axs[:3], panels):
        for key, lab, col in qty:
            dname, k = (key, "s_axial_shear") if name == "lobes" else (name, key)
            I = cont["isolated"][dname]
            P = cont["periodic"][dname]
            ax.plot([q["d_A"] for q in P], [q[k] for q in P], color=col, lw=1.2, label=lab)
            ax.plot(I["d_A"], I[k], color=col, lw=0.9, ls="--")
            rows = md_rows(md, dname)
            if rows:
                ax.errorbar([q["d_A"] for q in rows], [q[k] for q in rows],
                            yerr=[q[k + "_sem"] for q in rows], fmt="o", ms=2.4, color=col,
                            mfc="white", elinewidth=0.6, capsize=0)
        if name != "lobes":
            ax.axhspan(*YIELD, color=GREY, alpha=0.18, lw=0)
            ax.axhspan(-YIELD[1], -YIELD[0], color=GREY, alpha=0.18, lw=0)
        if layer > 0:
            ax.axvspan(0, layer, color=GREY, alpha=0.10, hatch="////", lw=0)
        ax.axhline(0, color=INK, lw=0.5)
        ax.set_xlim(0, dmax)
        ax.set_title(title, fontsize=8.5)
        ax.set_xlabel(t("distance from surface $d$, Å", "расстояние от поверхности $d$, Å"))
        top = ax.secondary_xaxis("top", functions=(lambda d: d / radius * R_MICRON,
                                                   lambda u: u * radius / R_MICRON))
        top.set_xlabel(t("for $R$ = 2.5 µm, µm", "при $R$ = 2,5 мкм, мкм"), fontsize=7)
        top.tick_params(labelsize=7)
        ax.legend(fontsize=6.3, frameon=False, loc="center right" if name == "pole" else "best")
    axs[0].set_ylabel(t("added stress, MPa", "дополнительное напряжение, МПа"))
    # (d) far field of the single sphere, log-log in r/R
    ax = axs[3]
    for dname, k, lab, col in (("pole", "srr", t("along the field", "вдоль поля"), ORANGE),
                               ("equator", "srr", t("across the field", "поперёк поля"), BLUE),
                               ("lobe25", "s_axial_shear", t("shear, 25°", "касательное, 25°"), TEAL)):
        I = cont["isolated"][dname]
        r = 1 + np.array(I["d_A"]) / radius
        ax.loglog(r, np.abs(I[k]), color=col, lw=1.1, label=lab)
    rr = np.array([2.0, 8.0])
    ax.loglog(rr, 60 * (rr / 2.0) ** -3, color=GREY, lw=0.8, ls=":")
    ax.text(4.2, 60 * (4.2 / 2) ** -3 * 1.5, r"$\propto r^{-3}$", fontsize=7, color=GREY)
    ax.axhspan(*YIELD, color=GREY, alpha=0.18, lw=0)
    ax.set_xlim(1, 10)
    ax.set_ylim(0.1, 300)
    from matplotlib.ticker import FixedLocator, FixedFormatter, NullFormatter
    ax.xaxis.set_major_locator(FixedLocator([1, 2, 5, 10]))
    ax.xaxis.set_major_formatter(FixedFormatter(["1", "2", "5", "10"]))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel(t("$r/R$ (single sphere)", "$r/R$ (одиночная сфера)"))
    ax.set_ylabel(t("magnitude, MPa", "модуль напряжения, МПа"))
    ax.set_title(t("(d) far field", "(г) дальнее поле"), fontsize=8.5)
    ax.legend(fontsize=6.3, frameon=False, loc="lower left")
    fig.tight_layout()
    save(fig, t.name("fig_decay"))


# ----------------------------------------------------------------- fig_glide
def figure_glide(t: Text, md: dict | None, cont: dict) -> None:
    fig, ax = plt.subplots(figsize=(4.2, 2.9))
    cols = {"5": TEAL, "10": ORANGE, "20": BLUE}
    for h, col in cols.items():
        P = cont["periodic_glide_planes"][h]
        x = np.array(P["x_A"]) / 10
        y = np.array([np.nan if v is None else v for v in P["line_average_MPa"]])
        ax.plot(x, y, color=col, lw=1.1, label=t("$h$ = %s Å" % h, "$h$ = %s Å" % h))
        if md and h in md["glide_planes"]:
            G = md["glide_planes"][h]
            ym = np.array([np.nan if v is None else v for v in G["line_average_MPa"]])
            ax.plot(np.array(G["x_A"]) / 10, ym, "o", ms=2.2, color=col, mfc="white")
    ax.axhline(0, color=INK, lw=0.5)
    ax.axvspan(-2.5, 2.5, color=INCLUSION, alpha=0.25, lw=0)
    ax.set_xlabel(t("position of the dislocation $x$, nm", "положение дислокации $x$, нм"))
    ax.set_ylabel(t(r"line-averaged $\tau$, MPa", r"среднее по линии $\tau$, МПа"))
    sec = ax.secondary_yaxis("right", functions=(lambda s: s * 2.864e-10 * 1e6 * 1e3,
                                                 lambda f: f / (2.864e-10 * 1e6 * 1e3)))
    sec.set_ylabel(t(r"force $\tau b$, mN/m", r"сила $\tau b$, мН/м"))
    ax.legend(fontsize=7, frameon=False, loc="upper right")
    fig.tight_layout()
    save(fig, t.name("fig_glide"))


# ----------------------------------------------------------------- fig_creep
def figure_creep(t: Text, creep: dict) -> None:
    v = np.array(creep["vstar_b3"])
    fig, ax = plt.subplots(figsize=(3.8, 2.9))
    ax.plot(v, creep["required_amplitude_MPa"], color=INK, lw=1.4,
            label=t("needed for +25 %", "нужно для +25 %"))
    eff = [np.nan if e is None else e for e in creep["effective_amplitude_MPa"]["grains"]]
    ax.plot(v, eff, color=ORANGE, lw=1.4, ls="--",
            label=t("from the computed field", "даёт рассчитанное поле"))
    vt = creep["vstar_for_target_b3"]["grains"]
    ax.axvline(70, color=BLUE, lw=0.8, ls=":")
    ax.text(73, 4, "70 $b^3$\nAl–Mg–Si", color=BLUE, fontsize=7)
    ax.plot([vt], [np.interp(vt, v, creep["required_amplitude_MPa"])], "o", color=ORANGE, ms=4)
    ax.annotate(t.num("%.0f $b^3$" % vt), (vt, np.interp(vt, v, creep["required_amplitude_MPa"])),
                xytext=(vt + 12, 70), fontsize=7, arrowprops=dict(arrowstyle="-", lw=0.5, color=INK))
    ax.set_xlabel(t("activation volume $V^*$, $b^3$", "активационный объём $V^*$, $b^3$"))
    ax.set_ylabel(t("shear amplitude, MPa", "амплитуда $\\tau$, МПа"))
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
    todo = {"cell": lambda: figure_cell(t, a.cell, a.meta),
            "map": lambda: figure_map(t, md, cont, a.radius),
            "decay": lambda: figure_decay(t, md, cont, a.radius),
            "glide": lambda: figure_glide(t, md, cont),
            "creep": lambda: figure_creep(t, creep)}
    for key, fn in todo.items():
        if a.only is None or key in a.only:
            fn()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
