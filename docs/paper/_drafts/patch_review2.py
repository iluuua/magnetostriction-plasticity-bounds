#!/usr/bin/env python3
"""Fixes from the final 18-agent review (4 Sept 2026, 12:00). Drafts EN/RU,
main.tex/main_ru.tex preamble and Data availability, README.md, splice."""
from __future__ import annotations
import io, re, json
from pathlib import Path

DR = Path(__file__).resolve().parent
PAPER = DR.parent
REPO = PAPER.parents[1]
rep: list = []


def flex(s: str) -> str:
    return r"\s+".join(re.escape(p) for p in re.split(r"\s+", s.strip()))


def sub(t, old, new, tag, count=1):
    out, n = re.subn(flex(old), lambda m: new, t, count=count)
    if n == 0:
        rep.append(tag)
    return out


def load(name):
    return io.open(DR / name, encoding="utf-8").read()


def save(name, t):
    io.open(DR / name, "w", encoding="utf-8", newline="\n").write(t)


num = json.loads((DR / "numbers_round3.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------- Abstract (<= 150 words, no formulas)
ABS_EN = r"""\begin{abstract}
How pre-exposing an Al--Mg--Si alloy with Al$_{13}$Fe$_4$ inclusions to a
static magnetic field affects plastic deformation in uniaxial creep is
examined by molecular dynamics. The inclusion is elongated along the field by
0.194\%, the strain corresponding to the 147~MPa interface stress estimated in
earlier experiments, and is held at that strain while the matrix relaxes. The
resolved shear stress in the matrix reaches 15~MPa directly above the
inclusion and falls to the resolution of the calculation within 80~\AA{}.
Under shear, a pre-existing dislocation pair is torn apart from 95--105~MPa,
and no new dislocation forms at the interface up to 400~MPa in the unstrained
cell. A two-scale estimate reproduces the measured 25\% creep increase with
the computed stresses for the activation volumes reported for Al--Mg--Si,
provided the inclusions strain by 0.194\%; the magnetostriction measured for
Fe--Al alloys is twenty times smaller, and the persistence of the effect after
the field is removed is not explained by an elastic stress.
\end{abstract}"""

ABS_RU = r"""\noindent\textbf{Аннотация.}
Методом молекулярной динамики исследуется, как предварительная выдержка
сплава Al--Mg--Si с включениями Al$_{13}$Fe$_4$ в постоянном магнитном поле
влияет на пластическую деформацию при одноосной ползучести. Включение
удлинено вдоль поля на 0{,}194\% --- деформация, отвечающая оценённому в
ранних экспериментах межфазному напряжению 147~МПа, --- и удерживается при
этой деформации, пока матрица релаксирует. Разрешённое касательное
напряжение в матрице достигает 15~МПа непосредственно над включением и в
пределах 80~\AA{} спадает до разрешающей способности расчёта. При сдвиговом
нагружении существующая пара дислокаций разрывается начиная с 95--105~МПа, а
новых дислокаций на границе в недеформированной ячейке не образуется вплоть
до 400~МПа. Двухмасштабная оценка воспроизводит наблюдаемый прирост
ползучести 25\% при рассчитанных напряжениях для активационных объёмов,
измеренных для Al--Mg--Si, --- при условии, что включения действительно
деформируются на 0{,}194\%; измеренная магнитострикция сплавов Fe--Al в
двадцать раз меньше, а сохранение эффекта после снятия поля упругим
напряжением не объясняется."""


def replace_block(t, start, end, new, tag):
    i = t.find(start); j = t.find(end, i + 1) if i >= 0 else -1
    if i < 0 or j < 0:
        rep.append(tag); return t
    return t[:i] + new + "\n\n" + t[j:]


t = load("Abstract_and_keywords_en.tex"); t = replace_block(t, r"\begin{abstract}", r"\begin{keyword}", ABS_EN, "abs-en"); save("Abstract_and_keywords_en.tex", t)
t = load("Abstract_and_keywords_ru.tex"); t = replace_block(t, r"\noindent\textbf{Аннотация.}", r"\noindent\textbf{Ключевые слова:}", ABS_RU, "abs-ru"); save("Abstract_and_keywords_ru.tex", t)

# ---------------------------------------------------------------- Section 1
t = load("Section_1_en.tex")
t = sub(t, "at which new dislocations are nucleated at the interface;", "and whether new dislocations are nucleated at the interface up to the highest stress applied;", "s1-nuc")
save("Section_1_en.tex", t)
t = load("Section_1_ru.tex")
t = sub(t, "и напряжение, при котором на границе зарождаются новые дислокации", "и образуются ли на границе новые дислокации вплоть до наибольшего приложенного напряжения", "s1-nuc-ru")
save("Section_1_ru.tex", t)

# ---------------------------------------------------------------- Section 2
t = load("Section_2_en.tex")
t = sub(t, r"""Straining the flat layer as well was tried: a layer that is periodic in its
plane cannot be sheared coherently, and holding it at the strain loaded the
whole slab uniformly by about 150~MPa (Section~\ref{sec:eigenstrain}); the
layer is therefore left unstrained and the ridge alone carries the strain.""",
        r"""The flat layer is left unstrained and the ridge alone carries the strain
(Section~\ref{sec:eigenstrain}).""", "s2-flat")
t = sub(t, "so that the pair is stable and stays where it is placed until",
        "so that in a uniform, stress-free crystal the pair is stable and stays where it is placed until", "s2-stable")
t = sub(t, r"""The cell is
loaded both with the strained inclusion and with the unstrained one.""",
        r"""Three ramps were run: the unstrained cell with the inclusion free to relax,
to 400~MPa over 96~ps; and the unstrained and the strained cell with the
inclusion held by the springs of Section~\ref{sec:eigenstrain}, at the same
rate of rise, to 145~MPa over 40~ps---the pair that compares strained with
unstrained.""", "s2-ramps")
t = sub(t, r"""retains 0.2--0.4 of the imposed strain, the value depending on how far the
interface is relaxed in the two minimisations compared.""",
        r"""retains 0.2--0.4 of the imposed strain ($0.20\pm0.11$ and $0.44\pm0.10$ in
two minimisations, both stopped before full convergence).""", "s2-free")
t = sub(t, "linear rise from 0 to 400~MPa over 96~ps after 5~ps at zero stress (a); for",
        "linear rise from 0 to 400~MPa over 96~ps after 5~ps at zero stress (the\nheld cells were ramped at the same rate to 145~MPa) (a); for", "s2-figcap")
save("Section_2_en.tex", t)

t = load("Section_2_ru.tex")
t = sub(t, r"""Деформировать и плоский слой пробовали: слой, периодичный в своей
плоскости, нельзя когерентно сдвинуть, и удержание его при заданной
деформации однородно нагружало весь слой алюминия примерно на 150~МПа
(раздел~2.2); поэтому плоский слой оставлен недеформированным, и деформацию
несёт один гребень.""",
        r"""Плоский слой оставлен недеформированным, деформацию несёт только гребень
(раздел~2.2).""", "s2-flat-ru")
t = sub(t, "так что пара устойчива и остаётся там, где помещена,",
        "так что в однородном ненагруженном кристалле пара устойчива и остаётся там, где помещена,", "s2-stable-ru")
t = sub(t, r"""Ячейка нагружается как с деформированным включением, так и с
недеформированным.""",
        r"""Выполнены три рампы: недеформированная ячейка со свободно релаксирующим
включением --- до 400~МПа за 96~пс; недеформированная и деформированная
ячейки с включением, удерживаемым пружинами раздела~2.2, --- при той же
скорости роста до 145~МПа за 40~пс (эта пара и сравнивает деформированный
гребень с недеформированным).""", "s2-ramps-ru")
t = sub(t, r"""сохраняет 0{,}2--0{,}4
наложенной деформации --- значение зависит от того, насколько релаксирована
граница в двух сравниваемых минимизациях.""",
        r"""сохраняет 0{,}2--0{,}4
наложенной деформации ($0{,}20 \pm 0{,}11$ и $0{,}44 \pm 0{,}10$ в двух
минимизациях, обе остановлены до полной сходимости).""", "s2-free-ru")
t = sub(t, "линейный рост от 0 до 400~МПа за 96~пс после 5~пс при нулевом",
        "линейный рост от 0 до 400~МПа за 96~пс после 5~пс при нулевом напряжении (удерживаемые ячейки нагружались с той же скоростью до 145~МПа)", "s2-figcap-ru")
t = sub(t, "напряжении (удерживаемые ячейки нагружались с той же скоростью до 145~МПа)\nнапряжении (а);", "напряжении (удерживаемые ячейки нагружались с той же скоростью до 145~МПа) (а);", "s2-figcap-ru2")
save("Section_2_ru.tex", t)

# ---------------------------------------------------------------- Section 3
t = load("Section_3_en.tex")
t = sub(t, "same difference is much smaller, 2--5~MPa with a maximum of 5.0~MPa at",
        "same difference is much smaller, up to 5~MPa (maximum 5.0~MPa at", "s3-widthavg")
t = sub(t, r"$r=50$~\AA{}, because the ridge occupies", r"$r=50$~\AA{}, one slice at 0.6~MPa), because the ridge occupies", "s3-widthavg2")
t = sub(t, "35~\\AA{}, held at the same strain in an unbounded aluminium matrix: 41~MPa\nat the surface of the sphere, 11~MPa at $d=17$~\\AA{}, 5~MPa at",
        "35~\\AA{}, held at the same strain in an unbounded aluminium matrix: 41~MPa\ninside the sphere (47~MPa just outside its surface), 11~MPa at $d=17$~\\AA{}, 5~MPa at", "s3-sphere")
t = sub(t, r"""Over $d=15$--$50$~\AA{} the ridge and the sphere agree
within a factor of two.""",
        r"""On the ridge axis the ridge and the sphere agree within a factor of two
out to $d\approx30$~\AA{} and within a factor of three out to
$d=50$~\AA{}; the width-averaged field lies three to six times below the
sphere over the same distances.""", "s3-factor2")
t = sub(t, "difference, 5--60~MPa from one 4~\\AA{} slice to the next, mixes the response",
        "difference, 6--61~MPa from one 4~\\AA{} slice to the next, mixes the response", "s3-flank")
t = sub(t, r"""retains only 0.2--0.4 of the strain and the shear stress on the ridge axis
falls below 5~MPa;""",
        r"""retains only 0.2--0.4 of the strain ($0.20\pm0.11$ and $0.44\pm0.10$ in two
minimisations stopped before full convergence) and the shear stress on the
ridge axis falls below 5~MPa;""", "s3-free")
t = sub(t, "after which it hovers within a few {\\aa}ngstr\\\"om", "after which it hovers within a few {\\aa}ngstr{\\\"o}ms", "s3-angstrom")
t = sub(t, r"""The only new segments, from 377~MPa on, are partial dislocations 10--20~\AA{} long at the periodic boundary of the cell, at the seam left by the insertion of the pair, and are a construction artefact.""",
        r"""The only new segments---transiently at 232--241~MPa and again from 377~MPa on---are partial dislocations 10--25~\AA{} long at the periodic boundary of the cell, at the seam left by the insertion of the pair; none is at the interface, and they are a construction artefact.""", "s3-seam")
t = sub(t, num["FLD_PARA"],
        r"""With the inclusion held by springs, as in the interface cells, the picture
changes in one respect and not in the other. The lower partner is then not
held even at zero applied stress: in the control cell and in the strained
cell alike it leaves within the first 8~ps, through the periodic boundary,
because the coherency field of a rigidly held, unrelaxed inclusion is
stronger than that of one free to relax. The upper partner moves 31--33~\AA{}
over the ridge in the first 6~ps in both cells, coming to rest 7--10~\AA{}
from its axis, and departs at 105--115~MPa in the control and 115--125~MPa in
the strained cell, one frame of the ramp apart; these two ramps were carried
to 145~MPa, and by 140~MPa the strained cell contains no dislocation while
the control retains only fragments 13--26~\AA{} long at the periodic seam.
A short segment at that seam ($x=8$--$10$~\AA{}, $z=57$--$69$~\AA{}) is
present in both held cells from 12--14~ps on, the same construction
artefact as in the free ramp. The strain of the ridge thus changes the fate
of the pair by at most one frame, 9~MPa. This is the expected result: the
field of the strained ridge at the initial positions of the partners is
5--10~MPa, and on the ridge axis at the height where the upper partner
comes to rest, $d\approx32$~\AA{}, it is 13--14~MPa
(Section~\ref{sec:sigma_r})---both of the order of one frame of the ramp,
so a shift of one frame is neither resolved nor excluded.""", "s3-fldpara")
t = sub(t, r"""its bias on the pair is «TAU_SHIFT_TXT» (Section~\ref{sec:sigma_r} gives
5--10~MPa at the position of the pair).""".replace("«TAU_SHIFT_TXT»", num["TAU_SHIFT_TXT"]),
        r"""its bias on the pair is below the resolution of the ramp, one frame or
9~MPa, which is the order of the 5--14~MPa it produces where the pair sits.""", "s3-bias")
t = sub(t, "which sets how strongly the glide rate responds to stress)cannot", "which sets how strongly the glide rate responds to stress) cannot", "s3-space")
t = sub(t, r"""$b=2.86$~\AA{}, the elementary displacement of the lattice produced by the
passage of one dislocation---""", r"""$b=2.86$~\AA{}---""", "s3-burgers")
save("Section_3_en.tex", t)

t = load("Section_3_ru.tex")
t = sub(t, "разность много меньше, 2--5~МПа с максимумом 5{,}0~МПа при $r = 50$~\\AA{},",
        "разность много меньше, не более 5~МПа (максимум 5{,}0~МПа при $r = 50$~\\AA{}, один слой при 0{,}6~МПа),", "s3-widthavg-ru")
t = sub(t, "41~МПа на\nповерхности сферы, 11~МПа при $d = 17$~\\AA{}", "41~МПа внутри\nсферы (47~МПа непосредственно у её поверхности снаружи), 11~МПа при $d = 17$~\\AA{}", "s3-sphere-ru")
t = sub(t, r"""В интервале $d = 15$--$50$~\AA{} гребень и
сфера согласуются в пределах множителя два.""",
        r"""На оси гребня гребень и сфера согласуются в пределах множителя два до
$d \approx 30$~\AA{} и в пределах множителя три до $d = 50$~\AA{}; среднее
по ширине поле на тех же расстояниях в три--шесть раз ниже сферы.""", "s3-factor2-ru")
t = sub(t, "5--60~МПа от одного слоя толщиной 4~\\AA{} к следующему, смешивает отклик",
        "6--61~МПа от одного слоя толщиной 4~\\AA{} к следующему, смешивает отклик", "s3-flank-ru")
t = sub(t, r"""гребень сохраняет лишь
0{,}2--0{,}4 деформации, а касательное напряжение на оси гребня падает ниже
5~МПа;""",
        r"""гребень сохраняет лишь
0{,}2--0{,}4 деформации ($0{,}20 \pm 0{,}11$ и $0{,}44 \pm 0{,}10$ в двух
минимизациях, остановленных до полной сходимости), а касательное напряжение
на оси гребня падает ниже 5~МПа;""", "s3-free-ru")
t = sub(t, r"""Единственные новые сегменты, начиная с 377~МПа, --- частичные дислокации длиной 10--20~\AA{} у периодической границы ячейки, на шве, оставшемся от введения пары; это артефакт построения.""",
        r"""Единственные новые сегменты --- кратковременно при 232--241~МПа и вновь начиная с 377~МПа --- это частичные дислокации длиной 10--25~\AA{} у периодической границы ячейки, на шве, оставшемся от введения пары; на границе их нет, и это артефакт построения.""", "s3-seam-ru")
t = sub(t, num["FLD_PARA_RU"],
        r"""При включении, удерживаемом пружинами, как в ячейках границы, картина
меняется в одном отношении и не меняется в другом. Нижний партнёр тогда не
удерживается даже при нулевом приложенном напряжении: и в контрольной, и в
деформированной ячейке он уходит через периодическую границу в первые 8~пс,
потому что поле когерентности жёстко удерживаемого, нерелаксировавшего
включения сильнее, чем у включения, свободно релаксирующего. Верхний партнёр
в обеих ячейках за первые 6~пс смещается на 31--33~\AA{} на гребень,
останавливаясь в 7--10~\AA{} от его оси, и уходит при 105--115~МПа в
контрольной и при 115--125~МПа в деформированной ячейке --- с разницей в
один кадр рампы; эти две рампы доведены до 145~МПа, и к 140~МПа
деформированная ячейка не содержит дислокаций, а в контрольной остаются
лишь обрывки длиной 13--26~\AA{} на периодическом шве. Короткий сегмент на
этом шве ($x = 8$--$10$~\AA{}, $z = 57$--$69$~\AA{}) присутствует в обеих
удерживаемых ячейках начиная с 12--14~пс --- тот же артефакт построения,
что и в свободной рампе. Деформация гребня, таким образом, меняет судьбу
пары не более чем на один кадр, 9~МПа. Это ожидаемый результат: поле
деформированного гребня в исходных положениях партнёров составляет
5--10~МПа, а на оси гребня на той высоте, где останавливается верхний
партнёр, $d \approx 32$~\AA{}, --- 13--14~МПа (раздел~3.1); и то и другое
порядка одного кадра рампы, так что сдвиг на один кадр не разрешается, но и
не исключается.""", "s3-fldpara-ru")
t = sub(t, r"""а его влияние на порог
пары --- «TAU_SHIFT_TXT_RU» (раздел~3.1 даёт 5--10~МПа в месте расположения
пары).""".replace("«TAU_SHIFT_TXT_RU»", num["TAU_SHIFT_TXT_RU"]),
        r"""а его влияние на порог пары ниже разрешающей способности рампы --- одного
кадра, 9~МПа, --- что порядка тех 5--14~МПа, которые он создаёт там, где
находится пара.""", "s3-bias-ru")
t = sub(t, "в\n6--7 раза меньше напряжения", "в\n6--7 раз меньше напряжения", "s3-raza1")
t = sub(t, "в 5 раза, а 41~МПа", "в 5 раз, а 41~МПа", "s3-raza2")
t = sub(t, r"""$b = 2{,}86$~\AA{}, ---
элементарного смещения решётки при прохождении одной дислокации, ---""", r"""$b = 2{,}86$~\AA{}, ---""", "s3-burgers-ru")
save("Section_3_ru.tex", t)

# ---------------------------------------------------------------- Sections 4-6
t = load("Sections_4_en.tex")
t = sub(t, "of the stress that acts along the slip direction in the slip plane, and hence",
        "of the stress that pushes a dislocation (Section~\\ref{sec:stress}), and hence", "s4-rss")
t = sub(t, "the required $\\tau_m$ by $0.007\\%$ at every $V^{*}$", "the required $\\tau_m$ by about $0.01\\%$ at every $V^{*}$", "s4-taum")
t = sub(t, "gives 41~MPa of resolved shear at its surface (Section~\\ref{sec:sigma_r});",
        "gives 41~MPa of resolved shear inside the particle and just outside it (Section~\\ref{sec:sigma_r});", "s4-sphere")
t = sub(t, "41~MPa (the surface value of the analytical sphere held at 0.194\\%;\n41.45 unrounded)",
        "41~MPa (the interior value of the analytical sphere held at 0.194\\%, which\nis also the amplitude of its inverse-cube far field; 41.45 unrounded)", "s4-tabcap")
t = sub(t, "gives 41~MPa of resolved shear at its surface,\nfalling as $(a/r)^{3}$ outside", "gives 41~MPa of resolved shear inside the particle,\nfalling as $(a/r)^{3}$ outside", "s5-sphere")
t = sub(t, "loaded cells with the ridge held or unstrained; none of them represents the",
        "loaded cells with the inclusion free (unstrained) or held (unstrained and strained); none of them represents the", "s5-loaded")
t = sub(t, "held at the same strain gives 41~MPa at its surface, falling as the inverse",
        "held at the same strain gives 41~MPa inside it, falling as the inverse", "s6-sphere")
t = sub(t, r"""is torn apart at an applied shear of 95--105~MPa, with no resolvable shift (less than one frame of the ramp, 9~MPa) when the ridge is strained; no new dislocation forms at the interface up to the end of the ramp at 400~MPa;""",
        r"""is torn apart at an applied shear of 95--105~MPa with the inclusion free to relax; with the inclusion held, the strained and the unstrained cell coincide within one frame of the ramp, 9~MPa, at every stage; no new dislocation forms at the interface up to the end of the ramp at 400~MPa in the unstrained cell;""", "s6-loaded")
save("Sections_4_en.tex", t)

t = load("Sections_4_ru.tex")
t = sub(t, "вдоль направления скольжения в плоскости скольжения и потому единственная",
        "толкающая дислокацию (раздел~2.4), и потому единственная", "s4-rss-ru")
t = sub(t, "повышает требуемое $\\tau_m$ на $0{,}007\\%$ при каждом $V^{*}$", "повышает требуемое $\\tau_m$ примерно на $0{,}01\\%$ при каждом $V^{*}$", "s4-taum-ru")
t = sub(t, "решение [7] даёт 41~МПа разрешённого сдвига на её поверхности", "решение [7] даёт 41~МПа разрешённого сдвига внутри частицы и непосредственно у её поверхности", "s4-sphere-ru")
t = sub(t, "41~МПа (значение на поверхности аналитической сферы, удерживаемой при\n0{,}194\\%; 41{,}45 без округления)",
        "41~МПа (значение внутри аналитической сферы, удерживаемой при 0{,}194\\%,\nоно же --- амплитуда её дальнего поля, спадающего как обратный куб; 41{,}45\nбез округления)", "s4-tabcap-ru")
t = sub(t, "нет, --- даёт 41~МПа разрешённого сдвига на её поверхности со спадом", "нет, --- даёт 41~МПа разрешённого сдвига внутри частицы со спадом", "s5-sphere-ru")
t = sub(t, "и нагружаемые ячейки с удерживаемым или\nнедеформированным гребнем;",
        "и нагружаемые ячейки со свободным (недеформированным) или удерживаемым\n(недеформированным и деформированным) включением;", "s5-loaded-ru")
t = sub(t, "даёт 41~МПа на\nеё поверхности со спадом обратно пропорционально кубу расстояния", "даёт 41~МПа\nвнутри неё со спадом обратно пропорционально кубу расстояния", "s6-sphere-ru")
t = sub(t, r"""разрывается при приложенном сдвиге 95--105~МПа, без разрешимого сдвига (менее одного кадра рампы, 9~МПа) при деформированном гребне; новых дислокаций на границе не образуется вплоть до конца рампы при 400~МПа;""",
        r"""разрывается при приложенном сдвиге 95--105~МПа при свободно релаксирующем включении; при удерживаемом включении деформированная и недеформированная ячейки на каждом этапе совпадают в пределах одного кадра рампы, 9~МПа; новых дислокаций на границе в недеформированной ячейке не образуется вплоть до конца рампы при 400~МПа;""", "s6-loaded-ru")
save("Sections_4_ru.tex", t)

# ---------------------------------------------------------------- Fig. 3 caption wording (shaded region)
for name, old, new in (("Section_3_en.tex", r"""The shaded band is the
width-averaged level beyond 60~\AA{}, $2.5\pm0.5$~MPa, the resolution of the
calculation for long-wavelength strains of the slab.""",
                        r"""The shaded region marks stresses below 3~MPa: the width-averaged level
beyond 60~\AA{} with its scatter, $2.5\pm0.5$~MPa, the resolution of the
calculation for long-wavelength strains of the slab."""),
                       ("Section_3_ru.tex", r"""Затенённая полоса --- уровень среднего по ширине за
60~\AA{}, $2{,}5 \pm 0{,}5$~МПа, разрешающая способность расчёта для
длинноволновых деформаций слоя.""",
                        r"""Затенённая область отмечает напряжения ниже 3~МПа: уровень среднего по
ширине за 60~\AA{} с его разбросом, $2{,}5 \pm 0{,}5$~МПа, разрешающая
способность расчёта для длинноволновых деформаций слоя.""")):
    t = load(name); t = sub(t, old, new, "fig3-" + name); save(name, t)

# ---------------------------------------------------------------- main files: preamble, Data availability
for name in ("main.tex", "main_ru.tex"):
    p = PAPER / name; m = io.open(p, encoding="utf-8").read()
    m = m.replace("\\providecommand{\\todo}[1]{\\textbf{[TODO: #1]}}\n", "")
    m = m.replace("(\\path{stageG1_dipole_tracking.py},\n\\path{stageG16_dipole_under_field.py})", "(\\path{stageG2_depinning.py})")
    m = m.replace("(\\path{stageG1_dipole_tracking.py}, \\path{stageG16_dipole_under_field.py})", "(\\path{stageG2_depinning.py})")
    m = re.sub(r"\(\\path\{stageG1_dipole_tracking\.py\},\s*\\path\{stageG16_dipole_under_field\.py\}\)", "(\\\\path{stageG2_depinning.py})", m)
    if name == "main.tex":
        m = m.replace("% Volatile numbers are collected in the macro block below so that late updates\n% from the G6 re-analysis touch exactly one place.\n", "")
    else:
        m = m.replace("% pdflatex + babel, статья до ~20 000 знаков, аннотация без структурирования,\n", "% pdflatex + babel, аннотация без структурирования,\n")
    io.open(p, "w", encoding="utf-8", newline="\n").write(m)
    if "stageG2_depinning.py" not in m:
        rep.append("data-availability-" + name)

# splice: do not add a second \todo definition
p = PAPER / "splice_drafts.py"; s = io.open(p, encoding="utf-8").read()
s = s.replace('    new.insert(pre_end, r"\\providecommand{\\todo}[1]{\\textbf{[TODO: #1]}}")\n', '')
io.open(p, "w", encoding="utf-8", newline="\n").write(s)

# ---------------------------------------------------------------- README
rp = REPO / "README.md"; r = io.open(rp, encoding="utf-8").read()
r = r.replace("95--105", "95–105")
r = r.replace("The field of the strained ridge at the pair's position is 5–10 MPa, below the 9 MPa frame resolution of the ramp.",
              "The field of the strained ridge where the pair sits is 5–14 MPa, comparable with the 9 MPa frame resolution of the ramp, so no shift of the onset is resolvable.")
r = r.replace("Поле деформированного гребня в позиции пары — 5–10 МПа, ниже разрешения рампы в 9 МПа.",
              "Поле деформированного гребня там, где находится пара, — 5–14 МПа, сравнимо с разрешением рампы (9 МПа), поэтому сдвиг порога не разрешается.")
r = r.replace("The loaded-cell trajectories (stages G15/G16, ~400 MB each)\nare not in the repository; their records are.",
              "The loaded-cell trajectories (stage G15, three ramps, 180–400 MB each) are\nnot in the repository; their records are (`stageG2_depinning_summary_G15ctl_free.json`,\n`stageG2_depinning_summary_G15held.json` and the per-frame CSVs).")
i = r.find("The conclusion it will carry"); j = r.find("## Licence", i)
if i > 0 and j > 0:
    r = r[:i] + ("The conclusion it carries is conditional. The stress the experiment requires,\n"
                 "8.4–62.7 MPa at the inclusion surface for activation volumes of 19–142 b³, is\n"
                 "reproduced by the computed 15–41 MPa for V* = 30–75 b³ — a range that contains\n"
                 "the value measured for Al–Mg–Si — but only if the inclusions really strain by\n"
                 "0.194 % in the field: the magnetostriction measured for bulk Fe–Al alloys is\n"
                 "twenty times smaller and would give an enhancement below 0.4 %. Two open\n"
                 "problems remain: the ferromagnetic constituent of the inclusions has not been\n"
                 "identified (stoichiometric Al₁₃Fe₄ does not order magnetically), and the\n"
                 "30-minute field-off protocol is a *memory*, which an elastic stress cannot\n"
                 "carry; a slow diffusional channel is the remaining candidate and these\n"
                 "calculations do not test it.\n\n") + r[j:]
else:
    rep.append("readme-conclusion")
io.open(rp, "w", encoding="utf-8", newline="\n").write(r)

# ---------------------------------------------------------------- highlights (round 3b template)
p = DR / "patch_round3b.py"; s = io.open(p, encoding="utf-8").read()
s = s.replace("\\item A two-scale estimate reproduces the +25\\% creep for $V^{*}$ = «VSTAR_LO»--«VSTAR_HI» $b^{3}$ if the strain is real",
              "\\item A two-scale estimate gives the +25\\% creep for $V^{*}$ = «VSTAR_LO»--«VSTAR_HI» $b^{3}$ if the strain is real")
io.open(p, "w", encoding="utf-8", newline="\n").write(s)

print("review-2 fixes applied; unmatched:", rep if rep else "none")
