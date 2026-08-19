#!/usr/bin/env python3
"""Stage G2b/G2c queue: eps-ladder run + seed replicas, sequential on one GPU.

Jobs (each via run_stageG1_ridge_dipole.py, shear-ramp protocol, common-origin starts):
  1. g2c-eps005            : G2_shear_eps005, inherited velocities (paired with the
                             completed seed-0 control run) - dose-response rung
  2. g2b-r90001            : control + physical, RESEED 90001
  3. g2b-r90002            : control + physical, RESEED 90002

After each job: the per-run status JSON is snapshotted to docs/reports/, and the
big .lammpstrj dumps are MOVED to B:\\backups (C: has <10 GB free); logs, restarts
and final data stay local. Queue status: docs/reports/stageG2b_queue_status.json
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
RUNNER = REPO_ROOT / "scripts" / "run_stageG1_ridge_dipole.py"
STATUS_SRC = REPO_ROOT / "docs" / "reports" / "stageG1_ridge_dipole_run_status.json"
QUEUE_STATUS = REPO_ROOT / "docs" / "reports" / "stageG2b_queue_status.json"
BACKUP_ROOT = Path("B:/backups/physics_md_al_fe/stageG2b")

JOBS = [
    {"name": "g2c-eps005", "cases": "G2_shear_eps005", "reseed": 0},
    {"name": "g2b-r90001", "cases": "G2_shear_eps0000,G2_shear_eps00194", "reseed": 90001},
    {"name": "g2b-r90002", "cases": "G2_shear_eps0000,G2_shear_eps00194", "reseed": 90002},
]
COMMON = ["--backend", "gpu", "--production-steps", "101000",
          "--production-input", "in.production_shear", "--tau-max", "400",
          "--production-data", str(REPO_ROOT / "structures" / "stageG2_common_origin")]


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> int:
    queue = {"created_at": now(), "jobs": {}}

    def save() -> None:
        queue["updated_at"] = now()
        QUEUE_STATUS.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")

    for job in JOBS:
        rec = {"state": "running", "started_at": now()}
        queue["jobs"][job["name"]] = rec
        save()
        cmd = [PY, str(RUNNER), *COMMON, "--cases", job["cases"]]
        if job["reseed"]:
            cmd += ["--reseed", str(job["reseed"])]
        print(f"[{now()}] QUEUE start {job['name']}: {' '.join(cmd[2:])}", flush=True)
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        rec["returncode"] = proc.returncode
        rec["stdout_tail"] = proc.stdout[-1500:]
        # snapshot per-run status and archive dumps
        if STATUS_SRC.exists():
            run_status = json.loads(STATUS_SRC.read_text(encoding="utf-8"))
            snap = REPO_ROOT / "docs" / "reports" / f"stageG2b_status_{job['name']}.json"
            snap.write_text(json.dumps(run_status, indent=2) + "\n", encoding="utf-8")
            rec["run_root"] = run_status.get("run_root")
            rec["verdict"] = run_status.get("verdict")
            run_root = Path(run_status.get("run_root", ""))
            if run_root.exists():
                for case_dir in run_root.iterdir():
                    prod = case_dir / "production"
                    if not prod.is_dir():
                        continue
                    # keep the run layout (<case>/production/...) so stageG2_depinning.py
                    # can analyze straight from the backup root
                    dest = BACKUP_ROOT / job["name"] / case_dir.name / "production"
                    dest.mkdir(parents=True, exist_ok=True)
                    for f in prod.iterdir():
                        if f.suffix == ".lammpstrj" or f.name.endswith(".restart.a") \
                                or f.name.endswith(".restart.b"):
                            shutil.copy2(f, dest / f.name)
                            if f.suffix == ".lammpstrj" and (dest / f.name).stat().st_size == f.stat().st_size:
                                f.unlink()
                    for name in ("log.lammps",):
                        src = prod / name
                        if src.exists():
                            shutil.copy2(src, dest / name)
        rec["state"] = "done" if proc.returncode == 0 else "failed"
        rec["finished_at"] = now()
        save()
        print(f"[{now()}] QUEUE done {job['name']}: rc={proc.returncode} verdict={rec.get('verdict')}", flush=True)
        if proc.returncode != 0:
            print("stopping queue on failure", flush=True)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
