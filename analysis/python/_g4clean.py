#!/usr/bin/env python3
"""Read the paired interface snapshots used for stress and strain analysis.

The default inputs are the held control and strained snapshots in
``data/stageG4_clean``. Coordinates are in angstroms; ``c_st[1:6]`` contains
LAMMPS stress/atom values in bar * angstrom^3, ordered xx, yy, zz, xy, xz, yz.
Readers accept plain or gzip text, use column names, and sort by atom ID.
"""

from __future__ import annotations

import glob
import gzip
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import numpy as np

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DIR = REPO / "data" / "stageG4_clean"

CONTROL = "G13_pert_ctl_held.gate.lammpstrj"
FIELD = "G13_pert_fld_held.gate.lammpstrj"
STRESS_COLUMNS = tuple(f"c_st[{i}]" for i in range(1, 7))


@dataclass
class DumpFrame:
    """One orthogonal LAMMPS frame with arrays sorted by atom ID."""

    timestep: int
    ids: np.ndarray
    types: np.ndarray
    positions: np.ndarray
    bounds: np.ndarray
    columns: tuple[str, ...]
    stress: np.ndarray | None = None


def source_dir(override: str | os.PathLike | None = None) -> Path:
    """Resolve an explicit directory, G4CLEAN_DIR, or the curated default."""
    if override:
        return Path(override)
    env = os.environ.get("G4CLEAN_DIR")
    return Path(env) if env else DEFAULT_DIR


def resolve_dump(path: str | os.PathLike) -> Path:
    """Find a file, falling back to its .gz counterpart."""
    path = Path(path)
    for candidate in (path, Path(str(path) + ".gz")):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"No dump at {path} or {path}.gz")


def open_text(path: str | os.PathLike) -> TextIO:
    """Open plain or gzip UTF-8 text without silently replacing bad bytes."""
    path = resolve_dump(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def open_dump(directory: Path, name: str) -> TextIO:
    """Open a named snapshot from the selected source directory."""
    return open_text(Path(directory) / name)


def trajectory_paths(pattern: str | os.PathLike) -> list[Path]:
    """Resolve a trajectory or a quoted, zero-padded shard glob for OVITO."""
    pattern = str(pattern)
    if glob.has_magic(pattern):
        paths = sorted(Path(p) for p in glob.glob(pattern) if Path(p).is_file())
        if not paths:
            raise FileNotFoundError(f"No trajectory matches {pattern}")
        return paths
    return [resolve_dump(pattern)]


def file_provenance(path: str | os.PathLike, *, checksum: bool = True) -> dict:
    """Describe an input; SHA-256 refers to the stored bytes, including gzip."""
    path = resolve_dump(path).resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = str(path)
    result = {"path": name, "size_bytes": path.stat().st_size}
    if checksum:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result["sha256"] = digest.hexdigest()
    return result


def read_snapshot(stream: TextIO, *, require_stress: bool = False) -> DumpFrame:
    """Read exactly one orthogonal frame; reject ambiguous or incomplete data.

    Extra columns and arbitrary row/column order are allowed. Scaled
    coordinates and triclinic boxes are rejected rather than misinterpreted.
    """
    if stream.readline().strip() != "ITEM: TIMESTEP":
        raise ValueError("Expected ITEM: TIMESTEP")
    timestep = int(stream.readline())
    if stream.readline().strip() != "ITEM: NUMBER OF ATOMS":
        raise ValueError("Expected ITEM: NUMBER OF ATOMS")
    count = int(stream.readline())
    if count <= 0:
        raise ValueError("Snapshot contains no atoms")
    box_header = stream.readline().split()
    if box_header[:3] != ["ITEM:", "BOX", "BOUNDS"]:
        raise ValueError("Expected ITEM: BOX BOUNDS")
    if any(key in box_header[3:] for key in ("xy", "xz", "yz", "abc", "origin")):
        raise ValueError("Only orthogonal snapshot boxes are supported")
    bounds = np.array([[float(v) for v in stream.readline().split()] for _ in range(3)])
    if bounds.shape != (3, 2) or np.any(bounds[:, 1] <= bounds[:, 0]):
        raise ValueError("Invalid orthogonal box bounds")
    header = stream.readline().split()
    if header[:2] != ["ITEM:", "ATOMS"]:
        raise ValueError("Expected ITEM: ATOMS")
    columns = tuple(header[2:])
    if len(columns) != len(set(columns)):
        raise ValueError("Duplicate atom column names")
    coordinates = ("x", "y", "z")
    if not all(key in columns for key in coordinates):
        coordinates = ("xu", "yu", "zu")
    required = ("id", "type", *coordinates)
    if require_stress:
        required += STRESS_COLUMNS
    missing = set(required).difference(columns)
    if missing:
        raise ValueError(f"Missing atom columns: {sorted(missing)}")
    indices = [columns.index(key) for key in required]
    rows = np.empty((count, len(required)), dtype=float)
    for i in range(count):
        values = stream.readline().split()
        if len(values) != len(columns) or values[:1] == ["ITEM:"]:
            raise ValueError(f"Incomplete atom row {i + 1} of {count}")
        rows[i] = [float(values[j]) for j in indices]
    if any(line.strip() for line in stream):
        raise ValueError("Expected one snapshot; multiple frames or trailing data found")
    if not np.isfinite(rows).all() or not np.isfinite(bounds).all():
        raise ValueError("Non-finite snapshot data")
    if np.any(rows[:, :2] != np.floor(rows[:, :2])) or np.any(rows[:, :2] <= 0):
        raise ValueError("Atom IDs and types must be positive integers")
    rows = rows[np.argsort(rows[:, 0])]
    ids = rows[:, 0].astype(np.int64)
    if len(np.unique(ids)) != count:
        raise ValueError("Duplicate atom IDs")
    return DumpFrame(
        timestep,
        ids,
        rows[:, 1].astype(int),
        rows[:, 2:5],
        bounds,
        columns,
        rows[:, 5:11] if require_stress else None,
    )


def validate_pair(control: DumpFrame, field: DumpFrame) -> None:
    """Check atom correspondence and fixed-box geometry before subtraction."""
    if not np.array_equal(control.ids, field.ids):
        raise ValueError("Control and strained snapshots have different atom IDs")
    if not np.array_equal(control.types, field.types):
        raise ValueError("Control and strained snapshots have different atom types")
    if not np.allclose(control.bounds, field.bounds, rtol=0.0, atol=1e-8):
        raise ValueError("Control and strained snapshots must use the same fixed box")
