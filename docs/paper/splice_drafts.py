#!/usr/bin/env python3
"""Assemble the rewritten manuscript from the section drafts in _drafts/.

Front matter (title, authors, affiliations, back matter) is kept from the
current main.tex / main_ru.tex; the abstract, keywords and every numbered
section are taken from the drafts. Output: main_v2.tex / main_ru_v2.tex,
which replace the originals once the numbers are final.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DR = HERE / "_drafts"


def read(p: Path) -> list[str]:
    return io.open(p, encoding="utf-8").read().splitlines()


def find(lines: list[str], startswith: str, after: int = 0) -> int:
    for i in range(after, len(lines)):
        if lines[i].startswith(startswith):
            return i
    raise SystemExit(f"marker not found: {startswith!r}")


def body(lang: str) -> list[str]:
    out = []
    for name in ("Section_1", "Section_2", "Section_3", "Sections_4"):
        d = read(DR / f"{name}_{lang}.tex")
        # drop the drafting header comment / providecommand at the top of Section_2
        d = [ln for ln in d if not ln.startswith("% \todo") and not ln.startswith("% and ")
             and not ln.startswith("\providecommand{\todo}")]
        while d and not d[0].strip():
            d.pop(0)
        out.extend(d)
        out.append("")
    return out


def splice_en() -> None:
    src = read(HERE / "main.tex")
    a0 = find(src, r"\begin{abstract}")
    a1 = find(src, r"\end{keyword}", a0)
    b0 = find(src, r"\section{Introduction}", a1)
    b1 = find(src, r"\section*{CRediT", b0)
    abstract = read(DR / "Abstract_and_keywords_en.tex")
    new = src[:a0] + abstract + src[a1 + 1:b0] + body("en") + src[b1:]
    # the drafts use \todo; make sure the macro exists once, in the preamble
    pre_end = find(new, r"\begin{document}")
    io.open(HERE / "main_v2.tex", "w", encoding="utf-8", newline="\n").write("\n".join(new) + "\n")
    print("main_v2.tex: %d lines (was %d)" % (len(new), len(src)))


def splice_ru() -> None:
    src = read(HERE / "main_ru.tex")
    a0 = find(src, r"\noindent\textbf{Аннотация.}")
    k0 = find(src, r"\noindent\textbf{Ключевые слова:}", a0)
    b0 = find(src, r"\section{Введение}", k0)
    b1 = find(src, r"\section*{Список литературы}", b0)
    abstract = read(DR / "Abstract_and_keywords_ru.tex")
    new = src[:a0] + abstract + [""] + body("ru") + src[b1:]
    pre_end = find(new, r"\begin{document}")
    io.open(HERE / "main_ru_v2.tex", "w", encoding="utf-8", newline="\n").write("\n".join(new) + "\n")
    print("main_ru_v2.tex: %d lines (was %d)" % (len(new), len(src)))


if __name__ == "__main__":
    splice_en(); splice_ru()
