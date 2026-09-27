#!/usr/bin/env python3
"""Build the English/Russian manuscripts and supplements with local LaTeX.

Sources and figures remain in docs/paper. Intermediate files are isolated in
build/paper; successful PDFs and bibliography output are copied back. Each
Overleaf archive contains only the source's referenced figures and bibliography.
Run the figure generator before this script. No simulation is started.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "docs/paper"
BUILD = ROOT / "build/paper"
DOCUMENTS = {
    "main": "manuscript_en.pdf",
    "main_ru": "manuscript_ru.pdf",
    "supplementary": "supplementary_en.pdf",
    "supplementary_ru": "supplementary_ru.pdf",
    "highlights": "highlights.pdf",
}


def figures(text: str) -> list[Path]:
    """Resolve each figure named by an includegraphics command."""
    result = []
    for name in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", text):
        candidate = PAPER / name
        if not candidate.suffix:
            candidate = next(
                (
                    candidate.with_suffix(s)
                    for s in (".pdf", ".png", ".jpg")
                    if candidate.with_suffix(s).is_file()
                ),
                candidate,
            )
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        result.append(candidate)
    return result


def run(arguments: list[str], env: dict[str, str]) -> None:
    """Run one TeX tool and keep its full diagnostics in the build directory."""
    proc = subprocess.run(
        arguments,
        cwd=BUILD,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    name = Path(arguments[0]).stem + "-" + Path(arguments[-1]).stem + ".txt"
    (BUILD / name).write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"{arguments[0]} failed; see {BUILD / name}\n{proc.stdout[-2000:]}")


def build(stem: str, executable: str, env: dict[str, str]) -> None:
    """Compile a document, resolve citations and reject undefined references."""
    source = PAPER / f"{stem}.tex"
    text = source.read_text(encoding="utf-8")
    used_figures = figures(text)
    for path in (source, PAPER / "references.bib", *used_figures):
        if path.is_file():
            shutil.copy2(path, BUILD / path.name)
    args = [executable, "-interaction=nonstopmode", "-halt-on-error", f"{stem}.tex"]
    run(args, env)
    aux = (BUILD / f"{stem}.aux").read_text(encoding="utf-8", errors="replace")
    if "\\bibdata" in aux:
        run(["bibtex", stem], env)
    run(args, env)
    run(args, env)
    log = (BUILD / f"{stem}.log").read_text(encoding="utf-8", errors="replace")
    if re.search(r"(?:Citation|Reference).*undefined|There were undefined", log):
        raise RuntimeError(f"Undefined references in {stem}.log")
    shutil.copy2(BUILD / f"{stem}.pdf", PAPER / DOCUMENTS[stem])
    if (BUILD / f"{stem}.bbl").is_file():
        shutil.copy2(BUILD / f"{stem}.bbl", PAPER / f"{stem}.bbl")
    if stem in ("main", "main_ru"):
        language = "en" if stem == "main" else "ru"
        with zipfile.ZipFile(
            PAPER / f"overleaf_{language}.zip", "w", zipfile.ZIP_DEFLATED
        ) as archive:
            archive.write(source, "main.tex")
            if "\\bibliography" in text:
                archive.write(PAPER / "references.bib", "references.bib")
            if (BUILD / f"{stem}.bbl").is_file():
                archive.write(BUILD / f"{stem}.bbl", "main.bbl")
            for figure in sorted(set(used_figures)):
                archive.write(figure, figure.name)
    print(f"Built {DOCUMENTS[stem]}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="pdflatex")
    parser.add_argument("--only", choices=tuple(DOCUMENTS))
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # MiKTeX rejects PATH entries that point at files rather than directories.
    env["PATH"] = os.pathsep.join(
        p for p in env.get("PATH", "").split(os.pathsep) if Path(p).is_dir()
    )
    for stem in [args.only] if args.only else DOCUMENTS:
        build(stem, args.engine, env)


if __name__ == "__main__":
    main()
