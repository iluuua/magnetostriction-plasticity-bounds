#!/usr/bin/env python3
"""Check data integrity and manuscript packaging without starting simulations.

Checks cover manifest hashes, JSON/CSV consistency, local citations and figure
references, and readable PDFs. They cannot establish the physical validity of
the potential, convergence of MD, or editorial suitability for a journal.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "docs/paper"
REPORTS = ROOT / "docs/reports"


def check_profile() -> None:
    """Check that the CSV describes the same held-pair profile as its JSON."""
    record = json.loads((REPORTS / "stageG10_field_profile.json").read_text(encoding="utf-8"))
    with (REPORTS / "stageG10_field_profile.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    profile = record["profile"]
    if len(rows) != len(profile):
        raise ValueError("Profile CSV and JSON have different numbers of bins")
    checked = 0
    for row, source in zip(rows, profile, strict=True):
        for key, text in row.items():
            value = source.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isclose(float(text), value, rel_tol=1e-6, abs_tol=1e-6):
                    raise ValueError(f"Profile CSV disagrees at {source.get('r_A')}: {key}")
                checked += 1
    if checked == 0:
        raise ValueError("No shared numeric profile fields checked")
    print(f"Profile agreement: {checked} shared numeric fields")


def strip_comments(text: str) -> str:
    """Remove TeX comments, retaining escaped percent symbols."""
    return re.sub(r"(?<!\\)%[^\n]*", "", text)


def check_document(stem: str, pdf_name: str, require_pdf: bool) -> dict:
    """Check local TeX references and the exported PDF, if requested."""
    text = strip_comments((PAPER / f"{stem}.tex").read_text(encoding="utf-8"))
    bibliography = (PAPER / "references.bib").read_text(encoding="utf-8")
    keys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)", bibliography))
    keys.update(re.findall(r"\\bibitem(?:\[[^]]*\])?\{([^}]+)\}", text))
    citations = re.findall(r"\\cite\w*\*?(?:\[[^]]*\])*\{([^}]+)\}", text)
    missing = {key.strip() for group in citations for key in group.split(",")} - keys
    if missing:
        raise ValueError(f"Missing bibliography keys in {stem}: {sorted(missing)}")
    labels = re.findall(r"\\label\{([^}]+)\}", text)
    references = set(re.findall(r"\\(?:eqref|ref|autoref)\{([^}]+)\}", text))
    if references - set(labels) or len(labels) != len(set(labels)):
        raise ValueError(f"Missing or duplicate labels in {stem}")
    figure_names = re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", text)
    for name in figure_names:
        if not (PAPER / name).is_file():
            raise FileNotFoundError(f"Missing figure in {stem}: {name}")
    for name in re.findall(r"\\path\{([^}]+)\}", text):
        candidates = list(ROOT.glob(name)) + list(REPORTS.glob(name))
        if not candidates:
            raise FileNotFoundError(f"Missing cited dataset in {stem}: {name}")
    if re.search(r"\\todo\b|\[TODO|«[A-Z_]", text):
        raise ValueError(f"Unresolved editing placeholder in {stem}")
    result = {
        "source": f"docs/paper/{stem}.tex",
        "figures": len(figure_names),
        "citation_keys": len(keys),
    }
    if require_pdf:
        import pymupdf

        with pymupdf.open(PAPER / pdf_name) as document:
            if not document.page_count or any(not page.get_text().strip() for page in document):
                raise ValueError(f"Empty page or unreadable PDF: {pdf_name}")
            bitmap_fonts = {
                font[3] for page in document for font in page.get_fonts() if font[2] == "Type3"
            }
            if bitmap_fonts:
                raise ValueError(f"Bitmap text fonts in {pdf_name}: {bitmap_fonts}")
            result["pages"] = document.page_count
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources-only", action="store_true", help="skip PDF checks before compilation"
    )
    args = parser.parse_args()
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/package_publication_data.py"), "--verify"], check=True
    )
    check_profile()
    results = [
        check_document(stem, pdf, not args.sources_only)
        for stem, pdf in (
            ("main", "manuscript_en.pdf"),
            ("main_ru", "manuscript_ru.pdf"),
            ("supplementary", "supplementary_en.pdf"),
            ("supplementary_ru", "supplementary_ru.pdf"),
        )
    ]
    print(json.dumps(results, indent=2))
    print("Integrity and packaging checks passed; scientific validation has a separate scope.")


if __name__ == "__main__":
    main()
