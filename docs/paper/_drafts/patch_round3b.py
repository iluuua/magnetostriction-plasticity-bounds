#!/usr/bin/env python3
"""Round 3b: the Fig. 5 caption (EN/RU) and highlights.tex, with the unified-cell
thresholds. Needs numbers_round3.json (TAU_NUC, TAU_MOVE_RANGE, TAU_MOVE, VSTAR_LO,
VSTAR_HI).

    python patch_round3b.py --numbers numbers_round3.json
"""
from __future__ import annotations
import argparse, io, json, re
from pathlib import Path

DR = Path(__file__).resolve().parent
PAPER = DR.parent


def fill(s: str, num: dict) -> str:
    return re.sub("«([A-Z0-9_]+)»", lambda m: str(num[m.group(1)]), s)


CAP_EN = r"""\caption{The stress produced by the strained inclusion against the stresses
at which dislocations respond: the shear stress resolved onto the most
favourable slip system, $\mathrm{RSS}_{\max}$, on a logarithmic scale,
against the distance $d$ from the nearest inclusion surface. Green circles:
the interface cell (91\,428 atoms) with the ridge held at 0.194\%, averaged
over the width of the cell; green diamonds: the same within 10~\AA{} of the
ridge axis; for the ridge $d=r-20$~\AA{} (the crest height). Purple squares:
the exact solution of Eshelby \cite{Eshelby1957} for a spherical inclusion
of radius $a=35$~\AA{} held at the same elongation in an infinite elastic
aluminium matrix ($\mu=26.5$~GPa, $\nu=0.347$, the volume-conserving
elongation of Eq.~(\ref{eq:eigenstrain}) with its axis at $45^{\circ}$ to
$z$, the same maximum over the twelve slip systems); for the sphere
$d=r-a$. Horizontal lines: the end of the ramp, «TAU_NUC»~MPa, up to which no new
dislocation formed at the interface (dotted), and the stress at which the
pre-existing dislocation pair starts to move («TAU_MOVE_RANGE»~MPa), both from
Section~\ref{sec:thresholds}; the shaded band, $75\pm22$~MPa, is the stress
withstood by the pinned dislocation of Section~\ref{sec:mobility} (the
applied 75~MPa, plus or minus the 22~MPa mutual stress of the pair, whose
sign is not resolved). The orange diamond marks the range spanned by the
omitted slices on the ridge flanks; it is not a measurement of the field.}"""

CAP_RU = r"""\caption{Напряжение от деформированного включения и напряжения отклика
дислокаций: касательное напряжение, спроецированное на наиболее
благоприятную систему скольжения, $\mathrm{RSS}_{\max}$, в логарифмическом
масштабе в зависимости от расстояния $d$ до ближайшей поверхности
включения. Зелёные кружки --- ячейка границы (91\,428 атомов) с гребнем,
удерживаемым при 0{,}194\%, в среднем по ширине ячейки; зелёные ромбы --- то
же в пределах 10~\AA{} от оси гребня; для гребня $d = r - 20$~\AA{} (высота
вершины). Фиолетовые квадраты --- точное решение Эшелби [7] для сферического
включения радиуса $a = 35$~\AA{}, удерживаемого при том же удлинении в
бесконечной упругой матрице алюминия ($\mu = 26{,}5$~ГПа, $\nu = 0{,}347$,
объём-сохраняющее удлинение формулы~(1) с осью под 45$^\circ$ к $z$, тот же
максимум по двенадцати системам скольжения); для сферы $d = r - a$.
Горизонтальные линии --- конец рампы, «TAU_NUC»~МПа, до которого новых
дислокаций на границе не образовалось (пунктир), и напряжение, при котором
приходит в движение существующая пара дислокаций («TAU_MOVE_RANGE»~МПа), оба
из раздела~3.2; затенённая полоса $75 \pm 22$~МПа --- напряжение, выдерживаемое
закреплённой дислокацией раздела~3.3 (приложенные 75~МПа плюс-минус взаимное
напряжение пары 22~МПа с неустановленным знаком). Оранжевый ромб отмечает
диапазон, охватываемый опущенными слоями на склонах гребня; измерением поля
он не является.}"""

HIGHLIGHTS = r"""% Highlights for Computational Materials Science (3-5 bullets, <= 85 chars each)
\documentclass{article}
\begin{document}
\section*{Highlights}
\begin{itemize}
\item An Al$_{13}$Fe$_4$ ridge held at 0.194\% strain stresses the Al matrix by 15 MPa to 30 \AA
\item A compact particle at the same strain carries 41 MPa inside it, decaying as $r^{-3}$
\item A pre-existing pair is torn apart at «TAU_MOVE» MPa; none nucleates up to «TAU_NUC» MPa
\item A two-scale estimate gives the +25\% creep for $V^{*}$ = «VSTAR_LO»--«VSTAR_HI» $b^{3}$ if the strain is real
\item Measured Fe--Al magnetostriction is 20$	imes$ smaller; the 30-min memory is not elastic
\end{itemize}
\end{document}
"""


def replace_caption(text: str, fig_key: str, new_cap: str) -> str:
    i = text.find(fig_key)
    j = text.find(r"\caption{", i)
    k = text.find(r"\label{fig:rss}", j)
    if min(i, j, k) < 0:
        raise SystemExit("fig:rss caption not found")
    # the caption ends at the last '}' before the label line
    end = text.rfind("}", j, k) + 1
    return text[:j] + new_cap + text[end:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--numbers", type=Path, required=True)
    a = ap.parse_args()
    num = json.loads(a.numbers.read_text(encoding="utf-8"))
    for name, key, cap in (("Section_3_en.tex", "fig_rss_vs_thresholds_en", CAP_EN),
                           ("Section_3_ru.tex", "fig_rss_vs_thresholds_ru", CAP_RU)):
        p = DR / name; t = io.open(p, encoding="utf-8").read()
        t = replace_caption(t, key, fill(cap, num))
        io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    io.open(PAPER / "highlights.tex", "w", encoding="utf-8", newline="\n").write(fill(HIGHLIGHTS, num))
    print("round 3b applied: Fig. 5 captions and highlights")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
