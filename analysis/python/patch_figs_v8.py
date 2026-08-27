#!/usr/bin/env python3
"""Patch stageG11_figures.py: retire "field-induced" from every label, add the
physical 100 ppm Eshelby curve and the 75 +- 22 MPa pinning band to Fig. 3."""
import io
import re

P = "analysis/python/stageG11_figures.py"
t = io.open(P, encoding="utf-8").read()

rep = [
    # ---- English labels
    ('f1y2="field-induced increment (MPa)"',
     'f1y2="affine-surrogate stress difference (MPa)"'),
    ('ctl="control ($\\\\varepsilon^*=0$)", fld="field ($\\\\varepsilon^*=1.94\\\\times10^{-3}$)"',
     'ctl="control ($\\\\lambda_s=0$)",\n'
     '        fld="affine-perturbed ($\\\\lambda_{\\\\mathrm{nom}}=1.94\\\\times10^{-3}$)"'),
    ('f3title="Field-induced driving stress against the thresholds it must overcome"',
     'f3title="Affine-surrogate and maintained-eigenstrain stress bounds"'),
    ('f3y="field-induced RSS$_{\\\\max}$ (MPa)"',
     'f3y="RSS$_{\\\\max}$ of the stress difference (MPa)"'),
    ('md="MD ridge, relaxed response to the same\\ninitial affine perturbation"',
     'md="MD ridge, relaxed response at $\\\\lambda_{\\\\mathrm{nom}}$\\n(diagnostic, inflated amplitude)"'),
    ('esh="3D Eshelby sphere, maintained $\\\\varepsilon^*=1.94\\\\times10^{-3}$"',
     'esh="3D Eshelby sphere, maintained $\\\\lambda_{\\\\mathrm{nom}}$\\n(diagnostic, inflated amplitude)"'),
    ('resc="rescaled to $\\\\lambda_s=100$ ppm on the retained\\namplitude $\\\\eta\\\\varepsilon^*$, $\\\\eta=0.30$"',
     'resc="Eshelby sphere at $\\\\lambda_s=100$ ppm\\n(physical: peak 2.4 MPa)"'),
    ('thr=["no depinning through 75 MPa - lower bound"',
     'thr=["no depinning through 75 MPa ($\\\\pm$22, dipole)"'),
    # ---- Russian labels
    ('f1y2="приращение от поля, МПа"',
     'f1y2="приращение после аффинного возмущения, МПа"'),
    ('ctl="контроль ($\\\\varepsilon^*=0$)"', 'ctl="контроль ($\\\\lambda_s=0$)"'),
    ('fld="поле ($\\\\varepsilon^*=1{,}94\\\\times10^{-3}$)"',
     'fld="аффинное возмущение\\n($\\\\lambda_{\\\\mathrm{nom}}=1{,}94\\\\times10^{-3}$)"'),
    ('f3title="Вызванное полем напряжение и пороги, которые оно должно преодолеть"',
     'f3title="Оценки напряжения: аффинный суррогат и поддерживаемая деформация"'),
    ('f3y="вызванное полем RSS$_{\\\\max}$, МПа"',
     'f3y="RSS$_{\\\\max}$ разностного тензора, МПа"'),
    ('md="MD, гребень: релаксированный отклик\\nна то же начальное возмущение"',
     'md="MD, гребень: релаксированный отклик при\\n$\\\\lambda_{\\\\mathrm{nom}}$ (диагностика, завышенная амплитуда)"'),
    ('esh="3D-сфера Эшелби, поддерживаемая $\\\\varepsilon^*=1{,}94\\\\times10^{-3}$"',
     'esh="3D-сфера Эшелби, поддерживаемая $\\\\lambda_{\\\\mathrm{nom}}$\\n(диагностика, завышенная амплитуда)"'),
    ('resc="пересчёт на $\\\\lambda_s=100$ ppm по удержанной\\nамплитуде $\\\\eta\\\\varepsilon^*$, $\\\\eta=0{,}30$"',
     'resc="сфера Эшелби при $\\\\lambda_s=100$ ppm\\n(физическая: пик 2{,}4 МПа)"'),
    ('thr=["открепления не было до 75 МПа - нижняя граница"',
     'thr=["открепления не было до 75 МПа ($\\\\pm$22, диполь)"'),
]
for a, b in rep:
    if a not in t:
        raise SystemExit("MISS: " + a[:70])
    t = t.replace(a, b, 1)

# ---- Fig. 3 body: physical curve + pinning band
old = """    scale = 1e-4 / (ETA_RETAINED * EPS_INFLATED)
    fig, ax = plt.subplots(figsize=(7.2, 4.9))
    ax.semilogy(dd, np.maximum(rss, 1e-3), "o-", ms=4.5, color="#3b8b52", label=t["md"])
    ax.semilogy(ed, ev, "s--", ms=5, color="#8b3b8b", label=t["esh"])
    ax.errorbar([1.0], [max(flank)], yerr=[[max(flank) - min(flank)], [0.0]],
                fmt="D", ms=6, color="#c07000", capsize=4, label=t["flank"])
    for y, ytxt, lbl, col in zip((75, 86, 195), (0.52, 1.10, 1.28), t["thr"],
                                 ("#444444", "#777777", "#aa2222")):
        ax.axhline(y, ls="--", lw=1.1, color=col)
        ax.text(73, y * ytxt, lbl, fontsize=8, color=col, ha="right")"""
new = """    # the physical curve: the maintained-eigenstrain solution rescaled from the
    # inflated nominal amplitude to a measured Fe-Al magnetostriction
    phys = ev * (1e-4 / EPS_INFLATED)
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.semilogy(dd, np.maximum(rss, 1e-3), "o-", ms=4.5, color="#3b8b52", label=t["md"])
    ax.semilogy(ed, ev, "s--", ms=5, color="#8b3b8b", label=t["esh"])
    ax.semilogy(ed, phys, "s-", ms=5, lw=2.0, color="#8b3b8b", alpha=0.45,
                label=t["resc"])
    ax.errorbar([1.0], [max(flank)], yerr=[[max(flank) - min(flank)], [0.0]],
                fmt="D", ms=6, color="#c07000", capsize=4, label=t["flank"])
    # the pinning bound is not unconditional: the dipole carries its own 22 MPa
    ax.axhspan(53, 97, color="#444444", alpha=0.13, lw=0)
    for y, ytxt, lbl, col in zip((75, 86, 195), (0.40, 1.13, 1.30), t["thr"],
                                 ("#444444", "#777777", "#aa2222")):
        ax.axhline(y, ls="--", lw=1.1, color=col)
        ax.text(73, y * ytxt, lbl, fontsize=8, color=col, ha="right")"""
if old not in t:
    raise SystemExit("MISS fig3 body")
t = t.replace(old, new, 1)
t = t.replace('ax.legend(fontsize=8.5, loc="lower left")',
              'ax.legend(fontsize=8.0, loc="lower left")', 1)

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("patched; remaining 'field-induced':",
      len(re.findall(r"field-induced|вызванное полем|от поля", t)))
