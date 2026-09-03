#!/usr/bin/env python3
"""Stage G13: the interface stress field at ~100k atoms, free and held.

Four minimisations of the same commensurate cell (38 x 13 periods, 94 Al
layers, 100,290 atoms), run one after another on the GPU:

  ctl_free  eps = 0        in.fieldgate       the protocol of stageG4/G10
  fld_free  eps = 0.00194  in.fieldgate       (affine perturbation, free relax)
  ctl_held  eps = 0        in.fieldgate_held  inclusion tethered to its given
  fld_held  eps = 0.00194  in.fieldgate_held  positions: a maintained eigenstrain

The two differences, fld - ctl within each pair, are the quantities the
manuscript needs: the relaxed response at the unified cell size, and the field
of a maintained transformation strain of the nominal amplitude.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GPU = Path("B:/builds/lammps-kokkos-cuda-cuda124-msvc1439/build/lmp_kokkos_cuda.exe")
POT = REPO / "potentials" / "meam" / "Jelinek_2012"
STRUCT = REPO / "structures" / "stageG4_tilted_solute"
INPUTS = REPO / "lammps" / "stageG4_tilted_solute"


def n_al_of(cell: str) -> int:
    """Matrix atoms come first in the data file; read the count from the
    generator's metadata rather than hard-coding it."""
    meta = next((STRUCT / cell).glob("*metadata.json"))
    return json.loads(meta.read_text(encoding="utf-8"))["counts"]["al_matrix"]


import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--cell", default="clean100k", help="structure tag: clean100k (38x13x94) or u100k (54x13x56)")
_ap.add_argument("--protocol", choices=("v1", "v2", "v3"), default="v3",
                 help="v1: CG only (the original gate); v2: CG + 10 ps 300 K + CG quench (stalls in the "
                      "tethered cell); v3: CG + 6 ps 300 K + 12 ps Langevin cooling + CG, two-norm criteria")
_ap.add_argument("--only", default="", help="comma list of case names to run")
_args = _ap.parse_args()
_c = "G4_tilted_eps0000_" + _args.cell
_f = "G4_tilted_eps00194_" + _args.cell
if _args.protocol == "v1":
    CASES = [("ctl_free", _c, "in.fieldgate", {}), ("fld_free", _f, "in.fieldgate", {}),
             ("ctl_held", _c, "in.fieldgate_held", {"N_AL": "meta"}),
             ("fld_held", _f, "in.fieldgate_held", {"N_AL": "meta"})]
else:
    _in = "in.fieldgate_" + _args.protocol
    CASES = [("ctl_free", _c, _in, {"N_AL": "meta", "HOLD_INCL": 0}),
             ("fld_free", _f, _in, {"N_AL": "meta", "HOLD_INCL": 0}),
             ("ctl_held", _c, _in, {"N_AL": "meta", "HOLD_INCL": 1}),
             ("fld_held", _f, _in, {"N_AL": "meta", "HOLD_INCL": 1})]
if _args.only:
    CASES = [c for c in CASES if c[0] in _args.only.split(",")]


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "_" + _args.cell + "_" + _args.protocol
    root = REPO / "runs" / "stageG13_interface100k" / stamp
    root.mkdir(parents=True)
    status = {"started": datetime.now().astimezone().isoformat(timespec="seconds"),
              "root": str(root), "cases": {}}
    for name, cell, infile, extra in CASES:
        d = root / name
        d.mkdir()
        data = next((STRUCT / cell).glob("*.start.data"))
        cmd = [str(GPU), "-k", "on", "g", "1", "-sf", "kk",
               "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "off",
               "-in", str(INPUTS / infile), "-log", str(d / "log.lammps"),
               "-var", "DATA_FILE", str(data), "-var", "POT_DIR", str(POT).replace(chr(92), "/"),
               "-var", "OUT_PREFIX", str(d / name)]
        for k, v in extra.items():
            cmd += ["-var", k, str(n_al_of(cell) if v == "meta" else v)]
        t0 = time.time()
        print("[%s] %s  <-  %s / %s" % (datetime.now().strftime("%H:%M:%S"), name, cell, infile), flush=True)
        proc = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=16 * 3600)
        (d / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
        (d / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
        dump = d / (name + ".gate.lammpstrj")
        ok = proc.returncode == 0 and dump.exists()
        status["cases"][name] = {"ok": ok, "returncode": proc.returncode,
                                 "wall_s": round(time.time() - t0),
                                 "dump": str(dump) if dump.exists() else None}
        print("   -> %s in %d s" % ("ok" if ok else "FAILED rc=%d" % proc.returncode,
                                     time.time() - t0), flush=True)
        (root / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        if not ok:
            print(proc.stderr[-1500:], flush=True)
            return 1
    status["finished"] = datetime.now().astimezone().isoformat(timespec="seconds")
    (root / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print("ALL DONE", root, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
