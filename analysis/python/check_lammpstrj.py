#!/usr/bin/env python3
"""Check that a LAMMPS dump can be read, using OVITO when available."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def fallback_read(path: Path) -> dict[str, object]:
    n_atoms = None
    n_frames = 0
    with path.open(errors="replace") as handle:
        for line in handle:
            if line.startswith("ITEM: TIMESTEP"):
                n_frames += 1
            elif line.startswith("ITEM: NUMBER OF ATOMS"):
                n_atoms = int(next(handle).strip())
    if n_atoms is None:
        raise ValueError(f"Could not find NUMBER OF ATOMS in {path}")
    print("OVITO Python module: unavailable")
    print("fallback: parsed lammpstrj headers")
    print(f"frames: {n_frames}")
    print(f"atoms_per_frame: {n_atoms}")
    return {
        "dump_path": str(path),
        "reader": "fallback_header_parser",
        "ovito_python_available": False,
        "frames": n_frames,
        "atoms_per_frame": n_atoms,
    }


def ovito_read(path: Path) -> dict[str, object] | None:
    try:
        from ovito.io import import_file
    except Exception as exc:
        print(f"OVITO Python import failed: {exc}")
        return None

    pipeline = import_file(str(path))
    data = pipeline.compute(0)
    print("OVITO Python module: available")
    print(f"frames: {pipeline.source.num_frames}")
    print(f"atoms_in_first_frame: {data.particles.count}")
    return {
        "dump_path": str(path),
        "reader": "ovito",
        "ovito_python_available": True,
        "frames": pipeline.source.num_frames,
        "atoms_per_frame": data.particles.count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dump_path",
        type=Path,
        nargs="?",
        default=Path("lammps/00_relax_al/dump.al_npt.lammpstrj"),
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    args = parser.parse_args()

    if not args.dump_path.exists():
        raise FileNotFoundError(args.dump_path)
    summary = ovito_read(args.dump_path)
    if summary is None:
        summary = fallback_read(args.dump_path)
    if args.output:
        args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
        print(f"json: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
