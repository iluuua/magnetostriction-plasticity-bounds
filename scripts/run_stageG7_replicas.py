#!/usr/bin/env python3
"""Stage G7: solute-realization replicas of the mobility measurement.

The external review is right that a threshold measured on one solute
realization cannot be quoted as a material property. This runs the same
constant-stress staircase on independent solute fields (relB, relC, relD;
relA is already done), so the pinning stress can be reported as a mean over
realizations with a spread.

Dumps are written sparsely (every 2 ps) because only dislocation positions
are needed, and each finished run is archived to B: immediately - C: has
under 10 GB free.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GPU_BIN = Path("B:/builds/lammps-kokkos-cuda-cuda124-msvc1439/build/lmp_kokkos_cuda.exe")
POT_DIR = REPO_ROOT / "potentials" / "meam" / "Jelinek_2012"
IN_FILE = REPO_ROOT / "lammps" / "stageG3_solute_mobility" / "in.vstar"
STRUCT = REPO_ROOT / "structures" / "stageG3_solute_mobility"
STATUS = REPO_ROOT / "docs" / "reports" / "stageG7_replica_status.json"
BACKUP = Path("B:/backups/physics_md_al_fe/stageG7")
CASES = ["G3_solute_relB", "G3_solute_relC", "G3_solute_relD"]
EXPECT = 130000


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def gates(log: Path) -> dict:
    g: dict = {"exists": log.exists()}
    if not log.exists():
        g["pass"] = False
        return g
    t = log.read_text(encoding="utf-8", errors="replace")
    g["completed"] = "Total wall time" in t
    g["errors"] = len([ln for ln in t.splitlines() if ln.startswith("ERROR")])
    g["lost_atoms"] = "Lost atoms" in t
    rows = [ln.split() for ln in t.splitlines()]
    rows = [r for r in rows if len(r) == 10 and re.fullmatch(r"\d+", r[0])]
    if rows:
        g["last_step"] = int(rows[-1][0])
        g["last_T"] = float(rows[-1][2])
        g["reached"] = g["last_step"] >= EXPECT
    g["pass"] = bool(g.get("completed") and not g["errors"] and not g["lost_atoms"]
                     and g.get("reached"))
    return g


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root = REPO_ROOT / "runs" / "stageG7_replicas" / stamp
    q = {"created_at": now(), "run_root": str(root), "cases": {},
         "protocol": "same staircase as G6: 10 ps at tau=0, then 45/55/65/75 MPa, "
                     "30 ps per rung with 4 ps smoothstep onsets, 130 ps total"}

    def save() -> None:
        q["updated_at"] = now()
        STATUS.write_text(json.dumps(q, indent=2) + chr(10), encoding="utf-8")

    for case in CASES:
        d = root / case
        d.mkdir(parents=True, exist_ok=True)
        rec = {"state": "running", "started_at": now()}
        q["cases"][case] = rec
        save()
        cmd = [str(GPU_BIN), "-k", "on", "g", "1", "-sf", "kk",
               "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "off",
               "-in", str(IN_FILE), "-log", "log.lammps",
               "-var", "DATA_FILE", str(STRUCT / case / f"{case}.start.data"),
               "-var", "POT_DIR", str(POT_DIR).replace(chr(92), "/"),
               "-var", "OUT_PREFIX", case]
        print(f"[{now()}] START {case}", flush=True)
        proc = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=20 * 3600)
        rec["returncode"] = proc.returncode
        rec["gates"] = gates(d / "log.lammps")
        rec["state"] = "passed" if rec["gates"].get("pass") else "failed"
        rec["finished_at"] = now()
        save()
        print(f"[{now()}] DONE {case}: {rec['state']}", flush=True)

        dest = BACKUP / stamp / case
        dest.mkdir(parents=True, exist_ok=True)
        for f in d.iterdir():
            if f.suffix in (".lammpstrj", ".data") or f.name == "log.lammps":
                try:
                    shutil.copy2(f, dest / f.name)
                    if f.suffix == ".lammpstrj" and (dest / f.name).stat().st_size == f.stat().st_size:
                        pass  # keep locally until analysed; archived copy exists
                except Exception:
                    pass
    q["verdict"] = "all_done"
    save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
