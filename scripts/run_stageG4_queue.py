#!/usr/bin/env python3
"""Stage G4 queue: control vs physical, the full Pshonkin system.

Al matrix + Fe4Al13 ridge inclusion + Mg/Si solutes + a 45-deg tilted
magnetostrictive eigenstrain, driven by a staircase of constant shear stresses.
Sequential on one GPU: ~0.28 ns/day at 81273 atoms => ~7.8 h per 90 ps run, ~16 h for the pair.

Status -> docs/reports/stageG4_queue_status.json after every stage; dumps are
copied to B: as each run finishes.
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
IN_FILE = REPO_ROOT / "lammps" / "stageG4_tilted_solute" / "in.mobility"
STRUCT = REPO_ROOT / "structures" / "stageG4_tilted_solute"
STATUS = REPO_ROOT / "docs" / "reports" / "stageG4_queue_status.json"
BACKUP = Path("B:/backups/physics_md_al_fe/stageG4")
CASES = ["G4_tilted_eps0000", "G4_tilted_eps00194"]
EXPECT_STEPS = 90000
CRASH = ("cudaErrorIllegalAddress", "cudaStreamSynchronize")


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def gates(log: Path, expect: int) -> dict:
    g = {"log_exists": log.exists()}
    if not log.exists():
        g["pass"] = False
        return g
    t = log.read_text(encoding="utf-8", errors="replace")
    g["has_error"] = "ERROR" in t
    g["error_lines"] = [ln.strip() for ln in t.splitlines() if "ERROR" in ln][:3]
    g["lost_atoms"] = "Lost atoms" in t
    g["gpu_crash"] = any(m in t for m in CRASH)
    g["completed"] = "Total wall time" in t
    rows = []
    for ln in t.splitlines():
        p = ln.split()
        if len(p) == 9 and re.fullmatch(r"\d+", p[0]):
            try:
                rows.append([float(v) for v in p])
            except ValueError:
                pass
    if rows:
        last = rows[-1]
        g["last_step"] = int(last[0])
        g["last_temp_K"] = last[2]
        g["final_tau_MPa"] = last[8]
        g["atoms_constant"] = all(r[1] == rows[0][1] for r in rows)
        g["reached_final"] = int(last[0]) >= expect
        g["temp_ok"] = abs(last[2] - 290.0) < 30.0
    perf = re.findall(r"Performance:\s+([\d.]+)\s+ns/day", t)
    if perf:
        g["ns_per_day"] = float(perf[-1])
    g["pass"] = bool(g.get("completed") and not g.get("has_error") and not g.get("lost_atoms")
                     and not g.get("gpu_crash") and g.get("reached_final")
                     and g.get("atoms_constant") and g.get("temp_ok"))
    return g


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root = REPO_ROOT / "runs" / "stageG4_tilted_solute" / stamp
    q = {"created_at": now(), "run_root": str(root), "expected_steps": EXPECT_STEPS,
         "model": "Al + Fe4Al13 ridge inclusion + Mg/Si solutes, 45-deg tilted eigenstrain",
         "protocol": "staircase tau = 30/40/50/60 MPa, 20 ps each, after 10 ps at tau=0",
         "observable": "dislocation velocity per step; V* = kT dln(v)/dtau; v_physical/v_control",
         "cases": {}}

    def save():
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
        rec["cmd"] = cmd
        print(f"[{now()}] START {case}", flush=True)
        proc = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=20 * 3600)
        rec["returncode"] = proc.returncode
        rec["gates"] = gates(d / "log.lammps", EXPECT_STEPS)
        rec["state"] = "passed" if rec["gates"].get("pass") else "failed"
        rec["finished_at"] = now()
        save()
        print(f"[{now()}] DONE {case}: {rec['state']} "
              f"({rec['gates'].get('ns_per_day')} ns/day, T={rec['gates'].get('last_temp_K')})",
              flush=True)
        dest = BACKUP / stamp / case
        dest.mkdir(parents=True, exist_ok=True)
        for f in d.iterdir():
            if f.suffix in (".lammpstrj", ".data") or f.name == "log.lammps" or ".restart." in f.name:
                try:
                    shutil.copy2(f, dest / f.name)
                except Exception:
                    pass
        if not rec["gates"].get("pass"):
            print("stopping queue on failure", flush=True)
            return 1
    q["verdict"] = "both_passed"
    save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
