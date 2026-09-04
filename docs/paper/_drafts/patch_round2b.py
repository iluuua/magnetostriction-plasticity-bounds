#!/usr/bin/env python3
"""Round 2b: Section 3.1 rewritten for the perturbation held pair of the
unified cell (on-axis and width-averaged profiles, the far-field level as
the resolution of the calculation, comparison with the sphere), with the
Fig. 3 caption. EN and RU.

    python patch_round2b.py --numbers numbers_round2.json
"""
from __future__ import annotations
import argparse, io, json, re
from pathlib import Path

DR = Path(__file__).resolve().parent


def fill(s: str, num: dict) -> str:
    return re.sub("«([A-Z0-9_]+)»", lambda m: str(num[m.group(1)]), s)


S31_EN = r"""\subsection{The interface stress field and its decay}
\label{sec:sigma_r}

Figure~\ref{fig:sigma} shows how the stress in the aluminium matrix varies
with the distance $r$ from the interface plane in the two interface cells of
Section~\ref{sec:cell}: the control cell, in which the ridge is unstrained,
and the cell in which the ridge has been elongated by
$\varepsilon=1.94\times10^{-3}$ along the field direction and held there
(Section~\ref{sec:eigenstrain}). The strained cell is built from the relaxed
control by displacing the ridge atoms and is then minimised, so that the two
cells differ in nothing but the strain of the ridge. The matrix is cut into
slices 4~\AA{} thick parallel to the interface, the six components of the
stress tensor are averaged over the aluminium atoms of each slice, and only
then are invariants formed from the averaged tensor
(Section~\ref{sec:stress}). Two averages are used. The first spans the whole
cell in $x$ and $y$, i.e.\ the region above the ridge and the region beside
it; the second is restricted to a window 20~\AA{} wide centred on the ridge
axis, which is the stress that the matrix sees directly above the inclusion.
The ridge---the half-elliptic bump of the inclusion, with semi-axes 35~\AA{}
along $x$ and 20~\AA{} along $z$ (Fig.~\ref{fig:cell})---has its crest at
$r=20$~\AA{}, so that above the crest the distance to the nearest inclusion
surface is $d=r-20$~\AA{}.

\begin{figure}
\centering
\includegraphics[width=0.85\linewidth]{fig_sigma_profile_en}
\caption{Stress in the aluminium matrix as a function of the distance $r$
from the interface plane in the two interface cells (91\,428 atoms): the
control cell with the unstrained ridge, and the cell in which the ridge is
elongated by 0.194\% along the field direction and held at that strain. The
matrix is cut into slices 4~\AA{} thick parallel to the interface; the six
stress components are averaged over the aluminium atoms of each slice before
any invariant is formed. Top: the von Mises stress in each cell; the
100--190~MPa just above the ridge crest, present in both cells, is the
coherency stress of the bonded interface between two crystals of different
spacing, and the curves coincide. Bottom: the difference
$\Delta\sigma_{ij}=\sigma_{ij}(\varepsilon)-\sigma_{ij}(0)$ as the shear
stress resolved onto the most favourable of the twelve slip systems of fcc
Al, $\mathrm{RSS}_{\max}$, averaged over the whole width of the cell
(circles) and within 10~\AA{} of the ridge axis (diamonds), together with
the von Mises stress of the difference tensor. The shaded band is the
width-averaged level beyond 60~\AA{}, $2.2\pm0.8$~MPa, the resolution of the
calculation for long-wavelength strains of the slab. Slices at the level of
the ridge flanks, closer to the interface plane than the crest, are omitted:
there $r$ is not a distance to the inclusion surface and the slices contain
inclusion atoms. The profile ends 20~\AA{} below the free surface of the
slab.}
\label{fig:sigma}
\end{figure}

The upper panel gives the von Mises stress---a single positive number that
measures the shear content of a stress state and enters the yield criterion
of a ductile metal---in each cell. Two features of the control curve need to
be stated plainly, because they are present without any imposed strain.
First, in the slices just above the ridge crest the stress is 100--190~MPa,
and at the level of the ridge flanks it reaches 0.8--2.2~GPa. This is the
coherency stress of the interface. Aluminium and Al$_{13}$Fe$_4$ are
different crystals with different interatomic spacings; across the interface
their atoms interact through the same interatomic potential as inside either
crystal, with no constraint of any kind (Section~\ref{sec:cell}), so the
interface is bonded and cannot slip, and the atoms on both sides are pushed
away from the positions their own lattice would assign them. It falls below
10~MPa by $r\approx55$~\AA{} and below 2~MPa beyond 90~\AA{}; the
alternation between neighbouring slices closer to the crest reflects the
bending of the atomic planes over the crest, where a 4~\AA{} slice holds one
or two planes whose stresses differ. This stress exists whether or not the
ridge is strained: the two curves of the upper panel coincide, the
difference tensor between them having a von Mises stress of at most 9~MPa
above the crest. That is why the effect of the imposed strain is measured
throughout as the difference between the strained and the control cell,
slice by slice. Second, the profile ends 20~\AA{} below the free surface of
the aluminium slab, which lies at $r=129$~\AA{}; in the slices nearer the
surface the per-atom stress is dominated by the surface layers themselves.

The lower panel shows the difference,
$\Delta\sigma_{ij}(r)=\sigma_{ij}(r;\varepsilon)-\sigma_{ij}(r;0)$, which is
the quantity that the mechanism of Ref.~\cite{Friha2024JMMM} requires to
exceed the yield stress of the matrix. Every threshold for dislocation
motion in Section~\ref{sec:thresholds} is a resolved shear stress, so the
difference is expressed in the same way. Here and below
$\mathrm{RSS}_{\max}$ denotes the shear stress resolved onto the slip plane
and slip direction of a dislocation, taken over the twelve
$\{111\}\langle110\rangle$ slip systems of fcc aluminium and reported as its
maximum---the quantity that actually drives dislocation motion. It is
computed from the difference tensor, not as a difference of von Mises
values, which would not be an invariant of $\Delta\sigma_{ij}$; the von
Mises stress of the difference tensor is plotted alongside it. In every
slice above the crest the most favourable system is $(111)[1\bar{1}0]$: the
glide plane parallel to the interface and the direction $x$, along which
the dislocations of Section~\ref{sec:thresholds} glide, for which the
resolved shear is simply the component $\Delta\sigma_{xz}$.

Above the ridge axis the resolved shear stress is 11--15~MPa from the crest
out to $d\approx30$~\AA{}, with its maximum of 15~MPa at $d=22$~\AA{}; it
then decays, to 10~MPa at $d=46$~\AA{}, 5~MPa at $d\approx65$~\AA{} and
2~MPa at $d\approx85$~\AA{}. Averaged over the whole width of the cell the
same difference is much smaller, 2--5~MPa with a maximum of 5.0~MPa at
$r=50$~\AA{}, because the ridge occupies less than half of the width and
the shear beside the ridge has the opposite sign to the shear above it.
Beyond 60~\AA{} the width-averaged $\mathrm{RSS}_{\max}$ settles at
$2.2\pm0.8$~MPa (mean and standard deviation over seventeen slices). This
level is the resolution of the calculation rather than a field of the
ridge: a uniform shear of 2~MPa across the slab exerts a force of
$10^{-4}$~eV/\AA{} on each atom, below what the minimisation resolves, and
it is with this level that the on-axis field merges at $d\approx80$~\AA{}.
The stress that the strained ridge sends into the matrix is therefore
local: 15~MPa directly above it within one ridge height, and a third of
that on average across a region twice the width of the ridge.

The field is compared in Fig.~\ref{fig:rss} with the exact solution of
Eshelby \cite{Eshelby1957} for a spherical inclusion of the same radius,
35~\AA{}, held at the same strain in an unbounded aluminium matrix: 41~MPa
at the surface of the sphere, 11~MPa at $d=17$~\AA{}, 5~MPa at
$d=35$~\AA{}, falling as the inverse cube of the distance from the centre.
The atomistic ridge produces a smaller stress at its surface and a flatter
profile: held rigidly on a rigid layer and infinite along $y$, it is closer
to a cylinder than to a sphere, and the two agree within a factor of two
over $d=15$--$50$~\AA{}. A two-dimensional elastic calculation for the ridge
alone, in an unbounded matrix of the same stiffness, gives 20~MPa at the
ridge surface falling to 5~MPa within 10~\AA{}
(Section~\ref{sec:limitations}). The retained fraction of the imposed
strain, measured by fitting the residual distortion of the Fe sublattice of
the ridge to $\varepsilon^{*}$ (Section~\ref{sec:eigenstrain}), is
$0.97\pm0.01$ in the held cell. When the springs are removed and the
inclusion is free to relax, the ridge retains «ETA_FREE» of the strain and
the stress in the matrix falls with it: the field of Fig.~\ref{fig:sigma}
exists only as long as something holds the inclusion at its strain.

Slices at the level of the ridge flanks, closer to the interface plane than
the crest, are omitted from the figure. There $r$ measures height above the
interface plane and not the distance to the inclusion surface, which differs
for every atom in the slice; the coherency stress is 0.8--2.2~GPa, and the
difference, 5--60~MPa from one 4~\AA{} slice to the next, mixes the response
of the matrix with the displaced inclusion atoms themselves. These slices
characterise the interface, not the field it sends into the matrix, and they
are not carried forward.

Two qualifications apply. The local stress is deliberately not compared
with the macroscopic yield stress $\sigma_Y\approx120$~MPa: a stress
averaged over a 4~\AA{} slice is not a quantity that can be set against a
yield stress measured on a specimen, and the stresses that matter for
dislocations are measured directly in Section~\ref{sec:thresholds}. Whether
the imposed strain plastifies the matrix is therefore decided by comparing
the difference profile with those measured onsets, not by a local yield
criterion; the interface cells are built without dislocations, and the
calculation gives no sign of a plastified layer around the inclusion.
Second, the range of the field---some 30~\AA{} at its full strength and
80~\AA{} in all---is set by the size of the ridge. This accords with a
general property of the Eshelby solution: the stress inside an inclusion
does not depend on its size, whereas the reach of its exterior field scales
with the size \cite{Eshelby1957}, so that a micron-sized inclusion held at
the same strain would carry the same stress over a fraction of a micron---a
point taken up in Section~\ref{sec:bridge}.

"""

S31_RU = r"""\subsection{Поле напряжений у границы и его затухание}

На рис.~\ref{fig:sigma} показано, как напряжение в матрице алюминия меняется
с расстоянием $r$ от плоскости границы в двух ячейках границы
(раздел~2.1): в контрольной, где гребень не деформирован, и в ячейке, где
гребень удлинён вдоль направления поля на $\varepsilon = 1{,}94\cdot10^{-3}$
и удерживается в этом состоянии (раздел~2.2). Деформированная ячейка
построена из релаксированной контрольной смещением атомов гребня и затем
минимизирована, так что две ячейки различаются только деформацией гребня.
Матрица разбита на слои толщиной 4~\AA{}, параллельные границе; шесть
компонент тензора напряжений усреднены по атомам алюминия каждого слоя, и
лишь из усреднённого тензора образованы инварианты (раздел~2.4).
Используются два усреднения. Первое охватывает всю ячейку по $x$ и $y$, то
есть область как над гребнем, так и рядом с ним; второе ограничено окном
шириной 20~\AA{} вокруг оси гребня --- это напряжение, которое матрица
испытывает непосредственно над включением. Гребень --- полуэллиптический
выступ включения с полуосями 35~\AA{} вдоль $x$ и 20~\AA{} вдоль $z$
(рис.~\ref{fig:cell}) --- имеет вершину при $r = 20$~\AA{}, так что над
вершиной расстояние до ближайшей поверхности включения равно
$d = r - 20$~\AA{}.

\begin{figure}[!htbp]
\centering
\includegraphics[width=0.85\linewidth]{fig_sigma_profile_ru}
\caption{Напряжение в матрице алюминия в зависимости от расстояния $r$ от
плоскости границы в двух ячейках границы (91\,428 атомов): в контрольной
ячейке с недеформированным гребнем и в ячейке, где гребень удлинён вдоль
направления поля на 0{,}194\% и удерживается при этой деформации. Матрица
разбита на слои толщиной 4~\AA{}, параллельные границе; шесть компонент
тензора напряжений усредняются по атомам алюминия каждого слоя, и лишь
затем из усреднённого тензора образуются инварианты. Сверху: напряжение фон
Мизеса в каждой из ячеек; 100--190~МПа непосредственно над вершиной гребня,
присутствующие в обеих ячейках, --- это напряжение когерентности сцеплённой
границы между двумя кристаллами с разными межатомными расстояниями; кривые
совпадают. Снизу: разность $\Delta\sigma_{ij} = \sigma_{ij}(\varepsilon) -
\sigma_{ij}(0)$ как касательное напряжение, спроецированное на наиболее
благоприятную из двенадцати систем скольжения ГЦК-алюминия,
$\mathrm{RSS}_{\max}$, в среднем по всей ширине ячейки (кружки) и в
пределах 10~\AA{} от оси гребня (ромбы), а также напряжение фон Мизеса
разностного тензора. Затенённая полоса --- уровень среднего по ширине за
60~\AA{}, $2{,}2 \pm 0{,}8$~МПа, разрешающая способность расчёта для
длинноволновых деформаций слоя. Слои на уровне склонов гребня, лежащие ближе
к плоскости границы, чем его вершина, опущены: там $r$ не является
расстоянием до поверхности включения, и слои содержат атомы включения.
Профиль обрывается в 20~\AA{} под свободной поверхностью слоя.}
\label{fig:sigma}
\end{figure}

Верхняя панель даёт напряжение фон Мизеса --- единственное положительное
число, характеризующее сдвиговую часть напряжённого состояния и входящее в
критерий текучести пластичного металла, --- в каждой ячейке. Две
особенности контрольной кривой требуют прямого объяснения, поскольку они
присутствуют без всякой заданной деформации. Во-первых, в слоях
непосредственно над вершиной гребня напряжение составляет 100--190~МПа, а
на уровне склонов гребня достигает 0{,}8--2{,}2~ГПа. Это напряжение
когерентности границы. Алюминий и Al$_{13}$Fe$_4$ --- разные кристаллы с
разными межатомными расстояниями; через границу их атомы взаимодействуют
тем же межатомным потенциалом, что и внутри каждого из кристаллов, без
каких-либо искусственных связей (раздел~2.1), так что граница сцеплена и
проскальзывать не может, а атомы по обе её стороны смещены с тех положений,
которые отвела бы им собственная решётка. К $r \approx 55$~\AA{} это
напряжение падает ниже 10~МПа, а за 90~\AA{} --- ниже 2~МПа; чередование
соседних слоёв ближе к вершине отражает изгиб атомных плоскостей над ней:
слой толщиной 4~\AA{} захватывает там одну или две плоскости с разными
напряжениями. Это напряжение существует независимо от того, деформирован
гребень или нет: две кривые верхней панели совпадают, напряжение фон Мизеса
разностного тензора над вершиной не превышает 9~МПа. Именно поэтому действие
заданной деформации всюду измеряется как разность между деформированной и
контрольной ячейками, слой за слоем. Во-вторых, профиль обрывается в
20~\AA{} под свободной поверхностью алюминиевого слоя, лежащей при
$r = 129$~\AA{}: в слоях ближе к поверхности поатомное напряжение
определяется самими поверхностными слоями.

Нижняя панель показывает саму разность
$\Delta\sigma_{ij}(r) = \sigma_{ij}(r;\varepsilon) - \sigma_{ij}(r;0)$ ---
ту величину, которая, согласно механизму работы [5], должна превышать
предел текучести матрицы. Все пороги движения дислокаций в разделе~3.2
выражены через разрешённое касательное напряжение, поэтому и разность
выражена так же. Здесь и далее $\mathrm{RSS}_{\max}$ обозначает касательное
напряжение, спроецированное на плоскость и направление скольжения
дислокации, вычисленное для всех двенадцати систем скольжения
$\{111\}\langle110\rangle$ ГЦК-алюминия и приведённое по максимальной из
них, --- ту величину, которая и приводит дислокацию в движение. Оно
вычисляется из разностного тензора, а не как разность значений фон Мизеса,
которая инвариантом $\Delta\sigma_{ij}$ не является; рядом построено
напряжение фон Мизеса самого разностного тензора. В каждом слое над
вершиной наиболее благоприятной оказывается система $(111)[1\bar{1}0]$ ---
плоскость скольжения, параллельная границе, и направление $x$, вдоль
которого скользят дислокации раздела~3.2; для неё разрешённый сдвиг есть
просто компонента $\Delta\sigma_{xz}$.

Над осью гребня разрешённое касательное напряжение составляет 11--15~МПа
от вершины до $d \approx 30$~\AA{} с максимумом 15~МПа при $d = 22$~\AA{};
далее оно спадает: 10~МПа при $d = 46$~\AA{}, 5~МПа при $d \approx 65$~\AA{}
и 2~МПа при $d \approx 85$~\AA{}. В среднем по всей ширине ячейки та же
разность много меньше, 2--5~МПа с максимумом 5{,}0~МПа при $r = 50$~\AA{},
потому что гребень занимает меньше половины ширины, а сдвиг рядом с гребнем
имеет знак, противоположный сдвигу над ним. За 60~\AA{} среднее по ширине
$\mathrm{RSS}_{\max}$ выходит на уровень $2{,}2 \pm 0{,}8$~МПа (среднее и
стандартное отклонение по семнадцати слоям). Этот уровень --- разрешающая
способность расчёта, а не поле гребня: однородный сдвиг слоя в 2~МПа создаёт
на каждом атоме силу $10^{-4}$~эВ/\AA{}, ниже того, что разрешает
минимизация; именно с этим уровнем сливается поле на оси при
$d \approx 80$~\AA{}. Напряжение, которое деформированный гребень посылает
в матрицу, таким образом, локально: 15~МПа непосредственно над ним в
пределах одной высоты гребня и втрое меньше в среднем по области вдвое шире
гребня.

На рис.~\ref{fig:rss} это поле сопоставлено с точным решением Эшелби [7]
для сферического включения того же радиуса, 35~\AA{}, удерживаемого при
той же деформации в неограниченной алюминиевой матрице: 41~МПа на
поверхности сферы, 11~МПа при $d = 17$~\AA{}, 5~МПа при $d = 35$~\AA{} со
спадом обратно пропорционально кубу расстояния от центра. Атомистический
гребень даёт меньшее напряжение у своей поверхности и более пологий
профиль: жёстко удерживаемый на жёстком слое и бесконечный вдоль $y$, он
ближе к цилиндру, чем к сфере, и в интервале $d = 15$--$50$~\AA{} оба
согласуются в пределах множителя два. Двумерный упругий расчёт для одного
гребня в неограниченной матрице той же жёсткости даёт 20~МПа у поверхности
гребня со спадом до 5~МПа в пределах 10~\AA{} (раздел~5.4). Сохранённая
доля заданной деформации, измеренная подгонкой остаточного искажения
Fe-подрешётки гребня к $\varepsilon^{*}$ (раздел~2.2), в удерживаемой
ячейке равна $0{,}97 \pm 0{,}01$. Если пружины снять и дать включению
релаксировать, гребень сохраняет «ETA_FREE_RU» деформации, и напряжение в
матрице падает вместе с ней: поле рис.~\ref{fig:sigma} существует лишь до
тех пор, пока что-то удерживает включение при его деформации.

Слои на уровне склонов гребня, лежащие ближе к плоскости границы, чем его
вершина, на рисунке опущены. Там $r$ измеряет высоту над плоскостью границы,
а не расстояние до поверхности включения, которое для каждого атома слоя
своё; напряжение когерентности составляет 0{,}8--2{,}2~ГПа, а разность,
5--60~МПа от одного слоя толщиной 4~\AA{} к следующему, смешивает отклик
матрицы с самими смещёнными атомами включения. Эти слои характеризуют
границу, а не поле, которое она посылает в матрицу, и дальше не
используются.

Две оговорки. Локальное напряжение сознательно не сопоставляется с
макроскопическим пределом текучести $\sigma_Y \approx 120$~МПа: напряжение,
усреднённое по слою толщиной 4~\AA{}, нельзя ставить рядом с пределом
текучести, измеренным на образце, а напряжения, существенные для дислокаций,
измерены непосредственно в разделе~3.2. Вопрос о том, пластифицирует ли
заданная деформация матрицу, решается поэтому сопоставлением разностного
профиля с измеренными порогами, а не локальным критерием текучести; ячейки
границы построены без дислокаций, и признаков пластифицированного слоя
вокруг включения расчёт не даёт. Во-вторых, протяжённость поля --- около
30~\AA{} в полную силу и 80~\AA{} в целом --- задаётся размером гребня. Это
согласуется с общим свойством решения Эшелби: напряжение внутри включения
от его размера не зависит, тогда как дальность его внешнего поля
масштабируется вместе с размером [7], так что включение микронного размера,
удерживаемое при той же деформации, несло бы то же напряжение на протяжении
долей микрона; этот вопрос рассматривается в разделе~4.

"""


def replace_region(text: str, start: str, end: str, new: str) -> str:
    i = text.find(start)
    j = text.find(end, i + 1)
    if i < 0 or j < 0:
        raise SystemExit(f"region not found: {start!r} .. {end!r}")
    return text[:i] + new + text[j:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--numbers", type=Path, required=True)
    a = ap.parse_args()
    num = json.loads(a.numbers.read_text(encoding="utf-8"))
    p = DR / "Section_3_en.tex"; t = io.open(p, encoding="utf-8").read()
    t = replace_region(t, r"\subsection{The interface stress field and its decay}",
                       r"\subsection{Thresholds for dislocation activity at the interface}", fill(S31_EN, num))
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    p = DR / "Section_3_ru.tex"; t = io.open(p, encoding="utf-8").read()
    t = replace_region(t, r"\subsection{Поле напряжений у границы и его затухание}",
                       r"\FloatBarrier", fill(S31_RU, num))
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("round 2b applied (Section 3.1 EN/RU)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
