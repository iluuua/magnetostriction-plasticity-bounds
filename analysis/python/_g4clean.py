#!/usr/bin/env python3
"""Locate and read the two minimized Stage G4 interface dumps.

These two files are the provenance of everything the manuscript says about the
stress field: the 6.3 MPa peak, the decay length, the noise floor and the
retained-strain table. They used to be read from a hard-coded Windows temp
directory, which meant the published analysis scripts could not run anywhere
else and would stop working here as soon as the temp directory was cleared.

They now live in data/stageG4_clean/ inside the repository, gzipped (5.6 MB
each raw, 2.0 MB each compressed). Set G4CLEAN_DIR, or pass --src, to read them
from somewhere else.
"""
from __future__ import annotations

import gzip
import io
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DIR = REPO / "data" / "stageG4_clean"

CONTROL = "G4_tilted_eps0000_clean.gate.lammpstrj"
FIELD = "G4_tilted_eps00194_clean.gate.lammpstrj"


def source_dir(override: str | os.PathLike | None = None) -> Path:
    if override:
        return Path(override)
    env = os.environ.get("G4CLEAN_DIR")
    return Path(env) if env else DEFAULT_DIR


def open_dump(directory: Path, name: str):
    """Open a dump whether it is stored plain or gzipped."""
    plain, gz = directory / name, directory / (name + ".gz")
    if plain.exists():
        return io.open(plain, encoding="utf-8", errors="replace")
    if gz.exists():
        return io.TextIOWrapper(gzip.open(gz, "rb"), encoding="utf-8", errors="replace")
    raise FileNotFoundError(
        "neither %s nor %s exists; set G4CLEAN_DIR or pass --src" % (plain, gz))
