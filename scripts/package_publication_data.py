#!/usr/bin/env python3
"""Package the saved simulations used by the manuscript, without running LAMMPS.

G15 trajectories retain every recorded frame and the original decimal strings
for atom IDs, types and coordinates. Per-atom energies and virials are omitted
from these position trajectories; the separate final dumps retain all columns.
The held-interface dumps in data/stageG4_clean retain the complete virials used
for the stress analysis. SHA-256 hashes identify every source and output.

Run from any directory with the original runs/ tree available. Outputs are
deterministic gzip files split at frame boundaries to stay below GitHub's
per-file size limit. --verify checks the published files without local runs.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "data/publication"
G15_RUNS = {
    "g15_free_control": ("runs/stageG15_unified/20260903-041548-482289/G15_ctl", "G15_ctl", "0000"),
    "g15_held_control": (
        "runs/stageG15_unified/20260904-021832-814770_held/G15_ctl",
        "G15_ctl",
        "0000",
    ),
    "g15_held_strained": (
        "runs/stageG15_unified/20260904-021832-814770_held/G15_fld",
        "G15_fld",
        "00194",
    ),
}
PERTURBATION = "runs/stageG13_interface100k/20260903-153826-627855_u100k_pert"
ALLOY = "runs/stageG6_vstar/20260823-174823/G3_solute_relA"


def sha256(path: Path) -> str:
    """Hash a file without loading its contents into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe(path: Path) -> dict:
    """Identify repository files or an external archive without exposing host paths."""
    return {
        "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def compress(source: Path, destination: Path) -> dict:
    """Losslessly gzip one file with a reproducible header."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as out:
            shutil.copyfileobj(src, out)
    return {
        "source": describe(source),
        "output": describe(destination),
        "transformation": "lossless gzip",
    }


def positions(
    source: Path, destination: Path, frames_per_file: int = 20, *, full_columns: bool = False
) -> dict:
    """Split a dump at frame boundaries, optionally retaining every original column."""
    destination.mkdir(parents=True, exist_ok=True)
    outputs, steps = [], []
    stream = raw = None
    with source.open("rb") as src:
        try:
            while marker := src.readline():
                if marker.strip() != b"ITEM: TIMESTEP":
                    raise ValueError(f"Unexpected dump header in {source}")
                step_line = src.readline()
                number_header, count_line = src.readline(), src.readline()
                bounds_header = src.readline()
                if number_header.strip() != b"ITEM: NUMBER OF ATOMS":
                    raise ValueError("Missing atom count")
                if not bounds_header.startswith(b"ITEM: BOX BOUNDS"):
                    raise ValueError("Missing simulation box")
                bounds = [src.readline() for _ in range(3)]
                atom_header = src.readline()
                fields = atom_header.split()[2:]
                indices = [fields.index(name) for name in (b"id", b"type", b"x", b"y", b"z")]
                if len(steps) % frames_per_file == 0:
                    if stream is not None:
                        stream.close()
                        raw.close()
                    out_path = destination / f"trajectory.{len(outputs):03d}.lammpstrj.gz"
                    outputs.append(out_path)
                    raw = out_path.open("wb")
                    stream = gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0)
                stream.writelines(
                    [
                        marker,
                        step_line,
                        number_header,
                        count_line,
                        bounds_header,
                        *bounds,
                        atom_header if full_columns else b"ITEM: ATOMS id type x y z\n",
                    ]
                )
                for _ in range(int(count_line)):
                    original = src.readline()
                    row = original.split()
                    if len(row) != len(fields):
                        raise ValueError(f"Truncated or malformed frame in {source}")
                    stream.write(
                        original if full_columns else b" ".join(row[i] for i in indices) + b"\n"
                    )
                steps.append(int(step_line))
        finally:
            if stream is not None:
                stream.close()
                raw.close()
    if any(b <= a for a, b in zip(steps, steps[1:], strict=False)):
        raise ValueError(f"Non-increasing timesteps in {source}")
    return {
        "source": describe(source),
        "outputs": [describe(p) for p in outputs],
        "transformation": (
            "lossless full-column gzip shards at frame boundaries"
            if full_columns
            else "all saved frames; unchanged id/type/x/y/z strings and box headers"
        ),
        "omitted_columns": [] if full_columns else ["per-atom potential energy and virial stress"],
        "timesteps": steps,
        "time_step_ps": 0.001,
    }


def build() -> None:
    """Collect the three ramps and the static and alloy supporting states."""
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "description": "Primary data for the shortened manuscript",
        "units": "LAMMPS metal: angstrom, ps, eV; stress/atom is bar angstrom^3",
        "files": [],
        "trajectories": {},
        "limitations": [
            "The alloy initial file is a candidate replay input. No launch-time hash "
            "or original copy verifies its initial mobile coordinates.",
            "The alloy preparation stops on energy tolerance with force two-norm "
            "10.118429 eV/angstrom; force convergence is not established.",
            "The original G6 alloy trajectory is unavailable in this checkout. "
            "Its saved frame analysis, input, log and final state are provided; "
            "these alone cannot reproduce time-resolved DXA.",
            "G15 position trajectories omit energy and stress columns. "
            "Full originals remain local; final and held-interface dumps retain all columns.",
            "Regular sampling stops before the run endpoint. "
            "The separately saved final state is not appended to the analysis sequence.",
        ],
    }
    previous_path = DESTINATION / "manifest.json"
    previous = (
        json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    )

    def initial_file(source: Path, output: Path) -> dict:
        # The curated repository ships the compressed initial state, not a duplicate.
        if source.exists():
            return compress(source, output)
        for entry in previous.get("files", []):
            if entry["output"]["path"] == output.relative_to(ROOT).as_posix():
                if output.exists() and sha256(output) == entry["output"]["sha256"]:
                    return entry
        raise FileNotFoundError(f"Neither original nor verified packaged initial state: {source}")

    for name, (run, case, strain) in G15_RUNS.items():
        folder, output = ROOT / run, DESTINATION / name
        manifest["trajectories"][name] = positions(folder / f"{case}.production.lammpstrj", output)
        for source_name, target_name in (
            (f"{case}.production.final.data", "final.data.gz"),
            (f"{case}.production.final.lammpstrj", "final.lammpstrj.gz"),
            ("log.lammps", "log.lammps.gz"),
        ):
            manifest["files"].append(compress(folder / source_name, output / target_name))
        cell = f"G4_tilted_eps{strain}_dipu100k"
        initial = ROOT / "structures/stageG4_tilted_solute" / cell / f"{cell}.start.data"
        manifest["files"].append(initial_file(initial, output / "initial.data.gz"))
        print(f"Packaged {name}", flush=True)
    for case in ("ctl", "fld"):
        manifest["files"].append(
            compress(
                ROOT / PERTURBATION / "cells" / f"pert_{case}.data",
                DESTINATION / "interface" / f"initial_{case}.data.gz",
            )
        )
    reference = (
        ROOT
        / "runs/stageG13_interface100k/20260903-001905-144804_u100k_v3"
        / "ctl_held/ctl_held.gate.lammpstrj"
    )
    manifest["files"].append(
        compress(reference, DESTINATION / "interface/relaxed_reference.lammpstrj.gz")
    )
    for name in ("G3_solute_relA.vstar.final.data", "log.lammps"):
        manifest["files"].append(
            compress(
                ROOT / ALLOY / name,
                DESTINATION
                / "alloy"
                / ("final.data.gz" if name.endswith("data") else "log.lammps.gz"),
            )
        )
    initial = ROOT / "structures/stageG3_solute_mobility/G3_solute_relA/G3_solute_relA.start.data"
    manifest["files"].append(initial_file(initial, DESTINATION / "alloy/initial.data.gz"))
    if "alloy" in previous.get("trajectories", {}):
        recovered = previous["trajectories"]["alloy"]
        for entry in recovered["outputs"]:
            if sha256(ROOT / entry["path"]) != entry["sha256"]:
                raise ValueError("Recovered alloy archive has changed; rebuild it explicitly")
        manifest["trajectories"]["alloy"] = recovered
        manifest["limitations"] = [
            item for item in manifest["limitations"] if not item.startswith("The original G6")
        ]
    preparation_log = reference.parent / "log.lammps"
    manifest["files"].append(
        compress(preparation_log, DESTINATION / "interface/preparation.log.lammps.gz")
    )
    manifest["held_stress_data"] = [
        describe(p) for p in sorted((ROOT / "data/stageG4_clean").glob("*.gz"))
    ]
    (DESTINATION / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def augment(alloy_trajectory: Path) -> None:
    """Add a recovered alloy history and reference-preparation log to the package."""
    manifest_path = DESTINATION / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["trajectories"]["alloy"] = positions(
        alloy_trajectory.resolve(), DESTINATION / "alloy", full_columns=True
    )
    manifest["trajectories"]["alloy"]["source_origin"] = "verified local backup of the original run"
    log = ROOT / "runs/stageG13_interface100k/20260903-001905-144804_u100k_v3/ctl_held/log.lammps"
    entry = compress(log, DESTINATION / "interface/preparation.log.lammps.gz")
    manifest["files"] = [
        item for item in manifest["files"] if item["output"]["path"] != entry["output"]["path"]
    ]
    manifest["files"].append(entry)
    manifest["limitations"] = [
        item for item in manifest["limitations"] if not item.startswith("The original G6")
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def verify() -> None:
    """Verify all published checksums; original runs are not required."""
    manifest = json.loads((DESTINATION / "manifest.json").read_text(encoding="utf-8"))
    outputs = [entry["output"] for entry in manifest["files"]]
    outputs.extend(item for entry in manifest["trajectories"].values() for item in entry["outputs"])
    outputs.extend(manifest["held_stress_data"])
    for entry in outputs:
        path = ROOT / entry["path"]
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise ValueError(f"Checksum mismatch: {path}")
        if path.stat().st_size >= 100 * 1024 * 1024:
            raise ValueError(f"File exceeds GitHub's single-file limit: {path}")
    print(f"Verified {len(outputs)} published files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify", action="store_true", help="check packaged data without reading runs/"
    )
    parser.add_argument(
        "--augment-alloy",
        type=Path,
        help="add a recovered full-column alloy trajectory to an existing package",
    )
    arguments = parser.parse_args()
    if arguments.augment_alloy:
        augment(arguments.augment_alloy)
    elif not arguments.verify:
        build()
    verify()
