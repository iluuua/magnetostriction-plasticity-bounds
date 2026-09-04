#!/usr/bin/env python3
"""Corrections from the record-versus-text cross-check (4 Sept 2026).

Every one of these is a place where the manuscript stated something the records
do not support. The claims the cross-check raised that turned out to be right as
written (the 96 ps ramp, which is PRE_STEPS=5000 to NSTEPS=101000 and not the
88 ps that a fit to the nominal-tau column suggests) are left alone.
"""
from __future__ import annotations
import io
import re
from pathlib import Path

DR = Path(__file__).resolve().parent
rep = []


def sub(t, old, new, tag, count=1):
    pat = r"\s+".join(re.escape(p) for p in re.split(r"\s+", old.strip()))
    out, n = re.subn(pat, lambda m: new, t, count=count)
    if n == 0:
        rep.append(tag)
    return out


def load(n):
    return io.open(DR / n, encoding="utf-8").read()


def save(n, t):
    io.open(DR / n, "w", encoding="utf-8", newline="\n").write(t)


# --------------------------------------------------------------- Section 2 EN
t = load("Section_2_en.tex")
# the standard error of the fit is 0.0038 in the record, not 0.01
t = sub(t, r"$0.97\pm0.01$ of the imposed strain", r"$0.97\pm0.004$ of the imposed strain",
        "s2-eta-en")
# 27 A is where the partner is placed; it relaxes to 32 A before the ramp starts
t = sub(t, r"""The lower
partner lies 27~\AA{} beyond the foot of the ridge and 29~\AA{} above the
interface plane,""",
        r"""The lower
partner is placed 27~\AA{} beyond the foot of the ridge and 29~\AA{} above the
interface plane,""", "s2-27-en")
save("Section_2_en.tex", t)

t = load("Section_2_ru.tex")
t = sub(t, r"$0{,}97\pm0{,}01$ наложенной деформации",
        r"$0{,}97\pm0{,}004$ наложенной деформации", "s2-eta-ru")
t = sub(t, "Нижний партнёр лежит в 27~\\AA{}", "Нижний партнёр помещён в 27~\\AA{}", "s2-27-ru")
save("Section_2_ru.tex", t)

# --------------------------------------------------------------- Section 3 EN
t = load("Section_3_en.tex")

# one slice out of the twenty-two is won by a different system, and it is the
# near-cancellation slice the same paragraph already singles out
t = sub(t, r"""In every
slice above the crest the most favourable system is $(111)[1\bar{1}0]$: the""",
        r"""In every
slice above the crest but one the most favourable system is
$(111)[1\bar{1}0]$: the""", "s3-system-en")
t = sub(t, r"""resolved shear is simply the component $\Delta\sigma_{xz}$.""",
        r"""resolved shear is simply the component $\Delta\sigma_{xz}$. The exception is
the slice at $r=46$~\AA{}, where the two contributions nearly cancel and the
largest of the twelve values, 0.6~MPa, falls on $(111)[01\bar{1}]$.""",
        "s3-system2-en")

# the ridge/sphere comparison as the records actually give it
t = sub(t, r"""On the ridge axis the ridge and the sphere agree within a factor of two
out to $d\approx30$~\AA{} and within a factor of three out to
$d=50$~\AA{}; the width-averaged field lies three to six times below the
sphere over the same distances.""",
        r"""On the ridge axis the two agree within a factor of two between $d=10$ and
$26$~\AA{}. They agree in magnitude only there: closer in the sphere is the
larger, and beyond $d\approx14$~\AA{} the ridge is, until at $d=50$~\AA{} it
exceeds the sphere threefold. The width-averaged curve is not comparable with
either in this way, because slices in which the two contributions nearly
cancel alternate with slices in which they do not.""", "s3-factor-en")

t = sub(t, r"$0.97\pm0.01$ in the held cell.", r"$0.97\pm0.004$ in the held cell.",
        "s3-eta-en")

# the lower partner during the ramp, from the record of the loaded cell
t = sub(t, r"""The lower partner, 27~\AA{} beyond the foot of the ridge,
settles by 13~\AA{} in the same interval and then holds.""",
        r"""The lower partner, which by the start of the ramp sits 32~\AA{} beyond the
foot of the ridge, settles by 13~\AA{} in the same interval and then holds.""",
        "s3-32-en")

# the held lower partner is gone at the 10 ps frame in both cells
t = sub(t, "cell alike it leaves within the first 8~ps, through the periodic boundary,",
        "cell alike it is gone by 10~ps, through the periodic boundary,", "s3-10ps-en")

# the seam window as the two held records give it
t = sub(t, r"A short segment at that seam ($x=8$--$10$~\AA{}, $z=57$--$69$~\AA{}) is",
        r"A short segment at that seam ($x=7$--$10$~\AA{}, $z=57$--$70$~\AA{}) is",
        "s3-seamwin-en")
save("Section_3_en.tex", t)

# --------------------------------------------------------------- Section 3 RU
t = load("Section_3_ru.tex")
t = sub(t, "В каждом слое над вершиной наиболее благоприятной оказывается система $(111)[1\\bar{1}0]$:",
        "В каждом слое над вершиной, кроме одного, наиболее благоприятной оказывается система $(111)[1\\bar{1}0]$:",
        "s3-system-ru")
t = sub(t, r"разрешённый сдвиг равен просто компоненте $\Delta\sigma_{xz}$.",
        r"""разрешённый сдвиг равен просто компоненте $\Delta\sigma_{xz}$. Исключение ---
слой при $r = 46$~\AA{}, где два вклада почти компенсируют друг друга и
наибольшее из двенадцати значений, 0{,}6~МПа, приходится на
$(111)[01\bar{1}]$.""", "s3-system2-ru")
t = sub(t, r"""На оси гребня гребень и сфера согласуются в пределах множителя два до
$d \approx 30$~\AA{} и в пределах множителя три до $d = 50$~\AA{}; среднее
по ширине поле на тех же расстояниях в три--шесть раз ниже сферы.""",
        r"""На оси гребня они согласуются в пределах множителя два между $d = 10$ и
$26$~\AA{}. Только там их величины и сравнимы: ближе больше сфера, а за
$d \approx 14$~\AA{} --- гребень, и при $d = 50$~\AA{} он превышает сферу
втрое. Среднее по ширине так сравнивать нельзя: слои, где два вклада почти
компенсируются, чередуются со слоями, где этого не происходит.""",
        "s3-factor-ru")
t = sub(t, r"ячейке равна $0{,}97 \pm 0{,}01$.", r"ячейке равна $0{,}97 \pm 0{,}004$.",
        "s3-eta-ru")
t = sub(t, r"""Нижний партнёр, в 27~\AA{} за подножием гребня,
оседает на 13~\AA{} за тот же интервал и далее удерживается.""",
        r"""Нижний партнёр, который к началу рампы находится в 32~\AA{} за подножием
гребня, оседает на 13~\AA{} за тот же интервал и далее удерживается.""",
        "s3-32-ru")
t = sub(t, "он уходит через периодическую границу в первые 8~пс,",
        "он уходит через периодическую границу к 10~пс,", "s3-10ps-ru")
t = sub(t, r"($x = 8$--$10$~\AA{}, $z = 57$--$69$~\AA{})",
        r"($x = 7$--$10$~\AA{}, $z = 57$--$70$~\AA{})", "s3-seamwin-ru")
save("Section_3_ru.tex", t)

print("cross-check corrections applied; unmatched:", rep if rep else "none")
