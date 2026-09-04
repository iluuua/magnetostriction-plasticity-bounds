#!/usr/bin/env python3
"""Produce Word versions of both manuscripts for review by a co-author.

Pandoc reads LaTeX well but not elsarticle's frontmatter, not BibTeX
citations, and not PDF figures (Word cannot display those). This script makes
a review copy of each source with those three things resolved -- citations
replaced by the numbers the compiled PDF shows, figures pointed at the PNG
twins, frontmatter flattened into ordinary headings -- and converts it.

The result is a .docx whose text, numbering and figure order match the PDF the
co-author already has, so a comment on page 7 of the PDF lands on the same
paragraph in Word.
"""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pypandoc

HERE = Path(__file__).resolve().parent
BUILD = HERE / "_docx_build"


def bbl_entries(path: Path) -> tuple[dict[str, int], list[str]]:
    """Citation key -> number, and the formatted entries in order."""
    raw = io.open(path, encoding="utf-8").read()
    chunks = raw.split("\\bibitem{")[1:]
    keys, texts = {}, []
    for i, ch in enumerate(chunks, 1):
        key, rest = ch.split("}", 1)
        rest = rest.split("\\bibitem")[0]
        rest = rest.replace("\\end{thebibliography}", "")
        # drop the href wrapper, keep the doi text
        rest = re.sub(r"\\newblock\s*", " ", rest)
        rest = re.sub(r"\\href\s*\{[^}]*\}\s*\{\\path\{([^}]*)\}\}", r"\1", rest)
        rest = re.sub(r"\\path\{([^}]*)\}", r"\1", rest)
        rest = re.sub(r"\s+", " ", rest).strip()
        keys[key] = i
        texts.append(rest)
    return keys, texts


def numbers_for(keys: dict[str, int], group: str) -> str:
    nums = []
    for k in group.split(","):
        k = k.strip()
        if k in keys:
            nums.append(keys[k])
    if not nums:
        return "[?]"
    nums.sort()
    # collapse runs of three or more
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append("%d--%d" % (nums[i], nums[j]) if j - i >= 2 else
                   ", ".join(str(n) for n in nums[i:j + 1]))
        i = j + 1
    return "[" + ", ".join(out) + "]"


def prepare_en(src: Path, dst: Path) -> None:
    t = io.open(src, encoding="utf-8").read()
    keys, refs = bbl_entries(HERE / "main.bbl")

    t = re.sub(r"\\cite\{([^}]*)\}", lambda m: numbers_for(keys, m.group(1)), t)

    # flatten the elsarticle frontmatter
    fm = t[t.index("\\begin{frontmatter}"):t.index("\\end{frontmatter}") + len("\\end{frontmatter}")]
    title = re.search(r"\\title\{(.*?)\}\s*\n\s*\n", fm, re.S)
    title_txt = re.sub(r"\s+", " ", title.group(1)) if title else "Manuscript"
    abstract = fm[fm.index("\\begin{abstract}") + len("\\begin{abstract}"):fm.index("\\end{abstract}")]
    keyw = fm[fm.index("\\begin{keyword}") + len("\\begin{keyword}"):fm.index("\\end{keyword}")]
    keyw = keyw.replace("\\sep", ";")
    new_fm = (
        "\\begin{center}\n{\\LARGE %s}\n\n\\medskip\nI.~Mikhailovskiy, D.~Pshonkin\n\n"
        "\\emph{Moscow Polytechnic University, Moscow, Russia}\n\n"
        "ilyamihailovsy@gmail.com\n\\end{center}\n\n"
        "\\section*{Abstract}\n%s\n\n\\section*{Keywords}\n%s\n" % (title_txt, abstract, keyw))
    t = t.replace(fm, new_fm)

    # bibliography from the .bbl, so the numbers match the PDF
    reflist = "\\section*{References}\n\\begin{enumerate}\n" + \
              "".join("\\item %s\n" % r for r in refs) + "\\end{enumerate}\n"
    t = re.sub(r"\\bibliographystyle\{[^}]*\}\s*\n\\bibliography\{[^}]*\}",
               lambda _m: reflist, t)

    finish(t, dst, "en")


def prepare_ru(src: Path, dst: Path) -> None:
    t = io.open(src, encoding="utf-8").read()
    # the RU list is already a manual enumerate; pandoc handles it
    finish(t, dst, "ru")


def finish(t: str, dst: Path, lang: str) -> None:
    # Word cannot show PDF figures: use the PNG twins
    t = re.sub(r"\\includegraphics(\[[^]]*\])?\{(fig_[a-z_]+_(?:en|ru))\}",
               r"\\includegraphics{\2.png}", t)
    # chemical formulae become Word equation objects if left in math mode, which
    # is awkward to edit; Unicode subscripts stay ordinary text
    subs = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
            "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉"}
    t = re.sub(r"\$_\{?(\d+)\}?\$",
               lambda m: "".join(subs[c] for c in m.group(1)), t)
    # packages and commands pandoc's reader does not need
    t = re.sub(r"\\FloatBarrier", "", t)
    t = t.replace("\\usepackage{placeins}", "")
    t = t.replace("\\path{", "\\texttt{")
    io.open(dst, "w", encoding="utf-8", newline="\n").write(t)


def main() -> int:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir()
    for f in HERE.glob("fig_*_??.png"):
        shutil.copy(f, BUILD / f.name)

    prepare_en(HERE / "main.tex", BUILD / "en.tex")
    prepare_ru(HERE / "main_ru.tex", BUILD / "ru.tex")

    for stem, out in (("en", "manuscript_EN_editable.docx"),
                      ("ru", "manuscript_RU_editable.docx")):
        pypandoc.convert_file(
            str(BUILD / (stem + ".tex")), "docx",
            outputfile=str(HERE / out),
            extra_args=["--resource-path=" + str(BUILD),
                        "--number-sections",
                        "--wrap=none"])
        print("%-32s %8d bytes" % (out, (HERE / out).stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
