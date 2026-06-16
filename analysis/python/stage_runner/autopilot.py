"""Autopilot orchestration: A0 smoke -> A0 production -> A0 analysis -> A1-small
build -> A1 smoke -> gate -> A1 production -> A1 analysis -> final report.

State is persisted to <run_dir>/state.json after every step, so an interrupted
pipeline resumes with:  --autopilot-A0-A1-production --run-dir <run_dir>
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from . import (
    builder,
    decisions,
    eigenstrain,
    lammps_detect,
    lammps_runner,
    paths,
    report,
    resources,
)
from .config import dump_effective

STEP_ORDER = [
    "plan",
    "env",
    "accel",
    "a0_eigenstrain",
    "a0_smoke",
    "a0_production",
    "a0_analysis",
    "a1_build",
    "a1_smoke",
    "a1_gate",
    "a1_production",
    "a1_analysis",
    "final_report",
]

A1_SEEDS = {"0025": 53021, "0100": 53041}


class StopPipeline(RuntimeError):
    """Controlled stop: write reports instead of blindly continuing."""


class AnalysisError(RuntimeError):
    pass


def _git(args: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(paths.REPO_ROOT)] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return proc.stdout.strip()
    except Exception as exc:  # git info is best-effort
        return f"(git unavailable: {exc})"


def git_info() -> dict:
    return {
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["log", "-1", "--oneline"]),
        "status_short": _git(["status", "--short"]) or "(clean)",
    }


def validate_plan(cfg: dict) -> tuple[bool, list[str]]:
    """Static validation: every input the sweep needs must already exist."""
    lines: list[str] = []
    ok = True

    def check(cond: bool, msg: str) -> None:
        nonlocal ok
        lines.append(("OK   " if cond else "FAIL ") + msg)
        if not cond:
            ok = False

    for eps in cfg["A0"]["eps_z"]:
        tag = paths.eps_tag(eps)
        tpl = paths.a0_template_for_tag(tag)
        check(tpl.is_file(), f"A0 template for eps_z={eps}: {tpl}")
    for eps in cfg["A1_small"]["eps_z"]:
        tag = paths.eps_tag(eps)
        tpl = paths.a0_template_for_tag(tag)
        check(tpl.is_file(), f"A1 base template for eps_z={eps}: {tpl}")

    check(paths.A0_BASELINE_DATA.is_file(), f"A0 baseline structure: {paths.A0_BASELINE_DATA}")
    check(paths.AL13FE4_DATA.is_file(), f"Fe4Al13 source crystal: {paths.AL13FE4_DATA}")
    check(paths.MEAM_LIBRARY.is_file(), f"MEAM library: {paths.MEAM_LIBRARY}")
    check(paths.MEAM_PARAMS.is_file(), f"MEAM parameters: {paths.MEAM_PARAMS}")

    py = python_executable(cfg)
    check(py.is_file(), f"python executable: {py}")

    res = cfg["resources"]
    try:
        plan, all_plans = builder.select_plan(
            cfg["A1_small"]["atoms_target_candidates"],
            res["cpu_mpi_ranks"],
            res["max_memory_gb"],
        )
        lines.append(
            f"OK   A1-small geometry plan: target {plan['target_atoms']} -> "
            f"{plan['nx']}x{plan['ny']}x{plan['nz']} cells, est. {plan['estimated_atoms']} atoms, "
            f"axes {plan['inclusion_axes_A']} A, est. mem {plan['estimated_memory_gb']} GB"
        )
        for p in all_plans:
            lines.append(
                f"     candidate {p['target_atoms']}: est {p['estimated_atoms']} atoms, "
                f"mem {p['estimated_memory_gb']} GB, feasible={p['feasible_under_memory_limit']}"
            )
    except builder.BuildError as exc:
        check(False, f"A1-small geometry planning failed: {exc}")

    lines.append("")
    lines.append("Planned stages (in order):")
    lines.append(
        f"  1. A0 smoke: {len(cfg['A0']['eps_z'])} cases x {cfg['A0']['smoke_steps']} steps"
    )
    lines.append(
        f"  2. A0 production: {len(cfg['A0']['eps_z'])} cases x {cfg['A0']['production_steps']} steps"
    )
    lines.append("  3. A0 OVITO DXA/CNA analysis + CSV")
    lines.append("  4. A1-small build + minimize/equil prep + run-local eigenstrain")
    lines.append(
        f"  5. A1-small smoke: {len(cfg['A1_small']['eps_z'])} cases x {cfg['A1_small']['smoke_steps']} steps"
    )
    lines.append("  6. pre-A1-production gate report")
    lines.append(
        f"  7. A1-small production (if gate passes): {len(cfg['A1_small']['eps_z'])} cases x "
        f"{cfg['A1_small']['production_steps']} steps"
    )
    lines.append("  8. A1 analysis + final report; STOP (no A1-medium / 500k / 1M)")
    return ok, lines


def python_executable(cfg: dict) -> Path:
    p = Path(cfg["resources"]["python_executable"])
    if not p.is_absolute():
        p = paths.REPO_ROOT / p
    return p


def check_env(cfg: dict, help_save_to: Path | None = None) -> tuple[bool, dict, list[str]]:
    """Detect LAMMPS/MPI/python/resources. Returns (ok, env, printable lines)."""
    lines: list[str] = []
    ok = True
    host = resources.host_summary(paths.REPO_ROOT)
    for k, v in host.items():
        lines.append(f"host.{k}: {v}")

    res = cfg["resources"]
    disk_ok, disk_msg = resources.check_disk(
        paths.REPO_ROOT, res["min_free_disk_gb_before_start"]
    )
    lines.append(disk_msg)
    ok &= disk_ok

    workdir = Path(tempfile.mkdtemp(prefix="lmp_detect_"))
    try:
        detect_info = lammps_detect.detect(
            res.get("lammps_executable", "auto"), workdir, save_help_to=help_save_to
        )
    except lammps_detect.DetectError as exc:
        lines.append(f"FAIL LAMMPS detection: {exc}")
        return False, {"host": host, "detect": {}, "git": git_info()}, lines

    for k in (
        "lmp_path", "mpiexec_path", "lammps_version", "has_meam", "has_meam_kk",
        "has_kokkos", "has_kokkos_cuda", "kokkos_api", "has_gpu_package", "gpu_api",
        "has_meam_gpu", "has_eam_alloy_gpu",
    ):
        lines.append(f"lammps.{k}: {detect_info.get(k)}")

    if not detect_info.get("has_meam"):
        lines.append("FAIL: LAMMPS build lacks MEAM")
        ok = False
    if not detect_info.get("mpiexec_path"):
        lines.append("FAIL: mpiexec not found")
        ok = False

    for mod in ("numpy", "scipy", "yaml"):
        try:
            __import__(mod)
            lines.append(f"python module {mod}: OK")
        except ImportError:
            lines.append(f"python module {mod}: MISSING")
            ok = False
    import importlib.util

    if importlib.util.find_spec("ovito") is not None:
        lines.append("python module ovito: OK (found)")
    else:
        lines.append("python module ovito: MISSING")
        ok = False

    env = {"host": host, "detect": detect_info, "git": git_info()}
    return ok, env, lines


class Autopilot:
    def __init__(self, cfg: dict, run_dir: Path | None = None):
        self.cfg = cfg
        self.run_dir: Path | None = None
        self.state: dict = {"steps": {}}
        if run_dir is not None:
            rd = Path(run_dir)
            if not rd.is_absolute():
                rd = paths.REPO_ROOT / rd
            if not rd.is_dir():
                raise StopPipeline(f"--run-dir does not exist: {rd}")
            self.run_dir = paths.ensure_inside_runs(rd)
            self._load_state()

    # ---------- infrastructure ----------

    def log(self, msg: str) -> None:
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        if self.run_dir is not None:
            log_path = self.run_dir / "logs" / "autopilot.log"
            log_path.parent.mkdir(exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _state_path(self) -> Path:
        return self.run_dir / "state.json"

    def _load_state(self) -> None:
        sp = self._state_path()
        if sp.is_file():
            self.state = json.loads(sp.read_text(encoding="utf-8"))

    def _save_state(self) -> None:
        if self.run_dir is not None:
            self._state_path().write_text(
                json.dumps(self.state, indent=2, default=str), encoding="utf-8"
            )

    def _step(self, name: str) -> dict:
        return self.state["steps"].setdefault(name, {})

    def _step_done(self, name: str) -> bool:
        return self.state["steps"].get(name, {}).get("status") == "done"

    def _mark(self, name: str, status: str, **details) -> None:
        step = self._step(name)
        step["status"] = status
        step["updated"] = datetime.now().isoformat(timespec="seconds")
        step.update(details)
        self._save_state()

    def ensure_run_dir(self) -> Path:
        if self.run_dir is None:
            self.run_dir = paths.new_run_dir()
            self.state = {
                "created": datetime.now().isoformat(timespec="seconds"),
                "steps": {},
            }
            dump_effective(self.cfg, self.run_dir / "config_effective.yaml")
            self._save_state()
            self.log(f"run directory created: {self.run_dir}")
        return self.run_dir

    @property
    def mode(self) -> str:
        return self.state["steps"].get("accel", {}).get("mode", "cpu_mpi_meam")

    @property
    def detect_info(self) -> dict:
        return self.state["steps"].get("env", {}).get("detect", {})

    # ---------- LAMMPS case execution ----------

    def _expected_files(self, tag: str) -> list[str]:
        return [f"dump.nvt_eps_{tag}_final.lammpstrj", f"data.nvt_eps_{tag}_final"]

    def _run_case(
        self,
        *,
        stage: str,
        eps: float,
        phase: str,
        run_steps: int,
        dump_every: int,
        timeout_s: float,
        read_data: Path | None,
        inclusion_id_range: tuple[int, int] | None = None,
        velocity_seed: int | None = None,
    ) -> tuple[dict, dict]:
        tag = paths.eps_tag(eps)
        template = paths.a0_template_for_tag(tag).read_text(encoding="utf-8")
        input_text = lammps_runner.rewrite_template(
            template,
            repo_root=paths.REPO_ROOT,
            read_data=read_data,
            run_steps=run_steps,
            dump_every=dump_every,
            restart_every=self.cfg["resources"]["restart_every"],
            inclusion_id_range=inclusion_id_range,
            velocity_seed=velocity_seed,
        )
        case_directory = paths.case_dir(self.run_dir, stage, tag, phase)
        name = f"{stage}_{phase}_eps_{tag}"
        self.log(
            f"  -> {name}: {run_steps} steps, dump every {dump_every}, "
            f"timeout {timeout_s / 60:.0f} min, dir {case_directory}"
        )
        rec = lammps_runner.execute_lammps(
            name=name,
            run_dir=case_directory,
            input_text=input_text,
            input_name=f"in.nvt_eps_{tag}",
            log_name=f"log.{phase}.lammps",
            mode=self.mode,
            lmp=self.detect_info["lmp_path"],
            mpiexec=self.detect_info.get("mpiexec_path"),
            ranks=self.cfg["resources"]["cpu_mpi_ranks"],
            omp_threads=self.cfg["resources"]["openmp_threads"],
            timeout_s=timeout_s,
        )
        ev = decisions.evaluate_case_run(rec, self._expected_files(tag))
        rate = rec.get("log", {}).get("timesteps_per_s")
        self.log(
            f"     {name}: exit={rec['exit_code']} dur={rec['duration_s']}s "
            f"rate={rate if rate else '?'} steps/s -> {'PASS' if ev['passed'] else 'FAIL'}"
        )
        if not ev["passed"]:
            for r in ev["reasons"]:
                self.log(f"     reason: {r}")
        return rec, ev

    def _run_stage_cases(
        self,
        *,
        step_name: str,
        stage: str,
        phase: str,
        eps_list: list[float],
        run_steps: int,
        dump_every: int,
        timeout_s: float,
        read_data_for: dict,
        inclusion_id_range: tuple[int, int] | None = None,
        seeds: dict | None = None,
    ) -> None:
        records, evals = {}, {}
        for eps in eps_list:
            tag = paths.eps_tag(eps)
            rec, ev = self._run_case(
                stage=stage,
                eps=eps,
                phase=phase,
                run_steps=run_steps,
                dump_every=dump_every,
                timeout_s=timeout_s,
                read_data=read_data_for[tag],
                inclusion_id_range=inclusion_id_range,
                velocity_seed=(seeds or {}).get(tag),
            )
            records[f"eps_{tag}"] = rec
            evals[f"eps_{tag}"] = ev
            self._mark(step_name, "running", records=records, evals=evals)
            if not ev["passed"]:
                # Stop the current stage at the first failure; do not blindly continue.
                stage_eval = {"passed": False, "reasons": [f"eps_{tag} failed; stage aborted"]}
                self._mark(step_name, "failed", records=records, evals=evals, stage_eval=stage_eval)
                raise StopPipeline(
                    f"{step_name}: case eps_{tag} failed: " + "; ".join(ev["reasons"])
                )
        disk_ok, disk_msg = resources.check_disk(
            paths.REPO_ROOT, self.cfg["resources"]["min_free_disk_gb_before_production"]
        )
        stage_eval = decisions.evaluate_stage(evals, disk_ok, disk_msg)
        status = "done" if stage_eval["passed"] else "failed"
        self._mark(step_name, status, records=records, evals=evals, stage_eval=stage_eval,
                   disk_after=disk_msg)
        if not stage_eval["passed"]:
            raise StopPipeline(f"{step_name} gate failed: " + "; ".join(stage_eval["reasons"]))

    # ---------- analysis ----------

    def _run_analysis_subprocess(
        self,
        dump: Path,
        matrix_max_id: int,
        center: tuple | None,
        axes: tuple | None,
        out_json: Path,
        timeout_s: float = 1800,
        attempts: int = 2,
    ) -> dict:
        py = python_executable(self.cfg)
        script = paths.REPO_ROOT / "analysis" / "python" / "stage_runner" / "analysis_runner.py"
        cmd = [
            str(py), str(script),
            "--dump", str(dump),
            "--matrix-max-id", str(matrix_max_id),
            "--out", str(out_json),
        ]
        if center is not None:
            cmd += ["--center", ",".join(f"{c}" for c in center)]
        if axes is not None:
            cmd += ["--axes", ",".join(f"{a}" for a in axes)]
        last_err = ""
        for attempt in range(1, attempts + 1):
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                cwd=str(paths.REPO_ROOT),
            )
            if proc.returncode == 0 and out_json.is_file():
                return json.loads(out_json.read_text(encoding="utf-8"))
            last_err = (proc.stderr or "")[-2000:]
            self.log(f"     analysis attempt {attempt} failed (exit {proc.returncode})")
        raise AnalysisError(f"OVITO analysis failed for {dump}: {last_err}")

    def _analyze_stage(
        self,
        *,
        step_name: str,
        stage: str,
        eps_list: list[float],
        phase: str,
        matrix_max_id: int,
        center: tuple,
        axes: tuple,
        csv_name: str | None,
        stop_on_failure: bool,
    ) -> tuple[list[dict], dict]:
        rows, statuses = [], {}
        for eps in eps_list:
            tag = paths.eps_tag(eps)
            dump = paths.case_dir(self.run_dir, stage, tag, phase) / f"dump.nvt_eps_{tag}_final.lammpstrj"
            case = f"{stage}_eps_{tag}_{phase}"
            if not dump.is_file():
                statuses[case] = "dump missing"
                if stop_on_failure:
                    raise StopPipeline(f"{step_name}: final dump missing for {case}: {dump}")
                continue
            out_json = dump.parent / "analysis_dxa.json"
            self.log(f"  -> DXA/CNA: {dump.name} in {dump.parent}")
            try:
                result = self._run_analysis_subprocess(
                    dump, matrix_max_id, center, axes, out_json
                )
            except AnalysisError as exc:
                statuses[case] = f"analysis failed: {exc}"
                self.log(f"     {case}: analysis FAILED")
                if stop_on_failure:
                    raise StopPipeline(str(exc))
                continue
            result["case"] = case
            result["eps_z"] = eps
            rows.append(result)
            statuses[case] = "ok"
            self.log(
                f"     {case}: segments={result['dislocation_segments']} "
                f"len={result['dislocation_length_A']} A "
                f"fcc={result['fcc_pct']}% hcp={result['hcp_pct']}% other={result['other_pct']}%"
            )
        if csv_name and rows:
            csv_path = self.run_dir / "tables" / csv_name
            report.write_defect_csv(csv_path, rows)
            self.log(f"  defect summary CSV written: {csv_path}")
        return rows, statuses

    # ---------- steps ----------

    def step_plan(self) -> None:
        ok, lines = validate_plan(self.cfg)
        for line in lines:
            self.log("plan: " + line)
        if not ok:
            self._mark("plan", "failed", lines=lines)
            raise StopPipeline("plan validation failed")
        self._mark("plan", "done", lines=lines)

    def step_env(self) -> None:
        help_path = self.run_dir / "logs" / "lmp_help.txt"
        ok, env, lines = check_env(self.cfg, help_save_to=help_path)
        for line in lines:
            self.log("env: " + line)
        report.write_env_report(
            self.run_dir / "env_report.md", env["host"], env["detect"], env["git"]
        )
        status = "done" if ok else "failed"
        self._mark("env", status, host=env["host"], detect=env["detect"], git=env["git"])
        if not ok:
            raise StopPipeline("environment check failed")

    def step_accel(self) -> None:
        decision = decisions.choose_acceleration(self.detect_info)
        report.write_acceleration_md(
            self.run_dir / "acceleration_decision.md",
            decision,
            self.detect_info,
            self.cfg["resources"],
        )
        self.log(f"acceleration decision: {decision['mode']} ({decision['reason']})")
        if decision["mode"] == "blocked":
            self._mark("accel", "failed", **decision)
            raise StopPipeline("no valid acceleration mode: " + decision["reason"])
        self._mark("accel", "done", **decision)

    def step_a0_eigenstrain(self) -> None:
        reports = {}
        for eps in self.cfg["A0"]["eps_z"]:
            if eps == 0.0:
                continue  # baseline structure used as-is, no regeneration
            tag = paths.eps_tag(eps)
            out_dir = paths.structure_dir(self.run_dir, "A0", tag)
            self.log(f"eigenstrain regen (run-local): eps_z={eps} -> {out_dir}")
            rep = eigenstrain.regenerate(
                paths.A0_BASELINE_DATA,
                out_dir,
                eps,
                inclusion_id_min=paths.A0_INCLUSION_ID_MIN,
                inclusion_id_max=paths.A0_INCLUSION_ID_MAX,
                expected_inclusion_atoms=paths.A0_INCLUSION_ATOMS,
                center=paths.A0_CENTER,
            )
            reports[f"eps_{tag}"] = {
                "output": rep["output"],
                "min_pair_distance_A": rep["min_pair_distance_A"],
                "pairs_below_1p8_A": rep["pairs_below_1p8_A"],
                "safe_basic": rep["safe_basic"],
            }
            if not rep["safe_basic"]:
                self._mark("a0_eigenstrain", "failed", reports=reports)
                raise StopPipeline(
                    f"eigenstrain structure for eps_z={eps} has hard pair overlaps (<1.8 A)"
                )
        self._mark("a0_eigenstrain", "done", reports=reports)

    def _a0_read_data(self) -> dict:
        rd = {}
        for eps in self.cfg["A0"]["eps_z"]:
            tag = paths.eps_tag(eps)
            if eps == 0.0:
                rd[tag] = None  # template's baseline path (absolutized) is used
            else:
                out_dir = paths.structure_dir(self.run_dir, "A0", tag)
                rd[tag] = out_dir / f"data.ellipsoid_eigenstrain_{paths.epsz_dirtag(eps)}"
        return rd

    def step_a0_smoke(self) -> None:
        res = self.cfg["resources"]
        disk_ok, disk_msg = resources.check_disk(
            paths.REPO_ROOT, res["min_free_disk_gb_before_start"]
        )
        self.log("a0_smoke: " + disk_msg)
        if not disk_ok:
            self._mark("a0_smoke", "failed", reason=disk_msg)
            raise StopPipeline("disk below start threshold: " + disk_msg)
        self._run_stage_cases(
            step_name="a0_smoke",
            stage="A0",
            phase="smoke",
            eps_list=self.cfg["A0"]["eps_z"],
            run_steps=self.cfg["A0"]["smoke_steps"],
            dump_every=res["dump_every_smoke"],
            timeout_s=res["max_walltime_smoke_minutes"] * 60,
            read_data_for=self._a0_read_data(),
        )

    def step_a0_production(self) -> None:
        if not self.cfg["A0"]["run_production_after_smoke_pass"]:
            self._mark("a0_production", "done", skipped="disabled by config")
            return
        res = self.cfg["resources"]
        disk_ok, disk_msg = resources.check_disk(
            paths.REPO_ROOT, res["min_free_disk_gb_before_production"]
        )
        self.log("a0_production: " + disk_msg)
        if not disk_ok:
            self._mark("a0_production", "failed", reason=disk_msg)
            raise StopPipeline("disk below production threshold: " + disk_msg)

        walltime_s = res["max_walltime_A0_production_hours"] * 3600
        smoke_records = self.state["steps"]["a0_smoke"].get("records", {})
        eta_notes = {}
        for case, rec in smoke_records.items():
            rate = rec.get("log", {}).get("timesteps_per_s")
            eta = decisions.production_eta_check(
                rate, self.cfg["A0"]["production_steps"], walltime_s
            )
            eta_notes[case] = eta["note"]
            self.log(f"a0_production ETA {case}: {eta['note']}")
            if not eta["ok"]:
                self._mark("a0_production", "failed", eta=eta_notes)
                raise StopPipeline(f"A0 production ETA exceeds walltime for {case}: {eta['note']}")

        self._run_stage_cases(
            step_name="a0_production",
            stage="A0",
            phase="production",
            eps_list=self.cfg["A0"]["eps_z"],
            run_steps=self.cfg["A0"]["production_steps"],
            dump_every=res["dump_every_production"],
            timeout_s=walltime_s,
            read_data_for=self._a0_read_data(),
        )
        step = self._step("a0_production")
        step["eta_notes"] = eta_notes
        self._save_state()

    def step_a0_analysis(self) -> None:
        rows, statuses = self._analyze_stage(
            step_name="a0_analysis",
            stage="A0",
            eps_list=self.cfg["A0"]["eps_z"],
            phase="production",
            matrix_max_id=paths.A0_MATRIX_MAX_ID,
            center=paths.A0_CENTER,
            axes=paths.A0_INCLUSION_AXES,
            csv_name="A0_defect_summary.csv",
            stop_on_failure=True,
        )
        self._write_runtime_report(
            "A0",
            self.run_dir / "summaries" / "A0_runtime_report.md",
            smoke_step="a0_smoke",
            prod_step="a0_production",
            analysis_rows=rows,
        )
        self._mark("a0_analysis", "done", rows=rows, statuses=statuses)

    def step_a1_build(self) -> None:
        res = self.cfg["resources"]
        a1 = self.cfg["A1_small"]
        build_dir = paths.ensure_inside_runs(self.run_dir / "A1_small" / "build")
        build_dir.mkdir(parents=True, exist_ok=True)

        try:
            plan, all_plans = builder.select_plan(
                a1["atoms_target_candidates"], res["cpu_mpi_ranks"], res["max_memory_gb"]
            )
            self.log(
                f"a1_build: selected target {plan['target_atoms']} "
                f"(est. {plan['estimated_atoms']} atoms, mem {plan['estimated_memory_gb']} GB)"
            )
            meta = builder.build_structure(plan, build_dir)
        except builder.BuildError as exc:
            self._mark("a1_build", "failed", reason=str(exc))
            raise StopPipeline(f"A1 build cannot be done safely: {exc}")

        self.log(
            f"a1_build: built {meta['total_atoms']} atoms "
            f"(matrix {meta['matrix_atoms']}, inclusion {meta['inclusion_atoms']}), "
            f"box {[round(b, 1) for b in meta['box_A']]} A"
        )
        mem_ok, mem_msg = resources.check_memory_estimate(
            meta["total_atoms"], res["cpu_mpi_ranks"], res["max_memory_gb"]
        )
        self.log("a1_build: " + mem_msg)
        if not mem_ok:
            self._mark("a1_build", "failed", reason=mem_msg, meta=meta)
            raise StopPipeline("A1 build cannot be done safely: " + mem_msg)

        # prep run: minimize + short all-atom NVT equilibration
        prep_input = builder.make_prep_input(
            meta,
            minimize_etol=a1.get("equil_minimize_etol", 1.0e-6),
            minimize_ftol=a1.get("equil_minimize_ftol", 1.0e-8),
            minimize_maxiter=a1.get("equil_minimize_maxiter", 4000),
            minimize_maxeval=a1.get("equil_minimize_maxeval", 8000),
            equil_steps=a1.get("equil_nvt_steps", 5000),
        )
        self.log("a1_build: prep run (minimize + NVT equil) starting")
        rec = lammps_runner.execute_lammps(
            name="A1_prep_minimize_equil",
            run_dir=build_dir,
            input_text=prep_input,
            input_name="in.a1_prep",
            log_name="log.a1_prep.lammps",
            mode=self.mode,
            lmp=self.detect_info["lmp_path"],
            mpiexec=self.detect_info.get("mpiexec_path"),
            ranks=res["cpu_mpi_ranks"],
            omp_threads=res["openmp_threads"],
            timeout_s=3600,  # 60 min cap for build prep
        )
        ev = decisions.evaluate_case_run(
            rec, ["data.a1_baseline_equil", "dump.a1_baseline_equil.lammpstrj"]
        )
        final_t = (rec.get("log", {}).get("final_thermo") or {}).get("Temp")
        self.log(
            f"a1_build: prep exit={rec['exit_code']} dur={rec['duration_s']}s "
            f"T_final={final_t} -> {'PASS' if ev['passed'] else 'FAIL'}"
        )
        if not ev["passed"]:
            self._mark("a1_build", "failed", meta=meta, prep=rec, prep_eval=ev)
            raise StopPipeline(
                "A1 build cannot be done safely: prep run failed: " + "; ".join(ev["reasons"])
            )

        # run-local eigenstrain on the equilibrated baseline
        equil_data = build_dir / "data.a1_baseline_equil"
        eig_reports = {}
        for eps in a1["eps_z"]:
            tag = paths.eps_tag(eps)
            out_dir = paths.ensure_inside_runs(build_dir / "eigenstrain" / f"eps_{tag}")
            self.log(f"a1_build: eigenstrain regen eps_z={eps} -> {out_dir}")
            rep = eigenstrain.regenerate(
                equil_data,
                out_dir,
                eps,
                inclusion_id_min=meta["inclusion_id_min"],
                inclusion_id_max=meta["inclusion_id_max"],
                expected_inclusion_atoms=meta["inclusion_atoms"],
                center=tuple(meta["center_A"]),
            )
            eig_reports[f"eps_{tag}"] = {
                "output": rep["output"],
                "min_pair_distance_A": rep["min_pair_distance_A"],
                "pairs_below_1p8_A": rep["pairs_below_1p8_A"],
                "safe_basic": rep["safe_basic"],
            }
            if not rep["safe_basic"]:
                self._mark("a1_build", "failed", meta=meta, prep=rec, eigenstrain=eig_reports)
                raise StopPipeline(
                    f"A1 build cannot be done safely: eigenstrain eps_z={eps} "
                    "has hard pair overlaps (<1.8 A)"
                )
        self._mark(
            "a1_build", "done", meta=meta, plan=plan, all_plans=all_plans,
            prep=rec, prep_eval=ev, eigenstrain=eig_reports,
        )

    def _a1_meta(self) -> dict:
        return self.state["steps"]["a1_build"]["meta"]

    def _a1_read_data(self) -> dict:
        build_dir = self.run_dir / "A1_small" / "build"
        rd = {}
        for eps in self.cfg["A1_small"]["eps_z"]:
            tag = paths.eps_tag(eps)
            rd[tag] = (
                build_dir / "eigenstrain" / f"eps_{tag}"
                / f"data.ellipsoid_eigenstrain_{paths.epsz_dirtag(eps)}"
            )
        return rd

    def step_a1_smoke(self) -> None:
        if not self.cfg["A1_small"]["run_smoke_after_A0_production_pass"]:
            self._mark("a1_smoke", "done", skipped="disabled by config")
            return
        res = self.cfg["resources"]
        meta = self._a1_meta()
        self._run_stage_cases(
            step_name="a1_smoke",
            stage="A1_small",
            phase="smoke",
            eps_list=self.cfg["A1_small"]["eps_z"],
            run_steps=self.cfg["A1_small"]["smoke_steps"],
            dump_every=res["dump_every_smoke"],
            timeout_s=res["max_walltime_smoke_minutes"] * 60,
            read_data_for=self._a1_read_data(),
            inclusion_id_range=(meta["inclusion_id_min"], meta["inclusion_id_max"]),
            seeds=A1_SEEDS,
        )
        # OVITO on smoke dumps: required to run or to have its failure reported.
        rows, statuses = self._analyze_stage(
            step_name="a1_smoke_analysis",
            stage="A1_small",
            eps_list=self.cfg["A1_small"]["eps_z"],
            phase="smoke",
            matrix_max_id=meta["matrix_max_id"],
            center=tuple(meta["center_A"]),
            axes=tuple(meta["inclusion_axes_A"]),
            csv_name=None,
            stop_on_failure=False,
        )
        step = self._step("a1_smoke")
        step["analysis_rows"] = rows
        step["analysis_statuses"] = statuses
        self._save_state()

    def step_a1_gate(self) -> None:
        res = self.cfg["resources"]
        steps = self.state["steps"]
        meta = self._a1_meta()

        disk_ok, disk_msg = resources.check_disk(
            paths.REPO_ROOT, res["min_free_disk_gb_before_production"]
        )
        mem_ok, mem_msg = resources.check_memory_estimate(
            meta["total_atoms"], res["cpu_mpi_ranks"], res["max_memory_gb"]
        )
        walltime_s = res["max_walltime_A1_production_hours"] * 3600
        eta_ok = True
        eta_notes = []
        for case, rec in steps["a1_smoke"].get("records", {}).items():
            rate = rec.get("log", {}).get("timesteps_per_s")
            eta = decisions.production_eta_check(
                rate, self.cfg["A1_small"]["production_steps"], walltime_s
            )
            eta_notes.append(f"{case}: {eta['note']}")
            eta_ok &= eta["ok"]

        approved, blockers = decisions.pre_a1_gate_decision(
            a0_smoke_passed=steps.get("a0_smoke", {}).get("stage_eval", {}).get("passed", False),
            a0_production_passed=steps.get("a0_production", {}).get("stage_eval", {}).get("passed", False),
            a0_analysis_ok=steps.get("a0_analysis", {}).get("status") == "done",
            a1_build_ok=steps.get("a1_build", {}).get("status") == "done",
            a1_smoke_passed=steps.get("a1_smoke", {}).get("stage_eval", {}).get("passed", False),
            disk_ok=disk_ok,
            memory_ok=mem_ok,
            eta_ok=eta_ok,
        )

        ram_total, ram_avail = resources.ram_info_gb()
        gate_path = self.run_dir / "summaries" / "pre_A1_production_gate_report.md"
        accel = steps.get("accel", {})
        lines = [
            "# Pre-A1-production gate report",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Run directory: {self.run_dir}",
            "",
            "## A0 smoke",
            "",
            report.case_table(steps["a0_smoke"].get("records", {}), steps["a0_smoke"].get("evals", {})),
            "## A0 production",
            "",
            report.case_table(steps["a0_production"].get("records", {}), steps["a0_production"].get("evals", {})),
            "## A0 analysis summary",
            "",
            report.analysis_table(steps.get("a0_analysis", {}).get("rows", [])),
            "## A1-small build",
            "",
            f"- selected atoms target: {meta['plan']['target_atoms']}",
            f"- built atoms: {meta['total_atoms']} (matrix {meta['matrix_atoms']}, inclusion {meta['inclusion_atoms']})",
            f"- box: {[round(b, 2) for b in meta['box_A']]} A",
            f"- inclusion axes: {[round(a, 2) for a in meta['inclusion_axes_A']]} A (ratio 1:1:2)",
            f"- inclusion ids: {meta['inclusion_id_min']}..{meta['inclusion_id_max']}",
            "",
            "## A1-small smoke",
            "",
            report.case_table(steps["a1_smoke"].get("records", {}), steps["a1_smoke"].get("evals", {})),
            "## A1-small smoke analysis",
            "",
            report.analysis_table(steps["a1_smoke"].get("analysis_rows", [])),
            "Analysis statuses: "
            + json.dumps(steps["a1_smoke"].get("analysis_statuses", {})),
            "",
            "## Acceleration",
            "",
            f"- mode used: {accel.get('mode')}",
            f"- GPU decision and reason: {accel.get('reason')}",
            "",
            "## Resources",
            "",
            f"- {disk_msg}",
            f"- {mem_msg}",
            f"- RAM total/available: {ram_total:.1f} / {ram_avail:.1f} GB" if ram_total else "- RAM: unknown",
            f"- production ETA: {'; '.join(eta_notes) if eta_notes else 'n/a'}",
            "",
            "## Decision",
            "",
        ]
        if approved:
            lines.append(f"**{decisions.GATE_APPROVED}**")
        else:
            lines.append(f"**{decisions.GATE_BLOCKED}**")
            lines.append("")
            lines.append("Blockers:")
            for b in blockers:
                lines.append(f"- {b}")
        gate_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log(
            f"a1_gate: {'APPROVED' if approved else 'BLOCKED'}"
            + ("" if approved else f" ({'; '.join(blockers)})")
        )
        self._mark("a1_gate", "done", approved=approved, blockers=blockers,
                   gate_report=str(gate_path))

    def step_a1_production(self) -> None:
        if not self.cfg["A1_small"]["run_production_after_gate_pass"]:
            self._mark("a1_production", "done", skipped="disabled by config")
            return
        gate_path = self.run_dir / "summaries" / "pre_A1_production_gate_report.md"
        gate_text = gate_path.read_text(encoding="utf-8") if gate_path.is_file() else ""
        if decisions.GATE_APPROVED not in gate_text:
            self._mark("a1_production", "failed", reason="gate report does not approve")
            raise StopPipeline(
                "A1 production blocked by gate report; see " + str(gate_path)
            )
        res = self.cfg["resources"]
        disk_ok, disk_msg = resources.check_disk(
            paths.REPO_ROOT, res["min_free_disk_gb_before_production"]
        )
        self.log("a1_production: " + disk_msg)
        if not disk_ok:
            self._mark("a1_production", "failed", reason=disk_msg)
            raise StopPipeline("disk below production threshold: " + disk_msg)
        meta = self._a1_meta()
        self._run_stage_cases(
            step_name="a1_production",
            stage="A1_small",
            phase="production",
            eps_list=self.cfg["A1_small"]["eps_z"],
            run_steps=self.cfg["A1_small"]["production_steps"],
            dump_every=res["dump_every_production"],
            timeout_s=res["max_walltime_A1_production_hours"] * 3600,
            read_data_for=self._a1_read_data(),
            inclusion_id_range=(meta["inclusion_id_min"], meta["inclusion_id_max"]),
            seeds=A1_SEEDS,
        )

    def step_a1_analysis(self) -> None:
        meta = self._a1_meta()
        rows, statuses = self._analyze_stage(
            step_name="a1_analysis",
            stage="A1_small",
            eps_list=self.cfg["A1_small"]["eps_z"],
            phase="production",
            matrix_max_id=meta["matrix_max_id"],
            center=tuple(meta["center_A"]),
            axes=tuple(meta["inclusion_axes_A"]),
            csv_name="A1_small_defect_summary.csv",
            stop_on_failure=True,
        )
        self._write_runtime_report(
            "A1_small",
            self.run_dir / "summaries" / "A1_small_runtime_report.md",
            smoke_step="a1_smoke",
            prod_step="a1_production",
            analysis_rows=rows,
        )
        self._mark("a1_analysis", "done", rows=rows, statuses=statuses)

    def _write_runtime_report(
        self, stage: str, out_path: Path, *, smoke_step: str, prod_step: str,
        analysis_rows: list[dict],
    ) -> None:
        steps = self.state["steps"]
        lines = [
            f"# {stage} runtime report",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Run directory: {self.run_dir}",
            f"Acceleration mode: {self.mode}",
            "",
            "## Smoke runs",
            "",
            report.case_table(
                steps.get(smoke_step, {}).get("records", {}),
                steps.get(smoke_step, {}).get("evals", {}),
            ),
            "## Production runs",
            "",
            report.case_table(
                steps.get(prod_step, {}).get("records", {}),
                steps.get(prod_step, {}).get("evals", {}),
            ),
            "## Defect / dislocation analysis (final dumps)",
            "",
            report.analysis_table(analysis_rows),
        ]
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---------- final report ----------

    def _next_recommendation(self) -> str:
        steps = self.state["steps"]
        a1_rows = steps.get("a1_analysis", {}).get("rows", [])
        a0_rows = steps.get("a0_analysis", {}).get("rows", [])
        if not a1_rows:
            return (
                "DEBUG: the pipeline did not produce analyzable A1-small production "
                "results; fix the blocking stage before any scale-up."
            )
        baseline = next(
            (r for r in a0_rows if r.get("eps_z") == 0.0), a0_rows[0] if a0_rows else None
        )
        base_beyond = 0
        if baseline:
            base_beyond = (baseline.get("plastic_zone") or {}).get(
                "defect_atoms_beyond_1p3_shell", 0
            ) or 0
        total_segments = sum(r.get("dislocation_segments", 0) for r in a1_rows)
        max_beyond = max(
            ((r.get("plastic_zone") or {}).get("defect_atoms_beyond_1p3_shell", 0) or 0)
            for r in a1_rows
        )
        growth = max_beyond > max(50, 2 * base_beyond)
        if total_segments == 0 and not growth:
            return (
                "ELASTIC RESPONSE / NO DISLOCATION NUCLEATION AT TESTED SCALE: A1-small "
                "production produced zero dislocations and no meaningful HCP/OTHER/"
                "plastic-zone growth beyond the inclusion interface shell. Do not claim "
                "plasticity. Next: either open A1-medium (200k-300k) as one controlled "
                "scale step (manual decision), or - if the null result persists there - "
                "pivot to grain boundaries / pre-existing defects / polycrystal / refined "
                "magnetostriction tensor instead of blindly scaling to 700k-1M."
            )
        return (
            f"DISLOCATION/DEFECT ACTIVITY DETECTED at A1-small "
            f"(total segments={total_segments}, max defect atoms beyond shell={max_beyond}): "
            "open A1-medium (200k-300k) to confirm scale dependence and refine the "
            "nucleation threshold."
        )

    def step_final_report(self) -> None:
        steps = self.state["steps"]
        out_path = self.run_dir / "final_report.md"
        git = git_info()
        cfg_text = (self.run_dir / "config_effective.yaml").read_text(encoding="utf-8")
        env_step = steps.get("env", {})
        accel = steps.get("accel", {})
        a1_meta = steps.get("a1_build", {}).get("meta")
        stop = self.state.get("stop")

        lines = [
            "# Final report - stage sweep A0 + A1-small production autopilot",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Run directory: {self.run_dir}",
            "",
        ]
        if stop:
            lines += [
                "## PIPELINE STOPPED EARLY",
                "",
                f"- at step: {stop.get('step')}",
                f"- reason: {stop.get('reason')}",
                "",
            ]
        lines += [
            "## 1. Changed files (git status at end)",
            "",
            "```",
            git["status_short"],
            "```",
            "",
            "## 2. Git state",
            "",
            f"- branch: {git['branch']}",
            f"- HEAD: {git['head']}",
            "",
            "## 3. Effective config",
            "",
            "```yaml",
            cfg_text.strip(),
            "```",
            "",
            "## 4. Hardware / environment",
            "",
        ]
        for k, v in (env_step.get("host") or {}).items():
            lines.append(f"- {k}: {v}")
        lines += ["", "## 5. LAMMPS capabilities", ""]
        for k in (
            "lmp_path", "mpiexec_path", "lammps_version", "has_meam", "has_meam_kk",
            "has_kokkos", "has_kokkos_cuda", "has_gpu_package", "has_meam_gpu",
            "has_eam_alloy_gpu",
        ):
            lines.append(f"- {k}: {(env_step.get('detect') or {}).get(k)}")
        lines += [
            "",
            "## 6. Acceleration decision",
            "",
            f"- mode: {accel.get('mode')}",
            f"- reason: {accel.get('reason')}",
            "",
            "## 7. A0 smoke results",
            "",
            report.case_table(steps.get("a0_smoke", {}).get("records", {}),
                              steps.get("a0_smoke", {}).get("evals", {})),
            "## 8. A0 production results",
            "",
            report.case_table(steps.get("a0_production", {}).get("records", {}),
                              steps.get("a0_production", {}).get("evals", {})),
            "## 9. A0 defect analysis",
            "",
            report.analysis_table(steps.get("a0_analysis", {}).get("rows", [])),
            f"CSV: {self.run_dir / 'tables' / 'A0_defect_summary.csv'}",
            "",
            "## 10. A1-small build",
            "",
        ]
        if a1_meta:
            lines += [
                f"- selected atoms target: {a1_meta['plan']['target_atoms']}",
                f"- built atoms: {a1_meta['total_atoms']} "
                f"(matrix {a1_meta['matrix_atoms']}, inclusion {a1_meta['inclusion_atoms']})",
                f"- box: {[round(b, 2) for b in a1_meta['box_A']]} A; "
                f"inclusion axes {[round(a, 2) for a in a1_meta['inclusion_axes_A']]} A (1:1:2)",
            ]
        else:
            lines.append("- not reached")
        lines += [
            "",
            "## 11. A1-small smoke results",
            "",
            report.case_table(steps.get("a1_smoke", {}).get("records", {}),
                              steps.get("a1_smoke", {}).get("evals", {})),
            "Smoke analysis:",
            "",
            report.analysis_table(steps.get("a1_smoke", {}).get("analysis_rows", [])),
            "## 12. Pre-A1-production gate",
            "",
            f"- approved: {steps.get('a1_gate', {}).get('approved')}",
            f"- report: {steps.get('a1_gate', {}).get('gate_report')}",
            "",
            "## 13. A1-small production results",
            "",
            report.case_table(steps.get("a1_production", {}).get("records", {}),
                              steps.get("a1_production", {}).get("evals", {})),
            "## 14. A1-small defect analysis",
            "",
            report.analysis_table(steps.get("a1_analysis", {}).get("rows", [])),
            f"CSV: {self.run_dir / 'tables' / 'A1_small_defect_summary.csv'}",
            "",
            "## 15. Next recommendation",
            "",
            self._next_recommendation(),
            "",
        ]
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log(f"final report written: {out_path}")
        self._mark("final_report", "done", path=str(out_path))

    # ---------- driver ----------

    STEP_FUNCS = {
        "plan": step_plan,
        "env": step_env,
        "accel": step_accel,
        "a0_eigenstrain": step_a0_eigenstrain,
        "a0_smoke": step_a0_smoke,
        "a0_production": step_a0_production,
        "a0_analysis": step_a0_analysis,
        "a1_build": step_a1_build,
        "a1_smoke": step_a1_smoke,
        "a1_gate": step_a1_gate,
        "a1_production": step_a1_production,
        "a1_analysis": step_a1_analysis,
        "final_report": step_final_report,
    }

    def run_until(self, target: str) -> bool:
        if target not in STEP_ORDER:
            raise ValueError(f"unknown target step: {target}")
        self.ensure_run_dir()
        self.log(f"=== autopilot: running steps up to '{target}' (mode resume-aware) ===")
        try:
            for name in STEP_ORDER:
                if STEP_ORDER.index(name) > STEP_ORDER.index(target):
                    break
                if name == "final_report" and target != "final_report":
                    break
                if self._step_done(name):
                    self.log(f"step {name}: already done, skipping")
                    continue
                self.log(f"=== step {name} ===")
                t0 = time.monotonic()
                self.STEP_FUNCS[name](self)
                self.log(f"=== step {name} finished in {time.monotonic() - t0:.0f}s ===")
            return True
        except StopPipeline as exc:
            self.state["stop"] = {
                "step": self._current_failed_step(),
                "reason": str(exc),
                "time": datetime.now().isoformat(timespec="seconds"),
            }
            self._save_state()
            self.log(f"PIPELINE STOPPED: {exc}")
            self._write_stop_report(str(exc))
            try:
                self.step_final_report()
            except Exception as report_exc:
                self.log(f"final report after stop failed: {report_exc}")
            return False

    def _current_failed_step(self) -> str:
        for name, step in self.state["steps"].items():
            if step.get("status") == "failed":
                return name
        return "unknown"

    def _write_stop_report(self, reason: str) -> None:
        out = self.run_dir / "summaries" / "stop_report.md"
        resume = (
            f".venv\\Scripts\\python.exe scripts\\run_stage_sweep.py "
            f"--config configs\\stage_sweep_A0_A1_production.yaml "
            f"--autopilot-A0-A1-production --run-dir {self.run_dir}"
        )
        lines = [
            "# Stop report",
            "",
            f"Time: {datetime.now().isoformat(timespec='seconds')}",
            f"Reason: {reason}",
            "",
            "Step statuses:",
            "",
        ]
        for name in STEP_ORDER:
            st = self.state["steps"].get(name, {}).get("status", "not started")
            lines.append(f"- {name}: {st}")
        lines += ["", "Resume command (after fixing the cause):", "", "```", resume, "```"]
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log(f"stop report written: {out}")

    def analyze_only(self) -> bool:
        """Re-run DXA/CNA on whatever final production dumps exist in the run dir."""
        if self.run_dir is None:
            raise StopPipeline("--analyze-only requires --run-dir (or an existing latest run)")
        self.log(f"analyze-only on {self.run_dir}")
        ok = True
        try:
            self.step_a0_analysis()
        except StopPipeline as exc:
            self.log(f"A0 analysis incomplete: {exc}")
            ok = False
        if self.state["steps"].get("a1_build", {}).get("status") == "done":
            try:
                self.step_a1_analysis()
            except StopPipeline as exc:
                self.log(f"A1 analysis incomplete: {exc}")
                ok = False
        else:
            self.log("A1 analysis skipped: no completed a1_build in state")
        return ok
