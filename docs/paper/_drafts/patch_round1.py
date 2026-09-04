#!/usr/bin/env python3
"""Round 1 of closing the \\todo items in the section drafts: unified-cell
geometry (91,428 atoms, 154.64 x 64.48 A), the two new figures, the bridge
table at f = 0.00246, dangling references. Items that need the v2 stress
profile are left with a %%NUM:<tag> comment so the numbers pass can find them.

Matching is whitespace-tolerant (the drafts are hard-wrapped)."""
from __future__ import annotations
import io, re, sys
from pathlib import Path

DR = Path(__file__).resolve().parent


def flex(s: str) -> str:
    return r"\s+".join(re.escape(p) for p in re.split(r"\s+", s.strip()))


def sub(text: str, old: str, new: str, tag: str, report: list) -> str:
    out, n = re.subn(flex(old), lambda m: new, text, count=1)
    if n == 0:
        report.append(tag)
    return out


def remove_todo(text: str, prefix: str, tag: str, report: list) -> str:
    """Remove a brace-balanced \\todo{...} whose content starts with prefix."""
    key = "\\todo{" + prefix
    i = text.find(key)
    if i < 0:
        report.append(tag)
        return text
    j = i + len("\\todo{")
    depth = 1
    while j < len(text) and depth:
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
        j += 1
    # swallow one trailing newline so no blank line is left behind
    if j < len(text) and text[j] == "\n":
        j += 1
    return text[:i] + text[j:]


FIG_CELL_EN = r"""\begin{figure}
\centering
\includegraphics[width=0.92\linewidth]{fig_cell_interface_en}
\caption{The interface cell, viewed along $y$ (the $x$--$z$ plane). Grey:
the aluminium matrix, 129~\AA{} of fcc aluminium with $x=[1\bar{1}0]$,
$y=[11\bar{2}]$ and $z=[111]$, so that the interface is parallel to a (111)
glide plane and $x$ is a glide direction. Red: the Al$_{13}$Fe$_4$ inclusion,
a flat layer with a half-elliptical ridge 70~\AA{} wide and 20~\AA{} high.
The lowest 6~\AA{} of the inclusion are held fixed; above the aluminium is
vacuum. The cell is periodic along $x$ and $y$. The imposed elongation of the
inclusion is directed at $45^{\circ}$ to the interface in the $x$--$z$
plane.}
\label{fig:cell}
\end{figure}"""

FIG_CELL_RU = r"""\begin{figure}[!htbp]
\centering
\includegraphics[width=0.92\linewidth]{fig_cell_interface_ru}
\caption{Расчётная ячейка границы в проекции вдоль $y$ (плоскость
$x$--$z$). Серым показана матрица алюминия --- 129~\AA{} ГЦК-алюминия с
осями $x = [1\bar{1}0]$, $y = [11\bar{2}]$, $z = [111]$, так что граница
параллельна плоскости скольжения (111), а $x$ --- направление скольжения.
Красным --- включение Al$_{13}$Fe$_4$: плоский слой с полуэллиптическим
гребнем шириной 70~\AA{} и высотой 20~\AA{}. Нижние 6~\AA{} включения
закреплены; над алюминием --- вакуум. Ячейка периодична вдоль $x$ и $y$.
Наложенное удлинение включения направлено под $45^{\circ}$ к границе в
плоскости $x$--$z$.}
\label{fig:cell}
\end{figure}"""

FIG_LOAD_EN = r"""\begin{figure}
\centering
\includegraphics[width=0.92\linewidth]{fig_cell_loading_en}\\[2mm]
\includegraphics[width=0.92\linewidth]{fig_loading_programme_en}
\caption{The loaded interface cell (top) and the two loading programmes
(bottom). Top: the cell of Fig.~\ref{fig:cell} with a pair of edge
dislocations of opposite sign next to the ridge (green: the dislocation lines
found by dislocation analysis; atoms of the perfect lattice are faded), both
on (111) glide planes parallel to the interface. A shear stress $\tau$ along
$x$ is applied through a uniform force on the top atomic layers and is taken
up by the fixed bottom layer. Bottom: the stress programmes---for this cell a
linear rise from 0 to 400~MPa over 96~ps after 5~ps at zero stress (a); for
the alloy cell without inclusion (Section~\ref{sec:mobility}) steps of 45,
55, 65 and 75~MPa, 30~ps each, after 10~ps without load (b).}
\label{fig:loading}
\end{figure}"""

FIG_LOAD_RU = r"""\begin{figure}[!htbp]
\centering
\includegraphics[width=0.92\linewidth]{fig_cell_loading_ru}\\[2mm]
\includegraphics[width=0.92\linewidth]{fig_loading_programme_ru}
\caption{Нагружаемая ячейка границы (вверху) и две программы нагружения
(внизу). Вверху: ячейка рис.~\ref{fig:cell} с парой краевых дислокаций
противоположного знака рядом с гребнем (зелёным показаны линии дислокаций,
найденные дислокационным анализом; атомы совершенной решётки приглушены), обе
в плоскостях скольжения (111), параллельных границе. Касательное напряжение
$\tau$ вдоль $x$ прикладывается однородной силой к верхним атомным слоям и
воспринимается закреплённым нижним слоем. Внизу: программы напряжения --- для
этой ячейки линейный рост от 0 до 400~МПа за 96~пс после 5~пс при нулевом
напряжении (а); для ячейки сплава без включения (раздел~3.3) ступени 45, 55,
65 и 75~МПа по 30~пс каждая после 10~пс без нагрузки (б).}
\label{fig:loading}
\end{figure}"""

TABLE_EN_OLD = r"""\caption{The two-scale estimate, Eq.~(\ref{eq:bridge}), at $T=300$~K,
$f=0.002$ \todo{G5: update table to f = 0.00246} and
$b=a/\sqrt{2}=2.8638$~\AA{}. Second column: the resolved shear stress
$\tau_m$ at the particle surface that reproduces the measured $+25\%$ creep
enhancement. Third and fourth columns: the enhancement
$\langle\dot\varepsilon\rangle/\dot\varepsilon_0-1$ that
Eq.~(\ref{eq:bridge}) predicts if 147~MPa or 5.3~MPa acted as $\tau_m$; the
last column repeats the fourth as a percentage. The observed value is 0.25.}
\label{tab:bridge}
\small
\begin{tabular}{lcccc}
\hline
$V^{*}$ & $\tau_m$ for $+25\%$ (MPa) & at 147~MPa & at 5.3~MPa & (\%) \\
\hline
$19\,b^{3}$  & 65.17 & $5.53\times10^{2}$  & $3.29\times10^{-4}$ & 0.033 \\
$30\,b^{3}$  & 41.27 & $3.16\times10^{6}$  & $8.32\times10^{-4}$ & 0.083 \\
$50\,b^{3}$  & 24.76 & $3.18\times10^{13}$ & $2.41\times10^{-3}$ & 0.241 \\
$70\,b^{3}$  & 17.69 & $3.89\times10^{20}$ & $5.02\times10^{-3}$ & 0.502 \\
$100\,b^{3}$ & 12.38 & $1.95\times10^{31}$ & $1.18\times10^{-2}$ & 1.176 \\
$142\,b^{3}$ & 8.72  & $2.18\times10^{46}$ & $3.17\times10^{-2}$ & 3.172 \\
\hline
\end{tabular}"""

TABLE_EN_NEW = r"""\caption{The two-scale estimate, Eq.~(\ref{eq:bridge}), at $T=300$~K,
$f=0.00246$ and $b=a/\sqrt{2}=2.8638$~\AA{}. Second column: the resolved
shear stress $\tau_m$ at the particle surface that reproduces the measured
$+25\%$ creep enhancement. The remaining columns give the enhancement
$\langle\dot\varepsilon\rangle/\dot\varepsilon_0-1$ that
Eq.~(\ref{eq:bridge}) predicts if $\tau_m$ were 147~MPa (the earlier
estimate), 41~MPa (the analytical sphere held at the strain of 0.194\%) or
20~MPa (the stress at the surface of the ridge in the interface cell,
Section~\ref{sec:sigma_r}). The observed value is 0.25.}
%%NUM:tab-bridge-col4
\label{tab:bridge}
\small
\begin{tabular}{lcccc}
\hline
$V^{*}$ & $\tau_m$ for $+25\%$ (MPa) & at 147~MPa & at 41~MPa & at 20~MPa \\
\hline
$19\,b^{3}$  & 62.7 & $6.8\times10^{2}$  & 0.045 & 0.007 \\
$30\,b^{3}$  & 39.7 & $3.9\times10^{6}$  & 0.31 & 0.021 \\
$50\,b^{3}$  & 23.8 & $3.9\times10^{13}$ & 17 & 0.12 \\
$70\,b^{3}$  & 17.0 & $4.8\times10^{20}$ & $1.2\times10^{3}$ & 0.75 \\
$100\,b^{3}$ & 11.9 & $2.4\times10^{31}$ & $9.3\times10^{5}$ & 15 \\
$142\,b^{3}$ & 8.4  & $2.7\times10^{46}$ & $1.2\times10^{10}$ & $1.3\times10^{3}$ \\
\hline
\end{tabular}"""

TABLE_RU_OLD = r"""\caption{Двухмасштабная оценка~(2) при $T = 300$~К, $f = 0{,}002$
\todo{G5: update table to f = 0.00246} и $b = 2{,}8638$~\AA{}. Второй
столбец --- разрешённое касательное напряжение $\tau_m$ на поверхности
частицы, воспроизводящее измеренный прирост ползучести 25\%. Третий и
четвёртый столбцы --- усиление
$\langle\dot\varepsilon\rangle/\dot\varepsilon_0 - 1$, которое
соотношение~(2) предсказывает, если бы в роли $\tau_m$ выступали 147 или
5{,}3~МПа; последний столбец повторяет четвёртый в процентах. Наблюдаемое
значение --- 0{,}25.}
\label{tab:bridge}
\begin{tabular}{lcccc}
\hline
$V^{*}$ & $\tau_m$ для $+25\%$, МПа & при 147~МПа & при 5{,}3~МПа & при 5{,}3~МПа, \% \\
\hline
$19\,b^{3}$  & 65{,}17 & $5{,}53\cdot10^{2}$  & $3{,}29\cdot10^{-4}$ & 0{,}033 \\
$30\,b^{3}$  & 41{,}27 & $3{,}16\cdot10^{6}$  & $8{,}32\cdot10^{-4}$ & 0{,}083 \\
$50\,b^{3}$  & 24{,}76 & $3{,}18\cdot10^{13}$ & $2{,}41\cdot10^{-3}$ & 0{,}241 \\
$70\,b^{3}$  & 17{,}69 & $3{,}89\cdot10^{20}$ & $5{,}02\cdot10^{-3}$ & 0{,}502 \\
$100\,b^{3}$ & 12{,}38 & $1{,}95\cdot10^{31}$ & $1{,}18\cdot10^{-2}$ & 1{,}176 \\
$142\,b^{3}$ & 8{,}72  & $2{,}18\cdot10^{46}$ & $3{,}17\cdot10^{-2}$ & 3{,}172 \\
\hline
\end{tabular}"""

TABLE_RU_NEW = r"""\caption{Двухмасштабная оценка~(2) при $T = 300$~К, $f = 0{,}00246$ и
$b = 2{,}8638$~\AA{}. Второй столбец --- разрешённое касательное напряжение
$\tau_m$ на поверхности частицы, воспроизводящее измеренный прирост
ползучести 25\%. Остальные столбцы --- усиление
$\langle\dot\varepsilon\rangle/\dot\varepsilon_0 - 1$, которое
соотношение~(2) предсказывает, если бы в роли $\tau_m$ выступали 147~МПа
(прежняя оценка), 41~МПа (аналитическая сфера, удерживаемая при деформации
0{,}194\%) или 20~МПа (напряжение у поверхности гребня в ячейке границы,
раздел~3.1). Наблюдаемое значение --- 0{,}25.}
%%NUM:tab-bridge-col4
\label{tab:bridge}
\begin{tabular}{lcccc}
\hline
$V^{*}$ & $\tau_m$ для $+25\%$, МПа & при 147~МПа & при 41~МПа & при 20~МПа \\
\hline
$19\,b^{3}$  & 62{,}7 & $6{,}8\cdot10^{2}$  & 0{,}045 & 0{,}007 \\
$30\,b^{3}$  & 39{,}7 & $3{,}9\cdot10^{6}$  & 0{,}31 & 0{,}021 \\
$50\,b^{3}$  & 23{,}8 & $3{,}9\cdot10^{13}$ & 17 & 0{,}12 \\
$70\,b^{3}$  & 17{,}0 & $4{,}8\cdot10^{20}$ & $1{,}2\cdot10^{3}$ & 0{,}75 \\
$100\,b^{3}$ & 11{,}9 & $2{,}4\cdot10^{31}$ & $9{,}3\cdot10^{5}$ & 15 \\
$142\,b^{3}$ & 8{,}4  & $2{,}7\cdot10^{46}$ & $1{,}2\cdot10^{10}$ & $1{,}3\cdot10^{3}$ \\
\hline
\end{tabular}"""


def patch(name: str, edits, todos) -> None:
    p = DR / name
    t = io.open(p, encoding="utf-8").read()
    rep: list = []
    for tag, old, new in edits:
        t = sub(t, old, new, tag, rep)
    for tag, prefix in todos:
        t = remove_todo(t, prefix, tag, rep)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("%-20s unmatched: %s" % (name, rep if rep else "none"))


# ------------------------------------------------------------------ EN
patch("Section_1_en.tex", [
    ("intro-phase", r"in Section~\ref{sec:limitations}. A series", r"in Section~\ref{sec:phase}. A series"),
], [])

patch("Section_2_en.tex", [
    ("misfit",
     r"""The in-plane dimensions ($L_x=108.82$~\AA{},
$L_y=64.48$~\AA{}) are chosen so that both lattices are periodic in the
plane. The small residual mismatch ($+0.31\%$ along $x$, $-0.26\%$ along $y$)
is taken up by the inclusion and is the same in every cell, so that it cancels
to first order when two cells are compared.""",
     r"""The in-plane dimensions ($L_x=154.64$~\AA{}, $L_y=64.48$~\AA{}: 54 and 13
periods of the aluminium lattice, ten and eight cells of Al$_{13}$Fe$_4$) are
chosen so that both lattices are periodic in the plane. The small residual
mismatch ($-0.22\%$ along $x$, $-0.26\%$ along $y$) is taken up by the
inclusion and is the same in the strained and in the control cell, so that it
cancels to first order when the two are compared."""),
    ("count",
     r"""The
aluminium layer above the interface is about 220~\AA{} thick, the whole cell
contains about $10^{5}$ atoms \todo{G13: exact count and cell height}, and
in $z$ it is bounded by a free surface with 15~\AA{} of vacuum above it and
by a layer 6~\AA{} thick at the bottom whose atoms are held fixed.""",
     r"""The
aluminium layer above the interface plane is 129~\AA{} thick (56 atomic (111)
planes), the whole cell contains 91\,428 atoms (72\,532 in the matrix and
18\,896 in the inclusion), and in $z$ it is bounded by a free surface with
17~\AA{} of vacuum above it and by a layer 6~\AA{} thick at the bottom whose
atoms are held fixed (Fig.~\ref{fig:cell})."""),
    ("fig-cell",
     r"""\todo{FIG: labelled cross-section of the cell in the $x$--$z$ plane: the
aluminium matrix above, the Al$_{13}$Fe$_4$ layer with its half-elliptical
ridge, the interface plane at $z=20$~\AA{}, the fixed bottom layer, the
vacuum gap, the crystallographic axes $x=[1\bar{1}0]$, $y=[11\bar{2}]$,
$z=[111]$, the (111) glide plane parallel to the interface, and the direction
$\mathbf{u}$ of the imposed strain at $45^{\circ}$ to $z$.}""",
     FIG_CELL_EN),
    ("spring",
     r"""\todo{G13: report the maintained-case profile and confirm the spring
stiffness.}""",
     r"""The stiffness of the springs is 20~eV/\AA$^{2}$; under the forces that arise
at the interface the inclusion atoms depart from their strained positions by
about 0.01~\AA{}, so that the inclusion retains almost all of the imposed
strain (Section~\ref{sec:sigma_r}).
%%NUM:held-eta"""),
    ("loaded-count",
     r"inclusion, about $10^{5}$ atoms in all \todo{G13: exact count}. The pair is",
     r"inclusion, 91\,428 atoms in all (Fig.~\ref{fig:loading}). The pair is"),
    ("partners",
     r"""the interface. \todo{G13: give the partner separation, the corresponding
mutual stress $\mu b/[8\pi(1-\nu)h]$, and the distance of the pair from the
ridge in the unified cell.} The cell is loaded""",
     r"""the interface. The partners are offset by 23.4~\AA{} along $x$ and by ten
(111) interplanar spacings, 23.4~\AA{}, along $z$, so that the line joining
them is inclined at $45^{\circ}$ to the glide planes. Two edge dislocations
of opposite sign on glide planes a distance $h$ apart attract with a shear
stress of up to $\mu b/[8\pi(1-\nu)h]$, which for $h=23.4$~\AA{} is 198~MPa
(with $\mu=26.5$~GPa, $\nu=0.347$ and $b=2.864$~\AA{}); this is the applied
stress at which they would pass each other in an unbounded crystal. The lower
partner lies 27~\AA{} beyond the foot of the ridge and 29~\AA{} above the
interface plane, the upper one 23~\AA{} higher and 23~\AA{} closer to the
ridge. The cell is loaded"""),
    ("g15",
     r"""\todo{G13: the loaded cell is being rebuilt with the $45^{\circ}$ strain of
Section~\ref{sec:eigenstrain}; the onsets quoted in
Section~\ref{sec:thresholds} were measured in a cell whose strain axis was
along $z$ (no shear on the glide plane, no maintained strain) and must either
be replaced by the unified-cell values or be stated as such in the text.}""",
     "%%NUM:G15-thresholds"),
    ("alloy-count",
     r"same orientation, about $10^{5}$ atoms \todo{G13: exact count}, in which",
     r"same orientation, 92\,800 atoms (91\,315~Al, 928~Mg, 557~Si; $114.6\times49.6\times291$~\AA{}), in which"),
    ("fig-load",
     r"""\todo{FIG: sketch of the loading scheme: the slab in the $x$--$z$ plane with
the fixed bottom layer, the top layers on which the force along $x$ is
applied, the dislocation dipole on its (111) glide planes next to the ridge,
and beside it the two stress-versus-time programmes, the linear ramp to
400~MPa over 96~ps and the 45/55/65/75~MPa steps of 30~ps each.}""",
     FIG_LOAD_EN),
], [])

patch("Section_3_en.tex", [
    ("fig-cell-ref",
     r"""\todo{FIG: labelled picture of the interface cell: Al matrix,
Al$_{13}$Fe$_4$ support slab and ridge, axes $x=[1\bar{1}0]$,
$y=[11\bar{2}]$, $z=[111]$, the direction of the field (and of the
elongation) at $45^{\circ}$ to the interface in the $x$--$z$ plane, the
fixed bottom layer and the free top surface; a draft exists as
fig\_cell\_interface\_en/ru.png.}""",
     r"The geometry is that of Fig.~\ref{fig:cell}."),
    ("surface",
     r"""higher, at $r=138$~\AA{}, and the slices within 20~\AA{} of it, where the
surface layers dominate the per-atom stress, are not plotted
\todo{G13: confirm the free-surface height and the plotted range for the
unified cell}. This rise""",
     r"""higher, at $r=129$~\AA{}, and the slices within 20~\AA{} of it, where the
surface layers dominate the per-atom stress, are not plotted.
%%NUM:S3-profile
This rise"""),
    ("tab-eta", r"(Table~\ref{tab:eta})", r"(Section~\ref{sec:eigenstrain})"),
    ("cap-count", r"""(about
$10^{5}$ atoms \todo{G13: exact count}): the control cell""", r"(91\,428 atoms): the control cell"),
    ("script-g10", r"(Al only) by \texttt{analysis/python/stageG10\_field\_profile.py}.", r"(Al only)."),
    ("fig-load-ref",
     r"""\todo{FIG: sketch of the loading scheme: the slab with its fixed bottom
layer, the uniform shear force applied to the top atomic layers, the
dislocation pair on glide planes parallel to the interface and the ridge
beneath it; the stress ramp 0--400~MPa in 96~ps for this cell, and the
staircase 45/55/65/75~MPa, 30~ps per step, for the alloy cell of
Section~\ref{sec:mobility}.}""",
     r"The cell and the loading programmes are shown in Fig.~\ref{fig:loading}."),
    ("script-g8", r"""(\texttt{analysis/python/stageG8\_eshelby3d.py}).""", "."),
], [("todo-fig1", "FIG: regenerate"), ("todo-fig2", "FIG: legend labels"), ("todo-fig3", "FIG: regenerate")])

patch("Sections_4_en.tex", [
    ("f-sentence",
     r"""0.35~wt\%, corresponding to a volume fraction $f\approx0.25\%$
\todo{G5: update table to f = 0.00246}; Table~\ref{tab:bridge} is evaluated
at $f=0.002$, within the 0.1--0.3\% reported in Ref.~\cite{Friha2024JMMM}.""",
     r"""0.35~wt\%, corresponding to a volume fraction $f=0.00246$, within the
0.1--0.3\% reported in Ref.~\cite{Friha2024JMMM}; Table~\ref{tab:bridge} is
evaluated at this value."""),
    ("table", TABLE_EN_OLD, TABLE_EN_NEW),
    ("phase-label", r"\subsection{Three stresses, and the identity of the magnetic phase}",
     "\\subsection{Three stresses, and the identity of the magnetic phase}\n\\label{sec:phase}"),
], [("todo-sketch", "FIG: sketch of the estimate"), ("todo-timeline", "FIG: timeline")])

# ------------------------------------------------------------------ RU
patch("Section_1_ru.tex", [
    ("intro-phase", r"рассматривается в разделе «Ограничения».", r"рассматривается в разделе~5.1."),
], [])

patch("Section_2_ru.tex", [
    ("misfit",
     r"""Размеры в плоскости ($L_x = 108{,}82$~\AA{}, $L_y = 64{,}48$~\AA{})
выбраны так, чтобы обе решётки были периодичны в плоскости. Малое остаточное
несоответствие ($+0{,}31\%$ вдоль $x$, $-0{,}26\%$ вдоль $y$) отнесено к
включению и одинаково во всех ячейках, поэтому при сравнении двух ячеек оно
сокращается в первом приближении.""",
     r"""Размеры в плоскости ($L_x = 154{,}64$~\AA{}, $L_y = 64{,}48$~\AA{}: 54 и
13 периодов решётки алюминия, десять и восемь ячеек Al$_{13}$Fe$_4$) выбраны
так, чтобы обе решётки были периодичны в плоскости. Малое остаточное
несоответствие ($-0{,}22\%$ вдоль $x$, $-0{,}26\%$ вдоль $y$) отнесено к
включению и одинаково в деформированной и контрольной ячейках, поэтому при их
сравнении оно сокращается в первом приближении."""),
    ("count",
     r"""Толщина слоя алюминия над границей около 220~\AA{}, ячейка в
целом содержит около $10^{5}$ атомов \todo{G13: точное число атомов и
высота ячейки}; вдоль $z$ она ограничена сверху свободной поверхностью и
15~\AA{} вакуума, снизу --- слоем толщиной 6~\AA{}, атомы которого
закреплены.""",
     r"""Толщина слоя алюминия над плоскостью границы 129~\AA{} (56 атомных
плоскостей (111)), ячейка в целом содержит 91\,428 атомов (72\,532 в матрице
и 18\,896 во включении); вдоль $z$ она ограничена сверху свободной
поверхностью и 17~\AA{} вакуума, снизу --- слоем толщиной 6~\AA{}, атомы
которого закреплены (рис.~\ref{fig:cell})."""),
    ("fig-cell",
     r"""\todo{FIG: подписанное сечение ячейки в плоскости $x$--$z$: матрица алюминия
сверху, слой Al$_{13}$Fe$_4$ с полуэллиптическим гребнем, плоскость границы
$z = 20$~\AA{}, закреплённый нижний слой, вакуумный зазор, кристаллографические
оси $x = [1\bar{1}0]$, $y = [11\bar{2}]$, $z = [111]$, плоскость скольжения
(111) параллельно границе и направление $\mathbf{u}$ наложенной деформации
под $45^{\circ}$ к $z$.}""",
     FIG_CELL_RU),
    ("spring",
     r"""\todo{G13: привести профиль для
удерживаемой деформации и подтвердить жёсткость пружин.}""",
     r"""Жёсткость пружин 20~эВ/\AA$^{2}$; под действием сил, возникающих на
границе, атомы включения отходят от заданных положений примерно на
0{,}01~\AA{}, так что включение сохраняет почти всю наложенную деформацию
(раздел~3.1).
%%NUM:held-eta"""),
    ("loaded-count",
     r"""всего около $10^{5}$
атомов \todo{G13: точное число атомов}. Пара представляет собой""",
     r"""всего 91\,428 атомов (рис.~\ref{fig:loading}). Пара представляет собой"""),
    ("partners",
     r"""\todo{G13: привести
расстояние между партнёрами, соответствующее взаимное напряжение
$\mu b/[8\pi(1-\nu)h]$ и расстояние пары от гребня в унифицированной
ячейке.} Ячейка нагружается""",
     r"""Партнёры смещены друг относительно друга на 23{,}4~\AA{} вдоль $x$ и на
десять межплоскостных расстояний (111), 23{,}4~\AA{}, вдоль $z$, так что
соединяющая их линия наклонена к плоскостям скольжения под $45^{\circ}$. Две
краевые дислокации противоположного знака в плоскостях скольжения на
расстоянии $h$ притягиваются с касательным напряжением до
$\mu b/[8\pi(1-\nu)h]$, что при $h = 23{,}4$~\AA{} составляет 198~МПа (при
$\mu = 26{,}5$~ГПа, $\nu = 0{,}347$, $b = 2{,}864$~\AA{}); это приложенное
напряжение, при котором они прошли бы друг мимо друга в неограниченном
кристалле. Нижний партнёр находится в 27~\AA{} за подножием гребня и в
29~\AA{} над плоскостью границы, верхний --- на 23~\AA{} выше и на 23~\AA{}
ближе к гребню. Ячейка нагружается"""),
    ("g15",
     r"""\todo{G13: нагружаемая ячейка перестраивается с
деформацией под $45^{\circ}$ из раздела~2.2; пороги, приводимые в
разделе~3.2, измерены в ячейке с осью деформации вдоль $z$ (без сдвига на
плоскости скольжения и без удерживаемой деформации) --- их нужно либо
заменить значениями из унифицированной ячейки, либо оговорить это в тексте.}""",
     "%%NUM:G15-thresholds"),
    ("alloy-count",
     r"""около $10^{5}$ атомов \todo{G13: точное число атомов}, в
котором""",
     r"""92\,800 атомов (91\,315~Al, 928~Mg, 557~Si;
$114{,}6\times49{,}6\times291$~\AA{}), в котором"""),
    ("fig-load",
     r"""\todo{FIG: схема нагружения: слой в плоскости $x$--$z$ с закреплённым нижним
слоем, верхними слоями, к которым приложена сила вдоль $x$, дислокационным
диполем на его плоскостях скольжения (111) рядом с гребнем, и рядом --- две
программы напряжение--время: линейный рост до 400~МПа за 96~пс и ступени
45/55/65/75~МПа по 30~пс.}""",
     FIG_LOAD_RU),
], [])

patch("Section_3_ru.tex", [
    ("fig-cell-ref",
     r"""\todo{FIG: labelled picture of the interface cell: Al matrix,
Al$_{13}$Fe$_4$ support slab and ridge, axes $x=[1\bar{1}0]$,
$y=[11\bar{2}]$, $z=[111]$, the direction of the field (and of the
elongation) at $45^{\circ}$ to the interface in the $x$--$z$ plane, the
fixed bottom layer and the free top surface; a draft exists as
fig\_cell\_interface\_en/ru.png.}""",
     r"Геометрия показана на рис.~\ref{fig:cell}."),
    ("surface",
     r"""20~\AA{} выше, при $r = 138$~\AA{}, и слои в пределах 20~\AA{} от неё, где
поатомное напряжение определяется поверхностными слоями, не строятся
\todo{G13: confirm the free-surface height and the plotted range for the
unified cell}. Этот рост""",
     r"""20~\AA{} выше, при $r = 129$~\AA{}, и слои в пределах 20~\AA{} от неё, где
поатомное напряжение определяется поверхностными слоями, не строятся.
%%NUM:S3-profile
Этот рост"""),
    ("tab-eta", r"(табл.~\ref{tab:eta})", r"(раздел~2.2)"),
    ("cap-count", r"""(около $10^{5}$
атомов \todo{G13: exact count}): в контрольной ячейке""", r"(91\,428 атомов): в контрольной ячейке"),
    ("script-g10", r"Al) скриптом \texttt{analysis/python/stageG10\_field\_profile.py}.", r"Al)."),
    ("fig-load-ref",
     r"""\todo{FIG: sketch of the loading scheme: the slab with its fixed bottom
layer, the uniform shear force applied to the top atomic layers, the
dislocation pair on glide planes parallel to the interface and the ridge
beneath it; the stress ramp 0--400~MPa in 96~ps for this cell, and the
staircase 45/55/65/75~MPa, 30~ps per step, for the alloy cell of
Section~3.3.}""",
     r"Ячейка и программы нагружения показаны на рис.~\ref{fig:loading}."),
    ("script-g8", r"""системам скольжения (\texttt{analysis/python/stageG8\_eshelby3d.py}).""", r"системам скольжения."),
], [("todo-fig1", "FIG: regenerate"), ("todo-fig2", "FIG: legend labels"), ("todo-fig3", "FIG: regenerate")])

patch("Sections_4_ru.tex", [
    ("f-sentence",
     r"""0{,}35~масс.\%, что отвечает объёмной доле $f \approx 0{,}25\%$
\todo{G5: update table to f = 0.00246}; табл.~\ref{tab:bridge}
рассчитана при $f = 0{,}002$, в пределах 0{,}1--0{,}3\%, указанных в [5].""",
     r"""0{,}35~масс.\%, что отвечает объёмной доле $f = 0{,}00246$, в пределах
0{,}1--0{,}3\%, указанных в [5]; табл.~\ref{tab:bridge} рассчитана при этом
значении."""),
    ("table", TABLE_RU_OLD, TABLE_RU_NEW),
], [("todo-sketch", "FIG: схема оценки"), ("todo-timeline", "FIG: схема протокола")])

# what is left
for f in sorted(DR.glob("*.tex")):
    t = io.open(f, encoding="utf-8").read()
    n = t.count("\\todo{")
    if n:
        print("%-28s %d todo left" % (f.name, n))
        for m in re.finditer(r"\\todo\{([^}]{0,70})", t):
            print("      ", m.group(1))
