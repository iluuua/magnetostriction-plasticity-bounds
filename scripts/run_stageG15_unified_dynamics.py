#!/usr/bin/env python3
"""Stages G15 and G16 on the unified ~10^5-atom cell (54 x 13 periods, 56 Al
layers, threshold-cell dislocation pair).

  G15  shear ramp 0 -> 400 MPa over 96 ps, control and strained cells, the
       stageG1 protocol at the unified size: the onset of pair motion and of
       nucleation at the interface.
  G16  the strained inclusion HELD at its strain, no applied shear, 100 ps at
       300 K, control and strained: does the maintained field move the pair?

Every geometry-dependent input variable is computed here from the cell's
metadata so the LAMMPS inputs stay box-agnostic. Runs go one after another on
the single GPU; each is 10^5 atoms for 10^5 steps, about 10 h.

Usage: run_stageG15_unified_dynamics.py [--only G15|G16] [--cases ctl,fld]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GPU = Path("B:/builds/lammps-kokkos-cuda-cuda124-msvc1439/build/lmp_kokkos_cuda.exe")
POT = str(REPO / "potentials" / "meam" / "Jelinek_2012").replace("\\", "/")
STRUCT = REPO / "structures" / "stageG4_tilted_solute"
INPUTS = REPO / "lammps" / "stageG4_tilted_solute"
KOKKOS = ["-k", "on", "g", "1", "-sf", "kk",
          "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "off"]
CELLS = {"ctl": "G4_tilted_eps0000_dipu100k", "fld": "G4_tilted_eps00194_dipu100k"}
D111 = 4.05 / 3 ** 0.5


def geometry(cell: str) -> dict:
    meta = json.loads(next((STRUCT / cell).glob("*metadata.json")).read_text(encoding="utf-8"))
    d = meta["dipole"]
    al_top = meta["cell"]["interface_plane_z_A"] + meta["cell"]["al_depth_A"] if "cell" in meta \
        else 20.0 + meta["al_depth_A"]
    px, mx = d["partner_plus"]["x"], d["partner_minus"]["x"]
    pz, mz = d["partner_plus"]["z"], d["partner_minus"]["z"]
    return {
        "N_AL": meta["counts"]["al_matrix"],
        "TOPZ": round(al_top - 6.0, 2),                 # top ~2.5 layers pull
        "XL0": round(px - 25.0, 2), "XL1": round(px + 25.0, 2),
        "ZL0": round(pz - 11.0, 2), "ZL1": round(pz + 11.0, 2),
        "XU0": round(mx - 25.0, 2), "XU1": round(mx + 25.0, 2),
        "ZU0": round(mz - 11.0, 2), "ZU1": round(mz + 11.0, 2),
    }


def launch(stage: str, case: str, root: Path, extra: dict, infile: str, nsteps: int) -> dict:
    cell = CELLS[case]
    d = root / f"{stage}_{case}"
    d.mkdir(parents=True, exist_ok=True)
    data = next((STRUCT / cell).glob("*.start.data"))
    cmd = [str(GPU), *KOKKOS, "-in", str(INPUTS / infile), "-log", str(d / "log.lammps"),
           "-var", "DATA_FILE", str(data), "-var", "POT_DIR", POT,
           "-var", "OUT_PREFIX", str(d / f"{stage}_{case}"), "-var", "NSTEPS", str(nsteps)]
    for k, v in extra.items():
        cmd += ["-var", k, str(v)]
    (d / "cmd.json").write_text(json.dumps(cmd, indent=1), encoding="utf-8")
    t0 = time.time()
    print("[%s] %s %s  <- %s" % (datetime.now().strftime("%H:%M:%S"), stage, case, cell), flush=True)
    proc = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=30 * 3600)
    (d / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (d / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    log = (d / "log.lammps").read_text(encoding="utf-8", errors="replace") if (d / "log.lammps").exists() else ""
    ok = proc.returncode == 0 and "Total wall time" in log
    print("   -> %s, %.1f h" % ("ok" if ok else "FAILED rc=%d" % proc.returncode, (time.time() - t0) / 3600), flush=True)
    if not ok:
        print(proc.stderr[-1500:], flush=True)
    return {"ok": ok, "returncode": proc.returncode, "wall_h": round((time.time() - t0) / 3600, 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=("G15", "G16"))
    ap.add_argument("--cases", default="ctl,fld")
    ap.add_argument("--nsteps", type=int, default=101000)
    args = ap.parse_args()
    cases = args.cases.split(",")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root = REPO / "runs" / "stageG15_unified" / stamp
    root.mkdir(parents=True)
    status = {"started": datetime.now().astimezone().isoformat(timespec="seconds"), "runs": {}}
    plan = []
    if args.only in (None, "G15"):
        for c in cases:
            g = geometry(CELLS[c])
            plan.append(("G15", c, {**g, "TAUMAX_MPA": 400, "HOLD_INCL": 0}, "in.ramp", args.nsteps))
    if args.only in (None, "G16"):
        for c in cases:
            g = geometry(CELLS[c])
            plan.append(("G16", c, {"N_AL": g["N_AL"]}, "in.fieldhold_dynamics", 100000))
    for stage, c, extra, infile, n in plan:
        status["runs"][f"{stage}_{c}"] = launch(stage, c, root, extra, infile, n)
        (root / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        if not status["runs"][f"{stage}_{c}"]["ok"]:
            return 1
    status["finished"] = datetime.now().astimezone().isoformat(timespec="seconds")
    (root / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print("ALL DONE", root, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
