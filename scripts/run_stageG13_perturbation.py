#!/usr/bin/env python3
"""Stage G13, perturbation pairs from one relaxed control.

  1. make_perturbed_cell.py: control dump -> <tag>_ctl.data, <tag>_fld.data
  2. four CG runs of in.fieldgate_pert on the GPU, in sequence:
       ctl_held  fld_held   (inclusion tethered: the ridge holds its strain)
       ctl_free  fld_free   (no springs: the inclusion may relax it)
     Both members of a pair start from the same control state and pass
     through the same rounding and the same minimiser, so their difference
     is the response to the ridge strain alone.

Usage: run_stageG13_perturbation.py --control-dump <ctl gate dump> --cell u100k
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
GPU = Path("B:/builds/lammps-kokkos-cuda-cuda124-msvc1439/build/lmp_kokkos_cuda.exe")
KOKKOS = ["-k", "on", "g", "1", "-sf", "kk", "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "off"]
POT = str(REPO / "potentials" / "meam" / "Jelinek_2012").replace("\\", "/")
STRUCT = REPO / "structures" / "stageG4_tilted_solute"
INPUTS = REPO / "lammps" / "stageG4_tilted_solute"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-dump", type=Path, required=True)
    ap.add_argument("--cell", default="u100k")
    ap.add_argument("--only", default="", help="comma list of ctl_held,fld_held,ctl_free,fld_free")
    ap.add_argument("--cg-max", type=int, default=6000)
    ap.add_argument("--cg-ftol", type=float, default=0.02)
    a = ap.parse_args()
    start = next((STRUCT / f"G4_tilted_eps0000_{a.cell}").glob("*.start.data"))
    meta = json.loads(next((STRUCT / f"G4_tilted_eps0000_{a.cell}").glob("*metadata.json")).read_text(encoding="utf-8"))
    n_al = meta["counts"]["al_matrix"]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "_" + a.cell + "_pert"
    root = REPO / "runs" / "stageG13_interface100k" / stamp
    root.mkdir(parents=True)
    cells = root / "cells"
    subprocess.run([sys.executable, str(REPO / "scripts/make_perturbed_cell.py"), "--control-dump", str(a.control_dump),
                    "--start-data", str(start), "--out-dir", str(cells), "--tag", "pert", "--n-al", str(n_al)], check=True)
    cases = [("ctl_held", "pert_ctl.data", 1), ("fld_held", "pert_fld.data", 1),
             ("ctl_free", "pert_ctl.data", 0), ("fld_free", "pert_fld.data", 0)]
    if a.only:
        cases = [c for c in cases if c[0] in a.only.split(",")]
    status = {"started": datetime.now().astimezone().isoformat(timespec="seconds"), "root": str(root),
              "control_dump": str(a.control_dump), "cases": {}}
    for name, data, hold in cases:
        d = root / name
        d.mkdir()
        cmd = [str(GPU), *KOKKOS, "-in", str(INPUTS / "in.fieldgate_pert"), "-log", str(d / "log.lammps"),
               "-var", "DATA_FILE", str(cells / data), "-var", "POT_DIR", POT, "-var", "OUT_PREFIX", str(d / name),
               "-var", "N_AL", str(n_al), "-var", "HOLD_INCL", str(hold), "-var", "CG_MAX", str(a.cg_max),
               "-var", "CG_FTOL", str(a.cg_ftol)]
        (d / "cmd.json").write_text(json.dumps(cmd, indent=1), encoding="utf-8")
        t0 = time.time()
        print("[%s] %s  <- %s (HOLD_INCL=%d)" % (datetime.now().strftime("%H:%M:%S"), name, data, hold), flush=True)
        p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=12 * 3600)
        (d / "stdout.txt").write_text(p.stdout, encoding="utf-8")
        (d / "stderr.txt").write_text(p.stderr, encoding="utf-8")
        log = (d / "log.lammps").read_text(encoding="utf-8", errors="replace") if (d / "log.lammps").exists() else ""
        ok = p.returncode == 0 and "Total wall time" in log
        print("   -> %s in %.0f s" % ("ok" if ok else "FAILED rc=%d" % p.returncode, time.time() - t0), flush=True)
        status["cases"][name] = {"ok": ok, "wall_s": round(time.time() - t0)}
        (root / "status.json").write_text(json.dumps(status, indent=1), encoding="utf-8")
        if not ok:
            print(p.stderr[-1500:], flush=True)
            return 1
    print("ALL DONE", root, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
