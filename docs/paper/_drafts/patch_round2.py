#!/usr/bin/env python3
"""Round 2: the amplitude argument once the strain 0.194 % is taken as given
and the inclusion is held at it (stage G13 v2, held pair). Replaces the
lambda_s-based passages of Sections 2.2, 4, 5.1, 5.2 and 5.4 in EN and RU.

Run after the held (and free) v2 pairs have been analysed:
    python patch_round2.py --numbers numbers_round2.json
The JSON supplies the «KEY» values below; every key must be present.
"""
from __future__ import annotations
import argparse, io, json, re, sys
from pathlib import Path

DR = Path(__file__).resolve().parent
KEYS = ["RIDGE_PEAK", "RIDGE_PEAK_RU", "RIDGE_WIDTHAVG", "RIDGE_WIDTHAVG_RU", "FAR", "FAR_RU",
        "DECAY", "ETA_HELD", "ETA_HELD_RU", "ETA_FREE", "ETA_FREE_RU",
        "ENH_RIDGE_50", "ENH_RIDGE_50_RU", "ENH_RIDGE_70", "ENH_RIDGE_70_RU",
        "VSTAR_LO", "VSTAR_HI", "BOW_RIDGE", "BOW_RIDGE_RU", "RATIO_SPHERE_RIDGE", "RATIO_SPHERE_RIDGE_RU",
        "CONT_RIDGE", "CONT_RIDGE_RU"]


def flex(s: str) -> str:
    return r"\s+".join(re.escape(p) for p in re.split(r"\s+", s.strip()))


def sub(text, old, new, tag, report):
    out, n = re.subn(flex(old), lambda m: new, text, count=1)
    if n == 0:
        report.append(tag)
    return out


def fill(s: str, num: dict) -> str:
    def rep(m):
        k = m.group(1)
        if k not in num:
            raise SystemExit("missing number: " + k)
        return str(num[k])
    return re.sub("«([A-Z0-9_]+)»", rep, s)


# ----------------------------------------------------------------- EN texts
EN = {}
EN["e_al"] = (
    r"""$\varepsilon=1.94\times10^{-3}$ (0.194\%), the elastic strain
$\sigma_m/E_{\mathrm{Al}}$ corresponding to the interface stress
$\sigma_m=147$~MPa estimated in those works \cite{Friha2024JMMM}, at
constant volume:""",
    r"""$\varepsilon=1.94\times10^{-3}$ (0.194\%), the elastic strain
$\sigma_m/E_{\mathrm{Al}}$ (with $E_{\mathrm{Al}}=75.7$~GPa) corresponding to
the interface stress $\sigma_m=147$~MPa estimated in those works
\cite{Friha2024JMMM}, at constant volume:""")

EN["held"] = (
    r"""The stiffness of the springs is 20~eV/\AA$^{2}$; under the forces that arise
at the interface the inclusion atoms depart from their strained positions by
about 0.01~\AA{}, so that the inclusion retains almost all of the imposed
strain (Section~\ref{sec:sigma_r}).
%%NUM:held-eta""",
    r"""Under the forces that arise at the interface the inclusion atoms depart from
their strained positions by about 0.01~\AA{}, and the ridge retains
«ETA_HELD» of the imposed strain (measured as described for the free case
below).""")

EN["free"] = (
    r"""In the \emph{free} case no springs are attached and the inclusion is free to
relax the imposed strain back out. It does so to a large extent: after
minimisation the ridge, which produces the field measured in the matrix,
retains $0.30\pm0.10$ of the imposed strain (the flat layer beneath it,
constrained by the periodicity, retains $0.74\pm0.08$); the fraction is
measured as the projection of the residual distortion of the Fe sublattice of
the inclusion onto $\varepsilon^{*}$, and the uncertainty is the standard
error of the least-squares fit of that distortion. The retention is not
uniform: the shear component that acts on the glide plane is retained at
0.39 of its imposed value, while the normal components relax almost
completely. The stress field of the free cell is therefore the relaxed
response to the imposed strain, not the field of an inclusion that maintains
it.""",
    r"""In the \emph{free} case no springs are attached and the inclusion is free to
relax the imposed strain back out. It does so almost completely: after
minimisation the ridge, which produces the field measured in the matrix,
retains «ETA_FREE» of the imposed strain. The fraction is measured as the
projection of the residual distortion of the Fe sublattice of the inclusion
onto $\varepsilon^{*}$, obtained by a least-squares fit of the displacements
between the strained and the control cell; the uncertainty is the standard
error of that fit. The free cell shows what an inclusion does when nothing
holds its strain; its stress field is the relaxed response, not the field of
an inclusion that maintains the strain, and it is the maintained case that is
compared with the dislocation thresholds below.""")

EN["applied"] = (
    r"""The strain is applied by displacing every inclusion atom relative to the
centre of the inclusion in proportion to its position,
$\mathbf{r}\rightarrow\mathbf{r}+\varepsilon^{*}\!\cdot\!\mathbf{r}$, which
stretches the inclusion uniformly along $\mathbf{u}$ and compresses it across
$\mathbf{u}$. The interatomic potential is not modified.""",
    r"""The strain is applied by displacing every atom of the ridge relative to the
centre of the ridge in proportion to its position,
$\mathbf{r}\rightarrow\mathbf{r}+\varepsilon^{*}\!\cdot\!\mathbf{r}$, which
stretches the ridge uniformly along $\mathbf{u}$ and compresses it across
$\mathbf{u}$. The flat layer beneath the ridge is left unstrained. It spans
the periodic cell, and a layer that is periodic in its plane cannot be
sheared coherently: held at the shear of Eq.~(\ref{eq:eigenstrain}) its
surface would be a sawtooth with a step of $\varepsilon^{*}_{xz}L_x=0.22$~\AA{}
at the cell boundary, and the whole aluminium slab above it would be
stretched along $z$ by about $\varepsilon^{*}_{xz}$---a stress of order
150~MPa across the cell, which is what was observed when this was tried. The
ridge is the particle whose field is measured; the layer only closes the
cell. The interatomic potential is not modified.""")

EN["maintained"] = (
    r"""In the \emph{maintained} case each inclusion atom is held at its displaced
position by a stiff spring (stiffness 20~eV/\AA$^{2}$, which keeps the atom
within about 0.01~\AA{} of that position) while the matrix relaxes around
it, so that the inclusion holds the strain of Eq.~(\ref{eq:eigenstrain})
throughout. The springs are attached in the same way in the corresponding
control cell, so they cancel in the difference between the two. This cell
gives the stress field of an inclusion that maintains its eigenstrain.""",
    r"""In the \emph{maintained} case every inclusion atom---the ridge at its
displaced position, the flat layer at its original one---is held by a stiff
spring (stiffness 20~eV/\AA$^{2}$, which keeps the atom within about
0.01~\AA{} of that position) while the matrix relaxes around it, so that the
ridge holds the strain of Eq.~(\ref{eq:eigenstrain}) throughout. The springs
are attached in the same way in the corresponding control cell, so they
cancel in the difference between the two. This cell gives the stress field
of a particle that maintains its eigenstrain.""")

EN["sec4"] = (
    r"""Two comparisons follow, and both point the same way. If the 147~MPa of
Ref.~\cite{Friha2024JMMM} were the resolved shear stress acting on the
dislocations, Eq.~(\ref{eq:bridge}) would predict enhancements from
$5.5\times10^{2}$ to $2.2\times10^{46}$ (third column), at least
$2.2\times10^{3}$ times the observed 0.25---more than three orders of
magnitude too large; 147~MPa acting as a shear stress is incompatible with
the observed enhancement. At the other end, an inclusion bonded to the matrix
and strained by $10^{-4}$---the upper end of the strain measured for
iron--aluminium alloys under field \cite{Hall1959,BormioNunes2012}---produces
in the matrix a stress no larger than $2\mu_{\mathrm{Al}}\times10^{-4}=5.3$~MPa,
with $\mu_{\mathrm{Al}}=26.5$~GPa the shear modulus of aluminium, and the
exact solution for a bonded sphere gives at most 2.4~MPa of resolved shear
just outside it (Fig.~\ref{fig:rss}). Taking the whole 5.3~MPa as resolved
shear---an upper bound deliberately favourable to the mechanism, since only a
part of the interface stress acts in any one slip plane---Eq.~(\ref{eq:bridge})
predicts an enhancement of 0.033--3.17\% depending on $V^{*}$ (last two
columns): short of the observed 25\% by a factor of 8--760, or, in terms of
stress, short of the required $\tau_m$ by a factor of 1.6--12. An inclusion
of realistic strain therefore cannot raise the creep rate by 25\%, neither by
exceeding the yield stress of the matrix nor by biasing thermally activated
glide.""",
    r"""Three comparisons follow. If the 147~MPa of Ref.~\cite{Friha2024JMMM} were
the resolved shear stress acting on the dislocations, Eq.~(\ref{eq:bridge})
would predict enhancements from $6.8\times10^{2}$ to $2.7\times10^{46}$
(third column), at least $2.7\times10^{3}$ times the observed 0.25; 147~MPa
acting as a shear stress is incompatible with the observed enhancement. The
stress that an inclusion strained by 0.194\% actually produces is smaller.
For a bonded sphere held at that strain the exact solution \cite{Eshelby1957}
gives 41~MPa of resolved shear at its surface (Section~\ref{sec:sigma_r});
with this amplitude Eq.~(\ref{eq:bridge}) gives 0.045 at $V^{*}=19\,b^{3}$,
0.31 at $30\,b^{3}$ and values far above 0.25 at larger $V^{*}$ (fourth
column). The ridge of the interface cell, held at the same strain, produces
«RIDGE_PEAK»~MPa of resolved shear just above its crest
(Section~\ref{sec:sigma_r}); with this amplitude the estimate gives
«ENH_RIDGE_50» at $V^{*}=50\,b^{3}$ and «ENH_RIDGE_70» at $70\,b^{3}$, the
activation volume measured for Al--Mg--Si \cite{Soula2022JALCOM} (last
column). At a strain of 0.194\%, therefore, the stress around the inclusions
is of the order the estimate requires: the observed 0.25 is reproduced for
$V^{*}$ between about «VSTAR_LO» and «VSTAR_HI»$\,b^{3}$, depending on which
of the two amplitudes is taken.

This is a consistency, not a confirmation, for three reasons. The estimate
is exponentially sensitive to the product $V^{*}\tau_m$: doubling $V^{*}$ at
fixed amplitude moves the prediction by two to four orders of magnitude, so
the agreement fixes little beyond the order of magnitude. The strain of
0.194\% is an input taken from the earlier estimate of the interface stress
\cite{Friha2024JMMM}, not a measured property of the inclusions; the
magnetostriction measured for bulk iron--aluminium alloys does not exceed
$10^{-4}$ \cite{Hall1959,BormioNunes2012}, twenty times less, and since the
stress is proportional to the strain an inclusion strained by $10^{-4}$ would
produce at most 2~MPa at its surface, for which Eq.~(\ref{eq:bridge}) gives
an enhancement below 0.4\% at every $V^{*}$ in the range. And the estimate
describes a field that exists while the inclusion is strained; it says
nothing about the tens of minutes for which the effect persists after the
field is removed (Section~\ref{sec:memory}). Whether the inclusions of this
alloy strain by 0.194\% in a field of 0.7~T is therefore the question on
which the elastic mechanism stands or falls, and it is an experimental one.""")

EN["sec51"] = (
    r"""The second is what
a bonded elastic inclusion of realistic strain can supply. An inclusion
strained by $10^{-4}$ and bonded to the matrix---no sliding at the interface:
the atoms on both sides interact through the same potential, and no artificial
constraint is applied there---produces a matrix stress of at most
$2\mu_{\mathrm{Al}}\times10^{-4}=5.3$~MPa, and the exact solution for a bonded
sphere \cite{Eshelby1957} gives at most 2.4~MPa of resolved shear just outside
it (Fig.~\ref{fig:rss}). The third is the field measured in the cell: at the
imposed strain of 0.194\%, the strain corresponding to the claimed 147~MPa
(Section~\ref{sec:eigenstrain}), the resolved shear stress in the matrix
peaks at 6.3~MPa at $r=30$~\AA{} and averages $0.5\pm0.6$~MPa beyond
60~\AA{} (Section~\ref{sec:sigma_r}). Because only $0.30\pm0.10$ of the
imposed strain remains once the atoms have relaxed, this is the relaxed
response of the cell, not the field of a strain held fixed, and it is not used
as the physical amplitude; the amplitude entered in Eq.~(\ref{eq:bridge}) is
the 5.3~MPa bound.""",
    r"""The second is what
a bonded elastic inclusion strained by 0.194\% supplies. The exact solution
for a bonded sphere \cite{Eshelby1957}---no sliding at the interface: the
atoms on both sides interact through the same potential, and no artificial
constraint is applied there---gives 41~MPa of resolved shear at its surface,
falling as $(a/r)^{3}$ outside (Fig.~\ref{fig:rss}). The third is the field
measured in the cell for the same strain held fixed
(Section~\ref{sec:sigma_r}): «RIDGE_PEAK»~MPa of resolved shear just above
the crest of the ridge, falling to the far-field level of «FAR»~MPa within
«DECAY»~\AA{}; averaged over the width of the cell the peak is
«RIDGE_WIDTHAVG»~MPa, because the ridge occupies less than half of that
width. The second and the third stress are of one order and together
bracket the amplitude entered in Eq.~(\ref{eq:bridge}). The first exceeds
them by a factor of 3.5--7 because $E\varepsilon$ is the stress of a rod held
at that strain, not of an inclusion embedded in a matrix that deforms with
it.""")

EN["sec52"] = (
    r"""At 5.3~MPa the corresponding size is about 1.4~$\mu$m, and at 2.4~MPa at
least 3.2~$\mu$m.""",
    r"""At 41~MPa the corresponding size is about 0.2~$\mu$m, and at «RIDGE_PEAK»~MPa
about «BOW_RIDGE»~$\mu$m.""")

EN["sec54"] = (
    r"""Equation~(\ref{eq:bridge}) takes
its spatial statistics from the three-dimensional solution for a compact
particle, and its amplitude, 5.3~MPa, from the upper bound
$2\mu_{\mathrm{Al}}\times10^{-4}$---not from the ridge cell, which tests the
atomistic geometry and the decay length but does not supply that amplitude. A
three-dimensional elastic calculation of the amplitude for a compact
particle, analytical or by finite elements, would strengthen the estimate.
Because the ridge of the cell (its strain relaxed) and the sphere of
Fig.~\ref{fig:rss} (its strain held fixed) are not strained by the same
source, their separation in that figure sets neither an upper nor a lower
bound on the effect of geometry.""",
    r"""Equation~(\ref{eq:bridge}) takes
its spatial statistics from the three-dimensional solution for a compact
particle and its amplitude either from that solution (41~MPa) or from the
ridge cell («RIDGE_PEAK»~MPa); the two differ by a factor of about
«RATIO_SPHERE_RIDGE», which is the effect of the geometry and is carried
through Table~\ref{tab:bridge} as the difference between its last two
columns. A two-dimensional elastic calculation for the ridge alone, with
the same strain and elastic constants but in an unbounded matrix of the same
stiffness, gives «CONT_RIDGE»~MPa at the ridge surface falling to 5~MPa
within 10~\AA{}; the atomistic ridge, held rigid on its rigid layer, gives a
smaller surface value and a flatter profile. The atomistic and the continuum
description of the ridge thus agree in magnitude, and the difference from
the sphere is geometric, not an artefact of the cell.""")

EN["memory_label"] = (r"\subsection{The memory protocol}", "\\subsection{The memory protocol}\n\\label{sec:memory}")

# ----------------------------------------------------------------- RU texts
RU = {}
RU["e_al"] = (
    r"""$\sigma_m/E_{\mathrm{Al}}$, отвечающую оценённому в этих работах напряжению""",
    r"""$\sigma_m/E_{\mathrm{Al}}$ (при $E_{\mathrm{Al}} = 75{,}7$~ГПа), отвечающую оценённому в этих работах напряжению""")

RU["held"] = (
    r"""Жёсткость пружин 20~эВ/\AA$^{2}$; под действием сил, возникающих на
границе, атомы включения отходят от заданных положений примерно на
0{,}01~\AA{}, так что включение сохраняет почти всю наложенную деформацию
(раздел~3.1).
%%NUM:held-eta""",
    r"""Под действием сил, возникающих на границе, атомы включения отходят от
заданных положений примерно на 0{,}01~\AA{}, и гребень сохраняет
«ETA_HELD_RU» наложенной деформации (измерено так же, как описано ниже для
свободного варианта).""")

RU["free"] = (
    r"""В \emph{свободном} варианте пружин нет, и включение вольно снять наложенную
деформацию. В значительной мере оно так и делает: после минимизации гребень,
который и создаёт измеряемое в матрице поле, сохраняет $0{,}30 \pm 0{,}10$
наложенной деформации (плоский слой под ним, стеснённый периодичностью, ---""",
    None)  # handled with a regex below: the paragraph continues with numbers we replace wholesale

RU["applied"] = (
    r"""Деформация задаётся смещением каждого атома включения относительно центра
включения пропорционально его положению,
$\mathbf{r} \rightarrow \mathbf{r} + \varepsilon^{*}\!\cdot\!\mathbf{r}$, что
однородно растягивает включение вдоль $\mathbf{u}$ и сжимает поперёк
$\mathbf{u}$. Межатомный потенциал не изменяется.""",
    r"""Деформация задаётся смещением каждого атома гребня относительно центра
гребня пропорционально его положению,
$\mathbf{r} \rightarrow \mathbf{r} + \varepsilon^{*}\!\cdot\!\mathbf{r}$, что
однородно растягивает гребень вдоль $\mathbf{u}$ и сжимает поперёк
$\mathbf{u}$. Плоский слой под гребнем оставлен недеформированным. Он
проходит через всю периодическую ячейку, а слой, периодичный в своей
плоскости, нельзя когерентно сдвинуть: удерживаемый при сдвиге формулы~(1),
он имел бы поверхность в виде пилы со ступенькой
$\varepsilon^{*}_{xz}L_x = 0{,}22$~\AA{} на границе ячейки, и весь слой
алюминия над ним оказался бы растянут вдоль $z$ примерно на
$\varepsilon^{*}_{xz}$ --- напряжение порядка 150~МПа по всей ячейке, что и
наблюдалось при такой попытке. Гребень --- та частица, поле которой
измеряется; слой лишь замыкает ячейку. Межатомный потенциал не изменяется.""")

RU["maintained"] = (
    r"""В варианте \emph{с удерживаемой деформацией} каждый атом включения
удерживается в смещённом положении жёсткой пружиной (жёсткость
20~эВ/\AA$^{2}$, что удерживает атом в пределах примерно 0{,}01~\AA{} от
этого положения), пока матрица релаксирует вокруг него, так что включение
сохраняет деформацию~(1) на всём протяжении расчёта. В соответствующей
контрольной ячейке пружины подключены точно так же, поэтому в разности двух
ячеек они сокращаются. Эта ячейка даёт поле напряжений включения,
поддерживающего свою собственную деформацию.""",
    r"""В варианте \emph{с удерживаемой деформацией} каждый атом включения ---
гребень в смещённом положении, плоский слой в исходном --- удерживается
жёсткой пружиной (жёсткость 20~эВ/\AA$^{2}$, что удерживает атом в пределах
примерно 0{,}01~\AA{} от этого положения), пока матрица релаксирует вокруг
него, так что гребень сохраняет деформацию~(1) на всём протяжении расчёта. В
соответствующей контрольной ячейке пружины подключены точно так же, поэтому
в разности двух ячеек они сокращаются. Эта ячейка даёт поле напряжений
частицы, поддерживающей свою собственную деформацию.""")

RU["sec4"] = (
    r"""Далее следуют два сопоставления, и оба ведут в одну сторону. Если бы
147~МПа работы [5] были разрешённым касательным напряжением, действующим на
дислокации, соотношение~(2) предсказало бы усиление от $5{,}5\cdot10^{2}$ до
$2{,}2\cdot10^{46}$ (третий столбец), то есть по меньшей мере в
$2{,}2\cdot10^{3}$ раза больше наблюдаемых 0{,}25 --- более трёх порядков;
147~МПа в роли касательного напряжения несовместимы с наблюдаемым усилением.
С другой стороны, включение, сцепленное с матрицей и деформированное на
$10^{-4}$ --- верхняя граница деформации, измеренной для сплавов
железо--алюминий в поле [11,\,12], --- создаёт в матрице напряжение не более
$2\mu_{\mathrm{Al}}\cdot10^{-4} = 5{,}3$~МПа при модуле сдвига алюминия
$\mu_{\mathrm{Al}} = 26{,}5$~ГПа, а точное решение для сцепленной сферы даёт
непосредственно вне её не более 2{,}4~МПа разрешённого сдвига
(рис.~\ref{fig:rss}). Подстановка всех 5{,}3~МПа как разрешённого сдвига ---
верхняя оценка, заведомо благоприятная для механизма, поскольку в любой
плоскости скольжения действует лишь часть межфазного напряжения, --- даёт
по~(2) усиление 0{,}033--3{,}17\% в зависимости от $V^{*}$ (два последних
столбца): в 8--760 раз меньше наблюдаемых 25\%, или, в терминах напряжения,
в 1{,}6--12 раз меньше требуемого $\tau_m$. Включение с реалистичной
деформацией, следовательно, не способно повысить скорость ползучести на 25\%
ни превышением предела текучести матрицы, ни смещением термически
активированного скольжения.""",
    r"""Далее следуют три сопоставления. Если бы 147~МПа работы [5] были
разрешённым касательным напряжением, действующим на дислокации,
соотношение~(2) предсказало бы усиление от $6{,}8\cdot10^{2}$ до
$2{,}7\cdot10^{46}$ (третий столбец), то есть по меньшей мере в
$2{,}7\cdot10^{3}$ раза больше наблюдаемых 0{,}25; 147~МПа в роли
касательного напряжения несовместимы с наблюдаемым усилением. Напряжение,
которое включение, деформированное на 0{,}194\%, создаёт в действительности,
меньше. Для сцепленной сферы, удерживаемой при этой деформации, точное
решение [7] даёт 41~МПа разрешённого сдвига на её поверхности
(раздел~3.1); при такой амплитуде соотношение~(2) даёт 0{,}045 при
$V^{*} = 19\,b^{3}$, 0{,}31 при $30\,b^{3}$ и значения, далеко превышающие
0{,}25, при больших $V^{*}$ (четвёртый столбец). Гребень ячейки границы,
удерживаемый при той же деформации, создаёт непосредственно над своей
вершиной «RIDGE_PEAK_RU»~МПа разрешённого сдвига (раздел~3.1); при такой
амплитуде оценка даёт «ENH_RIDGE_50_RU» при $V^{*} = 50\,b^{3}$ и
«ENH_RIDGE_70_RU» при $70\,b^{3}$ --- активационном объёме, измеренном для
Al--Mg--Si [17] (последний столбец). При деформации 0{,}194\%, таким
образом, напряжение вокруг включений имеет тот порядок, которого требует
оценка: наблюдаемые 0{,}25 воспроизводятся при $V^{*}$ примерно от
«VSTAR_LO» до «VSTAR_HI»$\,b^{3}$ в зависимости от того, какая из двух
амплитуд взята.

Это согласованность, а не подтверждение, по трём причинам. Оценка
экспоненциально чувствительна к произведению $V^{*}\tau_m$: удвоение $V^{*}$
при фиксированной амплитуде сдвигает предсказание на два--четыре порядка,
так что согласие фиксирует немногим больше порядка величины. Деформация
0{,}194\% --- входная величина, взятая из прежней оценки межфазного
напряжения [5], а не измеренное свойство включений; магнитострикция,
измеренная для объёмных сплавов железо--алюминий, не превышает $10^{-4}$
[11,\,12], то есть в двадцать раз меньше, и, поскольку напряжение
пропорционально деформации, включение с деформацией $10^{-4}$ создало бы на
своей поверхности не более 2~МПа, для которых соотношение~(2) даёт усиление
менее 0{,}4\% при любом $V^{*}$ из интервала. Наконец, оценка описывает
поле, существующее, пока включение деформировано; она ничего не говорит о
десятках минут, в течение которых эффект сохраняется после снятия поля
(раздел~5.3). Деформируются ли включения этого сплава на 0{,}194\% в поле
0{,}7~Тл --- вопрос, на котором упругий механизм стоит или падает, и вопрос
этот экспериментальный.""")

RU["sec51"] = (
    r"""Второе --- то, что способно дать упругое включение реалистичной деформации,
сцепленное с матрицей. Включение, деформированное на $10^{-4}$ и сцепленное с
матрицей --- без проскальзывания по границе: атомы по обе её стороны
взаимодействуют через один и тот же потенциал, и никакого искусственного
ограничения на границе нет, --- создаёт в матрице напряжение не более
$2\mu_{\mathrm{Al}}\cdot10^{-4} = 5{,}3$~МПа, а точное решение для сцепленной
сферы [7] даёт непосредственно вне её не более 2{,}4~МПа разрешённого сдвига
(рис.~\ref{fig:rss}). Третье --- поле, измеренное в ячейке: при наложенной
деформации 0{,}194\%, отвечающей заявленным 147~МПа (раздел~2.2),
разрешённое касательное напряжение в матрице достигает 6{,}3~МПа при
$r = 30$~\AA{} и в среднем составляет $0{,}5 \pm 0{,}6$~МПа за 60~\AA{}
(раздел~3.1). Поскольку после релаксации атомов от наложенной деформации
остаётся лишь $0{,}30 \pm 0{,}10$, это релаксированный отклик ячейки, а не
поле удерживаемой деформации; как физическая амплитуда он не используется ---
в соотношение~(2) подставляется верхняя оценка 5{,}3~МПа.""",
    r"""Второе --- то, что даёт упругое включение, деформированное на 0{,}194\% и
сцепленное с матрицей. Точное решение для сцепленной сферы [7] --- без
проскальзывания по границе: атомы по обе её стороны взаимодействуют через
один и тот же потенциал, и никакого искусственного ограничения на границе
нет, --- даёт 41~МПа разрешённого сдвига на её поверхности со спадом
$(a/r)^{3}$ снаружи (рис.~\ref{fig:rss}). Третье --- поле, измеренное в
ячейке при той же удерживаемой деформации (раздел~3.1):
«RIDGE_PEAK_RU»~МПа разрешённого сдвига непосредственно над вершиной гребня
со спадом до уровня дальнего поля «FAR_RU»~МПа в пределах «DECAY»~\AA{}; в
среднем по ширине ячейки максимум составляет «RIDGE_WIDTHAVG_RU»~МПа,
поскольку гребень занимает меньше половины этой ширины. Второе и третье
напряжения одного порядка и вместе ограничивают амплитуду, подставляемую в
соотношение~(2). Первое превышает их в 3{,}5--7 раз, потому что
$E\varepsilon$ --- напряжение стержня, удерживаемого при такой деформации, а
не включения, окружённого матрицей, которая деформируется вместе с ним.""")

RU["sec52"] = (
    r"""При 5{,}3~МПа соответствующий
размер составляет около 1{,}4~мкм, при 2{,}4~МПа --- не менее 3{,}2~мкм.""",
    r"""При 41~МПа соответствующий
размер составляет около 0{,}2~мкм, при «RIDGE_PEAK_RU»~МПа --- около
«BOW_RIDGE_RU»~мкм.""")

RU["sec54"] = (
    r"""Соотношение~(2) берёт
пространственную статистику из трёхмерного решения для компактной частицы, а
амплитуду 5{,}3~МПа --- из верхней оценки $2\mu_{\mathrm{Al}}\cdot10^{-4}$,
а не из ячейки с гребнем: та проверяет атомистическую геометрию и длину
затухания, но этой амплитуды не даёт. Трёхмерный упругий расчёт амплитуды для
компактной частицы --- аналитический или методом конечных элементов --- усилил
бы оценку. Поскольку гребень ячейки (с релаксировавшей деформацией) и сфера
рис.~\ref{fig:rss} (с удерживаемой) не деформированы одним и тем же
источником, их расхождение на рисунке не устанавливает ни верхней, ни нижней
границы влияния геометрии.""",
    r"""Соотношение~(2) берёт
пространственную статистику из трёхмерного решения для компактной частицы, а
амплитуду --- либо из того же решения (41~МПа), либо из ячейки с гребнем
(«RIDGE_PEAK_RU»~МПа); эти значения различаются примерно в
«RATIO_SPHERE_RIDGE_RU» раза, что и есть влияние геометрии, и это различие
проходит через табл.~\ref{tab:bridge} как разница двух её последних
столбцов. Двумерный упругий расчёт для одного гребня с теми же деформацией и
упругими постоянными, но в неограниченной матрице той же жёсткости, даёт
«CONT_RIDGE_RU»~МПа у поверхности гребня со спадом до 5~МПа в пределах
10~\AA{}; атомистический гребень, жёстко удерживаемый на жёстком слое, даёт
меньшее значение у поверхности и более пологий профиль. Атомистическое и
континуальное описания гребня, таким образом, согласуются по величине, а
отличие от сферы --- геометрическое, а не артефакт ячейки.""")

RU_FREE_NEW = r"""В \emph{свободном} варианте пружин нет, и включение вольно снять наложенную
деформацию. Оно снимает её почти полностью: после минимизации гребень,
который и создаёт измеряемое в матрице поле, сохраняет «ETA_FREE_RU»
наложенной деформации. Доля измеряется как проекция остаточного искажения
Fe-подрешётки включения на $\varepsilon^{*}$, найденного подгонкой смещений
между деформированной и контрольной ячейками методом наименьших квадратов;
погрешность --- стандартная ошибка этой подгонки. Свободный вариант
показывает, что делает включение, когда его деформацию ничто не удерживает;
его поле напряжений --- релаксированный отклик, а не поле включения,
поддерживающего деформацию, и с порогами движения дислокаций ниже
сопоставляется удерживаемый вариант."""


def patch_file(name: str, edits: dict, num: dict, todo_remove=()) -> None:
    p = DR / name
    t = io.open(p, encoding="utf-8").read()
    rep: list = []
    for tag, (old, new) in edits.items():
        if new is None:
            continue
        t = sub(t, old, fill(new, num), tag, rep)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("%-20s unmatched: %s" % (name, rep if rep else "none"))


def patch_ru_free(num: dict) -> None:
    p = DR / "Section_2_ru.tex"
    t = io.open(p, encoding="utf-8").read()
    start = t.find(r"В \emph{свободном} варианте пружин нет")
    end = t.find(r"\emph{Контрольная}", start)
    if start < 0 or end < 0:
        # the control paragraph may start differently; fall back to the next blank line pair
        end = t.find("\n\n", start)
        end = t.find("\n\n", end + 2) if end > 0 else -1
    if start < 0 or end < 0:
        print("Section_2_ru.tex      free paragraph NOT found")
        return
    # keep the paragraph boundary: replace up to the blank line before the next paragraph
    seg_end = t.rfind("\n\n", start, end)
    t = t[:start] + fill(RU_FREE_NEW, num) + t[seg_end:]
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("Section_2_ru.tex     free paragraph replaced")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--numbers", type=Path, required=True)
    args = ap.parse_args()
    num = json.loads(args.numbers.read_text(encoding="utf-8"))
    missing = [k for k in KEYS if k not in num]
    if missing:
        raise SystemExit("numbers file lacks: " + ", ".join(missing))
    patch_file("Section_2_en.tex", {k: EN[k] for k in ("e_al", "applied", "maintained", "held", "free")}, num)
    patch_file("Sections_4_en.tex", {k: EN[k] for k in ("sec4", "sec51", "sec52", "sec54", "memory_label")}, num)
    patch_file("Section_2_ru.tex", {k: RU[k] for k in ("e_al", "applied", "maintained", "held")}, num)
    patch_ru_free(num)
    patch_file("Sections_4_ru.tex", {k: RU[k] for k in ("sec4", "sec51", "sec52", "sec54")}, num)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
