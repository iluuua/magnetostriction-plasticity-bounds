#!/usr/bin/env python3
"""Round 3: thresholds from the unified loaded cell (stage G15), the no-load
test (stage G16), and every passage that depends on them - abstract,
Section 3.2 (rewritten), the 3.3 and 5.1 comparisons, Conclusions - in EN
and RU; plus README.md.

    python patch_round3.py --numbers numbers_round3.json

Keys (all strings, LaTeX-ready; *_RU with decimal commas):
  UPPER_JUMP_CTL, LOWER_JUMP_CTL   initial excursions at zero stress (A)
  TAU_MOVE_CTL_RANGE               lower-partner onset, control, e.g. "95--105"
  TAU_UPPER_CTL_RANGE              upper-partner departure, control
  TAU_GONE_CTL                     stress by which both lines are gone
  TAU_NUC_TXT / TAU_NUC_TXT_RU     sentence(s) on nucleation up to the end of the ramp
  FLD_PARA / FLD_PARA_RU           paragraph on the strained cell (G15 fld)
  TAU_SHIFT_TXT / TAU_SHIFT_TXT_RU clause after "what it does is bias the pair:"
  G16_TXT / G16_TXT_RU             sentence(s) on the no-load test
  TAU_MOVE                         short form for abstract/conclusions, e.g. "95--105"
  NUC_ABS / NUC_ABS_RU             short nucleation clause for the abstract
  NUC_CONCL / NUC_CONCL_RU         nucleation clause for the conclusions
  RATIO_MOVE(_RU), RATIO_NUC_TXT(_RU), RATIO_PIN(_RU)
  RIDGE_PEAK(_RU), DECAY, VSTAR_LO, VSTAR_HI, FAR(_RU), RIDGE_WIDTHAVG(_RU)
  README_ONSET, README_ONSET_RU, README_G16, README_G16_RU
"""
from __future__ import annotations
import argparse, io, json, re
from pathlib import Path

DR = Path(__file__).resolve().parent
PAPER = DR.parent
REPO = PAPER.parents[1]


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


def replace_block(text, start_marker, end_marker, new, tag, report):
    i = text.find(start_marker)
    j = text.find(end_marker, i + 1) if i >= 0 else -1
    if i < 0 or j < 0:
        report.append(tag)
        return text
    return text[:i] + new + text[j:]


# ------------------------------------------------------------------ abstract
ABSTRACT_EN = r"""\begin{abstract}
How pre-exposing an Al--Mg--Si alloy with Al$_{13}$Fe$_4$ inclusions to a
static magnetic field affects plastic deformation in uniaxial creep is
examined by molecular dynamics. The inclusion is elongated along the field by
0.194\%, the strain corresponding to the 147~MPa interface stress estimated in
earlier experiments, and is held at that strain while the matrix relaxes.
Computed are the stress at the interface, its decay into the matrix and the
stresses at which dislocations move and nucleate. The resolved shear stress in
the matrix reaches «RIDGE_PEAK»~MPa at the inclusion and falls to the
far-field level within «DECAY»~\AA{}; for a compact particle the analytical
solution gives 41~MPa at its surface. Under shear, a pre-existing dislocation
pair is torn apart from «TAU_MOVE»~MPa, «NUC_ABS», and Mg/Si atoms hold a
dislocation through 75~MPa. A two-scale estimate reproduces the measured 25\%
creep increase with the computed stresses for activation volumes of
«VSTAR_LO»--«VSTAR_HI»$\,b^{3}$, provided the inclusions strain by 0.194\%;
the magnetostriction measured for Fe--Al alloys is twenty times smaller, and
the persistence of the effect after the field is removed is not explained by
an elastic stress.
\end{abstract}"""

ABSTRACT_RU = r"""\noindent\textbf{Аннотация.}
Методом молекулярной динамики исследуется, как предварительная выдержка
сплава Al--Mg--Si с включениями Al$_{13}$Fe$_4$ в постоянном магнитном поле
влияет на пластическую деформацию при одноосной ползучести. Включение
удлинено вдоль поля на 0{,}194\% --- деформация, отвечающая оценённому в
ранних экспериментах межфазному напряжению 147~МПа, --- и удерживается при
этой деформации, пока матрица релаксирует. Рассчитаны напряжение на границе,
его спад в матрице и напряжения, при которых дислокации движутся и
зарождаются. Разрешённое касательное напряжение в матрице достигает у
включения «RIDGE_PEAK_RU»~МПа и спадает до уровня дальнего поля в пределах
«DECAY»~\AA{}; для компактной частицы аналитическое решение даёт 41~МПа на её
поверхности. При сдвиговом нагружении существующая пара дислокаций
разрывается начиная с «TAU_MOVE»~МПа, «NUC_ABS_RU», а атомы Mg и Si удерживают
дислокацию вплоть до 75~МПа. Двухмасштабная оценка воспроизводит
наблюдаемый прирост ползучести 25\% при рассчитанных напряжениях для
активационных объёмов «VSTAR_LO»--«VSTAR_HI»$\,b^{3}$ --- при условии, что
включения действительно деформируются на 0{,}194\%; измеренная
магнитострикция сплавов Fe--Al в двадцать раз меньше, а сохранение эффекта
после снятия поля упругим напряжением не объясняется."""

# ------------------------------------------------------------------ Section 3.2 (whole subsection up to Fig. 4)
S32_EN = r"""\subsection{Thresholds for dislocation activity at the interface}
\label{sec:thresholds}

The stresses at which dislocations respond were measured in the loaded cell
of Section~\ref{sec:loading}, which contains the same ridge together with a
pre-existing pair of edge dislocations of opposite sign (a dislocation
dipole) on glide planes parallel to the interface, under an applied shear
stress rising linearly from 0 to 400~MPa in 96~ps (Fig.~\ref{fig:loading}).
The position of each dislocation was followed frame by frame, every 2~ps, by
dislocation analysis. The onset of motion is defined as the stress at which
the position departs from its thermal oscillation by more than six times the
oscillation amplitude (and by at least 8~\AA{}) and does not return, either
because the line keeps moving or because it ceases to exist. One frame of the
ramp corresponds to 9~MPa, which is the resolution of every onset quoted.

In the control cell, with the ridge unstrained and the inclusion free to
relax during loading, the two partners behave differently from the start. The upper partner sits 32~\AA{} above the crest
of the ridge, in the coherency stress of the interface
(Section~\ref{sec:sigma_r}); it is not at rest at the position where it was
placed and glides «UPPER_JUMP_CTL»~\AA{} away from the ridge within the first
6~ps, at zero applied stress, after which it hovers within a few {\aa}ngstr\"om
of its new position. The lower partner, 27~\AA{} beyond the foot of the ridge,
settles by «LOWER_JUMP_CTL»~\AA{} in the same interval and then holds. It
starts to move at an applied shear of «TAU_MOVE_CTL_RANGE»~MPa, crosses the
periodic boundary of the cell and within the next 2~ps is no longer
recognised as a dislocation line: it has reacted with the interface. The
upper partner, now unopposed, departs at «TAU_UPPER_CTL_RANGE»~MPa and is
gone in the same way by «TAU_GONE_CTL»~MPa. «TAU_NUC_TXT»

«FLD_PARA»

«G16_TXT» All onsets are specific to this cell, to the single loading rate
of order $10^{8}$~s$^{-1}$ (relative to quasistatic loading they are upper
estimates), and to the interatomic potential; they are not material
constants. The stress at which the lower partner breaks away,
«TAU_MOVE_CTL_RANGE»~MPa, is of the order of the attraction between the two
partners at their separation ($\mu b/[8\pi(1-\nu)h]=198$~MPa for
$h=23.4$~\AA{}, Section~\ref{sec:loading}), reduced by the coherency field
that has already pulled them apart; it lies below the macroscopic yield
stress of the alloy, 120~MPa, because a pre-existing dislocation in a perfect
matrix has nothing but its partner to hold it.

Set against these onsets on the common footing of resolved shear stress, the
stress that the held ridge produces just above its crest, 15~MPa
(Section~\ref{sec:sigma_r}), is a factor of «RATIO_MOVE» below the stress at
which the lower partner starts to move and «RATIO_NUC_TXT», and it falls to
the far-field level within 80~\AA{} of the inclusion. The strained ridge
therefore neither moves the pair nor creates dislocations by itself, and
its bias on the pair is «TAU_SHIFT_TXT» (Section~\ref{sec:sigma_r} gives
5--10~MPa at the position of the pair). Figure~\ref{fig:rss} places the
stress profiles and the onsets on one plot.

"""

S32_RU = r"""\subsection{Пороги дислокационной активности на границе}

Напряжения, при которых дислокации откликаются, измерены в нагружаемой
ячейке раздела~2.3, содержащей тот же гребень и заранее введённую пару
краевых дислокаций противоположного знака (дислокационный диполь) в
плоскостях скольжения, параллельных границе, при приложенном сдвиговом
напряжении, линейно растущем от 0 до 400~МПа за 96~пс
(рис.~\ref{fig:loading}). Положение каждой дислокации прослеживалось кадр за
кадром, каждые 2~пс, дислокационным анализом. Порогом движения принято
напряжение, при котором положение отклоняется от тепловых колебаний более
чем на шесть их амплитуд (и не менее чем на 8~\AA{}) и уже не возвращается
--- потому ли, что линия продолжает двигаться, или потому, что она
перестаёт существовать. Один кадр рампы отвечает 9~МПа; такова разрешающая
способность каждого приводимого порога.

В контрольной ячейке, с недеформированным гребнем и включением, свободно
релаксирующим при нагружении, два партнёра с самого начала ведут себя
по-разному. Верхний партнёр находится в 32~\AA{} над
вершиной гребня, в поле напряжения когерентности границы (раздел~3.1); в
том положении, куда он помещён, он не находится в покое и за первые 6~пс при
нулевом приложенном напряжении уходит от гребня на «UPPER_JUMP_CTL»~\AA{},
после чего колеблется в пределах нескольких ангстрем около нового положения.
Нижний партнёр, в 27~\AA{} за подножием гребня, за то же время смещается на
«LOWER_JUMP_CTL»~\AA{} и затем стоит. Он приходит в движение при приложенном
сдвиге «TAU_MOVE_CTL_RANGE»~МПа, пересекает периодическую границу ячейки и в
течение следующих 2~пс перестаёт распознаваться как дислокационная линия:
он прореагировал с границей. Верхний партнёр, оставшись без противовеса,
уходит при «TAU_UPPER_CTL_RANGE»~МПа и тем же путём исчезает к
«TAU_GONE_CTL»~МПа. «TAU_NUC_TXT_RU»

«FLD_PARA_RU»

«G16_TXT_RU» Все пороги относятся к данной ячейке, к единственной скорости
нагружения порядка $10^{8}$~с$^{-1}$ (относительно квазистатического
нагружения они являются верхними оценками) и к использованному межатомному
потенциалу; константами материала они не являются. Напряжение, при котором
отрывается нижний партнёр, «TAU_MOVE_CTL_RANGE»~МПа, --- порядка притяжения
двух партнёров при их расстоянии ($\mu b/[8\pi(1-\nu)h] = 198$~МПа при
$h = 23{,}4$~\AA{}, раздел~2.3), ослабленного полем когерентности, которое
уже развело их; оно лежит ниже макроскопического предела текучести сплава
120~МПа, потому что существующую дислокацию в совершенной матрице не держит
ничто, кроме её партнёра.

Если сопоставить эти пороги с результатами раздела~3.1 на общем основании
разрешённого касательного напряжения, то напряжение, которое удерживаемый
гребень создаёт непосредственно над своей вершиной, 15~МПа (раздел~3.1), в
«RATIO_MOVE_RU» раза меньше напряжения, при котором нижний партнёр приходит в
движение, и «RATIO_NUC_TXT_RU», а до уровня дальнего поля оно спадает в
пределах 80~\AA{} от включения. Деформированный гребень, таким образом, сам
по себе не сдвигает пару и не создаёт дислокаций, а его влияние на порог
пары --- «TAU_SHIFT_TXT_RU» (раздел~3.1 даёт 5--10~МПа в месте расположения
пары). Рис.~\ref{fig:rss} сводит профили напряжений и пороги на одном
графике.

"""

# ------------------------------------------------------------------ Section 3.3 comparison
S33_EN_OLD = r"""This exceeds the 2.4~MPa of the
analytical solution at $1.0\times10^{-4}$ by a factor of at least 31. The
two dislocations of the pair exert a mutual stress of 22~MPa on each other,
whose sign relative to the applied shear is not resolved here, so the
conservative reading of the bound is $75\pm22$~MPa, with a lower edge of
53~MPa---a factor of 22 above the 2.4~MPa, which does not change the
conclusion. Even against the elastic estimate
$2\mu_{\mathrm{Al}}\varepsilon$ of 5.3~MPa---twice the shear modulus of
aluminium times the strain $1.0\times10^{-4}$, an upper estimate of the
total stress that a strain of this size can produce in the matrix, taken
without projection onto any slip system---the gap is about a factor of 14."""
S33_EN_NEW = r"""This exceeds the «RIDGE_PEAK»~MPa that the held ridge produces at its
surface (Section~\ref{sec:sigma_r}) by a factor of «RATIO_PIN», and the 41~MPa
of the analytical sphere by a factor of 1.8. The two dislocations of the pair
exert a mutual stress of 22~MPa on each other, whose sign relative to the
applied shear is not resolved here, so the conservative reading of the bound
is $75\pm22$~MPa, with a lower edge of 53~MPa, which still exceeds both
amplitudes."""

S33_RU_OLD = r"""Это превышает 2{,}4~МПа аналитического решения при
$1{,}0\cdot10^{-4}$ не менее чем в 31 раз. Две дислокации пары действуют
друг на друга взаимным напряжением 22~МПа, знак которого относительно
приложенного сдвига здесь не установлен, поэтому осторожное прочтение
границы --- $75 \pm 22$~МПа с нижним краем 53~МПа, что в 22 раза выше
2{,}4~МПа и вывода не меняет. Даже относительно упругой оценки
$2\mu_{\mathrm{Al}}\varepsilon$, равной 5{,}3~МПа, --- удвоенного модуля сдвига
алюминия, умноженного на деформацию $1{,}0\cdot10^{-4}$, то есть верхней
оценки полного напряжения, которое деформация такой величины способна
создать в матрице, взятой без проекции на какую-либо систему скольжения,
--- разрыв составляет примерно 14 раз."""
S33_RU_NEW = r"""Это превышает «RIDGE_PEAK_RU»~МПа, создаваемые удерживаемым гребнем у
своей поверхности (раздел~3.1), в «RATIO_PIN_RU» раза, а 41~МПа
аналитической сферы --- в 1{,}8 раза. Две дислокации пары действуют друг на
друга взаимным напряжением 22~МПа, знак которого относительно приложенного
сдвига здесь не установлен, поэтому осторожное прочтение границы ---
$75 \pm 22$~МПа с нижним краем 53~МПа, который всё ещё превышает обе
амплитуды."""

# ------------------------------------------------------------------ Section 5.1 threshold mention
S51_EN_OLD = r"""If it were the shear stress on
a slip plane it would exceed the 77--86~MPa at which the dislocation pair of
Section~\ref{sec:thresholds} begins to move, so the loaded cells cannot test
it by comparison with a threshold; what they test is whether a strained
inclusion produces anything of that order in the matrix."""
S51_EN_NEW = r"""If it were the shear stress on
a slip plane it would exceed the «TAU_MOVE_CTL_RANGE»~MPa at which the lower
partner of the dislocation pair of Section~\ref{sec:thresholds} breaks away,
so the loaded cells cannot test it by comparison with a threshold; what they
test is whether a strained inclusion produces anything of that order in the
matrix."""
S51_RU_OLD = r"""Будь оно касательным
напряжением в плоскости скольжения, оно превышало бы 77--86~МПа, при которых
приходит в движение дислокационная пара раздела~3.2; поэтому нагружаемые
ячейки не могут проверить эту оценку сравнением с порогом --- они проверяют,
создаёт ли деформированное включение в матрице что-либо такого порядка."""
S51_RU_NEW = r"""Будь оно касательным
напряжением в плоскости скольжения, оно превышало бы «TAU_MOVE_CTL_RANGE»~МПа,
при которых отрывается нижний партнёр дислокационной пары раздела~3.2;
поэтому нагружаемые ячейки не могут проверить эту оценку сравнением с
порогом --- они проверяют, создаёт ли деформированное включение в матрице
что-либо такого порядка."""

# ------------------------------------------------------------------ Conclusions
CONCL_EN = r"""\section{Conclusions}
\label{sec:conclusions}

The stress that a strained inclusion produces in the matrix was computed in
an Al/Al$_{13}$Fe$_4$ interface cell of 91\,428 atoms for an elongation of
the inclusion by 0.194\% along the field direction at constant volume, the
strain corresponding to the earlier estimate of 147~MPa, with the inclusion
held at that strain. The resolved shear stress in the matrix reaches
«RIDGE_PEAK»~MPa just above the inclusion and falls to the far-field level
of «FAR»~MPa within «DECAY»~\AA{}; averaged over the width of the cell the
peak is «RIDGE_WIDTHAVG»~MPa. The analytical solution for a compact particle
held at the same strain gives 41~MPa at its surface, falling as the inverse
cube of the distance, so that for a micron-sized inclusion the same field
extends over a fraction of a micron. An inclusion that is not held relaxes
most of the strain.

In the loaded cells, a pre-existing pair of dislocations next to the ridge
is torn apart at an applied shear of «TAU_MOVE_CTL_RANGE»~MPa, «TAU_SHIFT_CONCL»; «NUC_CONCL»; and a random
arrangement of Mg and Si atoms holds a dislocation through 75~MPa. «G16_TXT»
These values are specific to the cells, the loading rate and the potential
and are not material constants.

The two-scale estimate, Eq.~(\ref{eq:bridge}), requires a resolved shear
stress of 8.4--62.7~MPa at the inclusion surface to raise the creep rate by
25\% at $f=0.00246$ and $V^{*}=19$--$142\,b^{3}$. The computed amplitudes,
41~MPa for the particle and «RIDGE_PEAK»~MPa for the ridge, reproduce the
observed enhancement for $V^{*}$ of «VSTAR_LO»--«VSTAR_HI»$\,b^{3}$, a range
that contains the value measured for Al--Mg--Si; 147~MPa acting as resolved
shear would exceed the observed enhancement by a factor of at least
$2.7\times10^{3}$. The elastic mechanism is therefore quantitatively viable
if, and only if, the inclusions strain by about 0.2\% in the field: the
magnetostriction measured for bulk iron--aluminium alloys is twenty times
smaller and would give an enhancement below 0.4\%.

Because the field is off during the creep test, whatever it does must persist
for tens of minutes; an elastic strain cannot, and a slow rearrangement of
atoms is indicated as the remaining possibility---a hypothesis not tested by
the present calculations. The decisive next steps are the identification of
the ferromagnetic constituent of the inclusions, a direct measurement of their
strain under field, and a calculation in which the field is switched on, held,
switched off and the load then applied."""

CONCL_RU = r"""\section{Заключение}

Напряжение, создаваемое деформированным включением в матрице, рассчитано в
ячейке границы Al/Al$_{13}$Fe$_4$ из 91\,428 атомов при удлинении включения
вдоль направления поля на 0{,}194\% без изменения объёма --- деформации,
отвечающей прежней оценке 147~МПа, --- при удерживаемой деформации
включения. Разрешённое касательное напряжение в матрице достигает
«RIDGE_PEAK_RU»~МПа непосредственно над включением и спадает до уровня
дальнего поля «FAR_RU»~МПа в пределах «DECAY»~\AA{}; в среднем по ширине
ячейки максимум составляет «RIDGE_WIDTHAVG_RU»~МПа. Аналитическое решение
для компактной частицы, удерживаемой при той же деформации, даёт 41~МПа на
её поверхности со спадом обратно пропорционально кубу расстояния, так что для
включения микронного размера то же поле простирается на доли микрона.
Включение, которое ничто не удерживает, снимает большую часть деформации.

В нагружаемых ячейках заранее введённая пара дислокаций рядом с гребнем
разрывается при приложенном сдвиге «TAU_MOVE_CTL_RANGE»~МПа, «TAU_SHIFT_CONCL_RU»; «NUC_CONCL_RU»; а случайное
расположение атомов Mg и Si удерживает дислокацию вплоть до 75~МПа.
«G16_TXT_RU» Эти значения относятся к выбранным ячейкам, темпу нагружения и
потенциалу и не являются константами материала.

Двухмасштабная оценка~(2) требует разрешённого касательного напряжения
8{,}4--62{,}7~МПа на поверхности включения для повышения скорости
ползучести на 25\% при $f = 0{,}00246$ и $V^{*} = 19$--$142\,b^{3}$.
Рассчитанные амплитуды --- 41~МПа для частицы и «RIDGE_PEAK_RU»~МПа для
гребня --- воспроизводят наблюдаемое усиление при $V^{*}$ от «VSTAR_LO» до
«VSTAR_HI»$\,b^{3}$, то есть в интервале, содержащем значение, измеренное для
Al--Mg--Si; 147~МПа в роли разрешённого сдвига превысили бы наблюдаемое
усиление не менее чем в $2{,}7\cdot10^{3}$ раза. Упругий механизм,
следовательно, количественно состоятелен тогда и только тогда, когда
включения деформируются в поле примерно на 0{,}2\%: магнитострикция,
измеренная для объёмных сплавов железо--алюминий, в двадцать раз меньше и
дала бы усиление менее 0{,}4\%.

Поскольку во время испытания на ползучесть поле выключено, его действие
должно сохраняться десятки минут; упругая деформация на это не способна, и в
качестве оставшейся возможности указывается медленная перестройка атомов ---
гипотеза, настоящими расчётами не проверенная. Решающими дальнейшими шагами
представляются установление ферромагнитной составляющей включений, прямое
измерение их деформации в поле и расчёт, в котором поле включается,
выдерживается, выключается и лишь затем прикладывается нагрузка."""

# ------------------------------------------------------------------ README
README = r"""# Atomistic bounds on the magnetostrictive mechanism in Al–Mg–Si

Molecular-dynamics test of a specific published claim: that pre-exposing an
Al–Mg–Si alloy containing Al₁₃Fe₄ inclusions to a static 0.7 T field raises
its subsequent room-temperature creep by about 25% because magnetostriction of
the inclusion generates ≈147 MPa at the interface — above the 120 MPa yield
stress of the matrix — and plastifies the surrounding aluminium.

This repository holds the calculations and the analysis code that turn them
into numbers. The manuscript built from them is in co-author review and is
added on submission.

**The short version.** A magnetic field cannot be simulated in classical MD.
The inclusion is therefore elongated along the field by 0.194 % — the strain
that corresponds to the 147 MPa estimate — and held at that strain while the
matrix relaxes; the stress field is the difference between that cell and an
identical control. In one 91,428-atom cell (Al/Al₁₃Fe₄ interface with a
half-elliptical ridge) the resolved shear stress in the matrix is **«RIDGE_PEAK» MPa**
directly above the inclusion, decays to the far-field level within «DECAY» Å,
and averages 5 MPa over the cell width; the analytical sphere held at the same
strain gives 41 MPa at its surface. The same cell, loaded in applied shear,
tears a pre-existing dislocation pair apart at **«TAU_MOVE» MPa**«README_ONSET»;
a random Mg/Si configuration pins a dislocation through **≥75 MPa**. «README_G16»
A two-scale estimate with the alloy's inclusion fraction reproduces the measured
+25 % creep for activation volumes of «VSTAR_LO»–«VSTAR_HI» b³ **if** the
inclusions really strain by 0.194 % — the magnetostriction measured for bulk
Fe–Al alloys is twenty times smaller, and the 30-minute field-off memory is not
an elastic effect.

---

## The numbers

| Quantity | Value | Where it comes from |
|---|---|---|
| Resolved shear stress above the held ridge (on its axis) | «RIDGE_PEAK» MPa at 22 Å above the crest, 11–15 MPa out to 30 Å | `stageG10_field_profile.py` |
| Same, averaged over the cell width | 5.0 MPa peak | same |
| Far-field level beyond 60 Å (resolution of the minimisation) | «FAR_PLAIN» MPa | same |
| Fraction of the imposed strain the held ridge retains | 0.97 ± 0.01 (free ridge: 0.2–0.4) | `stageG12_eigenstrain_retention.py` |
| Eshelby sphere held at 0.194 % | 41 MPa at its surface, ∝ r⁻³ outside | `stageG8_eshelby3d.py` |
| 2D continuum solution for the ridge alone | 20 MPa at the surface, 5 MPa at 10 Å | `stageG17_ridge_continuum.py` |
| Onset of motion of the pre-existing pair (lower partner) | «TAU_MOVE» MPa applied shear«README_ONSET» | `stageG2_depinning.py` on stage G15 |
| Heterogeneous nucleation at the interface | «README_NUC» | same |
| Solute pinning bound | ≥ 75 MPa | `stageG7_pinning_stats.py` |
| Stress the measured +25 % creep requires (f = 0.00246) | 8.4–62.7 MPa for V* = 19–142 b³ | `stageG5_two_scale_bridge.py` |
| What the computed 41 / «RIDGE_PEAK» MPa predict | +25 % at V* ≈ «VSTAR_LO» / «VSTAR_HI» b³ | same |
| What 147 MPa would predict instead | ≥ 2.7 × 10³ × the observed effect | same |

Three stresses are kept apart throughout: the **147 MPa** interface estimate
of the experimental papers (E·ε of a rod, not of an embedded inclusion), the
**41 MPa** of a compact particle held at that strain, and the **«RIDGE_PEAK» MPa**
measured above the atomistic ridge held at the same strain.

## Reproducing the published numbers

The two minimised interface cells that every stress number is measured from are
in `data/stageG4_clean/` (gzipped LAMMPS dumps, ~4 MB each: the control and the
cell with the ridge held at 0.194 %, built from the same relaxed control).
Nothing else is needed for the stress field:

```bash
python analysis/python/stageG10_field_profile.py --r-max 110   # Fig. 3, the σ(r) profile
python analysis/python/stageG12_eigenstrain_retention.py       # retained strain
python analysis/python/stageG8_eshelby3d.py                    # the analytical sphere
python analysis/python/stageG17_ridge_continuum.py             # the 2D ridge solution
python analysis/python/stageG5_two_scale_bridge.py             # Table 2, the two-scale estimate
python analysis/python/stageG11_figures.py                     # Figs. 3-5
```

Each script writes a JSON record into `docs/reports/`, and the figures are drawn
from those records. The loaded-cell trajectories (stages G15/G16, ~400 MB each)
are not in the repository; their records are.
"""

README_RU = r"""### Кратко по-русски

Проверка методами молекулярной динамики конкретного опубликованного
утверждения: что выдержка сплава Al–Mg–Si с включениями Al₁₃Fe₄ в поле 0,7 Тл
повышает последующую ползучесть на ~25 %, поскольку магнитострикция включения
создаёт на границе ≈147 МПа. Включение удлинено вдоль поля на 0,194 % —
деформация, отвечающая этой оценке, — и удерживается при ней. В единой ячейке
из 91 428 атомов разрешённое касательное напряжение над включением составляет
«RIDGE_PEAK» МПа и спадает до уровня дальнего поля в пределах «DECAY» Å (в среднем по
ширине ячейки — 5 МПа); аналитическая сфера при той же деформации даёт 41 МПа.
Существующая пара дислокаций разрывается при «TAU_MOVE» МПа приложенного
сдвига«README_ONSET_RU»; примеси Mg/Si удерживают дислокацию до 75 МПа. «README_G16_RU»
Двухмасштабная оценка воспроизводит наблюдаемые +25 % при V* = «VSTAR_LO»–«VSTAR_HI» b³,
если включения действительно деформируются на 0,194 %; измеренная
магнитострикция Fe–Al в двадцать раз меньше, а 30-минутная память после
снятия поля упругим механизмом не объясняется.

Рукопись готовится и будет добавлена сюда после вычитки соавторами и подачи.
Пока репозиторий — это расчётная запись: всё, что статья утверждает, считается
командами из раздела «Reproducing the published numbers» выше.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--numbers", type=Path, required=True)
    a = ap.parse_args()
    num = json.loads(a.numbers.read_text(encoding="utf-8"))
    rep: list = []

    p = DR / "Abstract_and_keywords_en.tex"; t = io.open(p, encoding="utf-8").read()
    t = replace_block(t, r"\begin{abstract}", r"\begin{keyword}", fill(ABSTRACT_EN, num) + "\n\n", "abstract-en", rep)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    p = DR / "Abstract_and_keywords_ru.tex"; t = io.open(p, encoding="utf-8").read()
    t = replace_block(t, r"\noindent\textbf{Аннотация.}", r"\noindent\textbf{Ключевые слова:}", fill(ABSTRACT_RU, num) + "\n\n", "abstract-ru", rep)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)

    p = DR / "Section_3_en.tex"; t = io.open(p, encoding="utf-8").read()
    t = replace_block(t, r"\subsection{Thresholds for dislocation activity at the interface}", "\\begin{figure}", fill(S32_EN, num), "s32-en", rep)
    t = sub(t, S33_EN_OLD, fill(S33_EN_NEW, num), "s33-en", rep)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    p = DR / "Section_3_ru.tex"; t = io.open(p, encoding="utf-8").read()
    t = replace_block(t, r"\subsection{Пороги дислокационной активности на границе}", "\\begin{figure}", fill(S32_RU, num), "s32-ru", rep)
    t = sub(t, S33_RU_OLD, fill(S33_RU_NEW, num), "s33-ru", rep)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)

    p = DR / "Sections_4_en.tex"; t = io.open(p, encoding="utf-8").read()
    t = sub(t, S51_EN_OLD, fill(S51_EN_NEW, num), "s51-en", rep)
    i = t.find(r"\section{Conclusions}")
    if i < 0:
        rep.append("concl-en")
    else:
        t = t[:i] + fill(CONCL_EN, num) + "\n"
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    p = DR / "Sections_4_ru.tex"; t = io.open(p, encoding="utf-8").read()
    t = sub(t, S51_RU_OLD, fill(S51_RU_NEW, num), "s51-ru", rep)
    i = t.find(r"\section{Заключение}")
    if i < 0:
        rep.append("concl-ru")
    else:
        t = t[:i] + fill(CONCL_RU, num) + "\n"
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)

    # README: keep the middle sections (layout, licence, stage history) of the
    # current file; replace the head up to "## Reproducing" and the Russian tail
    rp = REPO / "README.md"; r = io.open(rp, encoding="utf-8").read()
    i = r.find("## Reproducing the published numbers")
    j = r.find("Each script writes a JSON record", i)
    k = r.find("\n", r.find("\n\n", j) + 2)  # end of that paragraph
    m = r.find("### Кратко по-русски")
    if min(i, j, m) < 0:
        rep.append("readme")
    else:
        head = fill(README, num)
        middle = r[r.find("\n\n", j) + 2:m]
        r = head + "\n" + middle + fill(README_RU, num)
        io.open(rp, "w", encoding="utf-8", newline="\n").write(r)

    print("round 3 applied; unmatched:", rep if rep else "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
