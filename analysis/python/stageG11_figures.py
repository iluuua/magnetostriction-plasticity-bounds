#!/usr/bin/env python3
"""Stage G11: the three manuscript figures, rebuilt from stageG10 data.

What changed relative to the previous set.

Fig. 1  The lower panel no longer plots vM(field) - vM(control). That is a
        difference of two invariants, it can be and was negative, and the text
        described it as the invariant of the difference tensor. It now plots
        the two non-negative quantities the argument actually uses, RSS_max(r)
        and sigma_vM[Delta sigma(r)], on the same bins as the upper panel, with
        the noise floor measured beyond 60 A shown as a band. The
        apex-straddling region, where distance from the interface is not
        well defined, is shaded and excluded from the quoted peak.

Fig. 3  Both curves are now plotted against the same coordinate, distance from
        the nearest inclusion surface. Previously the MD ridge was plotted
        against distance from the flat interface and the Eshelby sphere against
        distance from the sphere centre, which made the two curves
        incomparable. The solute-pinning threshold is 75 MPa, not the stale 65.

Every figure is emitted twice, with English and Russian labels.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "docs" / "reports"
PAPER = REPO / "docs" / "paper"
PRE, HOLD = 10000, 30000
RUNGS = [45, 55, 65, 75]
ETA_RETAINED = 0.30   # stageG12: fraction of the imposed mode the ridge keeps
A_RIDGE = 35.0          # ridge half-width, A
RIDGE_H = 20.0          # ridge height above the flat interface, A
EPS_INFLATED = 1.94e-3

L = {
    "en": dict(
        f1title="Stress decay from the Al$_{13}$Fe$_4$/Al interface\n"
                "(clean cell: no dislocations, no solutes, energy-minimised)",
        f1y1="von Mises stress (MPa)", f1y2="field-induced increment (MPa)",
        f1x="distance from the flat interface, $r$ (Å)",
        ctl="control ($\\varepsilon^*=0$)", fld="field ($\\varepsilon^*=1.94\\times10^{-3}$)",
        rss="RSS$_{\\max}$ of $\\Delta\\sigma_{ij}$", vmd="$\\sigma_{vM}[\\Delta\\sigma_{ij}]$",
        noise="noise floor measured beyond 60 Å",
        apex="bins straddling the ridge flank are excluded from the plot\n"
             "(diagnostic range 19-%.0f MPa; not a field measurement)",
        f2title="Dislocation trajectories in Al–Mg–Si under a constant-stress staircase",
        f2x="time (ps)", f2y="displacement along the glide direction (Å)",
        probe="probe line (lower plane)", partner="reaction partner (upper plane)",
        noload="no load", mpa="MPa",
        f3title="Field-induced driving stress against the thresholds it must overcome",
        f3x="distance from the nearest inclusion surface, $d$ (Å)",
        f3y="field-induced RSS$_{\\max}$ (MPa)",
        md="MD ridge, $\\varepsilon^*=1.94\\times10^{-3}$",
        esh="3D Eshelby sphere, same $\\varepsilon^*$",
        resc="rescaled to $\\lambda_s=100$ ppm on the retained\namplitude $\\eta\\varepsilon^*$, $\\eta=0.30$",
        flank="excluded diagnostic flank bins (19-80 MPa),\nnot a field measurement",
        thr=["no depinning through 75 MPa - lower bound",
             "interface nucleation 195 MPa"],
    ),
    "ru": dict(
        f1title="Затухание напряжения от границы Al$_{13}$Fe$_4$/Al\n"
                "(чистая ячейка: без дислокаций и примесей, минимизация)",
        f1y1="напряжение фон Мизеса, МПа",
        f1y2="приращение от поля, МПа",
        f1x="расстояние от плоской границы, $r$ (Å)",
        ctl="контроль ($\\varepsilon^*=0$)",
        fld="поле ($\\varepsilon^*=1{,}94\\times10^{-3}$)",
        rss="RSS$_{\\max}$ тензора $\\Delta\\sigma_{ij}$",
        vmd="$\\sigma_{vM}[\\Delta\\sigma_{ij}]$",
        noise="шумовой уровень за 60 Å",
        apex="бины, седлающие фланг гребня, исключены\n"
             "(диагностический разброс 19-%.0f МПа, не измерение поля)",
        f2title="Траектории дислокаций в Al–Mg–Si при ступенчатом нагружении",
        f2x="время, пс",
        f2y="смещение вдоль направления скольжения, Å",
        probe="дислокация-зонд (нижняя плоскость)",
        partner="партнёр (верхняя плоскость)",
        noload="без нагрузки", mpa="МПа",
        f3title="Вызванное полем напряжение и пороги, которые оно должно преодолеть",
        f3x="расстояние от ближайшей поверхности включения, $d$ (Å)",
        f3y="вызванное полем RSS$_{\\max}$, МПа",
        md="MD, гребень, $\\varepsilon^*=1{,}94\\times10^{-3}$",
        esh="3D-сфера Эшелби, та же $\\varepsilon^*$",
        resc="пересчёт на $\\lambda_s=100$ ppm по удержанной\nамплитуде $\\eta\\varepsilon^*$, $\\eta=0{,}30$",
        flank="исключённые диагностические бины фланга\n(19-80 МПа), не измерение поля",
        thr=["открепления не было до 75 МПа - нижняя граница",
             "движение диполя 77–86 МПа",
             "зарождение на границе 195 МПа"],
    ),
}


def prof():
    return json.loads(io.open(REPORTS / "stageG10_field_profile.json", encoding="utf-8").read())


def fig_sigma(lang: str) -> None:
    t = L[lang]
    d = prof()
    rows = d["profile"]
    r = np.array([x["r_A"] for x in rows])
    ok = np.array([x["above_apex"] for x in rows])
    vc = np.array([x["vm_control_MPa"] for x in rows])
    vf = np.array([x["vm_field_MPa"] for x in rows])
    rss = np.array([x["max_RSS_MPa"] for x in rows])
    vmd = np.array([x["vm_of_difference_MPa"] for x in rows])
    nf = d["noise_floor_beyond_60A"]
    band = nf["mean_max_RSS_MPa"] + nf["std_MPa"]
    apex_r = d["ridge_apex_A"] - d["z_interface_A"]

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 7.0), sharex=True)
    for ax in (a1, a2):
        ax.grid(alpha=0.3)

    a1.plot(r[ok], vc[ok], "o-", ms=3.5, lw=1.3, color="#3b6db3", label=t["ctl"])
    a1.plot(r[ok], vf[ok], "s-", ms=3.5, lw=1.3, color="#b23b3b", label=t["fld"])
    a1.set_ylabel(t["f1y1"])
    a1.set_title(t["f1title"], fontsize=11)
    a1.legend(fontsize=9)

    a2.plot(r[ok], rss[ok], "o-", ms=4, lw=1.5, color="#3b8b52", label=t["rss"])
    a2.plot(r[ok], vmd[ok], "^--", ms=4, lw=1.2, color="#7a4fa3", label=t["vmd"])
    a2.axhspan(0, band, color="0.75", alpha=0.45, label=t["noise"])
    a2.axhline(band, color="0.45", lw=0.8)
    a2.set_yscale("log")
    a2.set_ylim(0.02, 60)
    a2.set_ylabel(t["f1y2"])
    a2.set_xlabel(t["f1x"])
    a2.legend(fontsize=9, loc="upper right")
    a2.set_xlim(r[ok].min() - 3, r.max() + 3)
    flank_max = max(x["max_RSS_MPa"] for x in d["apex_straddling_bins_excluded"])
    a2.text(0.015, 0.035, t["apex"] % flank_max, transform=a2.transAxes,
            fontsize=8.2, color="#c07000", ha="left", va="bottom")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(PAPER / ("fig_sigma_profile_%s.%s" % (lang, ext)), dpi=150)
    plt.close(fig)
    print("fig_sigma_profile_%s written" % lang)


def fig_traj(lang: str) -> None:
    t = L[lang]
    p = REPORTS / "stageG6_vstar_relA_frames.csv"
    rows = list(csv.DictReader(io.open(p, encoding="utf-8")))
    tt, lo, up = [], [], []
    for x in rows:
        if not x.get("ux_lo") or not x.get("ux_up"):
            continue
        tt.append(float(x["step"]) * 1e-3)
        lo.append(float(x["ux_lo"]))
        up.append(float(x["ux_up"]))
    tt, lo, up = np.array(tt), np.array(lo), np.array(up)
    # zero at the onset of loading, not at t = 0: the pre-load excursion is the
    # line settling into its solute environment and is not part of the response
    i0 = int(np.argmax(tt >= PRE * 1e-3))
    lo, up = lo - lo[i0], up - up[i0]

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.plot(tt, lo, "o-", ms=3, lw=1.4, color="#b23b3b", label=t["probe"])
    ax.plot(tt, up, "s-", ms=3, lw=1.4, color="#3b6db3", label=t["partner"])
    ax.axhline(0.0, color="0.4", lw=0.8)
    ymin, ymax = ax.get_ylim()
    ax.set_ylim(ymin, ymax + 0.30 * (ymax - ymin))
    ytxt = ax.get_ylim()[1] - 0.07 * (ax.get_ylim()[1] - ymin)
    for k, tau in enumerate(RUNGS):
        x0 = (PRE + k * HOLD) * 1e-3
        ax.axvline(x0, color="gray", ls=":", lw=0.9)
        ax.text(x0 + 13, ytxt, "%d %s" % (tau, t["mpa"]),
                ha="center", va="top", fontsize=9, color="gray")
    ax.axvline(PRE * 1e-3, color="k", lw=0.9)
    ax.text(PRE * 1e-3 / 2, ytxt, t["noload"], ha="center", va="top",
            fontsize=8, color="gray", rotation=90)
    ax.set_xlabel(t["f2x"])
    ax.set_ylabel(t["f2y"])
    ax.set_title(t["f2title"], fontsize=11)
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(PAPER / ("fig_trajectories_%s.%s" % (lang, ext)), dpi=150)
    plt.close(fig)
    print("fig_trajectories_%s written" % lang)


def fig_rss(lang: str) -> None:
    t = L[lang]
    d = prof()
    rows = [x for x in d["profile"] if x["above_apex"]]
    # distance from the ridge crest, which is the nearest inclusion surface for
    # a bin lying above the apex
    dd = np.array([x["r_A"] for x in rows]) - RIDGE_H
    rss = np.array([x["max_RSS_MPa"] for x in rows])
    flank = [x["max_RSS_MPa"] for x in d["apex_straddling_bins_excluded"]]

    esh = json.loads(io.open(REPORTS / "stageG8_eshelby3d.json", encoding="utf-8").read())
    ed = np.array([(x["r_over_a"] - 1.0) * A_RIDGE for x in esh["exterior_decay_sphere"]])
    ev = np.array([x["max_RSS_MPa"] for x in esh["exterior_decay_sphere"]])

    scale = 1e-4 / (ETA_RETAINED * EPS_INFLATED)
    fig, ax = plt.subplots(figsize=(7.2, 4.9))
    ax.semilogy(dd, np.maximum(rss, 1e-3), "o-", ms=4.5, color="#3b8b52", label=t["md"])
    ax.semilogy(ed, ev, "s--", ms=5, color="#8b3b8b", label=t["esh"])
    ax.semilogy(dd, np.maximum(rss * scale, 1e-4), "o:", ms=3.5, color="#3b8b52",
                alpha=0.6, label=t["resc"])
    ax.errorbar([1.0], [max(flank)], yerr=[[max(flank) - min(flank)], [0.0]],
                fmt="D", ms=6, color="#c07000", capsize=4, label=t["flank"])
    for y, ytxt, lbl, col in zip((75, 86, 195), (0.52, 1.10, 1.28), t["thr"],
                                 ("#444444", "#777777", "#aa2222")):
        ax.axhline(y, ls="--", lw=1.1, color=col)
        ax.text(73, y * ytxt, lbl, fontsize=8, color=col, ha="right")
    ax.set_xlabel(t["f3x"])
    ax.set_ylabel(t["f3y"])
    ax.set_xlim(0, 75)
    ax.set_ylim(1e-3, 500)
    ax.set_title(t["f3title"], fontsize=11)
    ax.legend(fontsize=8.5, loc="lower left")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(PAPER / ("fig_rss_vs_thresholds_%s.%s" % (lang, ext)), dpi=150)
    plt.close(fig)
    print("fig_rss_vs_thresholds_%s written" % lang)


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["DejaVu Sans"]
    for lg in ("en", "ru"):
        fig_sigma(lg)
        fig_traj(lg)
        fig_rss(lg)
