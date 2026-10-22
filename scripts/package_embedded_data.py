#!/usr/bin/env python3
"""Package the embedded-inclusion calculations for the repository, without LAMMPS.

Copies, gzip-compressed and with SHA-256 checksums, the files the manuscript
relies on:

  embedded/field/       reference, +eps and -eps static dumps (positions and
                        per-atom virials), their final data files, the forces on
                        the held inclusion, the CG logs, and the relaxed reference
  embedded/peierls/     the sweep of the straight edge dislocation without an
                        inclusion: relaxation and sweep logs, the relaxed slab and
                        the full dumps written every NFULL steps
  embedded/margin/      the cells with 4 and 10 times the strain: final dumps,
                        data files and logs
  embedded/dislocation/ the slab with the dislocation above the inclusion:
                        relaxation logs and relaxed states with the inclusion
                        unstrained (ctl), strained (fld) and unstrained again
                        (rev), and the logs of the two loading ramps

Inputs are the run directories given on the command line. The manifest is
written to data/publication/embedded/manifest.json. --verify recomputes the
checksums of the published files.

    python scripts/package_embedded_data.py --field runs/.../static \
        --control runs/.../control_held --peierls runs/.../peierls
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data/publication/embedded"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def put(src: Path, dst: Path) -> dict:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as fi, gzip.GzipFile(dst, "wb", mtime=0) as fo:
        shutil.copyfileobj(fi, fo)
    return {"source": src.name, "source_bytes": src.stat().st_size, "source_sha256": sha256(src),
            "file": dst.relative_to(ROOT).as_posix(), "bytes": dst.stat().st_size, "sha256": sha256(dst)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--field", type=Path, help="static/ directory of the field pair")
    ap.add_argument("--control", type=Path, help="run directory of the reference relaxation")
    ap.add_argument("--peierls", type=Path, help="run directory of the sweep without an inclusion")
    ap.add_argument("--margin", type=Path, help="margin/ directory of the 4x and 10x cells")
    ap.add_argument("--dislocation", type=Path, help="run directory of the dislocation slab")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    man_path = DEST / "manifest.json"
    if a.verify:
        man = json.loads(man_path.read_text(encoding="utf-8"))
        bad = [e["file"] for e in man["files"] if sha256(ROOT / e["file"]) != e["sha256"]]
        print("verified" if not bad else "checksum mismatch: %s" % bad)
        return 1 if bad else 0
    files = []
    if a.control:
        for name in sorted(a.control.glob("*.control.data")) + [a.control / "log.lammps"]:
            files.append(put(name, DEST / "field" / ("reference_relax." + name.name + ".gz")))
    if a.field:
        for case in ("ref", "plus", "minus"):
            for suffix in ("static.lammpstrj", "static.data", "forces.lammpstrj"):
                src = a.field / f"{case}.{suffix}"
                if src.exists():
                    files.append(put(src, DEST / "field" / f"{case}.{suffix}.gz"))
            log = a.field / f"log.{case}"
            if log.exists():
                files.append(put(log, DEST / "field" / f"log.{case}.gz"))
    if a.peierls:
        for pattern in ("log.relax", "log.sweep", "slab.relaxed.data", "sweep.full.*.lammpstrj"):
            for src in sorted(a.peierls.glob(pattern)):
                files.append(put(src, DEST / "peierls" / (src.name + ".gz")))
    if a.margin:
        for case in ("x4", "x10"):
            for suffix in ("static.lammpstrj", "static.data"):
                src = a.margin / f"{case}.{suffix}"
                if src.exists():
                    files.append(put(src, DEST / "margin" / f"{case}.{suffix}.gz"))
            log = a.margin / f"log.{case}"
            if log.exists():
                files.append(put(log, DEST / "margin" / f"log.{case}.gz"))
    if a.dislocation:
        for pattern in ("log.ctl_relax", "log.fld_relax", "log.rev_relax", "log.ctl.sweep", "log.fld.sweep",
                        "ctl.relaxed.data", "fld.relaxed.data", "rev.relaxed.data",
                        "ctl.relaxed.lammpstrj", "fld.relaxed.lammpstrj", "rev.relaxed.lammpstrj"):
            for src in sorted(a.dislocation.glob(pattern)):
                files.append(put(src, DEST / "dislocation" / (src.name + ".gz")))
    man = {"created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "description": "Al13Fe4 sphere (R = 25 A) held at a given magnetostrictive strain in a "
                          "periodic Al cell: static field pair, cells at 4 and 10 times the strain, "
                          "an edge dislocation above the inclusion, and the sweep of a straight "
                          "edge dislocation without an inclusion",
           "files": files}
    DEST.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    total = sum(e["bytes"] for e in files)
    print("%d files, %.1f MB" % (len(files), total / 1e6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
