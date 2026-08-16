#!/usr/bin/env python3
"""Stage G1 ridge+dipole smoke-then-production runner (GPU KOKKOS with CPU fallback).

Policy:
- Backend auto: try GPU (KOKKOS CUDA MEAM/KK + the validated neighbor workaround
  `neigh_modify delay 0 every 10 check no`, milestone 2026-06-11) on the eps0000
  smoke. If the GPU smoke fails its gates, EVERYTHING runs on CPU instead -
  control and physical must share one backend for a clean Delta-Q.
- Order: smoke eps0000 -> smoke eps00194 -> production eps0000 -> production eps00194.
- Production starts only if both smokes pass. A mid-production failure is recorded
  as blocked (restart files exist); it is NOT silently rerun on another backend.
- Status after every stage -> docs/reports/stageG1_ridge_dipole_run_status.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
GPU_BIN = Path(r"B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe")
CPU_BIN = Path(r"C:\Users\dille\AppData\Local\LAMMPS 64-bit 22Jul2025-MSMPI\bin\lmp.exe")
MPIEXEC = Path(r"C:\Program Files\Microsoft MPI\Bin\mpiexec.exe")
POT_DIR = REPO_ROOT / "potentials" / "meam" / "Jelinek_2012"
IN_DIR = REPO_ROOT / "lammps" / "stageG1_ridge_dipole"
STRUCT_ROOT = REPO_ROOT / "structures" / "stageG1_ridge_dipole"
STATUS_PATH = REPO_ROOT / "docs" / "reports" / "stageG1_ridge_dipole_run_status.json"
CASES = ["G1_ridge_dipole_eps0000", "G1_ridge_dipole_eps00194"]
GPU_CRASH_MARKERS = ("cudaErrorIllegalAddress", "cudaStreamSynchronize", "Kokkos_Cuda")


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def parse_log(log_path: Path, expect_final_step: int) -> dict[str, Any]:
    gates: dict[str, Any] = {"log_exists": log_path.exists()}
    if not log_path.exists():
        gates["pass"] = False
        return gates
    text = log_path.read_text(encoding="utf-8", errors="replace")
    gates["has_error"] = "ERROR" in text
    gates["error_lines"] = [ln.strip() for ln in text.splitlines() if "ERROR" in ln][:5]
    gates["lost_atoms"] = "Lost atoms" in text
    gates["gpu_crash"] = any(m in text for m in GPU_CRASH_MARKERS)
    gates["completed"] = "Total wall time" in text
    thermo_rows = []
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) >= 10 and re.fullmatch(r"\d+", parts[0]):
            try:
                thermo_rows.append([float(v) for v in parts[:10]])
            except ValueError:
                pass
    if thermo_rows:
        last = thermo_rows[-1]
        gates["last_step"] = int(last[0])
        gates["last_atoms"] = int(last[1])
        gates["last_temp_K"] = last[2]
        gates["last_pe_eV"] = last[3]
        gates["reached_final_step"] = int(last[0]) >= expect_final_step
        temps = [r[2] for r in thermo_rows if r[0] > 0]
        gates["temp_ok"] = (abs(last[2] - 300.0) < 30.0) if temps else False
        atoms0 = thermo_rows[0][1]
        gates["atoms_constant"] = all(r[1] == atoms0 for r in thermo_rows)
        gates["nan_seen"] = "nan" in text.lower() and "-nan" in text.lower()
    perf = re.findall(r"Performance:\s+([\d.]+)\s+ns/day", text)
    if perf:
        gates["performance_ns_per_day"] = float(perf[-1])
    gates["pass"] = bool(
        gates.get("completed") and not gates.get("has_error") and not gates.get("lost_atoms")
        and not gates.get("gpu_crash") and gates.get("reached_final_step")
        and gates.get("temp_ok") and gates.get("atoms_constant")
    )
    return gates


class Runner:
    def __init__(self, run_root: Path, backend: str, production_steps: int,
                 production_input: str = "in.production", smoke_source: Path | None = None,
                 tau_max_mpa: int | None = None, production_data: Path | None = None,
                 cases: list[str] | None = None, reseed: int = 0) -> None:
        self.run_root = run_root
        self.backend = backend
        self.production_steps = production_steps
        self.production_input = production_input
        self.smoke_source = smoke_source
        self.tau_max_mpa = tau_max_mpa
        self.production_data = production_data
        self.cases = cases or CASES
        self.reseed = reseed
        self.status: dict[str, Any] = {
            "run_root": str(run_root), "backend_policy": backend, "created_at": now(),
            "git_head": git_head(), "seed": 88004, "timestep_ps": 0.001,
            "production_steps": production_steps,
            "production_input": production_input,
            "smoke_source": str(smoke_source) if smoke_source else None,
            "tau_max_mpa": tau_max_mpa,
            "production_data": str(production_data) if production_data else None,
            "cases": cases or CASES,
            "reseed": reseed,
            "gpu_binary": str(GPU_BIN), "cpu_binary": str(CPU_BIN),
            "neighbor_policy": "neigh_modify delay 0 every 10 check no (KOKKOS workaround 2026-06-11)",
            "stages": {},
        }

    def save(self) -> None:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.status["updated_at"] = now()
        STATUS_PATH.write_text(json.dumps(self.status, indent=2) + "\n", encoding="utf-8")

    def cmd_for(self, backend: str, in_file: Path, data_file: Path, prefix: str,
                extra_vars: list[str]) -> tuple[list[str], dict[str, str]]:
        var = ["-var", "DATA_FILE", str(data_file), "-var", "POT_DIR", str(POT_DIR).replace("\\", "/"),
               "-var", "OUT_PREFIX", prefix, *extra_vars]
        env = dict(os.environ)
        if backend == "gpu":
            cmd = [str(GPU_BIN), "-k", "on", "g", "1", "-sf", "kk",
                   "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "off",
                   "-in", str(in_file), "-log", "log.lammps", *var]
        else:
            env["OMP_NUM_THREADS"] = "2"
            env["OMP_PROC_BIND"] = "false"
            cmd = [str(MPIEXEC), "-np", "6", str(CPU_BIN), "-in", str(in_file),
                   "-log", "log.lammps", *var]
        return cmd, env

    def run_stage(self, case: str, stage: str, backend: str) -> dict[str, Any]:
        stage_dir = self.run_root / case / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        if stage == "smoke":
            in_file = IN_DIR / "in.smoke"
            data_file = STRUCT_ROOT / case / f"data.{case}"
            expect = 3000
            extra: list[str] = []
        else:
            in_file = IN_DIR / self.production_input
            if self.production_data is not None:
                data_file = self.production_data / case / f"{case}.start.data"
            else:
                smoke_root = self.smoke_source or self.run_root
                data_file = smoke_root / case / "smoke" / f"{case}.smoke.final.data"
            expect = self.production_steps
            extra = ["-var", "NSTEPS", str(self.production_steps)]
            if self.tau_max_mpa is not None:
                extra += ["-var", "TAUMAX_MPA", str(self.tau_max_mpa)]
            if self.reseed:
                extra += ["-var", "RESEED", str(self.reseed)]
        cmd, env = self.cmd_for(backend, in_file, data_file, case, extra)
        rec: dict[str, Any] = {"backend": backend, "cmd": cmd, "cwd": str(stage_dir),
                               "started_at": now(), "state": "running"}
        self.status["stages"][f"{case}/{stage}"] = rec
        self.save()
        print(f"[{now()}] START {case}/{stage} on {backend}", flush=True)
        try:
            proc = subprocess.run(cmd, cwd=stage_dir, env=env, capture_output=True,
                                  text=True, timeout=60 * 3600)
            rec["returncode"] = proc.returncode
            rec["stderr_tail"] = proc.stderr[-2000:]
        except subprocess.TimeoutExpired:
            rec["returncode"] = None
            rec["stderr_tail"] = "TIMEOUT 60h"
        rec["finished_at"] = now()
        rec["gates"] = parse_log(stage_dir / "log.lammps", expect)
        rec["state"] = "passed" if rec["gates"].get("pass") else "failed"
        self.save()
        print(f"[{now()}] DONE  {case}/{stage}: {rec['state']} "
              f"(perf={rec['gates'].get('performance_ns_per_day')} ns/day, "
              f"T={rec['gates'].get('last_temp_K')})", flush=True)
        return rec

    def run(self) -> int:
        backend = "gpu" if self.backend in ("auto", "gpu") else "cpu"
        if self.smoke_source is not None or self.production_data is not None:
            # Production-only mode: starts come from prior smokes or prepared data.
            for case in self.cases:
                if self.production_data is not None:
                    src = self.production_data / case / f"{case}.start.data"
                else:
                    src = self.smoke_source / case / "smoke" / f"{case}.smoke.final.data"
                if not src.exists():
                    print(f"missing production start data: {src}", flush=True)
                    self.status["verdict"] = "start_data_missing"
                    self.save()
                    return 2
            self.status["smoke_verdict"] = "production_only_mode"
            ok = True
            for case in self.cases:
                prec = self.run_stage(case, "production", backend)
                if not prec["gates"].get("pass"):
                    ok = False
                    self.status["verdict"] = f"production_failed_{case}"
                    self.save()
                    break
            if ok:
                self.status["verdict"] = f"production_completed_{backend}"
                self.save()
            return 0 if ok else 3
        # Smoke gate, case 1; auto-fallback to CPU on GPU failure.
        rec = self.run_stage(self.cases[0], "smoke", backend)
        if not rec["gates"].get("pass"):
            if backend == "gpu" and self.backend == "auto":
                print("GPU smoke failed - falling back to CPU for ALL stages", flush=True)
                self.status["gpu_fallback_reason"] = {
                    "gpu_crash": rec["gates"].get("gpu_crash"),
                    "error_lines": rec["gates"].get("error_lines"),
                }
                backend = "cpu"
                rec = self.run_stage(self.cases[0], "smoke", backend)
            if not rec["gates"].get("pass"):
                self.status["verdict"] = "smoke_failed_both_backends" if self.backend == "auto" else "smoke_failed"
                self.save()
                return 2
        rec2 = self.run_stage(self.cases[1], "smoke", backend)
        if not rec2["gates"].get("pass"):
            self.status["verdict"] = "smoke_case2_failed"
            self.save()
            return 2
        self.status["smoke_verdict"] = f"both_passed_{backend}"
        self.save()
        ok = True
        for case in self.cases:
            prec = self.run_stage(case, "production", backend)
            if not prec["gates"].get("pass"):
                ok = False
                self.status["verdict"] = f"production_failed_{case}"
                self.save()
                break
        if ok:
            self.status["verdict"] = f"production_completed_{backend}"
            self.save()
        return 0 if ok else 3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["auto", "gpu", "cpu"], default="auto")
    parser.add_argument("--production-steps", type=int, default=60000)
    parser.add_argument("--run-root", type=Path, default=None)
    parser.add_argument("--production-input", default="in.production",
                        help="input template in lammps/stageG1_ridge_dipole/")
    parser.add_argument("--smoke-source", type=Path, default=None,
                        help="previous run root whose passed smoke finals should seed production")
    parser.add_argument("--tau-max", type=int, default=None,
                        help="TAUMAX_MPA for in.production_shear")
    parser.add_argument("--production-data", type=Path, default=None,
                        help="dir with <case>/<case>.start.data prepared starts (production-only mode)")
    parser.add_argument("--cases", default=None,
                        help="comma-separated case names (default: G1 pair)")
    parser.add_argument("--reseed", type=int, default=0,
                        help="RESEED velocity seed for replica runs (0 = keep velocities)")
    args = parser.parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_root = args.run_root or (REPO_ROOT / "runs" / "stageG1_ridge_dipole" / stamp)
    runner = Runner(run_root, args.backend, args.production_steps,
                    production_input=args.production_input, smoke_source=args.smoke_source,
                    tau_max_mpa=args.tau_max,
                    production_data=args.production_data.resolve() if args.production_data else None,
                    cases=args.cases.split(",") if args.cases else None, reseed=args.reseed)
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
